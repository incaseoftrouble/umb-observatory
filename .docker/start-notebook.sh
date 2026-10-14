#!/usr/bin/env bash
# Start Jupyter on port 8000. The token is JUPYTER_TOKEN if set, otherwise a
# random one that is printed in the container log (docker logs <container>).
set -euo pipefail
TOKEN="${JUPYTER_TOKEN:-$(python -c 'import secrets; print(secrets.token_hex(16))')}"
echo "Open: http://localhost:${UMB_HOST_PORT:-8000}/lab?token=${TOKEN}  (flavor: ${UMB_FLAVOR:-unknown})"
exec jupyter lab --ip=0.0.0.0 --port=8000 --no-browser --allow-root \
  --ServerApp.token="${TOKEN}" --notebook-dir=/opt/umb
