"""Tkinter app for browsing folders and image zip slideshows."""

from __future__ import annotations

import logging
import json
import sys
from pathlib import Path
from typing import Literal, Optional, Sequence

import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from .browser_filter import filter_items
from .gallery_layout import move_gallery_index
from .gallery_view import SlideshowGalleryView
from .logging_config import setup_logging
from .slideshow import NavigationCommand, SlideshowState, apply_navigation, clamp_index
from .name_conflict_dialog import prompt_name_conflict
from .onboarding_dialog import show_onboarding
from .operation_log import OperationLog, OperationRecord
from .organize_ops import (
    OrganizeError,
    execute_move_or_copy_to_final,
    remove_path_for_overwrite,
    source_allows_move,
    unique_destination_path,
)
from .settings_store import (
    DEFAULT_THUMBNAIL_LEVEL,
    Settings,
    DEFAULT_HOTKEYS,
    load as load_settings,
    save as save_settings,
)
from .sorting_rules import resolve_destination
from .sources import FolderSource, ImageEntry, ImageSource, SourceError, SUPPORTED_EXTS, ZIP_EXT, ZipSource
from .toast import ToastOverlay

logger = logging.getLogger("image_viewer.app")

SlideshowView = Literal["image", "gallery"]
OrganizeTarget = Literal["zip_dir", "image"]
OrganizeOp = Literal["move", "copy"]


HELP_TEXT = """Commandes

Navigation
  Up / Down      selection
  Right / Enter  ouvrir dossier, zip, image
  Left           dossier parent
  Backspace      dossier parent
  Esc            quitter (navigation) ; quitter mode tri (mode tri)
  d              mode tri (deplacement / copie)

Diaporama
  Left           image precedente (ou fermer au debut)
  Right          image suivante (ou fermer a la fin)
  Up             premiere image
  Down           derniere image
  Page_Up        galerie miniatures (depuis l'image)
  Page_Down      (image) sans effet ; (galerie) ouvrir l'image selectionnee
  Space          autoplay on/off
  + / -          vitesse autoplay (image) ; taille vignettes (galerie)
  *              taille vignettes par defaut (galerie)
  ?              aide
  Esc            retour navigation (image) ; annuler galerie (galerie)

Galerie miniatures
  Fleches        deplacer la selection
  Page_Up        defiler la page vers le haut
  Entree         ouvrir l'image selectionnee
  Esc            fermer sans appliquer la selection

Mode tri (navigation, focus listbox)
  d              activer le mode ; cible zip/dossier (d) ou images (i)
  i              cible images
  m / c          deplacer / copier
  r              appliquer une regle auto (dry-run puis confirmation)
  u              annuler destination armee
  0-9            aller au raccourci dossier (config)
  Ctrl+Shift+chiffre  enregistrer le dossier courant pour ce chiffre (ligne ou pave)
  Entree         sur dossier: armer puis confirmer (2 fois) puis dialogue
  Right          entrer dossier ou ouvrir zip / image
  Esc            quitter le mode tri

Divers
  l              afficher/masquer le journal des operations (navigation)
  Ctrl+K         configurer les hotkeys
  g / j / t      etiqueter image courante (garder/jeter/a_trier) en diaporama
  e              exporter les etiquettes review (json+csv)
  r              en mode tri: appliquer une regle auto (dry-run + confirmation)
"""


class App(tk.Tk):
    def __init__(self, start_path: Path):
        super().__init__()
        self._base_window_title = "Diaporama images (dossier + zip)"
        self.title(self._base_window_title)
        self.minsize(720, 480)

        self._mode: str = "browser"
        self._browser_dir: Path = start_path if start_path.is_dir() else start_path.parent
        self._browser_items: list[Path] = []
        self._browser_items_all: list[Path] = []
        self._browser_selection: int = 0
        self._browser_filter_query = ""

        self._slideshow: Optional[SlideshowState] = None
        self._current_photo: Optional[ImageTk.PhotoImage] = None
        self._current_image_info: Optional[dict[str, str]] = None

        self._autoplay = False
        self._autoplay_ms = 2500
        self._autoplay_job: Optional[str] = None

        self._nav_drain_scheduled = False
        self._initial_geometry_applied = False
        self._resize_debounce_job: Optional[str] = None

        self._cwd = Path.cwd()
        self._settings: Settings = load_settings(self._cwd)
        self._settings_save_job: Optional[str] = None
        self._slideshow_view: SlideshowView = "image"
        self._gallery_saved_index: int = 0

        self._organize_active = False
        self._organize_target: OrganizeTarget = "zip_dir"
        self._organize_op: OrganizeOp = "move"
        self._organize_source: Optional[Path] = None
        self._organize_pending_dest: Optional[Path] = None
        self._organize_pending_overwrite = False
        self._operation_log = OperationLog(max_items=20)
        self._review_labels: dict[str, str] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._root = ttk.Frame(self, padding=8)
        self._root.grid(row=0, column=0, sticky="nsew")
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)

        self._content = ttk.Frame(self._root)
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

        self._path_label = ttk.Label(self._browser_frame, text="")
        self._path_label.grid(row=2, column=0, sticky="ew", pady=(0, 6))

        self._filter_var = tk.StringVar(value="")
        self._filter_entry = ttk.Entry(self._browser_frame, textvariable=self._filter_var)
        self._filter_entry.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        self._filter_entry.bind("<KeyRelease>", self._on_filter_changed)

        self._organize_panel = ttk.LabelFrame(self._browser_frame, text="Mode tri")
        self._organize_help = ttk.Label(
            self._organize_panel,
            justify="left",
            anchor="nw",
            text=(
                "d = cible zip/dossier   i = cible images   m = deplacer   c = copier\n"
                "r = regle auto (dry-run)   u = annuler destination armee\n"
                "0-9 = raccourci dossier   Ctrl+Shift+chiffre = enregistrer raccourci ici\n"
                "Entree sur dossier = armer, Entree encore = confirmer   Right = entrer dossier\n"
                "Esc = quitter le mode tri"
            ),
        )
        self._organize_help.grid(row=0, column=0, sticky="ew", padx=6, pady=4)
        self._organize_state_label = ttk.Label(self._organize_panel, text="", anchor="w")
        self._organize_state_label.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 4))

        self._listbox = tk.Listbox(self._browser_frame, activestyle="none")
        self._listbox.grid(row=4, column=0, sticky="nsew")
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

        self._bottom = ttk.Frame(self._root)
        self._bottom.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self._bottom.columnconfigure(2, weight=1)

        self._btn_prev = ttk.Button(self._bottom, text="← Precedent", command=self.prev_action)
        self._btn_next = ttk.Button(self._bottom, text="Suivant →", command=self.next_action)
        self._btn_prev.grid(row=0, column=0, padx=(0, 6))
        self._btn_next.grid(row=0, column=1, padx=(0, 12))

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
        self.bind("<Configure>", self._on_resize)

        self.bind("<Prior>", self._on_page_up)
        self.bind("<Next>", self._on_page_down)
        self.bind("<KP_Multiply>", self._on_star)
        self.bind("<Shift-Key-8>", self._on_star)
        self.bind("l", self._on_log_overlay)
        self.bind("g", self._on_review_keep)
        self.bind("j", self._on_review_drop)
        self.bind("t", self._on_review_todo)
        self.bind("e", self._on_review_export)
        self.bind("<Control-k>", self._on_open_hotkeys_dialog)

        self._listbox.bind("<Double-Button-1>", lambda e: self._enter_selected())
        self._listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        self.protocol("WM_DELETE_WINDOW", self._on_close_window)

        if not self._settings.onboarding_done:
            show_onboarding(self)
            self._settings.onboarding_done = True
            self._schedule_save_settings()
        self._refresh_browser()
        self.after(10, lambda: self._auto_open_start(start_path))

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

    def _update_mode_banner(self) -> None:
        if self._is_gallery_active():
            mode = "Mode: Galerie"
            hint = "Fleches selection, Page_Up scroll, Enter/Page_Down ouvrir, Esc annuler"
        elif self._mode == "slideshow":
            mode = "Mode: Diaporama"
            hint = "Left/Right images, Page_Up galerie, g/j/t review, e export, ? aide"
        elif self._organize_active:
            src = self._organize_source.name if self._organize_source is not None else "-"
            mode = f"Mode: Tri ({self._organize_target}/{self._organize_op}) source={src}"
            hint = "d/i cible, m/c operation, r regle, u annule, Entree confirme, Ctrl+Shift+chiffre"
        else:
            mode = "Mode: Navigation"
            hint = "Up/Down selection, Right/Enter ouvrir, Left parent, filtre via champ, d mode tri, l journal"
        self._mode_banner.config(text=mode)
        self._mode_hint.config(text=hint)

    def _apply_browser_filter(self, items: list[Path]) -> list[Path]:
        return filter_items(items, self._browser_filter_query)

    def _on_filter_changed(self, _evt=None) -> None:
        self._browser_filter_query = self._filter_var.get()
        self._refresh_browser()

    def _render_organize_highlights(self) -> None:
        for idx in range(self._listbox.size()):
            try:
                self._listbox.itemconfig(idx, bg="", fg="")
            except tk.TclError:
                pass
        if not self._organize_active:
            return
        for i, item in enumerate(self._browser_items):
            if self._organize_source is not None and item == self._organize_source:
                self._listbox.itemconfig(i, bg="#2d4f7a", fg="white")
            if self._organize_pending_dest is not None and item == self._organize_pending_dest:
                self._listbox.itemconfig(i, bg="#6e5c1f", fg="white")

    def _resolve_hotkey_action(self, lower: str) -> str | None:
        for action, key in self._settings.hotkeys.items():
            if key == lower:
                return action
        return None

    def _add_operation_log(self, kind: str, src: Path, dest: Path, detail: str = "") -> None:
        self._operation_log.add(OperationRecord(kind=kind, src=str(src), dest=str(dest), detail=detail))

    def _show_operation_log_overlay(self) -> None:
        lines = ["Historique operations (plus recent en haut):"]
        for rec in self._operation_log.items():
            suffix = f" ({rec.detail})" if rec.detail else ""
            lines.append(f"- {rec.kind}: {rec.src} -> {rec.dest}{suffix}")
        if len(lines) == 1:
            lines.append("- (aucune operation)")
        self._log_label.config(text="\n".join(lines))
        self._log_overlay.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
        self._log_overlay.lift()

    def _hide_log_overlay(self) -> None:
        self._log_overlay.grid_remove()

    def _organize_listbox_key(self, evt: tk.Event) -> Optional[str]:
        if self._mode != "browser":
            return None
        lower = evt.keysym.lower()
        action = self._resolve_hotkey_action(lower)
        if not self._organize_active:
            if action == "enter_organize_mode" or lower == "d":
                self._enter_organize_mode()
                return "break"
            return None
        sym = evt.keysym
        lower = sym.lower()
        action = self._resolve_hotkey_action(lower)
        if lower == "u":
            self._organize_pending_dest = None
            self._set_organize_browser_status()
            self._render_organize_highlights()
            return "break"
        if lower == "r":
            self._organize_apply_rule()
            return "break"
        if action == "organize_target_image" or lower == "i":
            self._organize_target = "image"
            self._organize_pending_dest = None
            self._snap_organize_source()
            self._update_organize_panel()
            self._set_organize_browser_status()
            self._update_mode_banner()
            return "break"
        if action == "organize_target_zip" or lower == "d":
            self._organize_target = "zip_dir"
            self._organize_pending_dest = None
            self._snap_organize_source()
            self._update_organize_panel()
            self._set_organize_browser_status()
            self._update_mode_banner()
            return "break"
        if action == "organize_op_copy" or lower == "c":
            self._organize_op = "copy"
            self._update_organize_panel()
            self._set_organize_browser_status()
            self._update_mode_banner()
            return "break"
        if action == "organize_op_move" or lower == "m":
            self._organize_op = "move"
            self._update_organize_panel()
            self._set_organize_browser_status()
            self._update_mode_banner()
            return "break"
        st = evt.state or 0
        ctrl = bool(st & 0x0004)
        shift = bool(st & 0x0001)
        if ctrl and shift:
            digit: Optional[str] = None
            if sym in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
                digit = sym
            elif sym.startswith("KP_") and len(sym) == 4 and sym[3].isdigit():
                digit = sym[3]
            if digit is not None:
                self._organize_save_shortcut(digit)
                return "break"
        if sym in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
            self._organize_jump_shortcut(sym)
            return "break"
        if sym.startswith("KP_") and len(sym) == 4 and sym[3].isdigit():
            self._organize_jump_shortcut(sym[3])
            return "break"
        return None

    def _enter_organize_mode(self) -> None:
        if self._mode != "browser":
            return
        self._organize_active = True
        self._organize_target = "zip_dir"
        self._organize_op = "move"
        self._organize_pending_dest = None
        self._snap_organize_source()
        self.title(f"[Tri] {self._base_window_title}")
        self._listbox.focus_set()
        self._update_organize_panel()
        self._set_organize_browser_status()
        self._organize_panel.grid(row=5, column=0, sticky="ew", pady=(0, 6))
        self._update_mode_banner()
        self._render_organize_highlights()

    def _leave_organize_mode(self) -> None:
        self._organize_active = False
        self._organize_pending_dest = None
        self._organize_source = None
        self.title(self._base_window_title)
        self._organize_panel.grid_remove()
        self._update_mode_banner()
        self._render_organize_highlights()

    def _organize_apply_rule(self) -> None:
        if self._organize_source is None:
            self._set_status("Selectionnez une source pour appliquer une regle.")
            return
        dest = resolve_destination(self._settings.sorting_rules, self._organize_source)
        if dest is None:
            self._set_status("Aucune regle de tri ne correspond a cette source.")
            return
        self._toast.show(f"[dry-run] regle: {self._organize_source.name} -> {dest}")
        if not messagebox.askyesno(
            "Mode tri",
            f"Appliquer la regle auto vers:\n{dest}\n\nExecuter maintenant ?",
        ):
            return
        if not dest.exists() or not dest.is_dir():
            self._set_status(f"Destination regle invalide: {dest}")
            return
        src = self._organize_source
        use_copy = self._organize_op == "copy" or not source_allows_move(src)
        final_dest = unique_destination_path(dest, src.name)
        try:
            out = execute_move_or_copy_to_final(src, final_dest, copy=use_copy)
        except OrganizeError as e:
            self._set_status(str(e))
            return
        self._add_operation_log("regle-auto", src, out, detail="sorting_rule")
        self._browser_dir = out.parent
        self._refresh_browser()
        self._organize_focus_list_after_operation(out.parent, out.name)
        self._toast.show(f"Regle auto appliquee -> {out.name}")

    def _selection_matches_organize_target(self, p: Path) -> bool:
        if self._organize_target == "image":
            return p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        if p.is_dir():
            return True
        return p.is_file() and p.suffix.lower() == ZIP_EXT

    def _snap_organize_source(self) -> None:
        if not self._organize_active or not self._browser_items:
            self._organize_source = None
            return
        p = self._browser_items[self._browser_selection]
        if self._selection_matches_organize_target(p):
            self._organize_source = p
        else:
            self._organize_source = None

    def _update_organize_panel(self) -> None:
        tgt = "images" if self._organize_target == "image" else "zip / dossiers"
        op = "copie" if self._organize_op == "copy" else "deplacement"
        move_ok = (
            self._organize_source is None
            or source_allows_move(self._organize_source)
        )
        extra = "" if move_ok else " (deplacement indisponible pour cette source: copie forcee)"
        self._organize_state_label.config(text=f"Cible: {tgt}   Operation: {op}{extra}")

    def _set_organize_browser_status(self) -> None:
        if not self._organize_active:
            return
        src = self._organize_source
        sn = src.name if src is not None else "(choisir une source valide)"
        self._set_status(
            f"[Tri] source={sn} — Right=ouvrir dossier, Entree confirme, r=regle, u=annuler, Esc=quitter"
        )
        self._update_mode_banner()

    def _organize_jump_shortcut(self, digit: str) -> None:
        raw = self._settings.folder_shortcuts.get(digit)
        if not raw:
            self._set_status(f"Aucun raccourci dossier pour la touche {digit}.")
            return
        try:
            dest = Path(raw).expanduser().resolve()
        except OSError as e:
            self._set_status(f"Raccourci invalide: {e}")
            return
        if not dest.is_dir():
            self._set_status(f"Le raccourci {digit} ne pointe pas vers un dossier: {raw}")
            return
        self._browser_dir = dest
        self._browser_selection = 0
        self._organize_pending_dest = None
        self._refresh_browser()

    def _organize_save_shortcut(self, digit: str) -> None:
        if not self._browser_dir.is_dir():
            return
        self._settings.folder_shortcuts[digit] = str(self._browser_dir.resolve())
        self._settings.clamp()
        self._schedule_save_settings()
        self._set_status(f"Raccourci dossier {digit} enregistre pour ce repertoire.")

    def _organize_focus_list_after_operation(self, dest_dir: Path, final_name: str) -> None:
        target = dest_dir / final_name
        idx: Optional[int] = None
        for i, item in enumerate(self._browser_items):
            try:
                if item.resolve() == target.resolve():
                    idx = i
                    break
            except OSError:
                if item.name == final_name:
                    idx = i
                    break
        if idx is not None:
            self._browser_selection = idx
            self._listbox.select_clear(0, tk.END)
            self._listbox.select_set(idx)
            self._listbox.see(idx)
        self._snap_organize_source()
        self._update_organize_panel()

    def _organize_handle_enter(self) -> None:
        if not self._organize_active or not self._browser_items:
            return
        p = self._browser_items[self._browser_selection]
        if not p.is_dir():
            self._set_status("Choisissez un dossier destination (Right pour entrer dans un dossier).")
            return
        if self._organize_source is None:
            self._set_status("Selectionnez une source valide (fichier image ou zip/dossier selon la cible).")
            return
        try:
            p_r = p.resolve()
            src_r = self._organize_source.resolve()
        except OSError as e:
            logger.debug("organize resolve paths: %s", e)
            self._set_status(f"Chemin invalide: {e}")
            return
        if p_r == src_r:
            self._set_status("La destination ne peut pas etre la source elle-meme.")
            return
        if p_r == src_r.parent:
            self._set_status("La source est deja dans ce dossier.")
            return
        pending = self._organize_pending_dest
        try:
            pending_same = pending is not None and pending.resolve() == p_r
        except OSError:
            pending_same = False
        if not pending_same:
            self._organize_pending_dest = p
            self._set_status(
                f"Destination: {p.name}. Appuyez encore sur Entree pour confirmer (boite de dialogue)."
            )
            return
        src = self._organize_source
        use_copy = self._organize_op == "copy" or not source_allows_move(src)
        verb = "Copier" if use_copy else "Deplacer"
        if not messagebox.askyesno(
            "Mode tri",
            f"{verb} « {src.name} » vers le dossier :\n{p}\n\nContinuer ?",
        ):
            self._organize_pending_dest = None
            self._set_organize_browser_status()
            return

        default_dest = p / src.name
        try:
            exists = default_dest.exists()
        except OSError as e:
            messagebox.showerror("Mode tri", f"Impossible de verifier la destination: {e}")
            return

        final_dest: Path
        detail = "normal"
        if exists:
            choice = prompt_name_conflict(self, src_name=src.name, dest_dir=p)
            if choice == "cancel":
                self._organize_pending_dest = None
                self._set_organize_browser_status()
                self._render_organize_highlights()
                return
            if choice == "rename":
                final_dest = unique_destination_path(p, src.name)
                detail = "rename"
            else:
                try:
                    remove_path_for_overwrite(default_dest)
                except OrganizeError as e:
                    messagebox.showerror("Mode tri", str(e))
                    self._set_status(str(e))
                    return
                final_dest = p / src.name
                detail = "overwrite"
        else:
            final_dest = default_dest

        try:
            executed = execute_move_or_copy_to_final(src, final_dest, copy=use_copy)
        except OrganizeError as e:
            messagebox.showerror("Mode tri", str(e))
            self._set_status(str(e))
            return
        self._organize_pending_dest = None
        dest_dir = executed.parent
        final_name = executed.name
        self._browser_dir = dest_dir
        self._refresh_browser()
        self._organize_focus_list_after_operation(dest_dir, final_name)
        self._set_organize_browser_status()
        self._render_organize_highlights()
        kind = "copie" if use_copy else "deplacement"
        self._add_operation_log(kind, src, executed, detail=detail)
        msg = f"{kind.capitalize()} vers {executed.name}"
        if detail == "rename":
            msg += " (renommage auto)"
        elif detail == "overwrite":
            msg += " (ecrasement)"
        self._toast.show(msg)

    def _on_close_window(self) -> None:
        if self._resize_debounce_job is not None:
            try:
                self.after_cancel(self._resize_debounce_job)
            except tk.TclError:
                pass
            self._resize_debounce_job = None
        self._flush_save_settings()
        self._close_slideshow()
        self.destroy()

    def _schedule_save_settings(self) -> None:
        if self._settings_save_job is not None:
            try:
                self.after_cancel(self._settings_save_job)
            except tk.TclError:
                pass
            self._settings_save_job = None
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
        if self._settings_save_job is not None:
            try:
                self.after_cancel(self._settings_save_job)
            except tk.TclError:
                pass
            self._settings_save_job = None
        self._persist_settings_now()

    def _is_gallery_active(self) -> bool:
        return self._mode == "slideshow" and self._slideshow_view == "gallery"

    def _open_gallery(self) -> None:
        if self._slideshow is None or self._mode != "slideshow":
            return
        self._cancel_autoplay()
        self._hide_help_overlay()
        self._gallery_saved_index = self._slideshow.index
        self._slideshow_view = "gallery"
        self._gallery.set_model(
            self._slideshow.source,
            self._slideshow.images,
            self._slideshow.index,
            self._settings.thumbnail_size_level,
        )
        self._gallery.bind_interaction()
        self._gallery_outer.lift()
        self._update_mode_banner()
        self._set_status(
            "Galerie: fleches, Page_Up defile, Entree/PageDown ouvrir, Esc annuler, +/-/* taille"
        )

    def _leave_gallery(self, commit: bool) -> None:
        if not self._is_gallery_active() or self._slideshow is None:
            return
        self._gallery.unbind_interaction()
        if commit:
            self._slideshow.index = clamp_index(
                self._gallery.get_selection(), len(self._slideshow.images)
            )
        else:
            self._slideshow.index = clamp_index(
                self._gallery_saved_index, len(self._slideshow.images)
            )
        self._slideshow_view = "image"
        self._canvas.lift()
        self._gallery_outer.lower()
        self._show_current_image()
        self._update_mode_banner()
        self._set_status(
            "Mode diaporama: Page_Up galerie, ← → images, ↑ ↓ debut/fin, ? aide, Esc navigation"
        )
        if self._autoplay:
            self._schedule_autoplay()

    def _refresh_browser(self) -> None:
        self._mode = "browser"
        self._slideshow_view = "image"
        self._gallery.unbind_interaction()
        self._gallery_outer.lower()
        self._hide_help_overlay()
        self._hide_log_overlay()
        self._canvas.lower()
        self._browser_frame.lift()

        try:
            self._path_label.config(text=str(self._browser_dir))
            items = []
            for p in self._browser_dir.iterdir():
                if p.is_dir():
                    items.append(p)
                elif p.is_file():
                    ext = p.suffix.lower()
                    if ext == ZIP_EXT or ext in SUPPORTED_EXTS:
                        items.append(p)
            items.sort(key=lambda p: (0 if p.is_dir() else 1, p.name.lower()))
            self._browser_items_all = items
            self._browser_items = self._apply_browser_filter(items)

            self._listbox.delete(0, tk.END)
            for p in self._browser_items:
                if p.is_dir():
                    self._listbox.insert(tk.END, f"[D] {p.name}")
                elif p.suffix.lower() == ZIP_EXT:
                    self._listbox.insert(tk.END, f"[Z] {p.name}")
                else:
                    self._listbox.insert(tk.END, f"[I] {p.name}")

            if not self._browser_items:
                self._browser_selection = 0
            else:
                self._browser_selection = max(0, min(self._browser_selection, len(self._browser_items) - 1))
                self._listbox.select_set(self._browser_selection)
                self._listbox.see(self._browser_selection)

            if self._organize_active:
                self._organize_panel.grid(row=5, column=0, sticky="ew", pady=(0, 6))
                self._snap_organize_source()
                self._update_organize_panel()
                self._set_organize_browser_status()
            else:
            self._set_status("Mode navigation: ↑↓ selectionner, →/Entree ouvrir, ← remonter, filtre actif, Esc quitter")
            self._update_mode_banner()
            self._render_organize_highlights()
        except (OSError, PermissionError) as e:
            self._browser_items = []
            self._browser_items_all = []
            self._listbox.delete(0, tk.END)
            self._set_status(f"Impossible de lire le dossier: {e}")
        except Exception as e:
            logger.exception("Lecture dossier navigateur")
            self._browser_items = []
            self._browser_items_all = []
            self._listbox.delete(0, tk.END)
            self._set_status(f"Impossible de lire le dossier: {e}")

    def _on_listbox_select(self, _evt=None) -> None:
        sel = self._listbox.curselection()
        if sel:
            idx = int(sel[0])
            if (
                self._organize_active
                and self._organize_pending_dest is not None
                and idx != self._browser_selection
            ):
                self._organize_pending_dest = None
            self._browser_selection = idx
        if self._organize_active:
            self._snap_organize_source()
            self._update_organize_panel()
            self._render_organize_highlights()

    def _move_selection(self, delta: int) -> None:
        if not self._browser_items:
            return
        self._browser_selection = max(0, min(self._browser_selection + delta, len(self._browser_items) - 1))
        self._listbox.select_clear(0, tk.END)
        self._listbox.select_set(self._browser_selection)
        self._listbox.see(self._browser_selection)
        self._render_organize_highlights()

    def _enter_selected(self) -> None:
        if not self._browser_items:
            return
        p = self._browser_items[self._browser_selection]
        if p.is_dir():
            self._browser_dir = p
            self._browser_selection = 0
            self._refresh_browser()
            return

        ext = p.suffix.lower()
        if ext == ZIP_EXT:
            self._open_zip(p)
        elif ext in SUPPORTED_EXTS:
            self._open_folder_or_image(p.parent, focus_file=p)

    def _go_parent(self) -> None:
        parent = self._browser_dir.parent
        if parent == self._browser_dir:
            return
        prev = self._browser_dir
        self._browser_dir = parent
        self._refresh_browser()
        try:
            idx = next(i for i, p in enumerate(self._browser_items) if p == prev)
            self._browser_selection = idx
            self._listbox.select_clear(0, tk.END)
            self._listbox.select_set(idx)
            self._listbox.see(idx)
        except StopIteration:
            pass

    def _open_folder_or_image(self, folder: Path, focus_file: Optional[Path] = None) -> None:
        src = FolderSource(folder)
        images = self._safe_list_images(src)
        if not images:
            src.close()
            self._set_status("Aucune image lisible dans ce dossier.")
            return

        idx = 0
        if focus_file is not None:
            for i, entry in enumerate(images):
                if entry.path == focus_file:
                    idx = i
                    break
        self._start_slideshow(src, images, idx)

    def _open_zip(self, zip_path: Path) -> None:
        src = ZipSource(zip_path)
        images = self._safe_list_images(src)
        if not images:
            src.close()
            self._set_status("Aucune image lisible dans ce zip (ou zip corrompu).")
            return
        self._start_slideshow(src, images, 0)

    def _safe_list_images(self, src: ImageSource) -> list[ImageEntry]:
        try:
            return src.list_images()
        except SourceError as e:
            self._set_status(str(e))
            return []
        except Exception as e:
            logger.exception("list_images inattendu")
            self._set_status(f"Erreur listing: {e}")
            return []

    def _start_slideshow(self, src: ImageSource, images: list[ImageEntry], index: int) -> None:
        if self._organize_active:
            self._leave_organize_mode()
        self._close_slideshow()
        self._slideshow = SlideshowState(source=src, images=images, index=clamp_index(index, len(images)))
        self._mode = "slideshow"
        self._slideshow_view = "image"
        self._browser_frame.lower()
        self._gallery.unbind_interaction()
        self._gallery_outer.lower()
        self._canvas.lift()
        self._update_mode_banner()
        self._set_status(
            "Mode diaporama: Page_Up galerie, ← → images, ↑ ↓ debut/fin, ? aide, Esc navigation"
        )
        self._show_current_image()
        self._schedule_autoplay()

    def _close_slideshow(self) -> None:
        self._cancel_autoplay()
        self._hide_help_overlay()
        self._hide_log_overlay()
        self._slideshow_view = "image"
        self._gallery.unbind_interaction()
        self._gallery_outer.lower()
        if self._slideshow is not None:
            self._slideshow.clear_navigation()
            try:
                self._slideshow.source.close()
            except OSError as e:
                logger.warning("Fermeture source diaporama: %s", e)
        self._slideshow = None
        self._current_photo = None
        self._current_image_info = None
        self._canvas.delete("all")
        self._update_mode_banner()

    def _show_current_image(self) -> None:
        if self._slideshow is None:
            return

        total = len(self._slideshow.images)
        if total == 0:
            self._end_slideshow_to_browser()
            return

        entry = self._slideshow.current_entry()
        if entry is None:
            self._end_slideshow_to_browser()
            return

        img = None
        last_error = None
        start_idx = self._slideshow.index

        while True:
            try:
                img = self._slideshow.source.open_image(entry)
                break
            except SourceError as e:
                last_error = str(e)
            except (OSError, ValueError, RuntimeError) as e:
                last_error = f"Erreur lecture image: {e}"
            except Exception as e:
                logger.exception("open_image inattendu")
                last_error = f"Erreur lecture image: {e}"

            if self._slideshow.index >= total - 1:
                break
            self._slideshow.index += 1
            entry = self._slideshow.images[self._slideshow.index]

        if img is None:
            if last_error:
                self._set_status(last_error)
            self._end_slideshow_to_browser()
            return

        self._render_image_fit(img)
        self._current_image_info = self._build_current_image_info(entry, img)
        self._apply_initial_geometry(img)
        if self._help_visible():
            self._help_label.config(text=self._help_text_with_context())

        name = entry.display_name()
        pos = self._slideshow.index + 1
        extra = f" - (skip: {last_error})" if last_error and start_idx != self._slideshow.index else ""
        key = f"{entry.path}|{entry.member or ''}"
        review = self._review_labels.get(key, "-")
        self._set_status(f"{pos}/{total} - {name}{extra} [review={review}]")

    def _build_current_image_info(self, entry: ImageEntry, img: Image.Image) -> dict[str, str]:
        info = self._slideshow.source.describe_entry(entry) if self._slideshow is not None else {}
        info["size"] = f"{img.width}x{img.height}"
        return info

    def _render_image_fit(self, img: Image.Image) -> None:
        cw = max(1, self._canvas.winfo_width())
        ch = max(1, self._canvas.winfo_height())

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
        self._current_photo = photo
        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, image=photo, anchor="center")

    def _set_initial_window_geometry(self) -> None:
        if self._initial_geometry_applied:
            return
        screen_w = max(1, self.winfo_screenwidth())
        screen_h = max(1, self.winfo_screenheight())
        target_w = min(max(960, int(screen_w * 0.78)), int(screen_w * 0.92))
        target_h = min(max(700, int(screen_h * 0.78)), int(screen_h * 0.92))
        pos_x = max(0, (screen_w - target_w) // 2)
        pos_y = max(0, (screen_h - target_h) // 3)
        self.geometry(f"{target_w}x{target_h}+{pos_x}+{pos_y}")
        self._initial_geometry_applied = True

    def _apply_initial_geometry(self, img: Image.Image) -> None:
        if self._initial_geometry_applied:
            return
        screen_w = max(1, self.winfo_screenwidth())
        screen_h = max(1, self.winfo_screenheight())
        target_w = min(max(img.width + 80, 900), int(screen_w * 0.9))
        target_h = min(max(img.height + 140, 650), int(screen_h * 0.9))
        pos_x = max(0, (screen_w - target_w) // 2)
        pos_y = max(0, (screen_h - target_h) // 3)
        self.geometry(f"{target_w}x{target_h}+{pos_x}+{pos_y}")
        self._initial_geometry_applied = True

    def _help_text_with_context(self) -> str:
        info = self._current_image_info or {}
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
        if self._mode != "slideshow":
            return
        self._hide_log_overlay()
        self._help_label.config(text=self._help_text_with_context())
        self._help_overlay.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
        self._help_overlay.lift()

    def _hide_help_overlay(self) -> None:
        self._help_overlay.grid_remove()

    def _help_visible(self) -> bool:
        return bool(self._help_overlay.winfo_ismapped())

    def _dismiss_help_on_command(self) -> bool:
        if self._help_visible():
            self._hide_help_overlay()
            return True
        if bool(self._log_overlay.winfo_ismapped()):
            self._hide_log_overlay()
            return True
        return False

    def _end_slideshow_to_browser(self) -> None:
        container = None
        if self._slideshow is not None:
            container = self._slideshow.source.container_dir()
        self._close_slideshow()

        if container and container.exists() and container.is_dir():
            self._browser_dir = container
        self._autoplay = False
        self._refresh_browser()

    def prev_action(self) -> None:
        if self._is_gallery_active() and self._slideshow is not None:
            cols = self._gallery.column_count
            total = len(self._slideshow.images)
            idx = move_gallery_index(self._gallery.get_selection(), total, cols, 0, -1)
            self._gallery.set_selection(idx)
            return
        if self._mode == "slideshow":
            self._queue_navigation("prev")
        else:
            self._go_parent()

    def next_action(self) -> None:
        if self._is_gallery_active() and self._slideshow is not None:
            cols = self._gallery.column_count
            total = len(self._slideshow.images)
            idx = move_gallery_index(self._gallery.get_selection(), total, cols, 0, 1)
            self._gallery.set_selection(idx)
            return
        if self._mode == "slideshow":
            self._queue_navigation("next")
        else:
            self._enter_selected()

    def _queue_navigation(self, command: NavigationCommand) -> None:
        if self._slideshow is None:
            return
        if not self._slideshow.enqueue_navigation(command):
            return
        if not self._nav_drain_scheduled:
            self._nav_drain_scheduled = True
            self.after_idle(self._drain_navigation_queue)

    def _drain_navigation_queue(self) -> None:
        self._nav_drain_scheduled = False
        if self._slideshow is None:
            return
        command = self._slideshow.pop_navigation()
        if command is None:
            return
        result = apply_navigation(self._slideshow, command)
        if result == "close":
            self._end_slideshow_to_browser()
            return
        if result == "show":
            self._show_current_image()
        if self._slideshow is not None and self._slideshow.pending_navigation:
            self._nav_drain_scheduled = True
            self.after(1, self._drain_navigation_queue)

    def _on_left(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        if self._is_gallery_active() and self._slideshow is not None:
            cols = self._gallery.column_count
            total = len(self._slideshow.images)
            idx = move_gallery_index(self._gallery.get_selection(), total, cols, 0, -1)
            self._gallery.set_selection(idx)
            return "break"
        if self._mode == "slideshow":
            self._queue_navigation("prev")
        else:
            self._go_parent()
        return None

    def _on_right(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        if self._is_gallery_active() and self._slideshow is not None:
            cols = self._gallery.column_count
            total = len(self._slideshow.images)
            idx = move_gallery_index(self._gallery.get_selection(), total, cols, 0, 1)
            self._gallery.set_selection(idx)
            return "break"
        if self._mode == "slideshow":
            self._queue_navigation("next")
        else:
            self._enter_selected()
        return None

    def _on_up(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        if self._is_gallery_active() and self._slideshow is not None:
            cols = self._gallery.column_count
            total = len(self._slideshow.images)
            idx = move_gallery_index(self._gallery.get_selection(), total, cols, -1, 0)
            self._gallery.set_selection(idx)
            return "break"
        if self._mode == "browser":
            self._move_selection(-1)
        elif self._mode == "slideshow":
            self._queue_navigation("first")
        return None

    def _on_down(self, _evt=None):
        if self._dismiss_help_on_command():
            return "break"
        if self._is_gallery_active() and self._slideshow is not None:
            cols = self._gallery.column_count
            total = len(self._slideshow.images)
            idx = move_gallery_index(self._gallery.get_selection(), total, cols, 1, 0)
            self._gallery.set_selection(idx)
            return "break"
        if self._mode == "browser":
            self._move_selection(+1)
        elif self._mode == "slideshow":
            self._queue_navigation("last")
        return None

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
        if self._dismiss_help_on_command():
            return "break"
        if self._mode == "browser":
            self._go_parent()
        return None

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
            self.destroy()
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

    def _on_resize(self, _evt=None) -> None:
        if self._resize_debounce_job is not None:
            try:
                self.after_cancel(self._resize_debounce_job)
            except tk.TclError:
                pass
            self._resize_debounce_job = None
        self._resize_debounce_job = self.after(300, self._apply_slideshow_resize)

    def _apply_slideshow_resize(self) -> None:
        self._resize_debounce_job = None
        if (
            self._mode != "slideshow"
            or self._slideshow_view != "image"
            or self._slideshow is None
        ):
            return
        try:
            entry = self._slideshow.current_entry()
            if entry is None:
                return
            img = self._slideshow.source.open_image(entry)
            self._render_image_fit(img)
        except SourceError as e:
            self._set_status(str(e))
        except (OSError, ValueError) as e:
            logger.warning("Rafraichissement image au redimensionnement: %s", e)

    def _set_status(self, text: str) -> None:
        self._status.config(text=text)

    def _cancel_autoplay(self) -> None:
        if self._autoplay_job is not None:
            try:
                self.after_cancel(self._autoplay_job)
            except tk.TclError:
                pass
            self._autoplay_job = None

    def _schedule_autoplay(self) -> None:
        self._cancel_autoplay()
        if not self._autoplay or self._mode != "slideshow":
            return
        self._autoplay_job = self.after(self._autoplay_ms, self._autoplay_tick)

    def _autoplay_tick(self) -> None:
        self._autoplay_job = None
        if not self._autoplay or self._mode != "slideshow":
            return
        if self._slideshow is None:
            self._autoplay = False
            return
        result = apply_navigation(self._slideshow, "next")
        if result == "close":
            self._autoplay = False
            self._end_slideshow_to_browser()
            return
        if result == "show":
            self._show_current_image()
        self._schedule_autoplay()

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
        self._autoplay_ms = max(250, self._autoplay_ms - 250)
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
        self._autoplay_ms = min(20000, self._autoplay_ms + 250)
        if self._autoplay:
            self._schedule_autoplay()
        self._set_status(f"Vitesse auto: {self._autoplay_ms} ms")
        return None

    def _on_help(self, _evt=None) -> str:
        if self._mode != "slideshow":
            return "break"
        if self._help_visible():
            self._hide_help_overlay()
        else:
            self._show_help_overlay()
        return "break"

    def _on_log_overlay(self, _evt=None):
        if self._mode != "browser":
            return None
        if bool(self._log_overlay.winfo_ismapped()):
            self._hide_log_overlay()
        else:
            self._show_operation_log_overlay()
        return "break"

    def _set_review_label(self, label: str) -> None:
        if self._mode != "slideshow" or self._slideshow is None:
            return
        entry = self._slideshow.current_entry()
        if entry is None:
            return
        key = f"{entry.path}|{entry.member or ''}"
        self._review_labels[key] = label
        self._toast.show(f"Review: {entry.display_name()} -> {label}")
        self._show_current_image()

    def _on_review_keep(self, _evt=None):
        self._set_review_label("garder")
        return "break" if self._mode == "slideshow" else None

    def _on_review_drop(self, _evt=None):
        self._set_review_label("jeter")
        return "break" if self._mode == "slideshow" else None

    def _on_review_todo(self, _evt=None):
        self._set_review_label("a_trier")
        return "break" if self._mode == "slideshow" else None

    def _on_review_export(self, _evt=None):
        if self._mode != "slideshow":
            return None
        out_json = self._cwd / "logs" / "review_labels.json"
        out_csv = self._cwd / "logs" / "review_labels.csv"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        payload = [{"entry": k, "label": v} for k, v in sorted(self._review_labels.items())]
        out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        csv_lines = ["entry,label"] + [f"\"{k}\",\"{v}\"" for k, v in sorted(self._review_labels.items())]
        out_csv.write_text("\n".join(csv_lines) + "\n", encoding="utf-8")
        self._toast.show(f"Export review: {out_json.name} / {out_csv.name}")
        return "break"

    def _on_open_hotkeys_dialog(self, _evt=None):
        win = tk.Toplevel(self)
        win.title("Raccourcis")
        win.transient(self.winfo_toplevel())
        win.grab_set()
        outer = ttk.Frame(win, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        rows: dict[str, ttk.Entry] = {}
        for r, (action, default_key) in enumerate(DEFAULT_HOTKEYS.items()):
            ttk.Label(outer, text=action).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=2)
            ent = ttk.Entry(outer, width=8)
            ent.insert(0, self._settings.hotkeys.get(action, default_key))
            ent.grid(row=r, column=1, sticky="w", pady=2)
            rows[action] = ent

        def save_hotkeys() -> None:
            for action, ent in rows.items():
                key = ent.get().strip().lower()
                if key:
                    self._settings.hotkeys[action] = key
            self._settings.clamp()
            self._schedule_save_settings()
            self._toast.show("Raccourcis mis a jour")
            win.destroy()

        ttk.Button(outer, text="Enregistrer", command=save_hotkeys).grid(
            row=len(rows), column=1, sticky="e", pady=(8, 0)
        )
        self.wait_window(win)
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
