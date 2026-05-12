#!/usr/bin/env bash
# Container entrypoint — dispatches between API, web portal, and CLI modes.
set -euo pipefail

case "${1:-api}" in
  api)
    exec python /opt/circuitforge/run_cloud.py "${@:2}"
    ;;
  web)
    exec python /opt/circuitforge/run_web.py "${@:2}"
    ;;
  cli)
    exec python -m circuitforge.cli "${@:2}"
    ;;
  shell)
    exec bash
    ;;
  *)
    exec "$@"
    ;;
esac
