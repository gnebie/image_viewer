"""Tkinter app for browsing folders and image zip slideshows."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Literal, Optional, Sequence

import tkinter as tk
from tkinter import messagebox, ttk

from .browser_mixin import BrowserMixin
from .gallery_layout import move_gallery_index
from .help_text import HELP_TEXT
from .gallery_view import SlideshowGalleryView
from .logging_config import setup_logging
from .onboarding_dialog import show_onboarding
from .operation_log import OperationLog
from .organize_mixin import OrganizeMixin
from .settings_store import (
    DEFAULT_THUMBNAIL_LEVEL,
    Settings,
    DEFAULT_HOTKEYS,
    load as load_settings,
    save as save_settings,
    AUTOPLAY_MS_MIN,
    AUTOPLAY_MS_MAX,
)
from .slideshow_mixin import SlideshowMixin
from .sources import SUPPORTED_EXTS, ZIP_EXT
from .toast import ToastOverlay
from .tooltip import ToolTip

logger = logging.getLogger("image_viewer.app")

SlideshowView = Literal["image", "gallery"]
OrganizeTarget = Literal["zip_dir", "image"]
OrganizeOp = Literal["move", "copy"]


class App(BrowserMixin, OrganizeMixin, SlideshowMixin, tk.Tk):
    def __init__(self, start_path: Path):
        super().__init__()
        self._base_window_title = "Diaporama images (dossier + zip)"
        self.title(self._base_window_title)
        self.minsize(720, 480)

        # Settings must be loaded before other state that depends on them.
        self._cwd = Path.cwd()
        self._settings: Settings = load_settings(self._cwd)
        self._settings_save_job: Optional[str] = None

        self._mode: str = "browser"
        self._browser_dir: Path = start_path if start_path.is_dir() else start_path.parent
        self._browser_items: list[Path] = []
        self._browser_items_all: list[Path] = []
        self._browser_selection: int = 0
        self._browser_filter_query = ""

        self._slideshow = None
        self._current_photo: Optional[object] = None
        self._current_image_info: Optional[dict[str, str]] = None

        self._autoplay = False
        self._autoplay_ms: int = self._settings.autoplay_ms
        self._autoplay_job: Optional[str] = None

        self._nav_drain_scheduled = False
        self._initial_geometry_applied = False
        self._resize_debounce_job: Optional[str] = None
        self._escape_arm_job: Optional[str] = None

        self._slideshow_view: SlideshowView = "image"
        self._gallery_saved_index: int = 0

        self._organize_active = False
        self._organize_target: OrganizeTarget = "zip_dir"
        self._organize_op: OrganizeOp = "move"
        self._organize_source: Optional[Path] = None
        self._organize_pending_dest: Optional[Path] = None
        self._operation_log = OperationLog(max_items=20)
        self._review_labels: dict[str, str] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._main_frame = ttk.Frame(self, padding=8)
        self._main_frame.grid(row=0, column=0, sticky="nsew")
        self._main_frame.columnconfigure(0, weight=1)
        self._main_frame.rowconfigure(0, weight=1)

        self._content = ttk.Frame(self._main_frame)
        self._content.grid(row=0, column=0, sticky="nsew")
        self._content.columnconfigure(0, weight=1)
        self._content.rowconfigure(0, weight=1)
        self._content.rowconfigure(1, weight=0)

        self._canvas = tk.Canvas(self._content, highlightthickness=0, bg="black")
        self._canvas.grid(row=0, column=0, sticky="nsew")

        self._gallery_outer = ttk.Frame(self._content)
        self._gallery_outer.grid(row=0, column=0, sticky="nsew")
        self._gallery_outer.lower()
        self._gallery = SlideshowGalleryView(self._gallery_outer)
        self._gallery.pack(fill=tk.BOTH, expand=True)

        self._browser_frame = ttk.Frame(self._content)
        self._browser_frame.grid(row=0, column=0, sticky="nsew")
        self._browser_frame.columnconfigure(0, weight=1)
        self._browser_frame.rowconfigure(4, weight=1)

        self._mode_banner = ttk.Label(self._browser_frame, text="", anchor="w")
        self._mode_banner.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        self._mode_hint = ttk.Label(self._browser_frame, text="", anchor="w")
        self._mode_hint.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        self._breadcrumb_frame = ttk.Frame(self._browser_frame)
        self._breadcrumb_frame.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        self._breadcrumb_widgets: list[ttk.Label] = []

        self._filter_sort_frame = ttk.Frame(self._browser_frame)
        self._filter_sort_frame.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        self._filter_sort_frame.columnconfigure(0, weight=1)

        self._filter_var = tk.StringVar(value="")
        self._filter_entry = ttk.Entry(self._filter_sort_frame, textvariable=self._filter_var)
        self._filter_entry.grid(row=0, column=0, sticky="ew")
        self._filter_entry.bind("<KeyRelease>", self._on_filter_changed)

        self._sort_var = tk.StringVar(value=self._settings.sort_mode)
        self._sort_combo = ttk.Combobox(
            self._filter_sort_frame,
            textvariable=self._sort_var,
            values=["name_asc", "name_desc", "date_asc", "date_desc"],
            state="readonly",
            width=12,
        )
        self._sort_combo.grid(row=0, column=1, padx=(6, 0))
        self._sort_combo.bind("<<ComboboxSelected>>", self._on_sort_changed)

        self._organize_panel = ttk.LabelFrame(self._browser_frame, text="Mode tri")
        self._organize_help = ttk.Label(
            self._organize_panel, justify="left", anchor="nw", text=""
        )
        self._organize_help.grid(row=0, column=0, sticky="ew", padx=6, pady=4)
        self._organize_state_label = ttk.Label(self._organize_panel, text="", anchor="w")
        self._organize_state_label.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 4))
        self._shortcuts_label = ttk.Label(
            self._organize_panel, text="", justify="left", anchor="nw"
        )
        self._shortcuts_label.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 4))

        self._listbox = tk.Listbox(self._browser_frame, activestyle="none")
        self._listbox_sb = ttk.Scrollbar(
            self._browser_frame, orient="vertical", command=self._listbox.yview
        )
        self._listbox.configure(yscrollcommand=self._listbox_sb.set)
        self._browser_frame.columnconfigure(1, weight=0)
        self._listbox.grid(row=4, column=0, sticky="nsew")
        self._listbox_sb.grid(row=4, column=1, sticky="ns")
        self._listbox.bindtags(("OrganizeIV",) + self._listbox.bindtags())
        self.bind_class("OrganizeIV", "<KeyPress>", self._organize_listbox_key)

        self._help_overlay = ttk.Frame(self._content, padding=16)
        self._help_overlay.columnconfigure(0, weight=1)
        self._help_overlay.rowconfigure(0, weight=1)
        self._help_label = ttk.Label(self._help_overlay, text="", justify="left", anchor="nw")
        self._help_label.grid(row=0, column=0, sticky="nsew")
        self._log_overlay = ttk.Frame(self._content, padding=16)
        self._log_overlay.columnconfigure(0, weight=1)
        self._log_overlay.rowconfigure(0, weight=1)
        self._log_label = ttk.Label(self._log_overlay, text="", justify="left", anchor="nw")
        self._log_label.grid(row=0, column=0, sticky="nsew")
        self._toast = ToastOverlay(self._content)

        self._bottom = ttk.Frame(self._main_frame)
        self._bottom.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self._bottom.columnconfigure(2, weight=1)

        self._btn_prev = ttk.Button(self._bottom, text="← Precedent", command=self.prev_action)
        self._btn_next = ttk.Button(self._bottom, text="Suivant →", command=self.next_action)
        self._btn_prev.grid(row=0, column=0, padx=(0, 6))
        self._btn_next.grid(row=0, column=1, padx=(0, 12))
        ToolTip(self._btn_prev, "Image precedente  ←")
        ToolTip(self._btn_next, "Image suivante  →")

        self._status = ttk.Label(self._bottom, text="", anchor="w")
        self._status.grid(row=0, column=2, sticky="ew")

        self._set_initial_window_geometry()

        self.bind("<space>", self._on_space)
        self.bind("<plus>", self._on_plus)
        self.bind("<minus>", self._on_minus)
        self.bind("<KP_Add>", self._on_plus)
        self.bind("<KP_Subtract>", self._on_minus)
        self.bind("?", self._on_help)

        self.bind("<Left>", self._on_left)
        self.bind("<Right>", self._on_right)
        self.bind("<Up>", self._on_up)
        self.bind("<Down>", self._on_down)
        self.bind("<Return>", self._on_enter)
        self.bind("<Escape>", self._on_escape)
        self.bind("<BackSpace>", self._on_backspace)
        self.bind("<Home>", self._on_home)
        self.bind("<End>", self._on_end)
        self.bind("<Configure>", self._on_resize)

        self.bind("<Prior>", self._on_page_up)
        self.bind("<Next>", self._on_page_down)
        self.bind("<KP_Multiply>", self._on_star)
        self.bind("<Shift-Key-8>", self._on_star)
        self.bind("f", self._on_fullscreen_toggle)
        self.bind("l", self._on_log_overlay)
        self.bind("n", self._on_gallery_goto)
        self.bind("<F5>", self._on_reload_browser)
        self.bind("g", self._on_review_keep)
        self.bind("j", self._on_review_drop)
        self.bind("t", self._on_review_todo)
        self.bind("e", self._on_review_export)
        self.bind("<Control-k>", self._on_open_hotkeys_dialog)

        self._listbox.bind("<Double-Button-1>", lambda e: self._enter_selected())
        self._listbox.bind("<<ListboxSelect>>", self._on_listbox_select)
        # The Listbox class bindings (tk::ListboxUpDown, xview scroll) would fire in
        # addition to the toplevel bindings — selection would move twice per keypress
        # and drift via the listbox's internal "active" element. Handle navigation on
        # the widget itself and "break" so neither the class nor the toplevel sees it.
        self._listbox.bind("<Up>", self._on_listbox_up)
        self._listbox.bind("<Down>", self._on_listbox_down)
        self._listbox.bind("<Home>", self._on_listbox_home)
        self._listbox.bind("<End>", self._on_listbox_end)
        self._listbox.bind("<Left>", self._on_listbox_left)
        self._listbox.bind("<Right>", self._on_listbox_right)

        self.protocol("WM_DELETE_WINDOW", self._on_close_window)

        if not self._settings.onboarding_done:
            show_onboarding(self)
            self._settings.onboarding_done = True
            self._schedule_save_settings()
        self._refresh_browser()
        self.after(10, lambda: self._auto_open_start(start_path))

    # ------------------------------------------------------------------ #
    # Startup                                                             #
    # ------------------------------------------------------------------ #

    def _auto_open_start(self, start_path: Path) -> None:
        try:
            if start_path.is_file():
                if start_path.suffix.lower() == ZIP_EXT:
                    self._open_zip(start_path)
                elif start_path.suffix.lower() in SUPPORTED_EXTS:
                    self._open_folder_or_image(start_path.parent, focus_file=start_path)
        except (OSError, ValueError) as e:
            self._set_status(f"Erreur ouverture initiale: {e}")
        except Exception as e:
            logger.exception("Erreur ouverture initiale inattendue")
            self._set_status(f"Erreur ouverture initiale: {e}")

    # ------------------------------------------------------------------ #
    # Mode banner                                                         #
    # ------------------------------------------------------------------ #

    def _update_mode_banner(self) -> None:
        if self._is_gallery_active():
            mode = "Mode: Galerie"
            hint = "Fleches selection, Page_Up scroll, Enter/Page_Down ouvrir, Esc annuler, ? aide"
        elif self._mode == "slideshow":
            auto_state = "ON" if self._autoplay else "OFF"
            mode = f"Mode: Diaporama  [autoplay {auto_state} — espace]"
            hint = "Left/Right images, Page_Up galerie, g/j/t review, e export, ? aide"
        elif self._organize_active:
            src = self._organize_source.name if self._organize_source is not None else "-"
            mode = f"Mode: Tri ({self._organize_target}/{self._organize_op}) source={src}"
            hint = "d/i cible, m/c operation, r regle, u annule, Entree confirme, Ctrl+Shift+chiffre, ? aide"
        else:
            mode = "Mode: Navigation"
            hint = "Up/Down selection, Right/Enter ouvrir, Left parent, filtre, d mode tri, l journal, ? aide"
        self._mode_banner.config(text=mode)
        self._mode_hint.config(text=hint)

    # ------------------------------------------------------------------ #
    # Settings persistence                                                #
    # ------------------------------------------------------------------ #

    def _cancel_save_job(self) -> None:
        if self._settings_save_job is not None:
            try:
                self.after_cancel(self._settings_save_job)
            except tk.TclError:
                pass
            self._settings_save_job = None

    def _schedule_save_settings(self) -> None:
        self._cancel_save_job()
        self._settings_save_job = self.after(450, self._timed_save_settings)

    def _timed_save_settings(self) -> None:
        self._settings_save_job = None
        self._persist_settings_now()

    def _persist_settings_now(self) -> None:
        try:
            save_settings(self._settings, self._cwd)
        except OSError as e:
            logger.warning("Could not save settings: %s", e)

    def _flush_save_settings(self) -> None:
        self._cancel_save_job()
        self._persist_settings_now()

    # ------------------------------------------------------------------ #
    # Window management                                                   #
    # ------------------------------------------------------------------ #

    def _set_initial_window_geometry(self) -> None:
        if self._initial_geometry_applied:
            return
        if self._settings.window_geometry:
            try:
                self.geometry(self._settings.window_geometry)
                self._initial_geometry_applied = True
                return
            except tk.TclError:
                pass
        screen_w = max(1, self.winfo_screenwidth())
        screen_h = max(1, self.winfo_screenheight())
        target_w = min(max(960, int(screen_w * 0.78)), int(screen_w * 0.92))
        target_h = min(max(700, int(screen_h * 0.78)), int(screen_h * 0.92))
        pos_x = max(0, (screen_w - target_w) // 2)
        pos_y = max(0, (screen_h - target_h) // 3)
        self.geometry(f"{target_w}x{target_h}+{pos_x}+{pos_y}")
        self._initial_geometry_applied = True

    def _on_reload_browser(self, _evt=None):
        if self._mode == "browser":
            self._refresh_browser()
            self._toast.show("Dossier recharge")
        return "break"

    def _on_close_window(self) -> None:
        if self._resize_debounce_job is not None:
            try:
                self.after_cancel(self._resize_debounce_job)
            except tk.TclError:
                pass
            self._resize_debounce_job = None
        try:
            if not bool(self.attributes("-fullscreen")):
                self._settings.window_geometry = self.geometry()
        except tk.TclError:
            pass
        self._flush_save_settings()
        self._close_slideshow()
        self.destroy()

    def _on_resize(self, evt=None) -> None:
        if evt is not None and evt.widget is not self:
            return
        if self._resize_debounce_job is not None:
            try:
                self.after_cancel(self._resize_debounce_job)
            except tk.TclError:
                pass
            self._resize_debounce_job = None
        self._resize_debounce_job = self.after(300, self._apply_slideshow_resize)

    def _set_status(self, text: str) -> None:
        self._status.config(text=text)

    def _text_input_focused(self) -> bool:
        """True when a text-entry widget has focus — global single-key and editing
        bindings must not fire while the user is typing in the filter or a combobox."""
        try:
            w = self.focus_get()
        except (KeyError, tk.TclError):
            return False
        return isinstance(w, (tk.Entry, ttk.Entry, tk.Text, tk.Spinbox))

    # ------------------------------------------------------------------ #
    # Button actions                                                      #
    # ------------------------------------------------------------------ #

    def _gallery_move(self, row_delta: int, col_delta: int) -> bool:
        """Move gallery selection. Returns True if gallery consumed the event."""
        if not (self._is_gallery_active() and self._slideshow is not None):
            return False
        cols = self._gallery.column_count
        total = len(self._slideshow.images)
        idx = move_gallery_index(self._gallery.get_selection(), total, cols, row_delta, col_delta)
        self._gallery.set_selection(idx)
        return True

    def prev_action(self) -> None:
        if self._gallery_move(0, -1):
            return
        if self._mode == "slideshow":
            self._queue_navigation("prev")
        else:
            self._go_parent()

    def next_action(self) -> None:
        if self._gallery_move(0, 1):
            return
        if self._mode == "slideshow":
            self._queue_navigation("next")
        else:
            self._enter_selected()

    # ------------------------------------------------------------------ #
    # Keyboard event handlers                                             #
    # ------------------------------------------------------------------ #

    def _on_left(self, _evt=None):
        if self._text_input_focused():
            return None
        if self._dismiss_help_on_command():
            return "break"
        if self._gallery_move(0, -1):
            return "break"
        if self._mode == "slideshow":
            self._queue_navigation("prev")
        else:
            self._go_parent()
        return None

    def _on_right(self, _evt=None):
        if self._text_input_focused():
            return None
        if self._dismiss_help_on_command():
            return "break"
        if self._gallery_move(0, 1):
            return "break"
        if self._mode == "slideshow":
            self._queue_navigation("next")
        else:
            self._enter_selected()
        return None

    def _on_up(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        if self._gallery_move(-1, 0):
            return "break"
        if self._mode == "browser":
            self._move_selection(-1)
        elif self._mode == "slideshow":
            self._queue_navigation("first")
        return None

    def _on_down(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        if self._gallery_move(1, 0):
            return "break"
        if self._mode == "browser":
            self._move_selection(+1)
        elif self._mode == "slideshow":
            self._queue_navigation("last")
        return None

    def _on_listbox_up(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        self._move_selection(-1)
        return "break"

    def _on_listbox_down(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        self._move_selection(+1)
        return "break"

    def _on_listbox_home(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        self._move_selection(-len(self._browser_items))
        return "break"

    def _on_listbox_end(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        self._move_selection(len(self._browser_items))
        return "break"

    def _on_listbox_left(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        self._go_parent()
        return "break"

    def _on_listbox_right(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        self._enter_selected()
        return "break"

    def _on_enter(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        if self._is_gallery_active():
            self._leave_gallery(commit=True)
            return "break"
        if self._mode == "browser" and self._organize_active:
            self._organize_handle_enter()
            return "break"
        if self._mode == "browser":
            self._enter_selected()
        return None

    def _on_backspace(self, _evt=None):
        if self._text_input_focused():
            return None
        if self._dismiss_help_on_command():
            return "break"
        if self._mode == "browser":
            self._go_parent()
        return None

    def _on_home(self, _evt=None):
        if self._text_input_focused():
            return None
        if self._mode == "browser":
            self._move_selection(-len(self._browser_items))
        return None

    def _on_end(self, _evt=None):
        if self._text_input_focused():
            return None
        if self._mode == "browser":
            self._move_selection(len(self._browser_items))
        return None

    def _arm_quit(self) -> None:
        self._toast.show("Appuyez a nouveau sur Esc pour quitter", ms=1500)
        self._escape_arm_job = self.after(1600, self._disarm_quit)

    def _disarm_quit(self) -> None:
        self._escape_arm_job = None

    def _on_escape(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        if self._is_gallery_active():
            self._leave_gallery(commit=False)
            return "break"
        if self._mode == "slideshow":
            self._end_slideshow_to_browser()
        elif self._organize_active:
            self._leave_organize_mode()
            self._set_status("Mode navigation: ↑↓ selectionner, →/Entree ouvrir, ← remonter, filtre actif, Esc quitter")
            return "break"
        else:
            if self._escape_arm_job is not None:
                try:
                    self.after_cancel(self._escape_arm_job)
                except tk.TclError:
                    pass
                self._escape_arm_job = None
                self._on_close_window()
            else:
                self._arm_quit()
        return None

    def _on_page_up(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        if self._is_gallery_active():
            self._gallery.scroll_canvas_page(-1)
            return "break"
        if self._mode == "slideshow" and self._slideshow_view == "image":
            self._open_gallery()
            return "break"
        return None

    def _on_page_down(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        if self._is_gallery_active():
            self._leave_gallery(commit=True)
            return "break"
        return None

    def _on_star(self, _evt=None):
        if not self._is_gallery_active():
            return None
        self._gallery.reset_thumb_level(DEFAULT_THUMBNAIL_LEVEL)
        self._settings.thumbnail_size_level = DEFAULT_THUMBNAIL_LEVEL
        self._schedule_save_settings()
        self._set_status("Taille vignettes: niveau par defaut")
        return "break"

    def _on_fullscreen_toggle(self, _evt=None):
        if self._text_input_focused():
            return None
        try:
            is_fullscreen = bool(self.attributes("-fullscreen"))
        except tk.TclError:
            is_fullscreen = False
        next_state = not is_fullscreen
        self.attributes("-fullscreen", next_state)
        self._set_status("Plein ecran: ON" if next_state else "Plein ecran: OFF")
        return "break"

    def _on_space(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        if self._is_gallery_active():
            return None
        if self._mode != "slideshow":
            return None
        self._autoplay = not self._autoplay
        if self._autoplay:
            self._set_status(f"Auto: ON ({self._autoplay_ms} ms) - espace pour pause")
            self._schedule_autoplay()
        else:
            self._cancel_autoplay()
            self._set_status("Auto: OFF - espace pour demarrer")
        self._update_mode_banner()
        return None

    def _on_plus(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        if self._is_gallery_active():
            self._gallery.bump_thumb_level(+1)
            self._settings.thumbnail_size_level = self._gallery.get_thumb_level()
            self._schedule_save_settings()
            self._set_status(f"Taille vignettes: niveau {self._settings.thumbnail_size_level}")
            return "break"
        if self._mode != "slideshow":
            return None
        self._autoplay_ms = max(AUTOPLAY_MS_MIN, self._autoplay_ms - 250)
        self._settings.autoplay_ms = self._autoplay_ms
        self._schedule_save_settings()
        if self._autoplay:
            self._schedule_autoplay()
        self._set_status(f"Vitesse auto: {self._autoplay_ms} ms")
        return None

    def _on_minus(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        if self._is_gallery_active():
            self._gallery.bump_thumb_level(-1)
            self._settings.thumbnail_size_level = self._gallery.get_thumb_level()
            self._schedule_save_settings()
            self._set_status(f"Taille vignettes: niveau {self._settings.thumbnail_size_level}")
            return "break"
        if self._mode != "slideshow":
            return None
        self._autoplay_ms = min(AUTOPLAY_MS_MAX, self._autoplay_ms + 250)
        self._settings.autoplay_ms = self._autoplay_ms
        self._schedule_save_settings()
        if self._autoplay:
            self._schedule_autoplay()
        self._set_status(f"Vitesse auto: {self._autoplay_ms} ms")
        return None

    def _on_help(self, _evt=None) -> Optional[str]:
        if self._text_input_focused():
            return None
        if self._help_visible():
            self._hide_help_overlay()
        else:
            self._show_help_overlay()
        return "break"


def _parse_start_path(argv: Sequence[str]) -> Path:
    if len(argv) >= 2:
        return Path(argv[1]).expanduser().resolve()
    return Path.cwd()


def main() -> None:
    setup_logging()
    logger.info("Demarrage image_viewer cwd=%s", Path.cwd())
    start = _parse_start_path(sys.argv)
    if not start.exists():
        messagebox.showerror("Erreur", f"Chemin introuvable: {start}")
        return

    app = App(start)
    app.mainloop()


def run_with_error_boundary() -> None:
    try:
        main()
    except Exception:
        logging.getLogger("image_viewer").exception("Erreur fatale")
        raise
