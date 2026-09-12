"""Shared fixtures."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FAKE_CLI = ROOT / "scripts" / "fake_hotspotshield.py"


@pytest.fixture()
def fake_state_file(tmp_path: Path) -> Path:
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "vpn": "disconnected",
                "location": None,
                "signed_in": True,
                "username": "user@example.com",
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture()
def fake_hotspotshield(tmp_path: Path, fake_state_file: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Install a ``hotspotshield`` shim on PATH that runs the fake CLI."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "hotspotshield"
    shim.write_text(
        "#!/bin/sh\n"
        f'export FAKE_HS_STATE_FILE="{fake_state_file}"\n'
        # Force success unless the test explicitly overrides FAKE_HS_MODE.
        'export FAKE_HS_MODE="${FAKE_HS_MODE:-success}"\n'
        f'exec "{sys.executable}" "{FAKE_CLI}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_HS_MODE", "success")
    monkeypatch.setenv("FAKE_HS_STATE_FILE", str(fake_state_file))
    monkeypatch.delenv("FAKE_HS_SLOW", raising=False)
    monkeypatch.delenv("FAKE_HS_TIMEOUT_SLEEP", raising=False)
    return shim


@pytest.fixture()
def fake_client(fake_hotspotshield: Path):
    from hotspotshield_gui.cli.hotspotshield_client import HotspotShieldClient
    from hotspotshield_gui.cli.process_runner import ProcessRunner

    return HotspotShieldClient(ProcessRunner(), executable=str(fake_hotspotshield))


@pytest.fixture(autouse=True)
def _hermetic_credential_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermetic tests may persist credentials without a desktop keyring."""
    monkeypatch.setenv("HOTSPOTSHIELD_ALLOW_PLAINTEXT_FALLBACK", "1")


@pytest.fixture()
def credentials():
    from hotspotshield_gui.security.secret_store import Credentials

    return Credentials(username="user@example.com", password="secret-password")


@pytest.fixture()
def scripted_ip_service():
    """Cycling baseline → VPN egress → post-disconnect IPs for verification."""
    from hotspotshield_gui.services.ip_service import IpConsensusResult, PublicIpInfo

    class _Scripted:
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
            info = PublicIpInfo(ip=ip, country="TS", raw_source="scripted")
            return IpConsensusResult(agreed=info, samples=(info, info), inconclusive=False)

        def has_basic_connectivity(self, host: str = "1.1.1.1", port: int = 53) -> bool:
            return True

    return _Scripted()


@pytest.fixture()
def vpn_service(fake_client, scripted_ip_service):
    from hotspotshield_gui.services.connection_verifier import ConnectionVerifier
    from hotspotshield_gui.services.vpn_service import VpnService

    verifier = ConnectionVerifier(fake_client, scripted_ip_service)
    return VpnService(
        fake_client,
        ip_service=scripted_ip_service,
        verifier=verifier,
        verify_egress=True,
    )


def make_vpn_service(client, ip_service):
    from hotspotshield_gui.services.connection_verifier import ConnectionVerifier
    from hotspotshield_gui.services.vpn_service import VpnService

    return VpnService(
        client,
        ip_service=ip_service,
        verifier=ConnectionVerifier(client, ip_service),
        verify_egress=True,
    )
