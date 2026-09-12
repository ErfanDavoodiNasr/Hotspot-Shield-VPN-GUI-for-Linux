"""Installer script smoke tests (host may be non-Linux — dry-run / syntax only)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.installer
def test_install_help() -> None:
    result = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Usage" in result.stdout


@pytest.mark.installer
def test_uninstall_help() -> None:
    result = subprocess.run(
        ["bash", str(ROOT / "uninstall.sh"), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


@pytest.mark.installer
def test_install_dry_run_on_linux_only() -> None:
    if sys.platform != "linux":
        pytest.skip("Installer dry-run targets Linux")
    env = os.environ.copy()
    env["HOME"] = str(Path("/tmp") / "hs-gui-home-test")
    result = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "--dry-run", "--yes"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "dry-run" in result.stdout.lower() or "Dry-run" in result.stdout


@pytest.mark.installer
def test_shellcheck_if_available() -> None:
    if not shutil.which("shellcheck"):
        pytest.skip("shellcheck not installed")
    result = subprocess.run(
        ["shellcheck", str(ROOT / "install.sh"), str(ROOT / "uninstall.sh")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
