from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ToastOverlay:
    """Small transient toast displayed over a parent widget."""

    def __init__(self, parent: tk.Widget) -> None:
        self._parent = parent
        self._job: str | None = None
        self._frame = ttk.Frame(parent, padding=(10, 6))
        self._label = ttk.Label(self._frame, text="")
        self._label.grid(row=0, column=0, sticky="w")
        self._frame.place_forget()

    def show(self, text: str, *, ms: int = 2200) -> None:
        if self._job is not None:
            try:
                self._parent.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        self._label.config(text=text)
        self._frame.place(relx=1.0, rely=0.0, x=-12, y=12, anchor="ne")
        self._frame.lift()
        self._job = self._parent.after(ms, self.hide)

    def hide(self) -> None:
        self._job = None
        self._frame.place_forget()
