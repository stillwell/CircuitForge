"""QR-code generation for ngrok-based client onboarding.

Produces a PNG containing either the bare public URL or a JSON client config
blob, depending on what is available. Uses the qrcode package if installed,
otherwise renders a minimal PNG manually via PIL if available, otherwise
returns None.
"""

import json
import os


def _data_dir():
    return os.environ.get("CIRCUITFORGE_DATA_DIR",
                          os.path.join(os.path.dirname(__file__), "..", "..", "data"))


def _read_public_url():
    p = os.path.join(_data_dir(), "ngrok_public_url.txt")
    if os.path.exists(p):
        return open(p).read().strip()
    return None


def generate_qr_for_config(out_path=None):
    """Generate a QR PNG for the current ngrok public URL.

    Returns the output path on success, or None if no URL is configured or
    no QR backend is installed.
    """
    url = _read_public_url()
    if not url:
        return None
    if out_path is None:
        out_path = os.path.join(_data_dir(), "ngrok_qr.png")
    os.makedirs(_data_dir(), exist_ok=True)
    payload = json.dumps({"server_url": f"{url}/api/v1",
                          "version": 1, "service": "circuitforge"})
    try:
        import qrcode
        qrcode.make(payload).save(out_path)
        return out_path
    except ImportError:
        pass
    # fallback: try to call the system `qrencode` binary
    import shutil
    import subprocess
    if shutil.which("qrencode"):
        subprocess.run(["qrencode", "-o", out_path, payload], check=True)
        return out_path
    return None
