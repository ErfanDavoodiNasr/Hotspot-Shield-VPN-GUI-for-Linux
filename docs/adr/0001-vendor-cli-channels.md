# ADR 0001: Vendor CLI channels

## Decision

Treat Hotspot Shield **1.0.7** as the only default/stable Linux CLI channel.
Treat **1.1.2** as experimental (vendor “WireGuard / Test only”).

Do not bundle vendor `.deb` blobs in git. Fetch via `scripts/fetch_vendor_cli.sh` with SHA256 verification against
`packaging/vendor_manifest.json`.

## Why

Official Linux support ended 2025-09-29. A higher version number does not mean production-stable.
