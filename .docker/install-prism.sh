#!/usr/bin/env bash
# Install Prism into /opt/prism so that the binary is /opt/prism/prism/bin/prism
# and the examples are in /opt/prism/prism-examples (the layout of a source checkout).
#   install-prism.sh binary   download the release PRISM_VERSION 
#   install-prism.sh source   build PRISM_REPO at PRISM_REF
set -euo pipefail

MODE="${1:?usage: install-prism.sh binary|source}"
cd /opt

case "${MODE}" in
  binary)
    # Architecture of the image we run in (not TARGETPLATFORM: the base image may be amd64-only).
    case "$(uname -m)" in
      x86_64)        ARCH=linux64-x86 ;;
      aarch64|arm64) ARCH=linux64-arm ;;
      *) echo "Unsupported architecture $(uname -m)" >&2; exit 1 ;;
    esac
    V="${PRISM_VERSION:?PRISM_VERSION is not set}"
    URL="https://github.com/prismmodelchecker/prism/releases/download/v${V}/prism-${V}-${ARCH}.tar.gz"
    echo "Downloading ${URL}"
    mkdir -p /opt/prism/prism
    curl -fsSL "${URL}" | tar xz -C /opt/prism/prism --strip-components=1
    ln -s /opt/prism/prism/prism-examples /opt/prism/prism-examples
    # The start scripts have PRISM_DIR of the build machine hard-coded; install.sh rewrites it.
    (cd /opt/prism/prism && sh install.sh silent)
    ;;
  source)
    /opt/git-checkout.sh "${PRISM_REPO:?}" "${PRISM_REF:?}" /opt/prism
    make -C /opt/prism/prism -j"$(nproc)"
    ;;
  *)
    echo "Unknown mode ${MODE}" >&2; exit 1 ;;
esac
/opt/prism/prism/bin/prism -version
