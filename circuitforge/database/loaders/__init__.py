"""Loaders pull component data from public/private sources into ComponentDB."""

from .base import Loader, LoaderError
from .jlcpcb import JLCPCBLoader
from .kicad import KiCadLoader
from .digikey import DigiKeyLoader
from .mouser import MouserLoader
from .octopart import OctopartLoader
from .ipc import LocalJSONLoader


LOADERS = {
    "jlcpcb":   JLCPCBLoader,
    "kicad":    KiCadLoader,
    "digikey":  DigiKeyLoader,
    "mouser":   MouserLoader,
    "octopart": OctopartLoader,
    "local":    LocalJSONLoader,
}


def get_loader(name):
    cls = LOADERS.get(name.lower())
    if not cls:
        raise LoaderError(f"unknown loader: {name}. Known: {', '.join(LOADERS)}")
    return cls


__all__ = ["Loader", "LoaderError", "LOADERS", "get_loader",
           "JLCPCBLoader", "KiCadLoader", "DigiKeyLoader", "MouserLoader",
           "OctopartLoader", "LocalJSONLoader"]
