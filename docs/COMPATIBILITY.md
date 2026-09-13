# Compatibility

Evidence-based support matrix for Hotspot Shield GUI for Linux.

This project is an **unofficial community GUI**. It is **not affiliated** with Hotspot Shield / Aura.
Hotspot Shield discontinued official Linux support on **2025-09-29**. The vendor Linux CLI is legacy.

## Vendor CLI channels

| Channel      | Version | Vendor label            | Default for this app? | Source                          |
|--------------|---------|-------------------------|-----------------------|---------------------------------|
| stable       | 1.0.7   | release path `deb/rel`  | **Yes**               | https://repo.hotspotshield.com/ |
| experimental | 1.1.2   | “Wirequard. Test only!” | **No**                | https://repo.hotspotshield.com/ |

Checksums: `packaging/vendor_manifest.json` / `packaging/VENDOR_CLI.txt`.
Fetch: `./scripts/fetch_vendor_cli.sh stable|experimental` (HTTPS + SHA256; does not auto-install).

Vendor Linux packages historically published for **amd64/x86_64 only**. There is no known ARM64 vendor CLI → **REAL VPN
UNSUPPORTED on arm64/aarch64** (GUI may still install).

## Environment matrix (actual evidence)

| Distro                     | Version | Desktop        | Session        | Arch  | Python    | Vendor CLI            | GUI                    | Real VPN                                   | Result                         |
|----------------------------|---------|----------------|----------------|-------|-----------|-----------------------|------------------------|--------------------------------------------|--------------------------------|
| Ubuntu                     | 24.04   | Xvfb           | X11 (headless) | amd64 | 3.12      | fake                  | PASS (Docker hermetic) | N/A                                        | **GUI_ONLY**                   |
| Ubuntu                     | 24.04   | —              | Docker Desktop | amd64 | 3.12      | 1.0.7 installable     | PASS (image)           | FAIL (CLI start blocked in Docker Desktop) | **EXPERIMENTAL**               |
| Ubuntu                     | 22.04   | —              | —              | amd64 | —         | —                     | —                      | —                                          | **UNTESTED**                   |
| Debian                     | 12      | —              | —              | amd64 | —         | —                     | —                      | —                                          | **UNTESTED**                   |
| Debian                     | 13      | —              | —              | amd64 | —         | —                     | —                      | —                                          | **UNTESTED**                   |
| Linux Mint                 | 22      | —              | —              | amd64 | —         | —                     | —                      | —                                          | **UNTESTED**                   |
| Pop!_OS                    | 22.04   | —              | —              | amd64 | —         | —                     | —                      | —                                          | **UNTESTED**                   |
| Fedora                     | current | —              | —              | amd64 | —         | RPM experimental only | —                      | —                                          | **UNTESTED**                   |
| macOS host                 | —       | —              | —              | arm64 | 3.14      | N/A                   | N/A                    | N/A                                        | **UNSUPPORTED**                |
| Bare-metal / full Linux VM | —       | GNOME/KDE/etc. | Wayland/X11    | amd64 | 3.10–3.13 | 1.0.7                 | Required               | Required                                   | **UNTESTED (release blocker)** |

Statuses: `SUPPORTED`, `EXPERIMENTAL`, `GUI_ONLY`, `UNSUPPORTED`, `UNTESTED`.

**No distro is marked SUPPORTED for real VPN until bare-metal/VM live certification completes.**

## Python versions

Declared: 3.10–3.13. CI matrix runs all four for hermetic tests. Local host may use other versions for non-GUI checks.

## Display servers

Hermetic GUI tests use **Xvfb (X11)**. Wayland / real desktop sessions are **UNTESTED** in this pass — Xvfb is not
Wayland proof.
