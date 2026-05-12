#!/usr/bin/env bash
# Pull the published image from Docker Hub and bring up the stack.
#
# Usage:
#   ./start_docker_hub.sh             # api + web
#   ./start_docker_hub.sh ngrok       # api + web + ngrok tunnel
set -euo pipefail
HERE="$(cd "$(dirname "$0")"; pwd)"
PROFILE=()

case "${1:-}" in
  ngrok)
    [[ -f "$HOME/.config/medpharm/ngrok.env" ]] || {
      echo "ngrok env not found; run ./install.sh --ngrok-login first" >&2
      exit 1
    }
    PROFILE=(--profile ngrok)
    ;;
esac

: "${CIRCUITFORGE_JWT_SECRET:?set CIRCUITFORGE_JWT_SECRET in your environment}"
: "${CIRCUITFORGE_SESSION_SECRET:?set CIRCUITFORGE_SESSION_SECRET}"

cd "$HERE"
docker compose -f docker-compose.hub.yml "${PROFILE[@]}" pull
exec docker compose -f docker-compose.hub.yml "${PROFILE[@]}" up
