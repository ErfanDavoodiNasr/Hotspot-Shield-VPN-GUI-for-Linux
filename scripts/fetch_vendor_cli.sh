#!/usr/bin/env bash
# Download + SHA256-verify a Hotspot Shield Linux package from the official repo.
# Never pipes a remote script into a shell. Never installs automatically.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="${ROOT}/packaging/vendor_manifest.json"
CHANNEL="${1:-stable}"
OUT_DIR="${2:-${ROOT}/vendor}"
HOST_ALLOW="repo.hotspotshield.com"

if [[ ! -f "${MANIFEST}" ]]; then
  echo "Missing manifest: ${MANIFEST}" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 required" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

python3 - "${MANIFEST}" "${CHANNEL}" "${OUT_DIR}" "${HOST_ALLOW}" <<'PY'
import hashlib
import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

manifest_path, channel, out_dir, host_allow = sys.argv[1:5]
data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
channels = data.get("channels") or {}
if channel not in channels:
    print(f"Unknown channel {channel!r}. Choose: {', '.join(channels)}", file=sys.stderr)
    sys.exit(2)
pkg = None
for candidate in channels[channel]["packages"]:
    if candidate.get("type") == "deb" and candidate.get("arch") == "amd64":
        pkg = candidate
        break
if pkg is None:
    pkg = channels[channel]["packages"][0]

url = pkg["url"]
parsed = urlparse(url)
if parsed.scheme != "https" or parsed.hostname != host_allow:
    print(f"Refusing download from untrusted URL: {url}", file=sys.stderr)
    sys.exit(3)

dest = Path(out_dir) / pkg["filename"]
max_bytes = int(pkg.get("max_bytes") or 20_000_000)
expected = pkg["sha256"].lower()

print(f"Downloading {url}")
print(f"Channel: {channel}  version: {channels[channel].get('version')}")
req = urllib.request.Request(url, headers={"User-Agent": "hotspotshield-gui-fetch/1.0"})
ctx = ssl.create_default_context()
try:
    with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
        if getattr(resp, "status", 200) != 200:
            print(f"HTTP {resp.status}", file=sys.stderr)
            sys.exit(4)
        chunks = []
        total = 0
        while True:
            block = resp.read(1024 * 256)
            if not block:
                break
            total += len(block)
            if total > max_bytes:
                print("Download exceeded max size", file=sys.stderr)
                sys.exit(5)
            chunks.append(block)
except urllib.error.URLError as exc:
    print(f"Download failed: {exc}", file=sys.stderr)
    sys.exit(6)

blob = b"".join(chunks)
digest = hashlib.sha256(blob).hexdigest()
if digest != expected:
    print(f"SHA256 mismatch!\n expected {expected}\n got      {digest}", file=sys.stderr)
    sys.exit(7)

tmp = dest.with_suffix(dest.suffix + ".partial")
tmp.write_bytes(blob)
tmp.replace(dest)
print(f"Verified OK → {dest}")
print(f"sha256:{digest}")
print("Install manually after review, e.g.:")
print(f"  sudo apt install ./{dest.name}")
PY
