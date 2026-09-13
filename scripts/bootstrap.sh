#!/usr/bin/env bash
# Bootstrap Hotspot Shield GUI for Linux from a published GitHub Release.
# This script only downloads, verifies, and invokes the canonical install.sh.
#
# Security note: piping this script from the network is remote code execution.
# Prefer: curl -fsSLo bootstrap.sh <URL> && less bootstrap.sh && bash bootstrap.sh
#
# IMPORTANT: when piping, put env vars on the bash side of the pipe:
#   curl -fsSL …/bootstrap.sh | HOTSPOTSHIELD_GUI_VERSION=1.0.0 bash
set -Eeuo pipefail

REPO="${HOTSPOTSHIELD_GUI_REPO:-ErfanDavoodiNasr/Hotspot-Shield-VPN-GUI-for-Linux}"
VERSION="${HOTSPOTSHIELD_GUI_VERSION:-}"
# Official installs require a SHA256 sidecar. Opt out only for maintainer debugging.
REQUIRE_CHECKSUM="${HOTSPOTSHIELD_REQUIRE_CHECKSUM:-1}"
CHANNEL_URL_BASE="https://github.com/${REPO}"
umask 077

log() { printf '%s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

need_cmd() { command -v "$1" >/dev/null 2>&1; }

download() {
  local url="$1" dest="$2"
  if need_cmd curl; then
    curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
      --max-redirs 5 --connect-timeout 20 --max-time 300 \
      -o "${dest}" "${url}"
  elif need_cmd wget; then
    wget -q -O "${dest}" "${url}"
  else
    die "Need curl or wget to download ${url}"
  fi
}

sha256_file() {
  if need_cmd sha256sum; then
    sha256sum "$1" | awk '{print $1}'
  elif need_cmd shasum; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    die "Need sha256sum or shasum"
  fi
}

usage() {
  cat <<EOF
Bootstrap installer for Hotspot Shield GUI (unofficial).

Usage:
  bootstrap.sh [--version X.Y.Z]

Environment:
  HOTSPOTSHIELD_GUI_VERSION     Pin to a release tag (e.g. 1.0.0)
  HOTSPOTSHIELD_GUI_REPO        Override GitHub repo (owner/name)
  HOTSPOTSHIELD_REQUIRE_CHECKSUM  Require .sha256 sidecar (default: 1)

Downloads a release asset (or tagged source archive), verifies SHA256, then
runs install.sh. Does not install from an arbitrary moving branch.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --version) VERSION="${2:-}"; shift 2 ;;
    *) die "Unknown option: $1" ;;
  esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
  die "This installer supports Linux only (found $(uname -s))."
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/hotspotshield-gui-bootstrap.XXXXXX")"
cleanup() { rm -rf "${TMP}"; }
trap cleanup EXIT

log "Hotspot Shield GUI bootstrap"
log "Repository: ${REPO}"

if [[ -z "${VERSION}" ]]; then
  api="${CHANNEL_URL_BASE}/releases/latest"
  meta="${TMP}/latest.json"
  if ! download "${api}" "${meta}"; then
    die "Could not resolve latest release. Publish a GitHub Release, or set HOTSPOTSHIELD_GUI_VERSION=… explicitly. Until a release exists, install from a git checkout: ./install.sh"
  fi
  VERSION="$(python3 - "${meta}" <<'PY' 2>/dev/null || true
import json,sys
data=json.load(open(sys.argv[1],encoding="utf-8"))
tag=(data.get("tag_name") or "").lstrip("v")
print(tag)
PY
)"
  [[ -n "${VERSION}" ]] || die "No GitHub Release found. Publish a release first, or install from source with ./install.sh"
fi

TAG="v${VERSION#v}"
ARCHIVE_NAME="hotspotshield-gui-${VERSION#v}.tar.gz"
ASSET_URL="${CHANNEL_URL_BASE}/releases/download/${TAG}/${ARCHIVE_NAME}"
CHECKSUM_URL="${ASSET_URL}.sha256"
TAG_TARBALL_URL="${CHANNEL_URL_BASE}/archive/refs/tags/${TAG}.tar.gz"

ARCHIVE="${TMP}/src.tar.gz"
CHECKSUM_FILE="${TMP}/src.tar.gz.sha256"

log "Downloading ${TAG}…"
if download "${ASSET_URL}" "${ARCHIVE}"; then
  :
elif download "${TAG_TARBALL_URL}" "${ARCHIVE}"; then
  log "Note: using tag source archive (prefer publishing the named release asset)."
  ARCHIVE_NAME="source-${TAG}.tar.gz"
  CHECKSUM_URL="${CHANNEL_URL_BASE}/releases/download/${TAG}/${ARCHIVE_NAME}.sha256"
else
  die "Failed to download release/tag ${TAG}. Create the GitHub Release/tag first."
fi

if download "${CHECKSUM_URL}" "${CHECKSUM_FILE}"; then
  EXPECTED="$(awk '{print $1}' "${CHECKSUM_FILE}" | head -n1 | tr '[:upper:]' '[:lower:]')"
  ACTUAL="$(sha256_file "${ARCHIVE}")"
  if [[ "${EXPECTED}" != "${ACTUAL}" ]]; then
    die "SHA256 mismatch for ${ARCHIVE_NAME}: expected ${EXPECTED}; got ${ACTUAL}"
  fi
  log "SHA256 verified (${ACTUAL})"
else
  if [[ "${REQUIRE_CHECKSUM}" == "1" ]]; then
    die "Missing ${ARCHIVE_NAME}.sha256 on the release. Refusing to install without checksum (set HOTSPOTSHIELD_REQUIRE_CHECKSUM=0 to override for debugging only)."
  fi
  log "WARNING: no checksum sidecar — integrity not verified beyond HTTPS (REQUIRE_CHECKSUM=0)."
fi

mkdir -p "${TMP}/extract"
tar -xzf "${ARCHIVE}" -C "${TMP}/extract"
SRC="$(find "${TMP}/extract" -maxdepth 2 -type f -name install.sh -print -quit | head -n1)"
[[ -n "${SRC}" ]] || die "install.sh not found in archive"
ROOT="$(cd "$(dirname "${SRC}")" && pwd)"
chmod 0755 "${ROOT}/install.sh" "${ROOT}/uninstall.sh" 2>/dev/null || true
[[ -x "${ROOT}/install.sh" ]] || die "install.sh is not executable after extract"

log "Running canonical installer…"
exec "${ROOT}/install.sh" --yes
