from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def show_onboarding(parent: tk.Misc) -> None:
    win = tk.Toplevel(parent)
    win.title("Bienvenue")
    win.transient(parent.winfo_toplevel())
    win.grab_set()
    win.resizable(False, False)

    steps = [
        "Navigation: utilisez les fleches puis Entree pour ouvrir.",
        "Diaporama: Left/Right pour naviguer, Page_Up pour la galerie.",
        "Mode tri: touche d pour activer, Entree en 2 temps pour confirmer.",
    ]
    idx = {"value": 0}

    outer = ttk.Frame(win, padding=16)
    outer.grid(row=0, column=0, sticky="nsew")
    label = ttk.Label(outer, text=steps[0], justify="left", wraplength=420)
    label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

    def refresh() -> None:
        label.config(text=steps[idx["value"]])
        prev_btn.state(["!disabled"] if idx["value"] > 0 else ["disabled"])
        next_btn.config(text="Terminer" if idx["value"] == len(steps) - 1 else "Suivant")

    def prev_step() -> None:
        if idx["value"] > 0:
            idx["value"] -= 1
            refresh()

    def next_step() -> None:
        if idx["value"] >= len(steps) - 1:
            win.destroy()
            return
        idx["value"] += 1
        refresh()

    prev_btn = ttk.Button(outer, text="Precedent", command=prev_step)
    next_btn = ttk.Button(outer, text="Suivant", command=next_step)
    prev_btn.grid(row=1, column=0, sticky="w")
    next_btn.grid(row=1, column=1, sticky="e")
    refresh()

    parent.wait_window(win)
