#!/usr/bin/env bash
set -euo pipefail

# Pick the binary for the architecture of the image we run in. (Not TARGETPLATFORM:
# a base image such as movesrwth/storm:ci may be amd64-only on an arm64 host.)
case "$(uname -m)" in
  x86_64)        ARCH=linux-x64   ;;
  aarch64|arm64) ARCH=linux-arm64 ;;
  *)
    echo "Unsupported architecture $(uname -m)" >&2
    exit 1
    ;;
esac

# MODEST_VERSION is either LATEST (default) or an explicit version such as
# v3.1.315-g0a0763b35, which gives the filename
# Modest-Toolset-v3.1.315-g0a0763b35-linux-x64.zip
# For LATEST, version.txt publishes the most recent version.
echo "Downloading Modest for ${ARCH}"
BASE="https://www.modestchecker.net/downloads"
VERSION="${MODEST_VERSION:-LATEST}"
if [ "${VERSION}" = "LATEST" ]; then
  VERSION=$(curl -fsSL "${BASE}/version.txt" | tr -d '[:space:]')
fi
if ! [[ "${VERSION}" =~ ^v[0-9.]+-g[0-9a-f]+$ ]]; then
  echo "Unexpected Modest version '${VERSION}' (expected LATEST or e.g. v3.1.315-g0a0763b35)" >&2
  exit 1
fi
STEM="Modest-Toolset-${VERSION}"

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
cd "${TMP}"

echo "Downloading ${STEM}-${ARCH}.zip"
curl -fsSLO "${BASE}/${STEM}-${ARCH}.zip"
unzip -q "${STEM}-${ARCH}.zip"

echo "Installing Modest to /opt/Modest"
if [ ! -d Modest ]; then
  echo "Expected a 'Modest' directory inside the download, not found" >&2
  exit 1
fi
rm -f "${STEM}-${ARCH}.zip"
rm -rf /opt/Modest
mv Modest /opt/Modest