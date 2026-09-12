"""Lightweight architecture boundary checks."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "src" / "hotspotshield_gui"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
            # also full hotspotshield paths
            found.add(node.module)
    return found


def _py_files(*parts: str) -> list[Path]:
    base = ROOT.joinpath(*parts) if parts else ROOT
    if base.is_file():
        return [base]
    return sorted(base.rglob("*.py"))


@pytest.mark.parametrize("path", _py_files("models") + _py_files("cli", "parser.py"))
def test_domainish_modules_avoid_tkinter(path: Path) -> None:
    imports = _imports(path)
    assert "tkinter" not in imports
    assert "hotspotshield_gui.ui" not in imports


def test_ui_does_not_import_subprocess() -> None:
    for path in _py_files("ui"):
        text = path.read_text(encoding="utf-8")
        assert "subprocess" not in text
        assert "os.system" not in text


def test_ui_does_not_import_process_runner() -> None:
    for path in _py_files("ui"):
        imports = _imports(path)
        assert "hotspotshield_gui.cli.process_runner" not in imports
        assert "hotspotshield_gui.cli.hotspotshield_client" not in imports


def test_no_circular_ui_to_domain_via_models() -> None:
    # models must not import controllers/services/ui
    for path in _py_files("models"):
        imports = _imports(path)
        assert "hotspotshield_gui.controllers" not in imports
        assert "hotspotshield_gui.services" not in imports
        assert "hotspotshield_gui.ui" not in imports
