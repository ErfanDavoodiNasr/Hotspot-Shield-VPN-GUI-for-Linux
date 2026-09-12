# Hotspot Shield GUI for Linux

Unofficial community desktop GUI for the legacy Hotspot Shield Linux CLI.

**Not affiliated with Hotspot Shield / Aura.** Hotspot Shield discontinued official Linux support on **2025-09-29**.

![Main window](docs/screenshots/01-main-disconnected.png)

## Install (normal users)

### Easy install (one command)

```bash
curl -fsSL https://raw.githubusercontent.com/ErfanDavoodiNasr/Hotspot-Shield-VPN-GUI-for-Linux/main/scripts/bootstrap.sh | bash
```

Pin a release:

```bash
HOTSPOTSHIELD_GUI_VERSION=1.0.0 curl -fsSL https://raw.githubusercontent.com/ErfanDavoodiNasr/Hotspot-Shield-VPN-GUI-for-Linux/main/scripts/bootstrap.sh | bash
```

Then open **Hotspot Shield GUI** from your applications menu.

You still need the vendor **Hotspot Shield Linux CLI** (stable **1.0.7**). If it is missing, the app explains how to install it. See `docs/COMPATIBILITY.md`.

### Inspect before running (safer)

Downloading and running a remote script is remote code execution. Prefer:

```bash
curl -fsSLo bootstrap.sh https://raw.githubusercontent.com/ErfanDavoodiNasr/Hotspot-Shield-VPN-GUI-for-Linux/main/scripts/bootstrap.sh
less bootstrap.sh
bash bootstrap.sh
```

### Developer checkout

```bash
git clone https://github.com/ErfanDavoodiNasr/Hotspot-Shield-VPN-GUI-for-Linux.git
cd Hotspot-Shield-VPN-GUI-for-Linux
./install.sh
```

### Vendor CLI (stable channel)

```bash
./scripts/fetch_vendor_cli.sh stable
sudo apt install ./vendor/hotspotshield_1.0.7_amd64.deb
```

Experimental `1.1.2` is **not** the default (`./scripts/fetch_vendor_cli.sh experimental`).

## Features

- Clear status, searchable locations, connect / disconnect / switch
- Independent egress IP verification before showing Connected
- Keyring-first credentials (session-only if keyring unavailable)
- Cancel that actually interrupts CLI subprocesses

## Uninstall

```bash
hotspotshield-gui-uninstall
```

(No git checkout required after install.)

## Compatibility & security

- Matrix: [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md)
- Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Testing: [`docs/TESTING.md`](docs/TESTING.md)
- Security policy: [`SECURITY.md`](SECURITY.md)

## Developers

```bash
python3 -m pip install -e ".[dev]"
make lint typecheck test test-security
make test-docker
```

Live VPN tests need a real Linux desktop/VM — Docker Desktop is not sufficient.

## License

MIT — see [`LICENSE`](LICENSE).
