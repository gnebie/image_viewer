"""Slideshow, gallery, autoplay, and help-overlay mixin for App."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from .settings_store import DEFAULT_HOTKEYS
from .slideshow import NavigationCommand, SlideshowState, apply_navigation, clamp_index
from .sources import ImageEntry, ImageSource, SourceError

logger = logging.getLogger(__name__)


class SlideshowMixin:
    """Slideshow, gallery, autoplay, and help/overlay methods mixed into App."""

    # ------------------------------------------------------------------ #
    # Gallery                                                             #
    # ------------------------------------------------------------------ #

    def _is_gallery_active(self) -> bool:
        return self._mode == "slideshow" and self._slideshow_view == "gallery"  # type: ignore[attr-defined]

    def _open_gallery(self) -> None:
        if self._slideshow is None or self._mode != "slideshow":  # type: ignore[attr-defined]
            return
        self._cancel_autoplay()
        self._hide_help_overlay()
        self._gallery_saved_index = self._slideshow.index  # type: ignore[attr-defined]
        self._slideshow_view = "gallery"  # type: ignore[attr-defined]
        self._gallery.set_model(  # type: ignore[attr-defined]
            self._slideshow.source,  # type: ignore[attr-defined]
            self._slideshow.images,  # type: ignore[attr-defined]
            self._slideshow.index,  # type: ignore[attr-defined]
            self._settings.thumbnail_size_level,  # type: ignore[attr-defined]
        )
        self._gallery.bind_interaction()  # type: ignore[attr-defined]
        self._gallery_outer.lift()  # type: ignore[attr-defined]
        self._update_mode_banner()  # type: ignore[attr-defined]
        self._set_status("Galerie: fleches, Page_Up defile, Entree/PageDown ouvrir, Esc annuler, +/-/* taille")  # type: ignore[attr-defined]

    def _leave_gallery(self, commit: bool) -> None:
        if not self._is_gallery_active() or self._slideshow is None:  # type: ignore[attr-defined]
            return
        self._gallery.unbind_interaction()  # type: ignore[attr-defined]
        if commit:
            self._slideshow.index = clamp_index(  # type: ignore[attr-defined]
                self._gallery.get_selection(), len(self._slideshow.images)  # type: ignore[attr-defined]
            )
        else:
            self._slideshow.index = clamp_index(  # type: ignore[attr-defined]
                self._gallery_saved_index, len(self._slideshow.images)  # type: ignore[attr-defined]
            )
        self._slideshow_view = "image"  # type: ignore[attr-defined]
        tk.Misc.lift(self._canvas)  # type: ignore[attr-defined]
        self._gallery_outer.lower()  # type: ignore[attr-defined]
        self._show_current_image()
        self._update_mode_banner()  # type: ignore[attr-defined]
        self._set_status("Mode diaporama: Page_Up galerie, ← → images, ↑ ↓ debut/fin, ? aide, Esc navigation")  # type: ignore[attr-defined]
        if self._autoplay:  # type: ignore[attr-defined]
            self._schedule_autoplay()

    # ------------------------------------------------------------------ #
    # Slideshow lifecycle                                                 #
    # ------------------------------------------------------------------ #

    def _start_slideshow(self, src: ImageSource, images: list[ImageEntry], index: int) -> None:
        if self._organize_active:  # type: ignore[attr-defined]
            self._leave_organize_mode()  # type: ignore[attr-defined]
        self._close_slideshow()
        self._slideshow = SlideshowState(source=src, images=images, index=clamp_index(index, len(images)))  # type: ignore[attr-defined]
        self._mode = "slideshow"  # type: ignore[attr-defined]
        self._slideshow_view = "image"  # type: ignore[attr-defined]
        self.title(f"{src.container_dir().name} — {self._base_window_title}")  # type: ignore[attr-defined]
        self._browser_frame.lower()  # type: ignore[attr-defined]
        self._gallery.unbind_interaction()  # type: ignore[attr-defined]
        self._gallery_outer.lower()  # type: ignore[attr-defined]
        tk.Misc.lift(self._canvas)  # type: ignore[attr-defined]
        self._update_mode_banner()  # type: ignore[attr-defined]
        self._set_status("Mode diaporama: Page_Up galerie, ← → images, ↑ ↓ debut/fin, ? aide, Esc navigation")  # type: ignore[attr-defined]
        self._show_current_image()
        self._schedule_autoplay()

    def _close_slideshow(self) -> None:
        self._cancel_autoplay()
        self._hide_help_overlay()
        self._hide_log_overlay()  # type: ignore[attr-defined]
        self._slideshow_view = "image"  # type: ignore[attr-defined]
        self._gallery.unbind_interaction()  # type: ignore[attr-defined]
        self._gallery_outer.lower()  # type: ignore[attr-defined]
        if self._slideshow is not None:  # type: ignore[attr-defined]
            self._slideshow.clear_navigation()  # type: ignore[attr-defined]
            try:
                self._slideshow.source.close()  # type: ignore[attr-defined]
            except OSError as e:
                logger.warning("Fermeture source diaporama: %s", e)
        self._slideshow = None  # type: ignore[attr-defined]
        self._current_photo = None  # type: ignore[attr-defined]
        self._current_image_info = None  # type: ignore[attr-defined]
        self._canvas.delete("all")  # type: ignore[attr-defined]
        self._update_mode_banner()  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    # Image display                                                       #
    # ------------------------------------------------------------------ #

    def _find_first_readable_entry(
        self, start_index: int
    ) -> tuple[int, ImageEntry, Image.Image, Optional[str]] | None:
        """Scan forward from start_index for the first image that opens.

        Returns (final_index, entry, image, skip_error) or None if all fail.
        skip_error is non-None when at least one corrupt image was skipped.
        """
        if self._slideshow is None:  # type: ignore[attr-defined]
            return None
        images = self._slideshow.images  # type: ignore[attr-defined]
        total = len(images)
        last_error: Optional[str] = None
        idx = start_index
        while idx < total:
            entry = images[idx]
            try:
                img = self._slideshow.source.open_image(entry)  # type: ignore[attr-defined]
                skip_error = last_error if idx != start_index else None
                return (idx, entry, img, skip_error)
            except SourceError as e:
                last_error = str(e)
            except (OSError, ValueError, RuntimeError) as e:
                last_error = f"Erreur lecture image: {e}"
            except Exception as e:
                logger.exception("open_image inattendu")
                last_error = f"Erreur lecture image: {e}"
            idx += 1
        return None

    def _show_current_image(self) -> None:
        if self._slideshow is None:  # type: ignore[attr-defined]
            return
        total = len(self._slideshow.images)  # type: ignore[attr-defined]
        if total == 0:
            self._end_slideshow_to_browser()
            return
        if self._slideshow.current_entry() is None:  # type: ignore[attr-defined]
            self._end_slideshow_to_browser()
            return
        result = self._find_first_readable_entry(self._slideshow.index)  # type: ignore[attr-defined]
        if result is None:
            self._set_status("Aucune image lisible a partir de cette position.")  # type: ignore[attr-defined]
            self._end_slideshow_to_browser()
            return
        final_idx, entry, img, skip_error = result
        self._slideshow.index = final_idx  # type: ignore[attr-defined]
        self._render_image_fit(img)
        self._current_image_info = self._build_current_image_info(entry, img)  # type: ignore[attr-defined]
        if self._help_visible():
            self._help_label.config(text=self._help_text_with_context())  # type: ignore[attr-defined]
        name = entry.display_name()
        pos = self._slideshow.index + 1  # type: ignore[attr-defined]
        extra = f" - (skip: {skip_error})" if skip_error else ""
        key = f"{entry.path}|{entry.member or ''}"
        review = self._review_labels.get(key, "-")  # type: ignore[attr-defined]
        self._set_status(f"{pos}/{total} - {name}{extra} [review={review}]")  # type: ignore[attr-defined]

    def _build_current_image_info(self, entry: ImageEntry, img: Image.Image) -> dict[str, str]:
        info = self._slideshow.source.describe_entry(entry) if self._slideshow is not None else {}  # type: ignore[attr-defined]
        info["size"] = f"{img.width}x{img.height}"
        return info

    def _render_image_fit(self, img: Image.Image) -> None:
        cw = max(1, self._canvas.winfo_width())  # type: ignore[attr-defined]
        ch = max(1, self._canvas.winfo_height())  # type: ignore[attr-defined]
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        iw, ih = img.size
        scale = min(cw / iw, ch / ih)
        nw = max(1, int(iw * scale))
        nh = max(1, int(ih * scale))
        try:
            resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        except (OSError, ValueError, MemoryError):
            resized = img.resize((nw, nh))
        photo = ImageTk.PhotoImage(resized)
        self._current_photo = photo  # type: ignore[attr-defined]
        self._canvas.delete("all")  # type: ignore[attr-defined]
        self._canvas.create_image(cw // 2, ch // 2, image=photo, anchor="center")  # type: ignore[attr-defined]

    def _apply_slideshow_resize(self) -> None:
        self._resize_debounce_job = None  # type: ignore[attr-defined]
        if (
            self._mode != "slideshow"  # type: ignore[attr-defined]
            or self._slideshow_view != "image"  # type: ignore[attr-defined]
            or self._slideshow is None  # type: ignore[attr-defined]
        ):
            return
        try:
            entry = self._slideshow.current_entry()  # type: ignore[attr-defined]
            if entry is None:
                return
            img = self._slideshow.source.open_image(entry)  # type: ignore[attr-defined]
            self._render_image_fit(img)
        except SourceError as e:
            self._set_status(str(e))  # type: ignore[attr-defined]
        except (OSError, ValueError) as e:
            logger.warning("Rafraichissement image au redimensionnement: %s", e)

    def _end_slideshow_to_browser(self) -> None:
        container = None
        if self._slideshow is not None:  # type: ignore[attr-defined]
            container = self._slideshow.source.container_dir()  # type: ignore[attr-defined]
        self._close_slideshow()
        if container and container.exists() and container.is_dir():
            self._browser_dir = container  # type: ignore[attr-defined]
        self._autoplay = False  # type: ignore[attr-defined]
        self._refresh_browser()  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    # Navigation queue                                                    #
    # ------------------------------------------------------------------ #

    def _queue_navigation(self, command: NavigationCommand) -> None:
        if self._slideshow is None:  # type: ignore[attr-defined]
            return
        if not self._slideshow.enqueue_navigation(command):  # type: ignore[attr-defined]
            return
        if not self._nav_drain_scheduled:  # type: ignore[attr-defined]
            self._nav_drain_scheduled = True  # type: ignore[attr-defined]
            self.after_idle(self._drain_navigation_queue)  # type: ignore[attr-defined]

    def _drain_navigation_queue(self) -> None:
        self._nav_drain_scheduled = False  # type: ignore[attr-defined]
        if self._slideshow is None:  # type: ignore[attr-defined]
            return
        command = self._slideshow.pop_navigation()  # type: ignore[attr-defined]
        if command is None:
            return
        result = apply_navigation(self._slideshow, command)  # type: ignore[attr-defined]
        if result == "close":
            self._end_slideshow_to_browser()
            return
        if result == "show":
            self._show_current_image()
        if self._slideshow is not None and self._slideshow.pending_navigation:  # type: ignore[attr-defined]
            self._nav_drain_scheduled = True  # type: ignore[attr-defined]
            self.after(1, self._drain_navigation_queue)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    # Autoplay                                                            #
    # ------------------------------------------------------------------ #

    def _cancel_autoplay(self) -> None:
        if self._autoplay_job is not None:  # type: ignore[attr-defined]
            try:
                self.after_cancel(self._autoplay_job)  # type: ignore[attr-defined]
            except tk.TclError:
                pass
            self._autoplay_job = None  # type: ignore[attr-defined]

    def _schedule_autoplay(self) -> None:
        self._cancel_autoplay()
        if not self._autoplay or self._mode != "slideshow":  # type: ignore[attr-defined]
            return
        self._autoplay_job = self.after(self._autoplay_ms, self._autoplay_tick)  # type: ignore[attr-defined]

    def _autoplay_tick(self) -> None:
        self._autoplay_job = None  # type: ignore[attr-defined]
        if not self._autoplay or self._mode != "slideshow":  # type: ignore[attr-defined]
            return
        if self._slideshow is None:  # type: ignore[attr-defined]
            self._autoplay = False  # type: ignore[attr-defined]
            return
        result = apply_navigation(self._slideshow, "next")  # type: ignore[attr-defined]
        if result == "close":
            self._autoplay = False  # type: ignore[attr-defined]
            self._end_slideshow_to_browser()
            return
        if result == "show":
            self._show_current_image()
        self._schedule_autoplay()

    # ------------------------------------------------------------------ #
    # Help overlay                                                        #
    # ------------------------------------------------------------------ #

    def _help_text_with_context(self) -> str:
        from .app import HELP_TEXT  # avoid circular at module level
        info = self._current_image_info or {}  # type: ignore[attr-defined]
        lines = [HELP_TEXT.rstrip()]
        if self._is_gallery_active():
            lines.extend(
                [
                    "",
                    "Galerie (active)",
                    "  Fleches        selection dans la grille",
                    "  Page_Up        defiler la page",
                    "  Page_Down      ouvrir la vignette selectionnee",
                    "  Entree         idem Page_Down",
                    "  Esc            annuler (restaure l'index a l'ouverture de la galerie)",
                    "  + / - / *      taille des vignettes (* = defaut)",
                ]
            )
        if info:
            lines.extend(
                [
                    "",
                    "Image courante",
                    f"  Nom            {info.get('name', '')}",
                    f"  Taille         {info.get('size', '')}",
                    f"  Chemin         {info.get('path', '')}",
                    f"  Source         {info.get('source_type', '')}",
                ]
            )
            if info.get("zip_path"):
                lines.append(f"  Zip            {info['zip_path']}")
            if info.get("zip_member"):
                lines.append(f"  Entree zip     {info['zip_member']}")
        return "\n".join(lines)

    def _show_help_overlay(self) -> None:
        self._hide_log_overlay()  # type: ignore[attr-defined]
        self._help_label.config(text=self._help_text_with_context())  # type: ignore[attr-defined]
        self._help_overlay.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)  # type: ignore[attr-defined]
        self._help_overlay.lift()  # type: ignore[attr-defined]

    def _hide_help_overlay(self) -> None:
        self._help_overlay.grid_remove()  # type: ignore[attr-defined]

    def _help_visible(self) -> bool:
        return bool(self._help_overlay.winfo_ismapped())  # type: ignore[attr-defined]

    def _dismiss_help_on_command(self) -> bool:
        if self._help_visible():
            self._hide_help_overlay()
            return True
        if bool(self._log_overlay.winfo_ismapped()):  # type: ignore[attr-defined]
            self._hide_log_overlay()  # type: ignore[attr-defined]
            return True
        return False

    # ------------------------------------------------------------------ #
    # Hotkeys dialog                                                      #
    # ------------------------------------------------------------------ #

    def _on_open_hotkeys_dialog(self, _evt=None):
        win = tk.Toplevel(self)  # type: ignore[arg-type]
        win.title("Raccourcis")
        win.transient(self.winfo_toplevel())  # type: ignore[attr-defined]
        win.grab_set()
        outer = ttk.Frame(win, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        rows: dict[str, ttk.Entry] = {}
        for r, (action, default_key) in enumerate(DEFAULT_HOTKEYS.items()):
            ttk.Label(outer, text=action).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=2)
            ent = ttk.Entry(outer, width=8)
            ent.insert(0, self._settings.hotkeys.get(action, default_key))  # type: ignore[attr-defined]
            ent.grid(row=r, column=1, sticky="w", pady=2)
            rows[action] = ent

        def save_hotkeys() -> None:
            for action, ent in rows.items():
                key = ent.get().strip().lower()
                if key:
                    self._settings.hotkeys[action] = key  # type: ignore[attr-defined]
            self._settings.clamp()  # type: ignore[attr-defined]
            self._schedule_save_settings()  # type: ignore[attr-defined]
            self._toast.show("Raccourcis mis a jour")  # type: ignore[attr-defined]
            win.destroy()

        ttk.Button(outer, text="Enregistrer", command=save_hotkeys).grid(
            row=len(rows), column=1, sticky="e", pady=(8, 0)
        )
        self.wait_window(win)  # type: ignore[attr-defined]
        return "break"
