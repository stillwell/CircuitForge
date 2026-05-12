#!/usr/bin/env bash
# CircuitForge uninstaller. Reverses install.sh.
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$0")"; pwd)"
VENV_DIR="${VENV_DIR:-$INSTALL_DIR/.venv}"
CF_CONFIG_DIR="$HOME/.config/circuitforge"
NGROK_DIR="$HOME/.config/medpharm"
KEEP_NGROK=0
KEEP_DATA=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep-ngrok) KEEP_NGROK=1 ;;
    --keep-data)  KEEP_DATA=1 ;;
    --help|-h)
      echo "Usage: $0 [--keep-ngrok] [--keep-data]"; exit 0 ;;
    *) echo "unknown option: $1"; exit 1 ;;
  esac
  shift
done

log() { printf '\033[1;36m[uninstall]\033[0m %s\n' "$*"; }

# stop services if running
if command -v systemctl >/dev/null; then
  for svc in circuitforge-api circuitforge-web; do
    systemctl --user is-active "$svc.service" >/dev/null 2>&1 && \
      systemctl --user stop "$svc.service" && log "stopped $svc"
    systemctl --user is-enabled "$svc.service" >/dev/null 2>&1 && \
      systemctl --user disable "$svc.service" && log "disabled $svc"
    rm -f "$HOME/.config/systemd/user/$svc.service" && log "removed unit $svc.service"
  done
  systemctl --user daemon-reload 2>/dev/null || true
fi

# kill any running circuitforge processes
pgrep -fa "circuitforge" 2>/dev/null | while read -r pid _; do
  log "killing pid $pid"
  kill "$pid" 2>/dev/null || true
done

# remove venv
if [[ -d "$VENV_DIR" ]]; then
  log "removing venv at $VENV_DIR"
  rm -rf "$VENV_DIR"
fi

# remove config
if [[ -d "$CF_CONFIG_DIR" ]]; then
  log "removing config at $CF_CONFIG_DIR"
  rm -rf "$CF_CONFIG_DIR"
fi

# remove ngrok config (shared with MedPharm — opt-in)
if [[ $KEEP_NGROK -eq 0 && -f "$NGROK_DIR/ngrok.env" ]]; then
  log "removing ngrok credentials"
  rm -f "$NGROK_DIR/ngrok.env"
fi

# remove data
if [[ $KEEP_DATA -eq 0 && -d "$INSTALL_DIR/data" ]]; then
  log "removing data/"
  rm -rf "$INSTALL_DIR/data"
fi

# remove install log
rm -f "$INSTALL_DIR/install.log"
log "Uninstall complete."
