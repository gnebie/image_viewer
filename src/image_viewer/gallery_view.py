"""Scrollable thumbnail grid for slideshow gallery mode."""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Optional

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from .gallery_layout import compute_columns, rc_from_index, visible_rows
from .settings_store import level_to_thumb_max_px
from .sources import ImageEntry, ImageSource, SourceError

logger = logging.getLogger(__name__)

# Decode at most this edge before building the on-screen thumbnail (memory / CPU).
GALLERY_DECODE_MAX_EDGE = 512
# At most this many indices around the viewport may load full decode+thumbnail work.
GALLERY_INDEX_BATCH = 100


class OrderedImageCache:
    """LRU-ish cache for small PIL thumbnails keyed by (index, max_edge_px)."""

    def __init__(self, max_items: int = 240) -> None:
        self._max = max_items
        self._data: OrderedDict[tuple[int, int], Image.Image] = OrderedDict()

    def get_copy(self, key: tuple[int, int]) -> Optional[Image.Image]:
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key].copy()

    def put(self, key: tuple[int, int], value: Image.Image) -> None:
        if key in self._data:
            del self._data[key]
        self._data[key] = value
        while len(self._data) > self._max:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()


class SlideshowGalleryView(ttk.Frame):
    """Tk grid of thumbnails with selection highlight and scroll."""

    def __init__(
        self,
        master: tk.Widget,
        *,
        gap: int = 8,
        pad: int = 8,
        bg: str = "#1a1a1a",
        selection_color: str = "#f5d742",
    ) -> None:
        super().__init__(master)
        self._gap = gap
        self._pad = pad
        self._bg = bg
        self._selection_color = selection_color

        self._source: Optional[ImageSource] = None
        self._images: list[ImageEntry] = []
        self._selection = 0
        self._thumb_level = 5
        self._thumb_max_px = level_to_thumb_max_px(self._thumb_level)

        self._ncols = 1
        self._slot_px = self._thumb_max_px + 4
        self._row_h = self._slot_px + self._gap

        self._tile_refs: dict[int, tuple[int, ImageTk.PhotoImage]] = {}
        self._pil_cache = OrderedImageCache(max_items=240)
        self._sel_rect: Optional[int] = None
        self._placeholder_photo: Optional[ImageTk.PhotoImage] = None
        self._thumb_load_lo = 0
        self._thumb_load_hi_excl = 0

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(self, highlightthickness=0, bg=self._bg)
        self._vsb = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._hsb = ttk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(
            yscrollcommand=self._y_scroll_set,
            xscrollcommand=self._x_scroll_set,
        )
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vsb.grid(row=0, column=1, sticky="ns")
        self._hsb.grid(row=1, column=0, sticky="ew")

        self._canvas.bind("<Configure>", self._on_canvas_configure)

    def _y_scroll_set(self, *args: str) -> None:
        self._vsb.set(*args)
        self.after_idle(self._sync_tiles)

    def _x_scroll_set(self, *args: str) -> None:
        self._hsb.set(*args)
        self.after_idle(self._sync_tiles)

    def set_model(
        self,
        source: ImageSource,
        images: list[ImageEntry],
        selection_index: int,
        thumb_level: int,
    ) -> None:
        self._source = source
        self._images = images
        self._selection = max(0, min(selection_index, len(images) - 1)) if images else 0
        self.set_thumb_level(thumb_level)
        self._full_rebuild()

    def get_selection(self) -> int:
        return self._selection

    def get_thumb_level(self) -> int:
        return self._thumb_level

    @property
    def column_count(self) -> int:
        return max(1, self._ncols)

    @property
    def row_height(self) -> int:
        return max(1, self._row_h)

    def set_selection(self, index: int) -> None:
        if not self._images:
            return
        self._selection = max(0, min(index, len(self._images) - 1))
        self._update_selection_rect()
        self._ensure_selection_visible()

    def set_thumb_level(self, level: int) -> None:
        self._thumb_level = level
        self._thumb_max_px = level_to_thumb_max_px(level)
        self._slot_px = self._thumb_max_px + 4
        self._row_h = self._slot_px + self._gap
        self._pil_cache.clear()
        self._placeholder_photo = None
        self._full_rebuild()

    def bump_thumb_level(self, delta: int) -> int:
        new_level = max(1, min(9, self._thumb_level + delta))
        if new_level != self._thumb_level:
            self.set_thumb_level(new_level)
        return self._thumb_level

    def reset_thumb_level(self, default_level: int) -> int:
        self.set_thumb_level(default_level)
        return self._thumb_level

    def page_selection(self, rows_delta: int) -> None:
        """Move selection by roughly one screen of rows (used if we want Page+selection)."""
        if not self._images or rows_delta == 0:
            return
        rows = visible_rows(max(1, self._canvas.winfo_height()), self._row_h)
        step = rows * self._ncols * (1 if rows_delta > 0 else -1)
        self.set_selection(self._selection + step)

    def scroll_canvas_page(self, pages: int) -> None:
        """Scroll the viewport by ``pages`` (negative = toward the top of the content)."""
        if pages == 0:
            return
        self._canvas.yview_scroll(pages, "pages")
        self._sync_tiles()

    def _on_canvas_configure(self, _evt=None) -> None:
        if not self._images:
            return
        self._reflow_columns()

    def _inner_width(self) -> int:
        w = self._canvas.winfo_width()
        return max(1, w - 2 * self._pad)

    def _reflow_columns(self) -> None:
        inner = self._inner_width()
        ncols = compute_columns(inner, self._slot_px, self._gap)
        if ncols != self._ncols:
            self._ncols = ncols
            self._full_rebuild()
        else:
            self._resize_scrollregion()
            self._sync_tiles()

    def _total_rows(self) -> int:
        n = len(self._images)
        if n == 0:
            return 0
        return (n + self._ncols - 1) // self._ncols

    def _resize_scrollregion(self) -> None:
        cols = max(1, self._ncols)
        rows = self._total_rows()
        width = self._pad * 2 + cols * self._slot_px + max(0, cols - 1) * self._gap
        height = self._pad * 2 + rows * self._slot_px + max(0, rows - 1) * self._gap
        self._canvas.configure(scrollregion=(0, 0, width, height))

    def _full_rebuild(self) -> None:
        self._canvas.delete("all")
        self._tile_refs.clear()
        self._sel_rect = None
        if not self._images:
            self._ncols = 1
            return
        self._ncols = compute_columns(self._inner_width(), self._slot_px, self._gap)
        self._resize_scrollregion()
        self._sync_tiles(force=True)
        self._update_selection_rect()
        self._ensure_selection_visible()

    def _cell_xy(self, index: int) -> tuple[int, int]:
        row, col = rc_from_index(index, self._ncols)
        x0 = self._pad + col * (self._slot_px + self._gap)
        y0 = self._pad + row * (self._slot_px + self._gap)
        return x0, y0

    def _sync_tiles(self, force: bool = False) -> None:
        if not self._images or self._source is None:
            return
        self._canvas.update_idletasks()
        cy = self._canvas.canvasy(0)
        ch = max(1, self._canvas.winfo_height())
        first_row = max(0, int((cy - self._pad) // self._row_h) - 1)
        last_row = int((cy + ch - self._pad) // self._row_h) + 2
        first_idx = first_row * self._ncols
        last_idx = min(len(self._images), (last_row + 1) * self._ncols)
        n = len(self._images)
        lo = max(0, first_idx)
        hi_excl = last_idx
        if hi_excl > lo:
            hi = hi_excl - 1
            batch = GALLERY_INDEX_BATCH
            span = hi - lo + 1
            if span >= batch:
                load_lo = max(0, hi - batch + 1)
            else:
                load_lo = max(0, min(lo, n - batch))
                if hi >= load_lo + batch:
                    load_lo = max(0, hi - batch + 1)
            load_hi_excl = min(n, load_lo + batch)
        else:
            load_lo = 0
            load_hi_excl = 0
        self._thumb_load_lo = load_lo
        self._thumb_load_hi_excl = load_hi_excl

        needed = set(range(first_idx, last_idx))
        for idx in list(self._tile_refs.keys()):
            in_batch = self._thumb_load_lo <= idx < self._thumb_load_hi_excl
            if idx not in needed or force or not in_batch:
                img_id, _ph = self._tile_refs.pop(idx)
                self._canvas.delete(img_id)

        for idx in range(first_idx, last_idx):
            if idx in self._tile_refs and not force:
                continue
            self._paint_tile(idx)

        self._update_selection_rect()

    def _paint_tile(self, idx: int) -> None:
        if self._source is None or idx < 0 or idx >= len(self._images):
            return
        entry = self._images[idx]
        x0, y0 = self._cell_xy(idx)
        cx = x0 + self._slot_px // 2
        cy = y0 + self._slot_px // 2

        if not (self._thumb_load_lo <= idx < self._thumb_load_hi_excl):
            ph = self._placeholder_photo_image()
        else:
            thumb = self._load_thumb(entry, idx)
            if thumb is None:
                ph = ImageTk.PhotoImage(
                    Image.new("RGB", (self._thumb_max_px, self._thumb_max_px), (48, 48, 52))
                )
            else:
                ph = ImageTk.PhotoImage(thumb)

        img_id = self._canvas.create_image(cx, cy, image=ph, anchor="center")
        self._tile_refs[idx] = (img_id, ph)

    def _placeholder_photo_image(self) -> ImageTk.PhotoImage:
        if self._placeholder_photo is None:
            self._placeholder_photo = ImageTk.PhotoImage(
                Image.new("RGB", (self._thumb_max_px, self._thumb_max_px), (30, 30, 35))
            )
        return self._placeholder_photo

    def _load_thumb(self, entry: ImageEntry, idx: int) -> Optional[Image.Image]:
        key = (idx, self._thumb_max_px)
        cached = self._pil_cache.get_copy(key)
        if cached is not None:
            return cached
        try:
            img = self._source.open_image(entry)
        except (SourceError, OSError, ValueError) as e:
            logger.debug("Gallery thumb failed for %s: %s", entry.display_name(), e)
            return None
        try:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            work = img.copy()
            mw, mh = work.size
            if max(mw, mh) > GALLERY_DECODE_MAX_EDGE:
                work.thumbnail(
                    (GALLERY_DECODE_MAX_EDGE, GALLERY_DECODE_MAX_EDGE),
                    Image.Resampling.LANCZOS,
                )
            thumb = work.copy()
            thumb.thumbnail((self._thumb_max_px, self._thumb_max_px), Image.Resampling.LANCZOS)
        except (OSError, ValueError, MemoryError) as e:
            logger.debug("Gallery thumb resize failed: %s", e)
            return None
        finally:
            try:
                img.close()
            except OSError:
                pass
        self._pil_cache.put(key, thumb.copy())
        return thumb

    def _selection_rect_coords(self) -> Optional[tuple[int, int, int, int]]:
        if not self._images:
            return None
        x0, y0 = self._cell_xy(self._selection)
        return (x0 - 2, y0 - 2, x0 + self._slot_px + 2, y0 + self._slot_px + 2)

    def _update_selection_rect(self) -> None:
        coords = self._selection_rect_coords()
        if coords is None:
            return
        if self._sel_rect is not None:
            self._canvas.coords(self._sel_rect, *coords)
        else:
            self._sel_rect = self._canvas.create_rectangle(
                *coords, outline=self._selection_color, width=3
            )
        self._canvas.tag_raise(self._sel_rect)
        for idx, (img_id, _ph) in self._tile_refs.items():
            self._canvas.tag_raise(img_id)
        self._canvas.tag_raise(self._sel_rect)

    def _ensure_selection_visible(self) -> None:
        coords = self._selection_rect_coords()
        if coords is None:
            return
        _x1, y1, _x2, y2 = coords
        self._canvas.update_idletasks()
        bbox_all = self._canvas.bbox("all")
        if not bbox_all:
            return
        _ax0, _ay0, _ax1, total_h = bbox_all
        ch = max(1, self._canvas.winfo_height())
        top = self._canvas.canvasy(0)
        bottom = top + ch
        if y1 < top:
            span = max(1.0, total_h - ch)
            fraction = max(0.0, min(1.0, (y1 - self._pad) / span))
            self._canvas.yview_moveto(fraction)
        elif y2 > bottom:
            span = max(1.0, total_h - ch)
            fraction = max(0.0, min(1.0, (y2 - ch) / span))
            self._canvas.yview_moveto(fraction)
        self._sync_tiles()

    def bind_interaction(self) -> None:
        self._canvas.bind("<Button-1>", self._on_click, add=True)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel, add=True)
        self._canvas.bind("<Button-4>", self._on_mousewheel_linux_up, add=True)
        self._canvas.bind("<Button-5>", self._on_mousewheel_linux_down, add=True)

    def unbind_interaction(self) -> None:
        for seq in ("<Button-1>", "<MouseWheel>", "<Button-4>", "<Button-5>"):
            self._canvas.unbind(seq)

    def _on_click(self, evt: tk.Event) -> None:
        if not self._images:
            return
        x = self._canvas.canvasx(evt.x)
        y = self._canvas.canvasy(evt.y)
        col = int((x - self._pad) // (self._slot_px + self._gap))
        row = int((y - self._pad) // (self._slot_px + self._gap))
        if col < 0 or row < 0:
            return
        idx = row * self._ncols + col
        if 0 <= idx < len(self._images):
            self.set_selection(idx)

    def _on_mousewheel(self, evt: tk.Event) -> None:
        delta = evt.delta
        steps = -1 if delta > 0 else 1
        self._canvas.yview_scroll(steps, "units")
        self._sync_tiles()

    def _on_mousewheel_linux_up(self, _evt: tk.Event) -> None:
        self._canvas.yview_scroll(-3, "units")
        self._sync_tiles()

    def _on_mousewheel_linux_down(self, _evt: tk.Event) -> None:
        self._canvas.yview_scroll(3, "units")
        self._sync_tiles()
