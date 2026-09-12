"""GUI smoke tests (require Tk; use Xvfb in CI/Docker)."""

from __future__ import annotations

import os
import time

import pytest

pytest.importorskip("tkinter")

tk = pytest.importorskip("tkinter")


@pytest.mark.gui
def test_main_window_starts(fake_client, credentials, tmp_path, monkeypatch, scripted_ip_service) -> None:
    # Skip if no display and no xvfb assumption — CI sets DISPLAY.
    if not os.environ.get("DISPLAY") and os.name != "nt":
        pytest.skip("No DISPLAY for GUI test")

    from hotspotshield_gui.config.settings import SettingsRepository
    from hotspotshield_gui.controllers.vpn_controller import VpnController
    from hotspotshield_gui.security.secret_store import SecretStore
    from hotspotshield_gui.ui.main_window import MainWindow
    from hotspotshield_gui.ui.theme import LIGHT
    from tests.conftest import make_vpn_service

    store = SecretStore(config_dir=tmp_path)
    store.save(credentials)
    controller = VpnController(
        service=make_vpn_service(fake_client, scripted_ip_service),
        secret_store=store,
        settings_repo=SettingsRepository(store),
    )
    root = tk.Tk()
    root.withdraw()
    try:
        window = MainWindow(root, controller, theme=LIGHT)
        root.deiconify()
        deadline = time.time() + 8
        while time.time() < deadline:
            for event in controller.poll_events():
                window._handle_event(event)
            root.update()
            if controller.locations and window.location_selector._all:
                break
            time.sleep(0.05)
        assert controller.locations
        assert window.location_selector._all
        assert window.primary_btn is not None
        # Location search interactions
        window.location_selector.search_var.set("ger")
        window.location_selector._on_query()
        root.update()
        assert any(loc.code == "DE" for loc in window.location_selector._filtered)
        window.location_selector.search_var.set("nonexistent-location")
        window.location_selector._on_query()
        root.update()
        assert window.location_selector._filtered == []
        # Resize
        root.geometry("1024x768")
        root.update()
        root.geometry("1280x720")
        root.update()
        controller.shutdown()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
