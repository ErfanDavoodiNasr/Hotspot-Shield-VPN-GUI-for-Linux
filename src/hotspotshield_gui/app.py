"""Application entry point."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hotspotshield-gui", description="Hotspot Shield VPN GUI")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    parser.add_argument(
        "--cli",
        default=None,
        help="Path to hotspotshield executable (default: search PATH)",
    )
    args = parser.parse_args(argv)

    from hotspotshield_gui.utils.logging import setup_logging

    setup_logging(args.log_level)

    try:
        import tkinter as tk
    except ImportError:
        print(
            "Tkinter is not available. On Debian/Ubuntu install: sudo apt install python3-tk",
            file=sys.stderr,
        )
        return 2

    from hotspotshield_gui.cli.hotspotshield_client import HotspotShieldClient
    from hotspotshield_gui.cli.process_runner import ProcessRunner
    from hotspotshield_gui.config.settings import SettingsRepository, legacy_vpnconfig_candidates
    from hotspotshield_gui.controllers.vpn_controller import VpnController
    from hotspotshield_gui.security.secret_store import SecretStore, migrate_legacy_vpnconfig
    from hotspotshield_gui.services.vpn_service import VpnService
    from hotspotshield_gui.ui.main_window import MainWindow
    from hotspotshield_gui.ui.theme import resolve_theme

    store = SecretStore()
    if store.load() is None:
        for candidate in legacy_vpnconfig_candidates():
            legacy = migrate_legacy_vpnconfig(candidate)
            if legacy is not None:
                store.save(legacy)
                break

    runner = ProcessRunner()
    client = HotspotShieldClient(runner, executable=args.cli)
    service = VpnService(client)
    settings_repo = SettingsRepository(store)
    controller = VpnController(
        service=service,
        secret_store=store,
        settings_repo=settings_repo,
    )

    root = tk.Tk()
    theme = resolve_theme(controller.settings.theme, root)
    MainWindow(root, controller, theme=theme)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
