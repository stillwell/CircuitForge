"""Component library manager.

A library is a JSON file mapping symbol_name → {description, kind, default_value,
default_footprint, pins[], spice_template}. Libraries are loaded from
circuitforge/libs/ and from user-specified paths.
"""

import json
import os
from typing import Dict, Any, List, Optional


DEFAULT_LIB = os.path.join(os.path.dirname(__file__), "..", "libs", "components.json")


class LibraryEntry:
    __slots__ = ("name", "kind", "description", "value", "footprint",
                 "pins", "spice", "manufacturer", "datasheet")

    def __init__(self, name, **kw):
        self.name = name
        self.kind = kw.get("kind", "generic")
        self.description = kw.get("description", "")
        self.value = kw.get("value")
        self.footprint = kw.get("footprint")
        self.pins = kw.get("pins", [])
        self.spice = kw.get("spice")
        self.manufacturer = kw.get("manufacturer", "")
        self.datasheet = kw.get("datasheet", "")

    def __repr__(self):
        return f"<LibraryEntry {self.name} kind={self.kind}>"


class ComponentLibrary:
    """Searchable collection of LibraryEntry objects."""

    def __init__(self):
        self.entries: Dict[str, LibraryEntry] = {}

    def load(self, path):
        with open(path) as f:
            data = json.load(f)
        for item in data.get("components", []):
            item = dict(item)            # copy so we can pop
            name = item.pop("name")
            self.entries[name] = LibraryEntry(name=name, **item)

    def load_default(self):
        if os.path.exists(DEFAULT_LIB):
            self.load(DEFAULT_LIB)
        return self

    def search(self, query, kind=None) -> List[LibraryEntry]:
        q = query.lower()
        out = []
        for e in self.entries.values():
            if kind and e.kind != kind:
                continue
            if q in e.name.lower() or q in e.description.lower():
                out.append(e)
        return out

    def get(self, name) -> Optional[LibraryEntry]:
        return self.entries.get(name)

    def kinds(self):
        return sorted({e.kind for e in self.entries.values()})

    def __len__(self):
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries.values())
