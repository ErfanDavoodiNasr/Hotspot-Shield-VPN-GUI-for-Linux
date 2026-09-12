#!/usr/bin/env bash
# Bootstrap Hotspot Shield GUI for Linux from a GitHub Release (or tagged source).
# This script only downloads, verifies, and invokes the canonical install.sh.
#
# Security note: piping this script from the network is remote code execution.
# Prefer: curl -fsSLo bootstrap.sh <URL> && less bootstrap.sh && bash bootstrap.sh
set -Eeuo pipefail

REPO="${HOTSPOTSHIELD_GUI_REPO:-ErfanDavoodiNasr/Hotspot-Shield-VPN-GUI-for-Linux}"
VERSION="${HOTSPOTSHIELD_GUI_VERSION:-}"
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
  HOTSPOTSHIELD_GUI_VERSION   Pin to a release tag (e.g. 1.0.0)
  HOTSPOTSHIELD_GUI_REPO      Override GitHub repo (owner/name)

This downloads a release source archive, verifies SHA256 when a checksum
asset is published, then runs install.sh from that tree.
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
  # Resolve latest release tag via GitHub API (HTTPS).
  api="${CHANNEL_URL_BASE}/releases/latest"
  meta="${TMP}/latest.json"
  if ! download "${api}" "${meta}"; then
    die "Could not resolve latest release. Set HOTSPOTSHIELD_GUI_VERSION=... explicitly."
  fi
  VERSION="$(python3 - "${meta}" <<'PY' 2>/dev/null || true
import json,sys
data=json.load(open(sys.argv[1],encoding="utf-8"))
tag=(data.get("tag_name") or "").lstrip("v")
print(tag)
PY
)"
  [[ -n "${VERSION}" ]] || die "No GitHub Release found. Publish a release, or pass --version / HOTSPOTSHIELD_GUI_VERSION."
fi

TAG="v${VERSION#v}"
ARCHIVE_NAME="hotspotshield-gui-${VERSION#v}.tar.gz"
# Prefer release asset; fall back to GitHub tag tarball (checksum optional then).
ASSET_URL="${CHANNEL_URL_BASE}/releases/download/${TAG}/${ARCHIVE_NAME}"
CHECKSUM_URL="${ASSET_URL}.sha256"
TAG_TARBALL_URL="${CHANNEL_URL_BASE}/archive/refs/tags/${TAG}.tar.gz"

ARCHIVE="${TMP}/src.tar.gz"
CHECKSUM_FILE="${TMP}/src.tar.gz.sha256"

log "Downloading ${TAG}…"
if download "${ASSET_URL}" "${ARCHIVE}"; then
  :
elif download "${TAG_TARBALL_URL}" "${ARCHIVE}"; then
  log "Note: using tag source archive (no separate release asset)."
  ARCHIVE_NAME="source-${TAG}.tar.gz"
else
  die "Failed to download release ${TAG}"
fi

EXPECTED=""
if download "${CHECKSUM_URL}" "${CHECKSUM_FILE}"; then
  EXPECTED="$(awk '{print $1}' "${CHECKSUM_FILE}" | head -n1 | tr '[:upper:]' '[:lower:]')"
  ACTUAL="$(sha256_file "${ARCHIVE}")"
  if [[ "${EXPECTED}" != "${ACTUAL}" ]]; then
    die "SHA256 mismatch for ${ARCHIVE_NAME}
 expected ${EXPECTED}
 got      ${ACTUAL}"
  fi
  log "SHA256 verified (${ACTUAL})"
else
  log "WARNING: no ${ARCHIVE_NAME}.sha256 on the release — integrity not verified beyond HTTPS."
  log "Maintainers should publish a SHA256 sidecar for every release."
fi

mkdir -p "${TMP}/extract"
tar -xzf "${ARCHIVE}" -C "${TMP}/extract"
# GitHub tag archives nest as <repo>-<tag>/
SRC="$(find "${TMP}/extract" -maxdepth 2 -type f -name install.sh -print -quit | head -n1)"
[[ -n "${SRC}" ]] || die "install.sh not found in archive"
ROOT="$(cd "$(dirname "${SRC}")" && pwd)"
chmod 0755 "${ROOT}/install.sh" "${ROOT}/uninstall.sh" 2>/dev/null || true
[[ -x "${ROOT}/install.sh" ]] || die "install.sh is not executable after extract"

log "Running canonical installer…"
exec "${ROOT}/install.sh" --yes
