#!/usr/bin/env bash
# Remove Hotspot Shield GUI application files (not the vendor CLI).
set -Eeuo pipefail

APP_ID="hotspotshield-gui"
YES=0
PURGE_CONFIG=0

XDG_DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
XDG_STATE_HOME="${XDG_STATE_HOME:-${HOME}/.local/state}"
XDG_BIN_HOME="${HOME}/.local/bin"
APP_HOME="${XDG_DATA_HOME}/${APP_ID}"
DESKTOP_FILE="${XDG_DATA_HOME}/applications/${APP_ID}.desktop"
ICON_FILE="${XDG_DATA_HOME}/icons/hicolor/scalable/apps/${APP_ID}.svg"
WRAPPER="${XDG_BIN_HOME}/${APP_ID}"
CONFIG_DIR="${XDG_CONFIG_HOME}/${APP_ID}"
STATE_DIR="${XDG_STATE_HOME}/${APP_ID}"

log() { printf '%s\n' "$*"; }
ok() { printf '✓ %s\n' "$*"; }
die() { printf '✗ %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<EOF
Uninstall ${APP_ID}

Options:
  -y, --yes           Non-interactive
  --purge-config      Also delete preferences/logs (asks unless --yes)
  -h, --help          Show help

This does NOT remove the Hotspot Shield vendor CLI or your VPN account.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -y|--yes) YES=1; shift ;;
    --purge-config) PURGE_CONFIG=1; shift ;;
    *) die "Unknown option: $1" ;;
  esac
done

remove_path() {
  local path="$1"
  if [[ -e "${path}" || -L "${path}" ]]; then
    rm -rf "${path}"
    ok "Removed ${path}"
  fi
}

main() {
  log "Hotspot Shield GUI Uninstaller"
  log "=============================="
  if [[ "${YES}" -eq 0 ]]; then
    read -r -p "Remove Hotspot Shield GUI from this user account? [y/N] " ans || true
    case "${ans}" in
      y|Y|yes|YES) ;;
      *) log "Cancelled."; exit 0 ;;
    esac
  fi
  remove_path "${WRAPPER}"
  remove_path "${DESKTOP_FILE}"
  remove_path "${ICON_FILE}"
  remove_path "${APP_HOME}"

  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${XDG_DATA_HOME}/applications" >/dev/null 2>&1 || true
  fi
  if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${XDG_DATA_HOME}/icons/hicolor" >/dev/null 2>&1 || true
  fi

  if [[ "${PURGE_CONFIG}" -eq 1 ]]; then
    if [[ "${YES}" -eq 0 ]]; then
      read -r -p "Delete preferences and logs under ${CONFIG_DIR} / ${STATE_DIR}? [y/N] " ans || true
      case "${ans}" in
        y|Y|yes|YES) ;;
        *) log "Keeping configuration."; return 0 ;;
      esac
    fi
    remove_path "${CONFIG_DIR}"
    remove_path "${STATE_DIR}"
  else
    log "Preferences kept at ${CONFIG_DIR} (use --purge-config to remove)."
  fi
  ok "Uninstall complete."
}

main "$@"
