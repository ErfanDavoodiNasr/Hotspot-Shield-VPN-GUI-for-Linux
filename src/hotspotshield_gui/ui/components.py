"""Reusable UI helpers."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from hotspotshield_gui.ui.theme import Theme


def configure_styles(root: tk.Misc, theme: Theme) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("App.TFrame", background=theme.bg)
    style.configure("Card.TFrame", background=theme.surface)
    style.configure("App.TLabel", background=theme.bg, foreground=theme.fg, font=("TkDefaultFont", 11))
    style.configure(
        "Muted.TLabel",
        background=theme.bg,
        foreground=theme.muted,
        font=("TkDefaultFont", 10),
    )
    style.configure(
        "Title.TLabel",
        background=theme.bg,
        foreground=theme.fg,
        font=("TkDefaultFont", 22, "bold"),
    )
    style.configure(
        "Status.TLabel",
        background=theme.surface,
        foreground=theme.fg,
        font=("TkDefaultFont", 18, "bold"),
    )
    style.configure(
        "Card.TLabel",
        background=theme.surface,
        foreground=theme.fg,
        font=("TkDefaultFont", 11),
    )
    style.configure(
        "CardMuted.TLabel",
        background=theme.surface,
        foreground=theme.muted,
        font=("TkDefaultFont", 10),
    )
    style.configure(
        "Primary.TButton",
        font=("TkDefaultFont", 12, "bold"),
        padding=(16, 10),
    )
    style.map(
        "Primary.TButton",
        background=[("!disabled", theme.accent), ("disabled", theme.border)],
        foreground=[("!disabled", theme.accent_fg), ("disabled", theme.muted)],
    )
    style.configure(
        "Danger.TButton",
        font=("TkDefaultFont", 12, "bold"),
        padding=(16, 10),
    )
    style.map(
        "Danger.TButton",
        background=[("!disabled", theme.danger), ("disabled", theme.border)],
        foreground=[("!disabled", theme.danger_fg), ("disabled", theme.muted)],
    )
    style.configure(
        "Ghost.TButton",
        font=("TkDefaultFont", 10),
        padding=(10, 6),
    )
    style.configure(
        "Search.TEntry",
        fieldbackground=theme.input_bg,
        foreground=theme.input_fg,
        insertcolor=theme.input_fg,
        padding=8,
    )
    return style


class StatusBadge(ttk.Frame):
    def __init__(self, master: tk.Misc, theme: Theme, **kwargs: object) -> None:
        super().__init__(master, style="Card.TFrame", **kwargs)  # type: ignore[arg-type]
        self.theme = theme
        self.canvas = tk.Canvas(
            self,
            width=14,
            height=14,
            highlightthickness=0,
            bg=theme.surface,
            bd=0,
        )
        self.canvas.pack(side=tk.LEFT, padx=(0, 8))
        self.label = ttk.Label(self, text="…", style="Status.TLabel")
        self.label.pack(side=tk.LEFT)
        self._dot = self.canvas.create_oval(2, 2, 12, 12, fill=theme.muted, outline="")

    def set_status(self, text: str, *, color: str) -> None:
        self.label.configure(text=text)
        self.canvas.itemconfigure(self._dot, fill=color)

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.configure(style="Card.TFrame")
        self.canvas.configure(bg=theme.surface)
        self.label.configure(style="Status.TLabel")
