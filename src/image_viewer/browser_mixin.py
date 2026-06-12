"""Browser navigation mixin for App."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import tkinter as tk

from .browser_filter import filter_items
from .sources import FolderSource, ImageEntry, ImageSource, SourceError, SUPPORTED_EXTS, ZIP_EXT, ZipSource

logger = logging.getLogger(__name__)


class BrowserMixin:
    """File-browser navigation methods mixed into App."""

    def _on_filter_changed(self, _evt=None) -> None:
        self._browser_filter_query = self._filter_var.get()  # type: ignore[attr-defined]
        self._refresh_browser()

    def _refresh_browser(self) -> None:
        self._mode = "browser"  # type: ignore[attr-defined]
        self._slideshow_view = "image"  # type: ignore[attr-defined]
        self._gallery.unbind_interaction()  # type: ignore[attr-defined]
        self._gallery_outer.lower()  # type: ignore[attr-defined]
        self._hide_help_overlay()  # type: ignore[attr-defined]
        self._hide_log_overlay()  # type: ignore[attr-defined]
        tk.Misc.lower(self._canvas)  # type: ignore[attr-defined]
        self._browser_frame.lift()  # type: ignore[attr-defined]
        self._filter_var.set(self._browser_filter_query)  # type: ignore[attr-defined]
        self.title(f"{self._browser_dir.name} — {self._base_window_title}")  # type: ignore[attr-defined]

        try:
            self._path_label.config(text=str(self._browser_dir))  # type: ignore[attr-defined]
            items: list[Path] = []
            for p in self._browser_dir.iterdir():  # type: ignore[attr-defined]
                if p.is_dir():
                    items.append(p)
                elif p.is_file():
                    ext = p.suffix.lower()
                    if ext == ZIP_EXT or ext in SUPPORTED_EXTS:
                        items.append(p)
            items.sort(key=lambda p: (0 if p.is_dir() else 1, p.name.lower()))
            self._browser_items_all = items  # type: ignore[attr-defined]
            self._browser_items = filter_items(items, self._browser_filter_query)  # type: ignore[attr-defined]

            self._listbox.delete(0, tk.END)  # type: ignore[attr-defined]
            for p in self._browser_items:  # type: ignore[attr-defined]
                if p.is_dir():
                    self._listbox.insert(tk.END, f"[D] {p.name}")  # type: ignore[attr-defined]
                elif p.suffix.lower() == ZIP_EXT:
                    self._listbox.insert(tk.END, f"[Z] {p.name}")  # type: ignore[attr-defined]
                else:
                    self._listbox.insert(tk.END, f"[I] {p.name}")  # type: ignore[attr-defined]

            if not self._browser_items:  # type: ignore[attr-defined]
                self._browser_selection = 0  # type: ignore[attr-defined]
            else:
                self._browser_selection = max(  # type: ignore[attr-defined]
                    0,
                    min(self._browser_selection, len(self._browser_items) - 1),  # type: ignore[attr-defined]
                )
                self._listbox.select_set(self._browser_selection)  # type: ignore[attr-defined]
                self._listbox.see(self._browser_selection)  # type: ignore[attr-defined]

            if self._organize_active:  # type: ignore[attr-defined]
                self._organize_panel.grid(row=5, column=0, sticky="ew", pady=(0, 6))  # type: ignore[attr-defined]
                self._snap_organize_source()  # type: ignore[attr-defined]
                self._update_organize_panel()  # type: ignore[attr-defined]
                self._set_organize_browser_status()  # type: ignore[attr-defined]
            else:
                self._set_status(  # type: ignore[attr-defined]
                    "Mode navigation: ↑↓ selectionner, →/Entree ouvrir, ← remonter, filtre actif, Esc quitter"
                )
            self._update_mode_banner()  # type: ignore[attr-defined]
            self._render_organize_highlights()  # type: ignore[attr-defined]
        except (OSError, PermissionError) as e:
            self._browser_items = []  # type: ignore[attr-defined]
            self._browser_items_all = []  # type: ignore[attr-defined]
            self._listbox.delete(0, tk.END)  # type: ignore[attr-defined]
            self._set_status(f"Impossible de lire le dossier: {e}")  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Lecture dossier navigateur")
            self._browser_items = []  # type: ignore[attr-defined]
            self._browser_items_all = []  # type: ignore[attr-defined]
            self._listbox.delete(0, tk.END)  # type: ignore[attr-defined]
            self._set_status(f"Impossible de lire le dossier: {e}")  # type: ignore[attr-defined]

    def _on_listbox_select(self, _evt=None) -> None:
        sel = self._listbox.curselection()  # type: ignore[attr-defined]
        if sel:
            idx = int(sel[0])
            if (
                self._organize_active  # type: ignore[attr-defined]
                and self._organize_pending_dest is not None  # type: ignore[attr-defined]
                and idx != self._browser_selection  # type: ignore[attr-defined]
            ):
                self._organize_pending_dest = None  # type: ignore[attr-defined]
            self._browser_selection = idx  # type: ignore[attr-defined]
        if self._organize_active:  # type: ignore[attr-defined]
            self._snap_organize_source()  # type: ignore[attr-defined]
            self._update_organize_panel()  # type: ignore[attr-defined]
            self._render_organize_highlights()  # type: ignore[attr-defined]

    def _move_selection(self, delta: int) -> None:
        if not self._browser_items:  # type: ignore[attr-defined]
            return
        self._browser_selection = max(  # type: ignore[attr-defined]
            0,
            min(self._browser_selection + delta, len(self._browser_items) - 1),  # type: ignore[attr-defined]
        )
        self._listbox.select_clear(0, tk.END)  # type: ignore[attr-defined]
        self._listbox.select_set(self._browser_selection)  # type: ignore[attr-defined]
        self._listbox.see(self._browser_selection)  # type: ignore[attr-defined]
        self._render_organize_highlights()  # type: ignore[attr-defined]

    def _enter_selected(self) -> None:
        if not self._browser_items:  # type: ignore[attr-defined]
            return
        p = self._browser_items[self._browser_selection]  # type: ignore[attr-defined]
        if p.is_dir():
            self._browser_dir = p  # type: ignore[attr-defined]
            self._browser_selection = 0  # type: ignore[attr-defined]
            self._refresh_browser()
            return
        ext = p.suffix.lower()
        if ext == ZIP_EXT:
            self._open_zip(p)
        elif ext in SUPPORTED_EXTS:
            self._open_folder_or_image(p.parent, focus_file=p)

    def _go_parent(self) -> None:
        parent = self._browser_dir.parent  # type: ignore[attr-defined]
        if parent == self._browser_dir:  # type: ignore[attr-defined]
            return
        prev = self._browser_dir  # type: ignore[attr-defined]
        self._browser_dir = parent  # type: ignore[attr-defined]
        self._refresh_browser()
        try:
            idx = next(i for i, p in enumerate(self._browser_items) if p == prev)  # type: ignore[attr-defined]
            self._browser_selection = idx  # type: ignore[attr-defined]
            self._listbox.select_clear(0, tk.END)  # type: ignore[attr-defined]
            self._listbox.select_set(idx)  # type: ignore[attr-defined]
            self._listbox.see(idx)  # type: ignore[attr-defined]
        except StopIteration:
            pass

    def _open_folder_or_image(self, folder: Path, focus_file: Optional[Path] = None) -> None:
        src = FolderSource(folder)
        images = self._safe_list_images(src)
        if not images:
            src.close()
            self._set_status("Aucune image lisible dans ce dossier.")  # type: ignore[attr-defined]
            return
        idx = 0
        if focus_file is not None:
            for i, entry in enumerate(images):
                if entry.path == focus_file:
                    idx = i
                    break
        self._start_slideshow(src, images, idx)  # type: ignore[attr-defined]

    def _open_zip(self, zip_path: Path) -> None:
        src = ZipSource(zip_path)
        images = self._safe_list_images(src)
        if not images:
            src.close()
            self._set_status("Aucune image lisible dans ce zip (ou zip corrompu).")  # type: ignore[attr-defined]
            return
        self._start_slideshow(src, images, 0)  # type: ignore[attr-defined]

    def _safe_list_images(self, src: ImageSource) -> list[ImageEntry]:
        try:
            return src.list_images()
        except SourceError as e:
            self._set_status(str(e))  # type: ignore[attr-defined]
            return []
        except Exception as e:
            logger.exception("list_images inattendu")
            self._set_status(f"Erreur listing: {e}")  # type: ignore[attr-defined]
            return []
