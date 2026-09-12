# Compatibility

Evidence-based support matrix for Hotspot Shield GUI for Linux.

This project is an **unofficial community GUI**. It is **not affiliated** with Hotspot Shield / Aura.
Hotspot Shield discontinued official Linux support on **2025-09-29**. The vendor Linux CLI is legacy.

## Vendor CLI channels

| Channel | Version | Vendor label | Default for this app? | Source |
| --- | --- | --- | --- | --- |
| stable | 1.0.7 | release path `deb/rel` | **Yes** | https://repo.hotspotshield.com/ |
| experimental | 1.1.2 | “Wirequard. Test only!” | **No** | https://repo.hotspotshield.com/ |

Checksums: `packaging/vendor_manifest.json` / `packaging/VENDOR_CLI.txt`.
Fetch: `./scripts/fetch_vendor_cli.sh stable|experimental` (HTTPS + SHA256; does not auto-install).

## Environment matrix (verified in this certification pass)

| OS / runtime | Python | GUI install | Hermetic tests | Vendor CLI install | Real VPN egress verify | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Ubuntu 24.04 (Docker hermetic/Xvfb) | 3.12 | PASS (installer dry-run + install smoke) | PASS | N/A (fake CLI) | N/A | **GUI ONLY / hermetic** |
| Ubuntu 24.04 (Docker live amd64) | 3.12 | PASS (image build) | N/A | PASS (stable 1.0.7 via verified download) | FAIL / blocked (CLI `start` refused in Docker Desktop) | **EXPERIMENTAL lab only** |
| macOS host (arm64) | 3.14 venv | N/A (Linux app) | PASS (non-GUI) / GUI needs Xvfb | Vendor deb is amd64 Linux | Not available on this host | **UNSUPPORTED for real VPN** |
| Bare-metal / full Linux VM desktop user | — | Not re-run in this pass | — | Required for LIVE | **Not completed in this pass** | **REQUIRED before READY** |

Statuses used: `SUPPORTED`, `GUI ONLY`, `EXPERIMENTAL`, `UNSUPPORTED`.

## Python versions

Declared: 3.10–3.13. Hermetic suite exercised primarily on 3.12 (CI) and 3.14 (local host).
Full matrix across 3.10/3.11/3.13 not completed in this pass → do not claim multi-version production proof yet.

## Display servers

Tkinter GUI is validated under Xvfb. Wayland/X11 desktop smoke not completed in this pass.
