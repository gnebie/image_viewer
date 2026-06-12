"""Organize-mode and review-label mixin for App."""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import messagebox

from .name_conflict_dialog import prompt_name_conflict
from .operation_log import OperationRecord
from .organize_ops import (
    OrganizeError,
    execute_move_or_copy_to_final,
    remove_path_for_overwrite,
    source_allows_move,
    unique_destination_path,
)
from .sorting_rules import resolve_destination
from .sources import SUPPORTED_EXTS, ZIP_EXT

logger = logging.getLogger(__name__)


class OrganizeMixin:
    """Organize-mode, operation-log, and review-label methods mixed into App."""

    # ------------------------------------------------------------------ #
    # Organize highlights / hotkey resolution                             #
    # ------------------------------------------------------------------ #

    def _render_organize_highlights(self) -> None:
        for idx in range(self._listbox.size()):  # type: ignore[attr-defined]
            try:
                self._listbox.itemconfig(idx, bg="", fg="")  # type: ignore[attr-defined]
            except tk.TclError:
                pass
        if not self._organize_active:  # type: ignore[attr-defined]
            return
        for i, item in enumerate(self._browser_items):  # type: ignore[attr-defined]
            if self._organize_source is not None and item == self._organize_source:  # type: ignore[attr-defined]
                self._listbox.itemconfig(i, bg="#2d4f7a", fg="white")  # type: ignore[attr-defined]
            if self._organize_pending_dest is not None and item == self._organize_pending_dest:  # type: ignore[attr-defined]
                self._listbox.itemconfig(i, bg="#6e5c1f", fg="white")  # type: ignore[attr-defined]

    def _resolve_hotkey_action(self, lower: str) -> str | None:
        for action, key in self._settings.hotkeys.items():  # type: ignore[attr-defined]
            if key == lower:
                return action
        return None

    # ------------------------------------------------------------------ #
    # Operation log overlay                                               #
    # ------------------------------------------------------------------ #

    def _add_operation_log(self, kind: str, src: Path, dest: Path, detail: str = "") -> None:
        self._operation_log.add(OperationRecord(kind=kind, src=str(src), dest=str(dest), detail=detail))  # type: ignore[attr-defined]

    def _show_operation_log_overlay(self) -> None:
        lines = ["Historique operations (plus recent en haut):"]
        for rec in self._operation_log.items():  # type: ignore[attr-defined]
            suffix = f" ({rec.detail})" if rec.detail else ""
            lines.append(f"- {rec.kind}: {rec.src} -> {rec.dest}{suffix}")
        if len(lines) == 1:
            lines.append("- (aucune operation)")
        self._log_label.config(text="\n".join(lines))  # type: ignore[attr-defined]
        self._log_overlay.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)  # type: ignore[attr-defined]
        self._log_overlay.lift()  # type: ignore[attr-defined]

    def _hide_log_overlay(self) -> None:
        self._log_overlay.grid_remove()  # type: ignore[attr-defined]

    def _on_log_overlay(self, _evt=None):
        if self._text_input_focused():  # type: ignore[attr-defined]
            return None
        if self._mode != "browser":  # type: ignore[attr-defined]
            return None
        if bool(self._log_overlay.winfo_ismapped()):  # type: ignore[attr-defined]
            self._hide_log_overlay()
        else:
            self._show_operation_log_overlay()
        return "break"

    # ------------------------------------------------------------------ #
    # Organize mode entry / exit                                          #
    # ------------------------------------------------------------------ #

    def _organize_listbox_key(self, evt: tk.Event) -> Optional[str]:
        if self._mode != "browser":  # type: ignore[attr-defined]
            return None
        lower = evt.keysym.lower()
        action = self._resolve_hotkey_action(lower)
        if not self._organize_active:  # type: ignore[attr-defined]
            if action == "enter_organize_mode":
                self._enter_organize_mode()
                return "break"
            return None
        sym = evt.keysym
        lower = sym.lower()
        action = self._resolve_hotkey_action(lower)
        if lower == "u":
            self._organize_pending_dest = None  # type: ignore[attr-defined]
            self._set_organize_browser_status()
            self._render_organize_highlights()
            return "break"
        if lower == "r":
            self._organize_apply_rule()
            return "break"
        if action == "organize_target_image":
            self._organize_target = "image"  # type: ignore[attr-defined]
            self._organize_pending_dest = None  # type: ignore[attr-defined]
            self._snap_organize_source()
            self._update_organize_panel()
            self._set_organize_browser_status()
            self._update_mode_banner()  # type: ignore[attr-defined]
            return "break"
        if action == "organize_target_zip":
            self._organize_target = "zip_dir"  # type: ignore[attr-defined]
            self._organize_pending_dest = None  # type: ignore[attr-defined]
            self._snap_organize_source()
            self._update_organize_panel()
            self._set_organize_browser_status()
            self._update_mode_banner()  # type: ignore[attr-defined]
            return "break"
        if action == "organize_op_copy":
            self._organize_op = "copy"  # type: ignore[attr-defined]
            self._update_organize_panel()
            self._set_organize_browser_status()
            self._update_mode_banner()  # type: ignore[attr-defined]
            return "break"
        if action == "organize_op_move":
            self._organize_op = "move"  # type: ignore[attr-defined]
            self._update_organize_panel()
            self._set_organize_browser_status()
            self._update_mode_banner()  # type: ignore[attr-defined]
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

    def _update_organize_help_panel(self) -> None:
        hk = self._settings.hotkeys  # type: ignore[attr-defined]
        d = hk.get("enter_organize_mode", "d")
        i = hk.get("organize_target_image", "i")
        m = hk.get("organize_op_move", "m")
        c = hk.get("organize_op_copy", "c")
        self._organize_help.config(  # type: ignore[attr-defined]
            text=(
                f"{d} = cible zip/dossier   {i} = cible images   {m} = deplacer   {c} = copier\n"
                "r = regle auto   u = annuler destination   0-9 = raccourci dossier\n"
                "Ctrl+Shift+chiffre = enregistrer raccourci ici\n"
                "Entree sur dossier = armer puis confirmer   Right = entrer dossier   Esc = quitter"
            )
        )

    def _enter_organize_mode(self) -> None:
        if self._mode != "browser":  # type: ignore[attr-defined]
            return
        self._organize_active = True  # type: ignore[attr-defined]
        self._organize_target = "zip_dir"  # type: ignore[attr-defined]
        self._organize_op = "move"  # type: ignore[attr-defined]
        self._organize_pending_dest = None  # type: ignore[attr-defined]
        self._snap_organize_source()
        self.title(f"[Tri] {self._base_window_title}")  # type: ignore[attr-defined]
        self._listbox.focus_set()  # type: ignore[attr-defined]
        self._update_organize_help_panel()
        self._update_organize_panel()
        self._set_organize_browser_status()
        self._update_shortcuts_display()
        self._organize_panel.grid(row=5, column=0, sticky="ew", pady=(0, 6))  # type: ignore[attr-defined]
        self._update_mode_banner()  # type: ignore[attr-defined]
        self._render_organize_highlights()

    def _leave_organize_mode(self) -> None:
        self._organize_active = False  # type: ignore[attr-defined]
        self._organize_pending_dest = None  # type: ignore[attr-defined]
        self._organize_source = None  # type: ignore[attr-defined]
        self.title(f"{self._browser_dir.name} — {self._base_window_title}")  # type: ignore[attr-defined]
        self._organize_panel.grid_remove()  # type: ignore[attr-defined]
        self._update_mode_banner()  # type: ignore[attr-defined]
        self._render_organize_highlights()

    # ------------------------------------------------------------------ #
    # Organize state helpers                                              #
    # ------------------------------------------------------------------ #

    def _organize_apply_rule(self) -> None:
        if self._organize_source is None:  # type: ignore[attr-defined]
            self._set_status("Selectionnez une source pour appliquer une regle.")  # type: ignore[attr-defined]
            return
        dest = resolve_destination(self._settings.sorting_rules, self._organize_source)  # type: ignore[attr-defined]
        if dest is None:
            self._set_status("Aucune regle de tri ne correspond a cette source.")  # type: ignore[attr-defined]
            return
        if not messagebox.askyesno(
            "Mode tri",
            f"Regle auto: {self._organize_source.name} -> {dest}\n\nAppliquer maintenant ?",  # type: ignore[attr-defined]
        ):
            return
        if not dest.exists() or not dest.is_dir():
            self._set_status(f"Destination regle invalide: {dest}")  # type: ignore[attr-defined]
            return
        src = self._organize_source  # type: ignore[attr-defined]
        use_copy = self._organize_op == "copy" or not source_allows_move(src)  # type: ignore[attr-defined]
        final_dest = unique_destination_path(dest, src.name)
        try:
            out = execute_move_or_copy_to_final(src, final_dest, copy=use_copy)
        except OrganizeError as e:
            self._set_status(str(e))  # type: ignore[attr-defined]
            return
        self._add_operation_log("regle-auto", src, out, detail="sorting_rule")
        self._browser_dir = out.parent  # type: ignore[attr-defined]
        self._refresh_browser()  # type: ignore[attr-defined]
        self._organize_focus_list_after_operation(out.parent, out.name)
        self._toast.show(f"Regle auto appliquee -> {out.name}")  # type: ignore[attr-defined]

    def _selection_matches_organize_target(self, p: Path) -> bool:
        if self._organize_target == "image":  # type: ignore[attr-defined]
            return p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        if p.is_dir():
            return True
        return p.is_file() and p.suffix.lower() == ZIP_EXT

    def _snap_organize_source(self) -> None:
        if not self._organize_active or not self._browser_items:  # type: ignore[attr-defined]
            self._organize_source = None  # type: ignore[attr-defined]
            return
        p = self._browser_items[self._browser_selection]  # type: ignore[attr-defined]
        if self._selection_matches_organize_target(p):
            self._organize_source = p  # type: ignore[attr-defined]
        else:
            self._organize_source = None  # type: ignore[attr-defined]

    def _update_organize_panel(self) -> None:
        tgt = "images" if self._organize_target == "image" else "zip / dossiers"  # type: ignore[attr-defined]
        op = "copie" if self._organize_op == "copy" else "deplacement"  # type: ignore[attr-defined]
        move_ok = (
            self._organize_source is None  # type: ignore[attr-defined]
            or source_allows_move(self._organize_source)  # type: ignore[attr-defined]
        )
        extra = "" if move_ok else " (deplacement indisponible pour cette source: copie forcee)"
        self._organize_state_label.config(text=f"Cible: {tgt}   Operation: {op}{extra}")  # type: ignore[attr-defined]

    def _set_organize_browser_status(self) -> None:
        if not self._organize_active:  # type: ignore[attr-defined]
            return
        src = self._organize_source  # type: ignore[attr-defined]
        sn = src.name if src is not None else "(choisir une source valide)"
        self._set_status(  # type: ignore[attr-defined]
            f"[Tri] source={sn} — Right=ouvrir dossier, Entree confirme, r=regle, u=annuler, Esc=quitter"
        )
        self._update_mode_banner()  # type: ignore[attr-defined]

    def _organize_jump_shortcut(self, digit: str) -> None:
        raw = self._settings.folder_shortcuts.get(digit)  # type: ignore[attr-defined]
        if not raw:
            self._set_status(f"Aucun raccourci dossier pour la touche {digit}.")  # type: ignore[attr-defined]
            return
        try:
            dest = Path(raw).expanduser().resolve()
        except OSError as e:
            self._set_status(f"Raccourci invalide: {e}")  # type: ignore[attr-defined]
            return
        if not dest.is_dir():
            self._set_status(f"Le raccourci {digit} ne pointe pas vers un dossier: {raw}")  # type: ignore[attr-defined]
            return
        self._browser_dir = dest  # type: ignore[attr-defined]
        self._browser_selection = 0  # type: ignore[attr-defined]
        self._organize_pending_dest = None  # type: ignore[attr-defined]
        self._refresh_browser()  # type: ignore[attr-defined]

    def _organize_save_shortcut(self, digit: str) -> None:
        if not self._browser_dir.is_dir():  # type: ignore[attr-defined]
            return
        self._settings.folder_shortcuts[digit] = str(self._browser_dir.resolve())  # type: ignore[attr-defined]
        self._settings.clamp()  # type: ignore[attr-defined]
        self._schedule_save_settings()  # type: ignore[attr-defined]
        self._set_status(f"Raccourci dossier {digit} enregistre pour ce repertoire.")  # type: ignore[attr-defined]
        self._update_shortcuts_display()

    def _update_shortcuts_display(self) -> None:
        shortcuts = self._settings.folder_shortcuts  # type: ignore[attr-defined]
        if not shortcuts:
            self._shortcuts_label.config(text="Raccourcis: aucun (Ctrl+Shift+chiffre pour enregistrer)")  # type: ignore[attr-defined]
            return
        parts = [f"{k}: {Path(v).name}" for k, v in sorted(shortcuts.items())]
        self._shortcuts_label.config(text="Raccourcis: " + "  ".join(parts))  # type: ignore[attr-defined]

    def _organize_focus_list_after_operation(self, dest_dir: Path, final_name: str) -> None:
        target = dest_dir / final_name
        idx: Optional[int] = None
        for i, item in enumerate(self._browser_items):  # type: ignore[attr-defined]
            try:
                if item.resolve() == target.resolve():
                    idx = i
                    break
            except OSError:
                if item.name == final_name:
                    idx = i
                    break
        if idx is not None:
            self._browser_selection = idx  # type: ignore[attr-defined]
            self._apply_listbox_selection()  # type: ignore[attr-defined]
        self._snap_organize_source()
        self._update_organize_panel()

    def _organize_handle_enter(self) -> None:
        if not self._organize_active or not self._browser_items:  # type: ignore[attr-defined]
            return
        p = self._browser_items[self._browser_selection]  # type: ignore[attr-defined]
        if not p.is_dir():
            self._set_status("Choisissez un dossier destination (Right pour entrer dans un dossier).")  # type: ignore[attr-defined]
            return
        if self._organize_source is None:  # type: ignore[attr-defined]
            self._set_status("Selectionnez une source valide (fichier image ou zip/dossier selon la cible).")  # type: ignore[attr-defined]
            return
        try:
            p_r = p.resolve()
            src_r = self._organize_source.resolve()  # type: ignore[attr-defined]
        except OSError as e:
            logger.debug("organize resolve paths: %s", e)
            self._set_status(f"Chemin invalide: {e}")  # type: ignore[attr-defined]
            return
        if p_r == src_r:
            self._set_status("La destination ne peut pas etre la source elle-meme.")  # type: ignore[attr-defined]
            return
        if p_r == src_r.parent:
            self._set_status("La source est deja dans ce dossier.")  # type: ignore[attr-defined]
            return
        pending = self._organize_pending_dest  # type: ignore[attr-defined]
        try:
            pending_same = pending is not None and pending.resolve() == p_r
        except OSError:
            pending_same = False
        if not pending_same:
            self._organize_pending_dest = p  # type: ignore[attr-defined]
            self._set_status(  # type: ignore[attr-defined]
                f"Destination: {p.name}. Appuyez encore sur Entree pour confirmer (boite de dialogue)."
            )
            return
        src = self._organize_source  # type: ignore[attr-defined]
        use_copy = self._organize_op == "copy" or not source_allows_move(src)  # type: ignore[attr-defined]
        verb = "Copier" if use_copy else "Deplacer"
        if not messagebox.askyesno(
            "Mode tri",
            f"{verb} « {src.name} » vers le dossier :\n{p}\n\nContinuer ?",
        ):
            self._organize_pending_dest = None  # type: ignore[attr-defined]
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
            choice = prompt_name_conflict(self, src_name=src.name, dest_dir=p)  # type: ignore[arg-type]
            if choice == "cancel":
                self._organize_pending_dest = None  # type: ignore[attr-defined]
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
                    self._set_status(str(e))  # type: ignore[attr-defined]
                    return
                final_dest = p / src.name
                detail = "overwrite"
        else:
            final_dest = default_dest
        try:
            executed = execute_move_or_copy_to_final(src, final_dest, copy=use_copy)
        except OrganizeError as e:
            messagebox.showerror("Mode tri", str(e))
            self._set_status(str(e))  # type: ignore[attr-defined]
            return
        self._organize_pending_dest = None  # type: ignore[attr-defined]
        dest_dir = executed.parent
        final_name = executed.name
        self._browser_dir = dest_dir  # type: ignore[attr-defined]
        self._refresh_browser()  # type: ignore[attr-defined]
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
        self._toast.show(msg)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    # Review labels                                                       #
    # ------------------------------------------------------------------ #

    def _set_review_label(self, label: str) -> None:
        if self._mode != "slideshow" or self._slideshow is None:  # type: ignore[attr-defined]
            return
        entry = self._slideshow.current_entry()  # type: ignore[attr-defined]
        if entry is None:
            return
        key = f"{entry.path}|{entry.member or ''}"
        self._review_labels[key] = label  # type: ignore[attr-defined]
        self._toast.show(f"Review: {entry.display_name()} -> {label}")  # type: ignore[attr-defined]
        self._autosave_review_labels()
        self._show_current_image()  # type: ignore[attr-defined]

    def _autosave_review_labels(self) -> None:
        if not self._review_labels:  # type: ignore[attr-defined]
            return
        try:
            out_json = self._cwd / "logs" / "review_labels.json"  # type: ignore[attr-defined]
            out_json.parent.mkdir(parents=True, exist_ok=True)
            payload = [{"entry": k, "label": v} for k, v in sorted(self._review_labels.items())]  # type: ignore[attr-defined]
            out_json.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        except OSError as e:
            logger.warning("Autosave review labels: %s", e)

    def _on_review_keep(self, _evt=None):
        if self._text_input_focused():  # type: ignore[attr-defined]
            return None
        if self._mode != "slideshow":  # type: ignore[attr-defined]
            self._set_status("Review disponible uniquement en mode diaporama.")  # type: ignore[attr-defined]
            return None
        self._set_review_label("garder")
        return "break"

    def _on_review_drop(self, _evt=None):
        if self._text_input_focused():  # type: ignore[attr-defined]
            return None
        if self._mode != "slideshow":  # type: ignore[attr-defined]
            self._set_status("Review disponible uniquement en mode diaporama.")  # type: ignore[attr-defined]
            return None
        self._set_review_label("jeter")
        return "break"

    def _on_review_todo(self, _evt=None):
        if self._text_input_focused():  # type: ignore[attr-defined]
            return None
        if self._mode != "slideshow":  # type: ignore[attr-defined]
            self._set_status("Review disponible uniquement en mode diaporama.")  # type: ignore[attr-defined]
            return None
        self._set_review_label("a_trier")
        return "break"

    def _on_review_export(self, _evt=None):
        if self._text_input_focused():  # type: ignore[attr-defined]
            return None
        if self._mode != "slideshow":  # type: ignore[attr-defined]
            return None
        out_json = self._cwd / "logs" / "review_labels.json"  # type: ignore[attr-defined]
        out_csv = self._cwd / "logs" / "review_labels.csv"  # type: ignore[attr-defined]
        out_json.parent.mkdir(parents=True, exist_ok=True)
        payload = [{"entry": k, "label": v} for k, v in sorted(self._review_labels.items())]  # type: ignore[attr-defined]
        out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["entry", "label"])
        writer.writerows(sorted(self._review_labels.items()))  # type: ignore[attr-defined]
        out_csv.write_text(buf.getvalue(), encoding="utf-8")
        try:
            display = str(out_json.relative_to(Path.cwd()))
        except ValueError:
            display = str(out_json)
        self._toast.show(f"Export review: {display} / {out_csv.name}")  # type: ignore[attr-defined]
        return "break"
