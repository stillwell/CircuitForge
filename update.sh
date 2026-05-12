#!/usr/bin/env bash
# CircuitForge updater. Polls GitHub for new commits, fast-forwards local tree.
#
#   ./update.sh                          # interactive
#   ./update.sh --auto                   # for unattended (cron / systemd timer)
#   ./update.sh --install-schedule[=hourly|daily|weekly]
#   ./update.sh --uninstall-schedule
#   ./update.sh --show-schedule
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$0")"; pwd)"
LOCK_DIR="$INSTALL_DIR/.update.lock.d"
AUTO=0
INSTALL_SCHEDULE=""
UNINSTALL_SCHEDULE=0
SHOW_SCHEDULE=0
SCHEDULE_PERIOD="daily"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --auto) AUTO=1 ;;
    --install-schedule) INSTALL_SCHEDULE="$SCHEDULE_PERIOD" ;;
    --install-schedule=*) INSTALL_SCHEDULE="${1#--install-schedule=}" ;;
    --uninstall-schedule) UNINSTALL_SCHEDULE=1 ;;
    --show-schedule) SHOW_SCHEDULE=1 ;;
    --help|-h)
      echo "Usage: $0 [--auto] [--install-schedule[=PERIOD]] [--uninstall-schedule] [--show-schedule]"
      exit 0 ;;
  esac
  shift
done

log() { printf '\033[1;36m[update]\033[0m %s\n' "$*"; }

if [[ $SHOW_SCHEDULE -eq 1 ]]; then
  systemctl --user list-timers circuitforge-update.timer 2>/dev/null \
    || crontab -l 2>/dev/null | grep -F "$INSTALL_DIR/update.sh" || echo "(no schedule installed)"
  exit 0
fi

if [[ $UNINSTALL_SCHEDULE -eq 1 ]]; then
  systemctl --user stop circuitforge-update.timer 2>/dev/null || true
  systemctl --user disable circuitforge-update.timer 2>/dev/null || true
  rm -f "$HOME/.config/systemd/user/circuitforge-update."{timer,service} || true
  systemctl --user daemon-reload 2>/dev/null || true
  crontab -l 2>/dev/null | grep -vF "$INSTALL_DIR/update.sh" | crontab - || true
  log "schedule uninstalled"
  exit 0
fi

if [[ -n "$INSTALL_SCHEDULE" ]]; then
  case "$INSTALL_SCHEDULE" in hourly|daily|weekly) ;; *) echo "bad period: $INSTALL_SCHEDULE"; exit 2 ;; esac
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/circuitforge-update.service" <<EOF
[Unit]
Description=CircuitForge automated updater
[Service]
Type=oneshot
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/update.sh --auto
EOF
  cat > "$HOME/.config/systemd/user/circuitforge-update.timer" <<EOF
[Unit]
Description=Scheduled CircuitForge update
[Timer]
OnCalendar=$INSTALL_SCHEDULE
Persistent=true
[Install]
WantedBy=timers.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now circuitforge-update.timer || {
    log "systemd timer failed; falling back to crontab"
    (crontab -l 2>/dev/null | grep -vF "$INSTALL_DIR/update.sh"; \
     case "$INSTALL_SCHEDULE" in
       hourly) echo "0 * * * * $INSTALL_DIR/update.sh --auto >/dev/null 2>&1" ;;
       daily)  echo "0 3 * * * $INSTALL_DIR/update.sh --auto >/dev/null 2>&1" ;;
       weekly) echo "0 3 * * 0 $INSTALL_DIR/update.sh --auto >/dev/null 2>&1" ;;
     esac) | crontab -
  }
  log "scheduled $INSTALL_SCHEDULE"
  exit 0
fi

# Concurrency lock
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "another update is in progress (lock at $LOCK_DIR) — aborting"
  exit 1
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

cd "$INSTALL_DIR"

# Require git tree
if [[ ! -d .git ]]; then
  log "not a git checkout — nothing to update"
  exit 0
fi

# Refuse to clobber a dirty tree in --auto
if [[ -n "$(git status --porcelain 2>/dev/null)" && $AUTO -eq 1 ]]; then
  log "working tree dirty — refusing to update in --auto mode"
  exit 2
fi

# Back up DB-ish data before pulling
mkdir -p data/.backup
if [[ -f data/users.json ]]; then
  cp -a data/users.json "data/.backup/users.json.$(date -u +%FT%H%M%SZ)"
  log "backed up users.json"
fi

log "fetching origin"
git fetch origin --quiet || { log "fetch failed"; exit 3; }
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse @{u} 2>/dev/null || echo "$LOCAL")"
if [[ "$LOCAL" == "$REMOTE" ]]; then
  log "already up to date ($LOCAL)"
  exit 0
fi
log "updating $LOCAL → $REMOTE"
git pull --ff-only --quiet || { log "non-fast-forward — aborting"; exit 4; }

# Reinstall requirements if they changed in this update
if git diff --name-only "$LOCAL" "$REMOTE" | grep -qE "requirements.*\.txt"; then
  log "requirements changed — reinstalling"
  "$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt" \
    || log "pip install failed (continuing)"
fi

log "update complete"
