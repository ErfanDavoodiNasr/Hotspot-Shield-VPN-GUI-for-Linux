# Testing

## Layers

1. **Hermetic** — `scripts/fake_hotspotshield.py` on PATH; no real VPN; run with `pytest -m "not live"`.
2. **GUI** — `@pytest.mark.gui` under Xvfb (`xvfb-run` / Docker).
3. **Security** — bandit, pip-audit, gitleaks, command-injection tests, redaction tests.
4. **Installer** — `install.sh` / `uninstall.sh` dry-run + Docker clean Ubuntu.
5. **Live** — real `hotspotshield` + credentials + independent egress verification. Opt-in only.

## Commands

```bash
python -m pip install -e ".[dev]"
make lint
make typecheck
make test
make test-security   # fail-closed
make test-docker
pytest -m live       # only on a real Linux desktop/VM with secrets
```

## Live credentials

Never commit secrets. Use:

- `HOTSPOTSHIELD_USERNAME` / `HOTSPOTSHIELD_PASSWORD`, or
- `HOTSPOTSHIELD_USE_SECRETS_FILE=1` and (for cwd files) `HOTSPOTSHIELD_ALLOW_CWD_SECRETS=1`

Production runs do **not** auto-load `./.secrets` from an arbitrary cwd.

## VPN verification

`ConnectionVerifier` requires CLI connected **and** multi-provider public IP consensus.
A CLI exit code of 0 alone is not treated as “Connected / Protected”.

## Reproducing vendor packages

```bash
./scripts/fetch_vendor_cli.sh stable
shasum -a 256 vendor/hotspotshield_1.0.7_amd64.deb
```
