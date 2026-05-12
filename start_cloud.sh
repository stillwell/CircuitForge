#!/usr/bin/env bash
# Launch the REST API. Defaults to port 8080, override via PORT=.
set -euo pipefail
HERE="$(cd "$(dirname "$0")"; pwd)"
VENV="${VENV_DIR:-$HERE/.venv}"
[[ -x "$VENV/bin/python" ]] || { echo "venv missing — run ./install.sh first" >&2; exit 1; }
exec "$VENV/bin/python" "$HERE/run_cloud.py" "$@"
