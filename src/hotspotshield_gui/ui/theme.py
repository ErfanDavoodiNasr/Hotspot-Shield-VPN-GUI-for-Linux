"""Theme tokens for light/dark appearance."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    surface: str
    surface_alt: str
    fg: str
    muted: str
    accent: str
    accent_fg: str
    danger: str
    danger_fg: str
    success: str
    warning: str
    border: str
    focus: str
    input_bg: str
    input_fg: str


LIGHT = Theme(
    name="light",
    bg="#F3F6F8",
    surface="#FFFFFF",
    surface_alt="#E8EEF2",
    fg="#14212B",
    muted="#5B6B76",
    accent="#0B6E4F",
    accent_fg="#FFFFFF",
    danger="#B42318",
    danger_fg="#FFFFFF",
    success="#0B6E4F",
    warning="#B54708",
    border="#C9D4DC",
    focus="#0B6E4F",
    input_bg="#FFFFFF",
    input_fg="#14212B",
)

DARK = Theme(
    name="dark",
    bg="#0F171C",
    surface="#182229",
    surface_alt="#223038",
    fg="#E7EEF2",
    muted="#9AADB8",
    accent="#2BB673",
    accent_fg="#062217",
    danger="#F97066",
    danger_fg="#2A0A08",
    success="#2BB673",
    warning="#FDB022",
    border="#31424C",
    focus="#2BB673",
    input_bg="#10181D",
    input_fg="#E7EEF2",
)


def resolve_theme(preference: str = "system", root: tk.Misc | None = None) -> Theme:
    pref = (preference or "system").lower()
    if pref == "light":
        return LIGHT
    if pref == "dark":
        return DARK
    # system
    if root is not None:
        try:
            # Tk 8.6+ / some platforms expose this; fall back gracefully.
            if bool(root.tk.call("tk", "windowingsystem") == "aqua"):
                # macOS — best-effort via appearance?
                pass
        except tk.TclError:
            pass
    # Prefer dark on Linux desktops that request it via COLORFGBG / dark env heuristics.
    import os

    gtk = os.environ.get("GTK_THEME", "").lower()
    if "dark" in gtk:
        return DARK
    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg.endswith(";0") or colorfgbg.endswith(";8"):
        return DARK
    return LIGHT
