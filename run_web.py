#!/usr/bin/env python3
"""Web portal launcher.

Defaults to the Flask dev server. Set PORT, HOST, or pass --prod to use Gunicorn.
"""

import os
import sys


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    if "--dev" in sys.argv or "--prod" not in sys.argv:
        from circuitforge.web.app import run
        run(host=host, port=port, debug="--debug" in sys.argv)
        return
    try:
        import gunicorn  # noqa: F401
        os.execvp("gunicorn", [
            "gunicorn", "--bind", f"{host}:{port}",
            "--workers", os.environ.get("WORKERS", "2"),
            "circuitforge.web.app:create_app()",
        ])
    except ImportError:
        from circuitforge.web.app import run
        run(host=host, port=port)


if __name__ == "__main__":
    main()
