#!/usr/bin/env bash
# Launch the CircuitForge desktop GUI (PyQt5/PySide6).
set -euo pipefail
HERE="$(cd "$(dirname "$0")"; pwd)"
VENV="${VENV_DIR:-$HERE/.venv}"
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "venv not found at $VENV — run ./install.sh first" >&2
  exit 1
fi

# Preflight: check the Qt platform plugin's native deps on Linux,
# since "Could not load the Qt platform plugin 'xcb'" is a confusing failure.
if [[ "$(uname -s)" == "Linux" ]] && [[ "${SKIP_QT_CHECK:-0}" != "1" ]]; then
  XCB_PLUGIN="$($VENV/bin/python -c 'import os, PyQt5; print(os.path.dirname(PyQt5.__file__))' 2>/dev/null)/Qt5/plugins/platforms/libqxcb.so"
  if [[ -f "$XCB_PLUGIN" ]]; then
    MISSING="$(ldd "$XCB_PLUGIN" 2>/dev/null | awk '/not found/ {print $1}' | paste -sd ' ')"
    if [[ -n "$MISSING" ]]; then
      cat >&2 <<EOF
Qt xcb plugin is missing system libraries:
    $MISSING
On Debian/Ubuntu install them with:
    sudo apt install libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0 \\
        libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \\
        libxcb-render-util0 libxcb-shape0 libxcb-sync1 libxcb-xfixes0 \\
        libxcb-xkb1 libxcb-util1
(Most are usually present already — apt will skip those.)
Or set SKIP_QT_CHECK=1 to bypass this preflight, or
QT_QPA_PLATFORM=offscreen to run headlessly.
EOF
      exit 2
    fi
  fi
fi

exec "$VENV/bin/python" "$HERE/main.py" "$@"
