"""Organize mode destination panel — shortcut buttons + source display."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import tkinter as tk
from tkinter import ttk


class OrganizeDestPanel(ttk.Frame):
    """Right-side destination panel shown while organize mode is active.

    Displays the current source file name, move/copy toggle, and 10 shortcut
    folder buttons.  Callbacks keep the widget decoupled from App state.
    """

    _DIGITS = "1234567890"

    def __init__(
        self,
        master: tk.Widget,
        *,
        on_send: Callable[[str], None],
        on_toggle_op: Callable[[str], None],
    ) -> None:
        super().__init__(master, padding=(14, 10))
        self._on_send = on_send
        self._on_toggle_op = on_toggle_op
        self._shortcut_btns: dict[str, ttk.Button] = {}
        self._current_op = "move"
        self._build()

    # ------------------------------------------------------------------ #
    # Construction                                                         #
    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        row = 0

        ttk.Label(
            self, text="Envoyer vers", font=("Sans Serif", 11, "bold"), foreground="#dedede"
        ).grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1

        src_row = ttk.Frame(self)
        src_row.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        src_row.columnconfigure(1, weight=1)
        ttk.Label(src_row, text="Source :", foreground="#909090").grid(row=0, column=0, padx=(0, 6))
        self._src_label = ttk.Label(
            src_row, text="—", anchor="w", foreground="#e0e0e0",
            font=("Sans Serif", 10, "bold"),
        )
        self._src_label.grid(row=0, column=1, sticky="ew")
        row += 1

        op_row = ttk.Frame(self)
        op_row.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(op_row, text="Opération :", foreground="#909090").grid(
            row=0, column=0, padx=(0, 8)
        )
        self._btn_move = ttk.Button(
            op_row, text="Déplacer", width=11, command=lambda: self._set_op("move")
        )
        self._btn_copy = ttk.Button(
            op_row, text="Copier", width=11, command=lambda: self._set_op("copy")
        )
        self._btn_move.grid(row=0, column=1, padx=(0, 4))
        self._btn_copy.grid(row=0, column=2)
        self._refresh_op_buttons()
        row += 1

        ttk.Separator(self, orient="horizontal").grid(
            row=row, column=0, sticky="ew", pady=(0, 10)
        )
        row += 1

        ttk.Label(
            self, text="Raccourcis rapides  (touches 1–9, 0)",
            foreground="#909090", font=("Sans Serif", 9),
        ).grid(row=row, column=0, sticky="w", pady=(0, 6))
        row += 1

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=row, column=0, sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        for i, digit in enumerate(self._DIGITS):
            r, c = divmod(i, 2)
            btn = ttk.Button(
                btn_frame,
                text=self._btn_text(digit, None),
                command=lambda d=digit: self._on_send(d),
                padding=(6, 7),
            )
            btn.grid(
                row=r, column=c, sticky="ew",
                padx=(0, 4) if c == 0 else 0,
                pady=2,
            )
            self._shortcut_btns[digit] = btn
        row += 1

        ttk.Separator(self, orient="horizontal").grid(
            row=row, column=0, sticky="ew", pady=(12, 8)
        )
        row += 1

        hint = (
            "Pour un autre dossier :\n"
            "naviguer à gauche (→ entrer, ← remonter)\n"
            "puis Entrée sur le dossier cible.\n\n"
            "Ctrl+Maj+1-9 : enregistrer ce dossier\n"
            "r : règle auto   l : historique   Esc : quitter"
        )
        ttk.Label(
            self, text=hint, justify="left", foreground="#666666",
            font=("Sans Serif", 9),
        ).grid(row=row, column=0, sticky="w")

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def set_source(self, name: str) -> None:
        self._src_label.configure(text=name or "—")

    def set_op(self, op: str) -> None:
        self._current_op = op
        self._refresh_op_buttons()

    def get_op(self) -> str:
        return self._current_op

    def update_shortcuts(self, shortcuts: dict[str, str]) -> None:
        for digit, btn in self._shortcut_btns.items():
            path_str = shortcuts.get(digit)
            btn.configure(
                text=self._btn_text(digit, path_str),
                style="Shortcut.TButton" if path_str else "Free.TButton",
            )

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _btn_text(digit: str, path_str: Optional[str]) -> str:
        label = "0" if digit == "0" else digit
        if not path_str:
            return f"[{label}]  — libre —"
        name = Path(path_str).name or path_str
        if len(name) > 17:
            name = name[:15] + "…"
        return f"[{label}]  {name}"

    def _set_op(self, op: str) -> None:
        self._current_op = op
        self._refresh_op_buttons()
        self._on_toggle_op(op)

    def _refresh_op_buttons(self) -> None:
        if self._current_op == "move":
            self._btn_move.configure(style="Accent.TButton")
            self._btn_copy.configure(style="TButton")
        else:
            self._btn_move.configure(style="TButton")
            self._btn_copy.configure(style="Accent.TButton")
