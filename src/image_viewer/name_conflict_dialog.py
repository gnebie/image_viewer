"""Three-way dialog for destination name conflicts (rename / overwrite / cancel)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Literal, Optional

NameConflictChoice = Literal["rename", "overwrite", "cancel"]


def prompt_name_conflict(
    parent: tk.Misc,
    *,
    src_name: str,
    dest_dir: Path,
) -> NameConflictChoice:
    """Show modal dialog. Default action is **rename** (first button, focused)."""
    conflict_path = dest_dir / src_name
    result: list[Optional[NameConflictChoice]] = [None]

    win = tk.Toplevel(parent)
    win.title("Conflit de nom")
    win.transient(parent.winfo_toplevel())
    win.grab_set()
    win.resizable(False, False)

    msg = (
        f"Un element nomme « {src_name} » existe deja dans :\n{dest_dir}\n\n"
        f"Chemin en conflit : {conflict_path}\n\n"
        "Que souhaitez-vous faire ?"
    )
    outer = ttk.Frame(win, padding=16)
    outer.pack(fill=tk.BOTH, expand=True)
    ttk.Label(outer, text=msg, justify="left").pack(anchor="w", pady=(0, 12))

    btn_row = ttk.Frame(outer)
    btn_row.pack(fill=tk.X)

    def pick(choice: NameConflictChoice) -> None:
        result[0] = choice
        win.destroy()

    b_rename = ttk.Button(btn_row, text="Renommer (ex. _1)", command=lambda: pick("rename"))
    b_over = ttk.Button(
        btn_row,
        text="Ecraser l'existant",
        command=lambda: pick("overwrite"),
    )
    b_cancel = ttk.Button(btn_row, text="Annuler", command=lambda: pick("cancel"))
    b_rename.pack(side=tk.LEFT, padx=(0, 8))
    b_over.pack(side=tk.LEFT, padx=(0, 8))
    b_cancel.pack(side=tk.LEFT)

    win.protocol("WM_DELETE_WINDOW", lambda: pick("cancel"))

    b_rename.focus_set()
    win.bind("<Escape>", lambda e: pick("cancel"))

    win.update_idletasks()
    px = parent.winfo_rootx() + 40
    py = parent.winfo_rooty() + 40
    win.geometry(f"+{px}+{py}")

    parent.wait_window(win)
    return result[0] or "cancel"
