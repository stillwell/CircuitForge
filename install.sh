#!/usr/bin/env bash
# CircuitForge installer.
# Cross-platform: detects pip/apt/brew, creates a virtualenv, installs deps,
# seeds the default user, optionally configures ngrok for remote access.
#
# Usage:
#   ./install.sh                     # default install
#   ./install.sh --no-gui            # skip PyQt
#   ./install.sh --ngrok-login       # interactive ngrok auth token capture
#   ./install.sh --systemd           # install systemd services after
#   ./install.sh --help              # full options
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-$(cd "$(dirname "$0")"; pwd)}"
VENV_DIR="${VENV_DIR:-$INSTALL_DIR/.venv}"
PYTHON="${PYTHON:-python3}"
LOG_FILE="$INSTALL_DIR/install.log"
NGROK_DIR="${NGROK_DIR:-$HOME/.config/medpharm}"  # shared convention
CF_CONFIG_DIR="$HOME/.config/circuitforge"
WANT_GUI=1
WANT_NGROK_LOGIN=0
WANT_SYSTEMD=0
WANT_DOCKER=0

usage() {
  cat <<EOF
CircuitForge installer

  --no-gui            Skip the PyQt5 / PySide6 dependency
  --ngrok-login       Open ngrok dashboard, prompt for auth token (hidden), persist
  --systemd           Install systemd --user services after deps are ready
  --docker            Build the Docker image instead of a venv install
  --venv DIR          Use a different virtualenv path (default: .venv)
  --python EXE        Use a specific Python interpreter (default: python3)
  --help              Show this help

After install you can run any of:

  ./start_desktop.sh         GUI app (Qt)
  ./start_cloud.sh           REST API on port 8080
  ./start_web.sh             Browser portal on port 5000
  ./start_ngrok.sh           ngrok tunnel + QR generation
  ./start_docker_hub.sh      Pull and run the published image
EOF
}

log() { printf '\033[1;36m[install]\033[0m %s\n' "$*" | tee -a "$LOG_FILE"; }
err() { printf '\033[1;31m[error ]\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-gui)        WANT_GUI=0 ;;
    --ngrok-login)   WANT_NGROK_LOGIN=1 ;;
    --systemd)       WANT_SYSTEMD=1 ;;
    --docker)        WANT_DOCKER=1 ;;
    --venv)          VENV_DIR="$2"; shift ;;
    --python)        PYTHON="$2"; shift ;;
    --help|-h)       usage; exit 0 ;;
    *) err "unknown option: $1" ;;
  esac
  shift
done

: > "$LOG_FILE"
log "CircuitForge installer starting in $INSTALL_DIR"
log "$(date)"

# -------- detect platform & python --------
UNAME="$(uname -s 2>/dev/null || echo unknown)"
log "Platform: $UNAME"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  err "$PYTHON not found. Install Python 3.8+ first."
fi
PYVER="$($PYTHON -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
log "Python: $($PYTHON --version 2>&1)"

# Refuse very-old Pythons
if [[ "$(printf '%s\n%s' 3.8 "$PYVER" | sort -V | head -n1)" != 3.8 ]]; then
  err "Python 3.8 or newer required (have $PYVER)"
fi

# -------- docker path --------
if [[ $WANT_DOCKER -eq 1 ]]; then
  command -v docker >/dev/null 2>&1 || err "docker not installed"
  log "Building Docker image circuitforge:latest"
  docker build -t circuitforge:latest "$INSTALL_DIR"
  log "Done. Use ./start_docker_hub.sh or docker compose up."
  exit 0
fi

# -------- venv --------
if [[ ! -d "$VENV_DIR" ]]; then
  log "Creating virtualenv at $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR" || err "venv creation failed"
fi

PIP="$VENV_DIR/bin/pip"
PYBIN="$VENV_DIR/bin/python"

log "Upgrading pip"
"$PIP" install --quiet --upgrade pip wheel setuptools

log "Installing core requirements"
"$PIP" install --quiet -r "$INSTALL_DIR/requirements.txt"

log "Installing server requirements (Flask, gunicorn)"
"$PIP" install --quiet flask flask-cors gunicorn

if [[ $WANT_GUI -eq 1 ]]; then
  if "$PYBIN" -c 'import PyQt5' 2>/dev/null; then
    log "PyQt5 already available — skipping install"
  else
    log "Installing PyQt5 (use --no-gui to skip)"
    if ! "$PIP" install --quiet PyQt5; then
      log "PyQt5 install failed; trying PySide6 instead"
      "$PIP" install --quiet PySide6 || log "PySide6 also failed — GUI will not be available"
    fi
  fi
fi

log "Optional: qrcode (for ngrok QR PNGs)"
"$PIP" install --quiet "qrcode[pil]" || log "qrcode install failed — system 'qrencode' will be used if present"

# -------- ngrok login (optional) --------
if [[ $WANT_NGROK_LOGIN -eq 1 ]]; then
  log "ngrok login flow"
  mkdir -p "$NGROK_DIR" "$HOME/.config/ngrok" "$CF_CONFIG_DIR"
  chmod 700 "$NGROK_DIR" "$HOME/.config/ngrok" "$CF_CONFIG_DIR"
  echo "Opening ngrok dashboard so you can copy your auth token…"
  if command -v xdg-open >/dev/null; then xdg-open https://dashboard.ngrok.com/get-started/your-authtoken >/dev/null 2>&1 || true
  elif command -v open    >/dev/null; then open https://dashboard.ngrok.com/get-started/your-authtoken >/dev/null 2>&1 || true
  fi
  read -srp "Paste ngrok auth token (input hidden): " NGROK_TOKEN
  echo
  if [[ -n "$NGROK_TOKEN" ]]; then
    if command -v ngrok >/dev/null; then
      ngrok config add-authtoken "$NGROK_TOKEN" || true
    fi
    printf "NGROK_AUTHTOKEN=%s\n" "$NGROK_TOKEN" > "$NGROK_DIR/ngrok.env"
    chmod 600 "$NGROK_DIR/ngrok.env"
    printf "NGROK_AUTHTOKEN=%s\n" "$NGROK_TOKEN" > "$CF_CONFIG_DIR/ngrok.env"
    chmod 600 "$CF_CONFIG_DIR/ngrok.env"
    log "Token saved (mode 0600) to $NGROK_DIR/ngrok.env and $CF_CONFIG_DIR/ngrok.env"
  else
    log "No token entered; skipping"
  fi
fi

# -------- systemd --------
if [[ $WANT_SYSTEMD -eq 1 ]]; then
  log "Installing user systemd services"
  bash "$INSTALL_DIR/install-services.sh" --user
fi

# -------- seed data dir --------
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$CF_CONFIG_DIR"

# Create marker so other scripts know we're installed
cat > "$CF_CONFIG_DIR/install_info.json" <<EOF
{
  "install_dir": "$INSTALL_DIR",
  "venv": "$VENV_DIR",
  "python_version": "$PYVER",
  "installed_at": "$(date -u +%FT%TZ)"
}
EOF

cat <<EOF

──────────────────────────────────────────────────────────────────
  CircuitForge installed.

  Quick start:
    source $VENV_DIR/bin/activate
    python -m circuitforge.cli simulate examples/divider.cir

  Or use the run scripts:
    ./start_desktop.sh        # GUI
    ./start_cloud.sh          # REST API on :8080
    ./start_web.sh            # Browser portal on :5000
    ./start_ngrok.sh          # ngrok tunnel (requires --ngrok-login first)

  Logs: $LOG_FILE
──────────────────────────────────────────────────────────────────
EOF
