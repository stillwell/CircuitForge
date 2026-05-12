"""Project file management — top-level container holding schematic, PCB, and metadata.

Project files are JSON. They reference (or embed) schematic and PCB data.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any


@dataclass
class ProjectMetadata:
    title: str = "Untitled"
    author: str = ""
    company: str = ""
    revision: str = "A"
    date: str = ""
    description: str = ""
    license: str = ""


class Project:
    """Top-level project. Bundles netlist + PCB + libraries + metadata."""

    EXTENSION = ".cfproj"

    def __init__(self, path=None, metadata=None):
        self.path = path
        self.metadata = metadata or ProjectMetadata()
        self.netlist = None         # Netlist object
        self.pcb = None             # Board object
        self.libraries = []         # paths to user libraries
        self.simulation_settings = {}
        self.last_results = None

    # ---- serialization ----
    def to_dict(self):
        return {
            "format": "circuitforge-project",
            "version": 1,
            "metadata": asdict(self.metadata),
            "libraries": list(self.libraries),
            "simulation_settings": dict(self.simulation_settings),
            "netlist_file": "schematic.cfsch" if self.netlist else None,
            "pcb_file": "board.cfpcb" if self.pcb else None,
        }

    @classmethod
    def from_dict(cls, d, path=None):
        proj = cls(path=path)
        meta = d.get("metadata") or {}
        proj.metadata = ProjectMetadata(**{k: v for k, v in meta.items()
                                           if k in ProjectMetadata.__dataclass_fields__})
        proj.libraries = list(d.get("libraries", []))
        proj.simulation_settings = dict(d.get("simulation_settings", {}))
        return proj

    def save(self, path=None):
        path = path or self.path
        if path is None:
            raise ValueError("project path not set")
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        self.path = path

    @classmethod
    def load(cls, path):
        with open(path) as f:
            d = json.load(f)
        return cls.from_dict(d, path=path)

    @property
    def directory(self):
        return os.path.dirname(self.path) if self.path else None
