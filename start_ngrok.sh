#!/usr/bin/env bash
# Start an ngrok tunnel to the CircuitForge API and publish the public URL.
#
# Polls the local ngrok inspector (http://127.0.0.1:4040/api/tunnels), writes:
#   data/ngrok_public_url.txt    bare URL, one line
#   data/ngrok_client_config.json   JSON config for mobile/desktop clients
#   data/ngrok_qr.png            QR PNG (if qrcode/qrencode is available)
set -euo pipefail

HERE="$(cd "$(dirname "$0")"; pwd)"
PORT="${PORT:-8080}"
DATA_DIR="$HERE/data"
NGROK_ENV="$HOME/.config/medpharm/ngrok.env"
[[ -f "$HOME/.config/circuitforge/ngrok.env" ]] && NGROK_ENV="$HOME/.config/circuitforge/ngrok.env"

mkdir -p "$DATA_DIR"

# Pick up the auth token if we stashed one
if [[ -f "$NGROK_ENV" ]]; then
  # shellcheck disable=SC1090
  . "$NGROK_ENV"
fi

if [[ -z "${NGROK_AUTHTOKEN:-}" ]]; then
  echo "No NGROK_AUTHTOKEN — run ./install.sh --ngrok-login first" >&2
  exit 1
fi

command -v ngrok >/dev/null 2>&1 || {
  echo "ngrok binary not on PATH. Install it from https://ngrok.com/download" >&2
  exit 2
}

# launch tunnel in the background
ngrok config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null
ngrok http "$PORT" --log stdout > "$DATA_DIR/ngrok.log" 2>&1 &
NGROK_PID=$!
echo "ngrok PID $NGROK_PID — log at $DATA_DIR/ngrok.log"
trap 'kill "$NGROK_PID" 2>/dev/null || true' EXIT

# Poll inspector until tunnel is up (max 30s)
for i in $(seq 1 30); do
  sleep 1
  if URL="$(curl --silent --fail http://127.0.0.1:4040/api/tunnels \
            | python3 -c 'import sys,json;
ts=json.load(sys.stdin).get("tunnels",[])
print(next((t["public_url"] for t in ts if t["public_url"].startswith("https")), ""))' 2>/dev/null)"; then
    if [[ -n "$URL" ]]; then
      echo "$URL" > "$DATA_DIR/ngrok_public_url.txt"
      cat > "$DATA_DIR/ngrok_client_config.json" <<EOF
{
  "server_url": "$URL/api/v1",
  "version": 1,
  "service": "circuitforge"
}
EOF
      echo "Public URL: $URL"
      # try to make a QR
      if command -v qrencode >/dev/null; then
        qrencode -o "$DATA_DIR/ngrok_qr.png" "$(cat "$DATA_DIR/ngrok_client_config.json")"
        echo "QR saved to $DATA_DIR/ngrok_qr.png"
      else
        "$HERE/.venv/bin/python" -c "
import qrcode, json
qrcode.make(open('$DATA_DIR/ngrok_client_config.json').read()).save('$DATA_DIR/ngrok_qr.png')
" 2>/dev/null && echo "QR saved to $DATA_DIR/ngrok_qr.png" \
                 || echo "(install 'qrcode' or 'qrencode' to enable QR generation)"
      fi
      break
    fi
  fi
done

echo "Press Ctrl-C to stop ngrok"
wait "$NGROK_PID"
