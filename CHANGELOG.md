# Changelog

## Unreleased

### Recovery / certification (2026-09-13)

- Fixed pytest collection in Docker: moved `make_vpn_service` to `tests/support/factories.py` (no `conftest` imports)
- Fixed `ProcessRunner` stdin/`communicate` crash after auth failure (`ValueError: I/O operation on closed file`)
- Startup/refresh no longer shows Connected from CLI text alone — verifies egress or reports `UNKNOWN`
- Live theme switching (system → light → dark) without restart
- Bootstrap requires SHA256 sidecar by default; README no longer pretends one-line install works without a Release
- Added draft `release.yml` (tag/version consistency + artifacts + checksums)
- Replaced mock JPEG “screenshots” with real PNG captures from shipped UI classes
- ARM64 installer warns that vendor CLI / real VPN is unsupported
- Docker entrypoint fail-closed for mypy/bandit; accepts override args; collect gate first

### Architecture / packaging

- Fixed Git executable bits for `install.sh` / `uninstall.sh` (root cause of Docker `permission denied`)
- Docker installer image enforces `chmod 0755` on install scripts
- Added `scripts/bootstrap.sh` one-line release bootstrap (HTTPS + optional SHA256)
- Installed `hotspotshield-gui-uninstall` wrapper (no git checkout needed)
- Removed legacy `vpngui.py`, `vpnconfig.py`, `hotspot-shield.desktop`, `requirements-dev.txt`, `release_notes.txt`
- Removed unused `network_service` facade
- Added architecture boundary tests and `docs/ARCHITECTURE.md`

### Security / correctness

- Never optimistic-report Connected/Disconnected when status verification fails.
- Added `ConnectionVerifier` with multi-provider public IP consensus (`ipaddress`-validated).
- Added VPN states: `VERIFYING_*`, `UNKNOWN`.
- Cancellable `ProcessRunner` using process groups (SIGTERM → SIGKILL).
- Credentials: no silent plaintext fallback; no automatic cwd `.secrets` injection.
- Makefile/CI security gates fail closed (bandit + pip-audit).

### Vendor packaging

- Separated **stable 1.0.7** vs **experimental 1.1.2** channels.
- Added `packaging/vendor_manifest.json` + `scripts/fetch_vendor_cli.sh` (HTTPS + SHA256).
- Stopped treating experimental WireGuard builds as the default.
