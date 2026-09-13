#!/usr/bin/env python3
"""Capture documentation screenshots from the real shipped UI classes.

Requires a display (Xvfb is fine). Uses the fake CLI + scripted IP service so
Connected screenshots only appear after verification succeeds.
Never writes a text placeholder as a .png.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _grab_png(root, path: Path) -> None:
    root.update_idletasks()
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    # Prefer ImageMagick window grab under Xvfb (reliable, real PNG).
    if shutil.which("import"):
        subprocess.run(
            ["import", "-window", "root", str(path)],
            check=True,
            capture_output=True,
        )
        if path.stat().st_size < 100 or path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"import produced invalid PNG: {path}")
        return
    try:
        from PIL import ImageGrab

        ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(path, format="PNG")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Screenshot capture requires ImageMagick `import` or Pillow ImageGrab"
        ) from exc
    if path.stat().st_size < 100 or path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"invalid PNG written: {path}")


def main() -> int:
    os.environ.setdefault("DISPLAY", ":99")
    os.environ["HOTSPOTSHIELD_ALLOW_PLAINTEXT_FALLBACK"] = "1"

    fake = ROOT / "scripts" / "fake_hotspotshield.py"
    bin_dir = OUT / "_bin"
    bin_dir.mkdir(exist_ok=True)
    state = OUT / "_state.json"
    state.write_text(
        '{"vpn":"disconnected","location":null,"signed_in":true,"username":"demo@example.com"}',
        encoding="utf-8",
    )
    shim = bin_dir / "hotspotshield"
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
    from hotspotshield_gui.security.secret_store import Credentials, SecretStore
    from hotspotshield_gui.services.ip_service import IpConsensusResult, PublicIpInfo
    from hotspotshield_gui.services.vpn_service import VpnService
    from hotspotshield_gui.ui.dialogs import ErrorDialog
    from hotspotshield_gui.ui.main_window import MainWindow
    from hotspotshield_gui.ui.theme import DARK, LIGHT
    from hotspotshield_gui.cli.hotspotshield_client import HotspotShieldClient
    from hotspotshield_gui.cli.process_runner import ProcessRunner
    from hotspotshield_gui.services.connection_verifier import ConnectionVerifier

    class ScriptedIp:
        def __init__(self) -> None:
            self.calls = 0

        def lookup(self):
            agreed = self.lookup_consensus().agreed
            assert agreed is not None
            return agreed

        def lookup_consensus(self):
            phase = self.calls % 3
            self.calls += 1
            ip = ("203.0.113.10", "198.51.100.20", "203.0.113.11")[phase]
            info = PublicIpInfo(ip=ip, country="TS", city="Testville", raw_source="scripted")
            return IpConsensusResult(agreed=info, samples=(info, info), inconclusive=False)

        def has_basic_connectivity(self, host: str = "1.1.1.1", port: int = 53) -> bool:
            return True

    cfg = OUT / "_cfg"
    if cfg.exists():
        shutil.rmtree(cfg)
    cfg.mkdir(exist_ok=True)
    store = SecretStore(config_dir=cfg)
    store.save(Credentials("demo@example.com", "demo-password-not-real"))
    ip = ScriptedIp()
    client = HotspotShieldClient(ProcessRunner(), executable=str(shim))
    service = VpnService(
        client,
        ip_service=ip,
        verifier=ConnectionVerifier(client, ip),
        verify_egress=True,
    )
    ctrl = VpnController(
        service=service,
        secret_store=store,
        settings_repo=SettingsRepository(store),
    )
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
        path = OUT / name
        _grab_png(root, path)
        print("wrote", path, path.stat().st_size)

    grab("01-main-disconnected.png")

    window.location_selector.search_var.set("United")
    window.location_selector._on_query()
    pump(0.4)
    grab("02-location-search.png")

    window.location_selector.search_var.set("")
    window.location_selector._on_query()
    if ctrl.locations:
        ctrl.select_location(ctrl.locations[0])
        ctrl.connect()
        pump(0.8)
        grab("03-connecting.png")
        pump(4.0)
    grab("04-connected.png")

    if len(ctrl.locations) > 1 and ctrl.machine.state.value == "connected":
        ctrl.switch_location(ctrl.locations[1])
        pump(0.8)
        grab("05-switching-location.png")
        pump(3.0)

    window.apply_theme(DARK)
    pump(0.3)
    grab("06-dark-theme.png")

    ErrorDialog(
        root,
        window.theme,
        message="Unable to connect.\n\nCheck your internet connection, pick another location, and try again.",
        technical="demo technical detail only",
        title="Something went wrong",
    )
    pump(0.5)
    grab("07-error-dialog.png")

    version = "unknown"
    try:
        import tomllib

        version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
            "version"
        ]
    except Exception:  # noqa: BLE001
        pass

    meta = {
        "commit": _git_sha(),
        "app_version": version,
        "capture_command": "python3 scripts/capture_screenshots.py",
        "screen_size": "960x640",
        "display": os.environ.get("DISPLAY", ""),
        "notes": "Captured from real MainWindow with fake CLI + scripted IP; no credentials/personal IP.",
    }
    (OUT / "METADATA.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT / "METADATA.json")

    ctrl.shutdown()
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
