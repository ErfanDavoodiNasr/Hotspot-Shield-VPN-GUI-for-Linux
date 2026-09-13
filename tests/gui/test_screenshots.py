"""Screenshot capture smoke (PNG integrity)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screenshots"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.mark.gui
def test_documentation_screenshots_are_real_pngs() -> None:
    required = [
        "01-main-disconnected.png",
        "02-location-search.png",
        "04-connected.png",
        "07-error-dialog.png",
    ]
    missing = [name for name in required if not (SHOTS / name).exists()]
    if missing:
        pytest.skip(f"screenshots not regenerated yet: {missing}")
    for name in required:
        path = SHOTS / name
        data = path.read_bytes()
        assert data[:8] == PNG_MAGIC, f"{name} is not a PNG (got {data[:8]!r})"
        assert path.stat().st_size > 1000
    meta = SHOTS / "METADATA.json"
    if meta.exists():
        assert "commit" in meta.read_text(encoding="utf-8")
