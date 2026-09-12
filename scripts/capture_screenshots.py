#!/usr/bin/env python3
"""Capture UI screenshots under Xvfb for documentation (no credentials)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    os.environ.setdefault("DISPLAY", ":99")
    # Ensure hermetic fake CLI if present
    fake = ROOT / "scripts" / "fake_hotspotshield.py"
    if fake.exists() and not os.environ.get("HOTSPOTSHIELD_GUI_REAL_CLI"):
        bin_dir = OUT / "_bin"
        bin_dir.mkdir(exist_ok=True)
        shim = bin_dir / "hotspotshield"
        state = OUT / "_state.json"
        state.write_text(
            '{"vpn":"disconnected","location":null,"signed_in":true,"username":"demo@example.com"}',
            encoding="utf-8",
        )
        shim.write_text(
            f"#!/bin/sh\nexport FAKE_HS_STATE_FILE='{state}'\nexport FAKE_HS_MODE=success\n"
            f'exec "{sys.executable}" "{fake}" "$@"\n',
            encoding="utf-8",
        )
        shim.chmod(0o755)
        os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"

    import tkinter as tk

    from hotspotshield_gui.config.settings import SettingsRepository
    from hotspotshield_gui.controllers.vpn_controller import VpnController
    from hotspotshield_gui.models.vpn_state import VpnState
    from hotspotshield_gui.security.secret_store import Credentials, SecretStore
    from hotspotshield_gui.services.vpn_service import VpnService
    from hotspotshield_gui.ui.main_window import MainWindow
    from hotspotshield_gui.ui.theme import LIGHT
    from hotspotshield_gui.ui.dialogs import ErrorDialog

    cfg = OUT / "_cfg"
    cfg.mkdir(exist_ok=True)
    store = SecretStore(config_dir=cfg)
    store.save(Credentials("demo@example.com", "demo-password-not-real"))
    ctrl = VpnController(service=VpnService(), secret_store=store, settings_repo=SettingsRepository(store))
    root = tk.Tk()
    root.geometry("960x640")
    window = MainWindow(root, ctrl, theme=LIGHT)

    def pump(seconds: float = 1.0) -> None:
        end = time.time() + seconds
        while time.time() < end:
            for event in ctrl.poll_events():
                window._handle_event(event)
            root.update()
            time.sleep(0.05)

    pump(2.5)

    def grab(name: str) -> None:
        root.update_idletasks()
        root.update()
        path = OUT / name
        try:
            from PIL import ImageGrab

            x = root.winfo_rootx()
            y = root.winfo_rooty()
            w = root.winfo_width()
            h = root.winfo_height()
            ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(path)
        except Exception:
            # Fallback: PostScript → not ideal; write a note file
            ps = OUT / (path.stem + ".ps")
            root.update()
            root.postscript(file=str(ps), colormode="color")
            path.write_text(f"Captured as {ps.name}; convert with Ghostscript if needed.\n")
            return
        print("wrote", path)

    grab("01-main-disconnected.png")

    # Search filter view
    window.location_selector.search_var.set("United")
    window.location_selector._on_query()
    pump(0.3)
    grab("02-location-search.png")

    # Connect
    if ctrl.locations:
        ctrl.select_location(ctrl.locations[0])
        ctrl.connect()
        pump(3.0)
    grab("03-connected.png")

    # Error dialog (no secrets)
    ErrorDialog(
        root,
        LIGHT,
        message="Unable to connect.\n\nCheck your internet connection, pick another location, and try again.",
        technical="demo technical detail only",
        title="Something went wrong",
    )
    pump(0.4)
    grab("04-error-dialog.png")

    ctrl.shutdown()
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
