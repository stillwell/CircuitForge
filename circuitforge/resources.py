"""Locate bundled resource files (logos, banners, icons).

Searches in order:
  1) the package's installed resource dir (circuitforge/_resources/)
  2) the project root's images/ directory (development checkout)
  3) /opt/circuitforge/images/ (systemd install layout)
"""

import os


_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_SEARCH_PATHS = [
    os.path.join(_PKG_DIR, "_resources"),
    os.path.join(_PKG_DIR, "..", "images"),
    "/opt/circuitforge/images",
]


def path(name):
    """Return the absolute path of resource `name`, or None if missing."""
    for d in _SEARCH_PATHS:
        p = os.path.abspath(os.path.join(d, name))
        if os.path.exists(p):
            return p
    return None


def banner():
    return path("enlightec-ltd-circuit-forge.png")


def company_logo():
    return path("enlightec-ltd.png")
