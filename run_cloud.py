#!/usr/bin/env python3
"""Cloud API launcher for CircuitForge.

Reads HOST / PORT from the environment, prefers Gunicorn in production,
falls back to the Flask dev server.

Mirrors the MedPharm ERP run_cloud.py pattern.
"""

import os
import sys


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    workers = int(os.environ.get("WORKERS", "2"))

    if "--dev" in sys.argv:
        from circuitforge.server.api import run
        run(host=host, port=port, debug=True)
        return

    try:
        import gunicorn  # noqa: F401
        os.execvp("gunicorn", [
            "gunicorn",
            "--bind", f"{host}:{port}",
            "--workers", str(workers),
            "--access-logfile", "-",
            "--error-logfile", "-",
            "circuitforge.server.api:create_app()",
        ])
    except ImportError:
        from circuitforge.server.api import run
        print(f"Gunicorn not installed — using Flask dev server on {host}:{port}",
              file=sys.stderr)
        run(host=host, port=port)


if __name__ == "__main__":
    main()
