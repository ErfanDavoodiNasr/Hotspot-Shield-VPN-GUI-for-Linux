"""Bootstrap script smoke tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.sh"


@pytest.mark.installer
def test_bootstrap_help() -> None:
    result = subprocess.run(
        ["bash", str(BOOTSTRAP), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Bootstrap" in result.stdout


@pytest.mark.installer
def test_bootstrap_shellcheck_if_available() -> None:
    if not shutil.which("shellcheck"):
        pytest.skip("shellcheck not installed")
    result = subprocess.run(
        ["shellcheck", str(BOOTSTRAP)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.installer
def test_scripts_are_executable_in_git_index() -> None:
    """Regression for Docker exec permission denied (git mode must be 100755)."""
    result = subprocess.run(
        ["git", "ls-files", "-s", "install.sh", "uninstall.sh"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.strip().splitlines():
        mode = line.split()[0]
        assert mode.endswith("755"), f"expected executable git mode, got {line!r}"
