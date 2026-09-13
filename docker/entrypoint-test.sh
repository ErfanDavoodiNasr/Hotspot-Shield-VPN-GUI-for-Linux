#!/usr/bin/env bash
set -Eeuo pipefail

Xvfb :99 -screen 0 1280x800x24 >/tmp/xvfb.log 2>&1 &
XVFB_PID=$!
cleanup() { kill "${XVFB_PID}" >/dev/null 2>&1 || true; }
trap cleanup EXIT

sleep 0.5
export DISPLAY=:99
export FAKE_HS_MODE="${FAKE_HS_MODE:-success}"

# Allow overriding the default hermetic suite, e.g. `docker run … pytest --collect-only`.
if [[ $# -gt 0 ]]; then
  exec "$@"
fi

echo "== collect =="
pytest --collect-only -q
echo "== lint =="
ruff check src tests
echo "== typecheck =="
mypy src/hotspotshield_gui
echo "== shellcheck =="
shellcheck -e SC2088 install.sh uninstall.sh scripts/bootstrap.sh scripts/fetch_vendor_cli.sh
echo "== pytest (hermetic) =="
pytest -m "not live" --cov=hotspotshield_gui --cov-report=term-missing
echo "== bandit =="
bandit -r src -q
echo "== installer dry-run =="
./install.sh --dry-run --yes
echo "== OK =="
