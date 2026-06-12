"""Organize-mode and review-label mixin for App."""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Optional

import tkinter as tk

from ..widgets.name_conflict_dialog import prompt_name_conflict
from ...domain.operation_log import OperationRecord
from ...domain.organize_ops import (
    OrganizeError,
    execute_move_or_copy_to_final,
    remove_path_for_overwrite,
    source_allows_move,
    unique_destination_path,
)
from ...domain.sorting_rules import resolve_destination

logger = logging.getLogger(__name__)


class OrganizeMixin:
    """Organize-mode, operation-log, and review-label methods mixed into App."""

    # ------------------------------------------------------------------ #
    # Highlights / hotkey resolution                                       #
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
                self._listbox.itemconfig(i, bg="#1a4a6e", fg="white")  # type: ignore[attr-defined]

    def _resolve_hotkey_action(self, lower: str) -> str | None:
        for action, key in self._settings.hotkeys.items():  # type: ignore[attr-defined]
            if key == lower:
                return action
        return None

    # ------------------------------------------------------------------ #
    # Operation log overlay                                               #
    # ------------------------------------------------------------------ #

    def _add_operation_log(self, kind: str, src: Path, dest: Path, detail: str = "") -> None:
        self._operation_log.add(  # type: ignore[attr-defined]
            OperationRecord(kind=kind, src=str(src), dest=str(dest), detail=detail)
        )

    def _show_operation_log_overlay(self) -> None:
        lines = ["Historique opérations (plus récent en haut) :"]
        for rec in self._operation_log.items():  # type: ignore[attr-defined]
            suffix = f" ({rec.detail})" if rec.detail else ""
            lines.append(f"- {rec.kind}: {rec.src} → {rec.dest}{suffix}")
        if len(lines) == 1:
            lines.append("- (aucune opération)")
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

    def _enter_organize_mode(self) -> None:
        if self._mode != "browser":  # type: ignore[attr-defined]
            return
        self._organize_active = True  # type: ignore[attr-defined]
        self._organize_op = "move"  # type: ignore[attr-defined]
        self._organize_source = None  # type: ignore[attr-defined]
        self._snap_organize_source()
        self._organize_dest_panel.set_op("move")  # type: ignore[attr-defined]
        self._organize_dest_panel.update_shortcuts(self._settings.folder_shortcuts)  # type: ignore[attr-defined]
        self._update_dest_panel_source()
        self._organize_dest_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))  # type: ignore[attr-defined]
        self._content.columnconfigure(1, weight=0, minsize=290)  # type: ignore[attr-defined]
        self.title(f"[Tri] {self._browser_dir.name} — {self._base_window_title}")  # type: ignore[attr-defined]
        self._listbox.focus_set()  # type: ignore[attr-defined]
        self._update_mode_banner()  # type: ignore[attr-defined]
        self._render_organize_highlights()
        self._set_status(  # type: ignore[attr-defined]
            "Mode Tri : 1-9 raccourcis, → entrer dossier, ↵ envoyer ici, r règle auto, Esc quitter"
        )

    def _leave_organize_mode(self) -> None:
        self._organize_active = False  # type: ignore[attr-defined]
        self._organize_source = None  # type: ignore[attr-defined]
        self._organize_dest_panel.grid_remove()  # type: ignore[attr-defined]
        self._content.columnconfigure(1, weight=0, minsize=0)  # type: ignore[attr-defined]
        self.title(f"{self._browser_dir.name} — {self._base_window_title}")  # type: ignore[attr-defined]
        self._update_mode_banner()  # type: ignore[attr-defined]
        self._render_organize_highlights()

    # ------------------------------------------------------------------ #
    # Source snapping                                                      #
    # ------------------------------------------------------------------ #

    def _snap_organize_source(self) -> None:
        if not self._organize_active or not self._browser_items:  # type: ignore[attr-defined]
            self._organize_source = None  # type: ignore[attr-defined]
            return
        p = self._browser_items[self._browser_selection]  # type: ignore[attr-defined]
        self._organize_source = p if p.is_file() else None  # type: ignore[attr-defined]

    def _update_dest_panel_source(self) -> None:
        src = self._organize_source  # type: ignore[attr-defined]
        name = src.name if src is not None else "— sélectionnez un fichier —"
        self._organize_dest_panel.set_source(name)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    # Execute operation                                                    #
    # ------------------------------------------------------------------ #

    def _execute_to_dir(self, dest_dir: Path) -> None:
        """Move or copy the current source file into dest_dir."""
        src = self._organize_source  # type: ignore[attr-defined]
        if src is None:
            self._set_status("Sélectionnez un fichier source (pas un dossier).")  # type: ignore[attr-defined]
            return
        if not dest_dir.is_dir():
            self._set_status(f"Destination invalide : {dest_dir}")  # type: ignore[attr-defined]
            return
        try:
            dest_r = dest_dir.resolve()
            src_r = src.resolve()
        except OSError as e:
            self._set_status(f"Chemin invalide : {e}")  # type: ignore[attr-defined]
            return
        if dest_r == src_r.parent:
            self._set_status(f"'{src.name}' est déjà dans ce dossier.")  # type: ignore[attr-defined]
            return

        use_copy = self._organize_op == "copy" or not source_allows_move(src)  # type: ignore[attr-defined]
        default_dest = dest_dir / src.name
        detail = "normal"
        final_dest: Path

        try:
            exists = default_dest.exists()
        except OSError as e:
            self._set_status(f"Impossible de vérifier la destination : {e}")  # type: ignore[attr-defined]
            return

        if exists:
            choice = prompt_name_conflict(self, src_name=src.name, dest_dir=dest_dir)  # type: ignore[arg-type]
            if choice == "cancel":
                self._set_status("Opération annulée.")  # type: ignore[attr-defined]
                return
            if choice == "rename":
                final_dest = unique_destination_path(dest_dir, src.name)
                detail = "rename"
            else:
                try:
                    remove_path_for_overwrite(default_dest)
                except OrganizeError as e:
                    self._set_status(str(e))  # type: ignore[attr-defined]
                    return
                final_dest = default_dest
                detail = "overwrite"
        else:
            final_dest = default_dest

        try:
            executed = execute_move_or_copy_to_final(src, final_dest, copy=use_copy)
        except OrganizeError as e:
            self._set_status(str(e))  # type: ignore[attr-defined]
            return

        kind = "copie" if use_copy else "déplacement"
        self._add_operation_log(kind, src, executed, detail=detail)
        msg = f"→ {executed.parent.name}/{executed.name}"
        if detail == "rename":
            msg += " (renommé)"
        elif detail == "overwrite":
            msg += " (écrasé)"
        self._toast.show(msg)  # type: ignore[attr-defined]

        self._refresh_browser()  # type: ignore[attr-defined]
        self._snap_organize_source()
        self._update_dest_panel_source()
        self._render_organize_highlights()

    # ------------------------------------------------------------------ #
    # Shortcuts                                                            #
    # ------------------------------------------------------------------ #

    def _organize_send_to_shortcut(self, digit: str) -> None:
        raw = self._settings.folder_shortcuts.get(digit)  # type: ignore[attr-defined]
        if not raw:
            self._set_status(  # type: ignore[attr-defined]
                f"Raccourci {digit} vide — Ctrl+Maj+{digit} pour enregistrer ce dossier."
            )
            return
        try:
            dest = Path(raw).expanduser().resolve()
        except OSError as e:
            self._set_status(f"Raccourci invalide : {e}")  # type: ignore[attr-defined]
            return
        if not dest.is_dir():
            self._set_status(f"Raccourci {digit} ne pointe plus vers un dossier valide.")  # type: ignore[attr-defined]
            return
        self._execute_to_dir(dest)

    def _organize_save_shortcut(self, digit: str) -> None:
        if not self._browser_dir.is_dir():  # type: ignore[attr-defined]
            return
        self._settings.folder_shortcuts[digit] = str(self._browser_dir.resolve())  # type: ignore[attr-defined]
        self._settings.clamp()  # type: ignore[attr-defined]
        self._schedule_save_settings()  # type: ignore[attr-defined]
        self._set_status(f"Raccourci {digit} → {self._browser_dir.name}")  # type: ignore[attr-defined]
        self._organize_dest_panel.update_shortcuts(self._settings.folder_shortcuts)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    # Auto-rule                                                            #
    # ------------------------------------------------------------------ #

    def _organize_apply_rule(self) -> None:
        src = self._organize_source  # type: ignore[attr-defined]
        if src is None:
            self._set_status("Sélectionnez un fichier source pour appliquer une règle.")  # type: ignore[attr-defined]
            return
        dest = resolve_destination(self._settings.sorting_rules, src)  # type: ignore[attr-defined]
        if dest is None:
            self._set_status("Aucune règle de tri ne correspond à ce fichier.")  # type: ignore[attr-defined]
            return
        if not dest.exists() or not dest.is_dir():
            self._set_status(f"Destination de la règle invalide : {dest}")  # type: ignore[attr-defined]
            return
        self._execute_to_dir(dest)

    # ------------------------------------------------------------------ #
    # Enter key                                                            #
    # ------------------------------------------------------------------ #

    def _organize_handle_enter(self) -> None:
        if not self._organize_active or not self._browser_items:  # type: ignore[attr-defined]
            return
        p = self._browser_items[self._browser_selection]  # type: ignore[attr-defined]
        if not p.is_dir():
            self._set_status("Sélectionnez un dossier cible (→ pour entrer dedans).")  # type: ignore[attr-defined]
            return
        self._execute_to_dir(p)

    # ------------------------------------------------------------------ #
    # Keyboard dispatcher                                                  #
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
        if lower == "r":
            self._organize_apply_rule()
            return "break"
        if action == "organize_op_copy":
            self._organize_op = "copy"  # type: ignore[attr-defined]
            self._organize_dest_panel.set_op("copy")  # type: ignore[attr-defined]
            self._update_mode_banner()  # type: ignore[attr-defined]
            return "break"
        if action == "organize_op_move":
            self._organize_op = "move"  # type: ignore[attr-defined]
            self._organize_dest_panel.set_op("move")  # type: ignore[attr-defined]
            self._update_mode_banner()  # type: ignore[attr-defined]
            return "break"
        st = evt.state or 0
        ctrl = bool(st & 0x0004)
        shift = bool(st & 0x0001)
        if ctrl and shift:
            digit: Optional[str] = None
            if sym in "0123456789":
                digit = sym
            elif sym.startswith("KP_") and len(sym) == 4 and sym[3].isdigit():
                digit = sym[3]
            if digit is not None:
                self._organize_save_shortcut(digit)
                return "break"
        if sym in "0123456789":
            self._organize_send_to_shortcut(sym)
            return "break"
        if sym.startswith("KP_") and len(sym) == 4 and sym[3].isdigit():
            self._organize_send_to_shortcut(sym[3])
            return "break"
        return None

    # ------------------------------------------------------------------ #
    # Review labels                                                        #
    # ------------------------------------------------------------------ #

    def _set_review_label(self, label: str) -> None:
        if self._mode != "slideshow" or self._slideshow is None:  # type: ignore[attr-defined]
            return
        entry = self._slideshow.current_entry()  # type: ignore[attr-defined]
        if entry is None:
            return
        key = f"{entry.path}|{entry.member or ''}"
        self._review_labels[key] = label  # type: ignore[attr-defined]
        self._toast.show(f"Review: {entry.display_name()} → {label}")  # type: ignore[attr-defined]
        self._autosave_review_labels()
        self._show_current_image()  # type: ignore[attr-defined]

    def _autosave_review_labels(self) -> None:
        if not self._review_labels:  # type: ignore[attr-defined]
            return
        try:
            out_json = self._cwd / "logs" / "review_labels.json"  # type: ignore[attr-defined]
            out_json.parent.mkdir(parents=True, exist_ok=True)
            payload = [
                {"entry": k, "label": v}
                for k, v in sorted(self._review_labels.items())  # type: ignore[attr-defined]
            ]
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
        payload = [
            {"entry": k, "label": v}
            for k, v in sorted(self._review_labels.items())  # type: ignore[attr-defined]
        ]
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
