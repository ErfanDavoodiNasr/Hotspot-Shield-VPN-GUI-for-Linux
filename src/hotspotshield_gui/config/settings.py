"""Application settings / preferences."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from hotspotshield_gui.security.secret_store import SecretStore, default_config_dir


@dataclass
class AppSettings:
    theme: str = "system"  # system | light | dark
    recent_locations: list[str] = field(default_factory=list)
    last_location_code: str | None = None
    window_geometry: str | None = None
    leave_vpn_on_exit: bool = True

    def remember_location(self, code: str, *, limit: int = 8) -> None:
        code = code.strip()
        if not code:
            return
        recent = [c for c in self.recent_locations if c != code]
        recent.insert(0, code)
        self.recent_locations = recent[:limit]
        self.last_location_code = code


class SettingsRepository:
    def __init__(self, store: SecretStore | None = None) -> None:
        self.store = store or SecretStore()

    def load(self) -> AppSettings:
        data = self.store.load_preferences()
        recent_raw = data.get("recent_locations", [])
        recent: list[str] = []
        if isinstance(recent_raw, list):
            recent = [str(x) for x in recent_raw if str(x).strip()]
        return AppSettings(
            theme=str(data.get("theme", "system")),
            recent_locations=recent,
            last_location_code=_opt_str(data.get("last_location_code")),
            window_geometry=_opt_str(data.get("window_geometry")),
            leave_vpn_on_exit=bool(data.get("leave_vpn_on_exit", True)),
        )

    def save(self, settings: AppSettings) -> None:
        self.store.save_preferences(
            {
                "theme": settings.theme,
                "recent_locations": settings.recent_locations,
                "last_location_code": settings.last_location_code,
                "window_geometry": settings.window_geometry,
                "leave_vpn_on_exit": settings.leave_vpn_on_exit,
            }
        )


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def legacy_vpnconfig_candidates() -> list[Path]:
    return [
        Path.cwd() / "vpnconfig.py",
        Path("/usr/local/bin/vpnconfig.py"),
        default_config_dir() / "vpnconfig.py",
    ]
