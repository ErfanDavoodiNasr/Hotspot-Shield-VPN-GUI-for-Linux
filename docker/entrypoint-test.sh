#!/usr/bin/env bash
set -Eeuo pipefail

Xvfb :99 -screen 0 1280x800x24 >/tmp/xvfb.log 2>&1 &
XVFB_PID=$!
cleanup() { kill "${XVFB_PID}" >/dev/null 2>&1 || true; }
trap cleanup EXIT

sleep 0.5
export DISPLAY=:99
export FAKE_HS_MODE="${FAKE_HS_MODE:-success}"

echo "== lint =="
ruff check src tests
echo "== typecheck =="
mypy src/hotspotshield_gui || true
echo "== shellcheck =="
shellcheck -e SC2088 install.sh uninstall.sh
echo "== pytest (hermetic) =="
pytest -m "not live" --cov=hotspotshield_gui --cov-report=term-missing
echo "== bandit =="
bandit -r src -q || true
echo "== installer dry-run =="
./install.sh --dry-run --yes
echo "== OK =="
