#!/usr/bin/env bash
# Hotspot Shield GUI installer — per-user, isolated environment.
set -Eeuo pipefail

APP_NAME="Hotspot Shield GUI"
APP_ID="hotspotshield-gui"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

YES=0
DRY_RUN=0
UPGRADE=0
ASSUME_UNSUPPORTED=0

XDG_DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
XDG_BIN_HOME="${HOME}/.local/bin"
APP_HOME="${XDG_DATA_HOME}/${APP_ID}"
VENV_DIR="${APP_HOME}/venv"
DESKTOP_DIR="${XDG_DATA_HOME}/applications"
ICON_DIR="${XDG_DATA_HOME}/icons/hicolor"
STAGING_DIR=""

log() { printf '%s\n' "$*"; }
ok() { printf '✓ %s\n' "$*"; }
warn() { printf '! %s\n' "$*" >&2; }
die() { printf '✗ %s\n' "$*" >&2; exit 1; }

cleanup() {
  if [[ -n "${STAGING_DIR}" && -d "${STAGING_DIR}" ]]; then
    rm -rf "${STAGING_DIR}"
  fi
}
trap cleanup EXIT

usage() {
  cat <<EOF
${APP_NAME} installer

Usage: ./install.sh [options]

Options:
  -h, --help       Show this help
  -y, --yes        Non-interactive; assume yes for prompts
  --dry-run        Show actions without modifying the system
  --upgrade        Reinstall / upgrade into the existing app home
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -y|--yes) YES=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --upgrade) UPGRADE=1; shift ;;
    *) die "Unknown option: $1 (try --help)" ;;
  esac
done

run() {
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    printf '[dry-run] %s\n' "$*"
    return 0
  fi
  "$@"
}

need_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

detect_os() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    die "This installer supports Linux only (detected: $(uname -s))."
  fi
  if [[ ! -r /etc/os-release ]]; then
    die "Cannot read /etc/os-release; unsupported system."
  fi
  # shellcheck disable=SC1091
  source /etc/os-release
  OS_ID="${ID:-unknown}"
  OS_LIKE="${ID_LIKE:-}"
  OS_NAME="${PRETTY_NAME:-$OS_ID}"
  ok "Linux detected (${OS_NAME})"
}

detect_arch() {
  ARCH="$(uname -m)"
  case "${ARCH}" in
    x86_64|amd64) ARCH_NORM="amd64" ;;
    aarch64|arm64)
      ARCH_NORM="arm64"
      warn "CPU is ${ARCH_NORM}. The legacy Hotspot Shield Linux CLI packages are amd64-only."
      warn "GUI may install, but real VPN is UNSUPPORTED on this architecture."
      ;;
    *) die "Unsupported CPU architecture: ${ARCH}" ;;
  esac
  ok "Architecture detected (${ARCH_NORM})"
}

supported_distro() {
  case "${OS_ID}" in
    ubuntu|debian|linuxmint|pop) return 0 ;;
  esac
  case " ${OS_LIKE} " in
    *" debian "*|*" ubuntu "*) return 0 ;;
  esac
  return 1
}

detect_python() {
  if ! need_cmd python3; then
    die "Python 3 is required. Install it with your package manager (e.g. sudo apt install python3)."
  fi
  PY_VERSION="$(python3 -c 'import sys; print("%d.%d"%sys.version_info[:2])')"
  PY_MAJOR="$(python3 -c 'import sys; print(sys.version_info[0])')"
  PY_MINOR="$(python3 -c 'import sys; print(sys.version_info[1])')"
  if [[ "${PY_MAJOR}" -lt 3 || "${PY_MINOR}" -lt 10 ]]; then
    die "Python 3.10+ is required (found ${PY_VERSION})."
  fi
  ok "Python ${PY_VERSION} detected"
  if ! python3 -c 'import venv' >/dev/null 2>&1; then
    die "Python venv module missing. On Debian/Ubuntu: sudo apt install python3-venv"
  fi
  ok "Python venv available"
  if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
    warn "Tkinter (python3-tk) is missing. The GUI will not start until it is installed."
    warn "On Debian/Ubuntu: sudo apt install python3-tk"
    if [[ "${YES}" -eq 0 && "${DRY_RUN}" -eq 0 ]]; then
      read -r -p "Continue installation anyway? [y/N] " ans || true
      case "${ans}" in
        y|Y|yes|YES) ;;
        *) die "Aborted. Install python3-tk and re-run." ;;
      esac
    fi
  else
    ok "Tkinter available"
  fi
}

detect_hotspotshield() {
  if need_cmd hotspotshield; then
    ok "Hotspot Shield CLI found ($(command -v hotspotshield))"
    return 0
  fi
  warn "Hotspot Shield CLI not found on PATH."
  warn "Hotspot Shield discontinued official Linux support on 2025-09-29."
  warn "This GUI is unofficial and targets the legacy Linux CLI only."
  warn "Preferred install path:"
  warn "  1) Use an already-installed hotspotshield on PATH, or"
  warn "  2) Fetch the STABLE package with SHA256 verification:"
  warn "       ./scripts/fetch_vendor_cli.sh stable"
  warn "     then: sudo apt install ./vendor/hotspotshield_1.0.7_amd64.deb"
  warn "Experimental WireGuard builds (1.1.2) are NOT the default:"
  warn "       ./scripts/fetch_vendor_cli.sh experimental"
  warn "Official index: https://repo.hotspotshield.com/"
  warn "Manifest: packaging/vendor_manifest.json"
}

create_venv_and_install() {
  run mkdir -p "${APP_HOME}" "${XDG_BIN_HOME}" "${DESKTOP_DIR}"
  STAGING_DIR="$(mktemp -d "${TMPDIR:-/tmp}/${APP_ID}.XXXXXX")"
  ok "Preparing application environment"

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "[dry-run] would create venv at ${VENV_DIR}"
    log "[dry-run] would pip install ${REPO_ROOT}"
    return 0
  fi

  if [[ ! -d "${VENV_DIR}" || "${UPGRADE}" -eq 1 ]]; then
    rm -rf "${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
  fi
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
  python -m pip install --upgrade pip setuptools wheel >/dev/null
  python -m pip install "${REPO_ROOT}"
  ok "Application installed into ${APP_HOME}"
}

install_launcher() {
  local wrapper="${XDG_BIN_HOME}/${APP_ID}"
  local uninstall_wrapper="${XDG_BIN_HOME}/${APP_ID}-uninstall"
  local desktop_src="${REPO_ROOT}/packaging/${APP_ID}.desktop"
  local desktop_dst="${DESKTOP_DIR}/${APP_ID}.desktop"
  local icon_src="${REPO_ROOT}/assets/icons/hotspotshield-gui.svg"
  local icon_dst_dir="${ICON_DIR}/scalable/apps"
  local icon_dst="${icon_dst_dir}/${APP_ID}.svg"
  local bundled_uninstall="${APP_HOME}/uninstall.sh"

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "[dry-run] would write wrapper ${wrapper}"
    log "[dry-run] would write uninstall wrapper ${uninstall_wrapper}"
    log "[dry-run] would install desktop entry ${desktop_dst}"
    return 0
  fi

  cat > "${wrapper}" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
exec "${VENV_DIR}/bin/hotspotshield-gui" "\$@"
EOF
  chmod 755 "${wrapper}"

  # Installed uninstall entrypoint — users should not need the git checkout.
  install -m 0755 "${REPO_ROOT}/uninstall.sh" "${bundled_uninstall}"
  cat > "${uninstall_wrapper}" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
exec "${bundled_uninstall}" "\$@"
EOF
  chmod 755 "${uninstall_wrapper}"

  mkdir -p "${icon_dst_dir}"
  if [[ -f "${icon_src}" ]]; then
    cp "${icon_src}" "${icon_dst}"
  fi

  mkdir -p "${DESKTOP_DIR}"
  sed \
    -e "s|@EXEC@|${wrapper}|g" \
    -e "s|@ICON@|${APP_ID}|g" \
    "${desktop_src}" > "${desktop_dst}"
  chmod 644 "${desktop_dst}"

  if need_cmd update-desktop-database; then
    update-desktop-database "${DESKTOP_DIR}" >/dev/null 2>&1 || true
  fi
  if need_cmd gtk-update-icon-cache; then
    gtk-update-icon-cache -f -t "${ICON_DIR}" >/dev/null 2>&1 || true
  fi
  ok "Desktop launcher installed"

  case ":${PATH}:" in
    *":${XDG_BIN_HOME}:"*) ok "\$HOME/.local/bin is on PATH" ;;
    *)
      warn "\$HOME/.local/bin is not on your PATH."
      warn "You can still launch from the application menu."
      warn "For a terminal command, add: export PATH=\"\$HOME/.local/bin:\$PATH\""
      ;;
  esac
}

verify_install() {
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    ok "Dry-run complete (no changes applied)"
    return 0
  fi
  [[ -x "${XDG_BIN_HOME}/${APP_ID}" ]] || die "Wrapper missing after install"
  "${VENV_DIR}/bin/python" -c "import hotspotshield_gui; print(hotspotshield_gui.__version__)" >/dev/null \
    || die "Application import failed"
  ok "Installation verified"
}

main() {
  log ""
  log "${APP_NAME} Installer"
  log "======================"
  detect_os
  detect_arch
  if ! supported_distro; then
    warn "Distribution '${OS_ID}' is not in the tested support matrix (Ubuntu/Debian family)."
    warn "Installation may still work if Python 3.10+, Tk, and Hotspot Shield CLI are available."
    if [[ "${YES}" -eq 0 && "${DRY_RUN}" -eq 0 ]]; then
      read -r -p "Continue anyway? [y/N] " ans || true
      case "${ans}" in
        y|Y|yes|YES) ;;
        *) die "Aborted." ;;
      esac
    fi
    ASSUME_UNSUPPORTED=1
  else
    ok "Supported distribution family"
  fi
  detect_python
  detect_hotspotshield
  create_venv_and_install
  install_launcher
  verify_install
  log ""
  ok "Installation complete."
  log ""
  log "Launch from your application menu:"
  log "  ${APP_NAME}"
  log ""
  log "Or run:"
  log "  ${APP_ID}"
  log ""
  log "Uninstall later (no git checkout needed):"
  log "  ${APP_ID}-uninstall"
  log ""
  log "Ensure ~/.local/bin is on your PATH (desktop launcher works without it)."
  if [[ "${ASSUME_UNSUPPORTED}" -eq 1 ]]; then
    warn "You installed on an untested distribution; please report issues."
  fi
}

main "$@"
