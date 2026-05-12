#!/usr/bin/env bash
# Install CircuitForge as native systemd services.
#
# Default: system-wide installation under /opt/circuitforge with a dedicated
# `circuitforge` user (UID 1000, /usr/sbin/nologin). Requires root.
#
# --user: install to ~/.config/systemd/user (no root, no /opt migration).
set -euo pipefail

INSTALL_SRC="$(cd "$(dirname "$0")"; pwd)"
TARGET="/opt/circuitforge"
SERVICE_USER="circuitforge"
SCOPE="system"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) SCOPE="user" ;;
    --target) TARGET="$2"; shift ;;
    --help|-h)
      echo "Usage: $0 [--user] [--target /path]"; exit 0 ;;
    *) echo "unknown: $1"; exit 1 ;;
  esac
  shift
done

log() { printf '\033[1;36m[svc]\033[0m %s\n' "$*"; }

if [[ $SCOPE == "system" ]]; then
  [[ $EUID -eq 0 ]] || { echo "system-wide install needs root (or --user)"; exit 2; }

  if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    log "creating system user $SERVICE_USER"
    useradd --system --uid 1000 --user-group \
            --home-dir "$TARGET" --shell /usr/sbin/nologin \
            "$SERVICE_USER" || groupadd --system "$SERVICE_USER"
  fi

  if [[ "$INSTALL_SRC" != "$TARGET" ]]; then
    log "migrating tree to $TARGET"
    mkdir -p "$TARGET"
    rsync -a --delete --exclude '.git' "$INSTALL_SRC/" "$TARGET/"
  fi
  mkdir -p "$TARGET/data" /etc/circuitforge
  chown -R "$SERVICE_USER:$SERVICE_USER" "$TARGET/data"

  if [[ ! -f "$TARGET/.venv/bin/python" ]]; then
    log "creating venv in $TARGET/.venv"
    python3 -m venv "$TARGET/.venv"
    "$TARGET/.venv/bin/pip" install --quiet --upgrade pip
    "$TARGET/.venv/bin/pip" install --quiet -r "$TARGET/requirements.txt" \
      flask flask-cors gunicorn
    chown -R "$SERVICE_USER:$SERVICE_USER" "$TARGET/.venv"
  fi

  cp "$INSTALL_SRC/systemd/circuitforge-api.service" /etc/systemd/system/
  cp "$INSTALL_SRC/systemd/circuitforge-web.service" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now circuitforge-api.service circuitforge-web.service
  log "system services installed; tail logs with: journalctl -u circuitforge-api -f"

else
  mkdir -p "$HOME/.config/systemd/user"
  # rewrite paths for user scope
  for svc in circuitforge-api circuitforge-web; do
    sed -e "s|^User=.*||" \
        -e "s|^Group=.*||" \
        -e "s|/opt/circuitforge|$INSTALL_SRC|g" \
        -e "s|^EnvironmentFile=.*|EnvironmentFile=-$HOME/.config/circuitforge/$svc.env|" \
        "$INSTALL_SRC/systemd/$svc.service" > "$HOME/.config/systemd/user/$svc.service"
  done
  mkdir -p "$HOME/.config/circuitforge"
  systemctl --user daemon-reload
  systemctl --user enable --now circuitforge-api.service circuitforge-web.service
  log "user services installed; tail logs with: journalctl --user -u circuitforge-api -f"
fi
