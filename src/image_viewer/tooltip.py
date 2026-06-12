"""Simple tooltip widget for Tkinter."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ToolTip:
    """Show a small label near a widget after a short hover delay."""

    def __init__(self, widget: tk.Widget, text: str, *, delay_ms: int = 500) -> None:
        self._widget = widget
        self._text = text
        self._delay_ms = delay_ms
        self._job: str | None = None
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._on_enter, add=True)
        widget.bind("<Leave>", self._on_leave, add=True)
        widget.bind("<ButtonPress>", self._on_leave, add=True)

    def update_text(self, text: str) -> None:
        self._text = text

    def _on_enter(self, _evt=None) -> None:
        self._cancel_job()
        self._job = self._widget.after(self._delay_ms, self._show)

    def _on_leave(self, _evt=None) -> None:
        self._cancel_job()
        self._hide()

    def _cancel_job(self) -> None:
        if self._job is not None:
            try:
                self._widget.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def _show(self) -> None:
        self._job = None
        if self._tip is not None:
            return
        x = self._widget.winfo_rootx()
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        ttk.Label(self._tip, text=self._text, relief="solid", padding=(6, 3)).pack()

    def _hide(self) -> None:
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None
