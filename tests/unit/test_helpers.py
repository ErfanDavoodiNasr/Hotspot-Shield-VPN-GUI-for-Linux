"""Additional unit coverage for helpers."""

from __future__ import annotations

from pathlib import Path

from hotspotshield_gui.models.location import Location
from hotspotshield_gui.security.secret_store import migrate_legacy_vpnconfig
from hotspotshield_gui.services.ip_service import IpService, PublicIpInfo
from hotspotshield_gui.services.network_service import NetworkService
from hotspotshield_gui.utils.logging import setup_logging


def test_location_display_and_empty_code() -> None:
    loc = Location("US", "United States")
    assert "US" in loc.display
    assert Location("DE", "").display == "DE"


def test_public_ip_display() -> None:
    info = PublicIpInfo(ip="1.2.3.4", city="X", country="Y")
    text = info.display()
    assert "1.2.3.4" in text
    assert "X" in text


def test_network_service_online_false(monkeypatch) -> None:
    svc = NetworkService(IpService(timeout=0.1))
    monkeypatch.setattr(svc.ip_service, "has_basic_connectivity", lambda **_: False)
    assert svc.online() is False


def test_setup_logging(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    logger = setup_logging("DEBUG", log_to_file=True)
    logger.info("password=should-redact")
    assert (tmp_path / "hotspotshield-gui" / "app.log").exists()


def test_migrate_legacy(tmp_path: Path) -> None:
    path = tmp_path / "vpnconfig.py"
    path.write_text("vpnusername = 'a@b.c'\nvpnpassword = 'pw'\n", encoding="utf-8")
    creds = migrate_legacy_vpnconfig(path)
    assert creds is not None
    assert creds.username == "a@b.c"
