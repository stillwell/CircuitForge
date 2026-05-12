"""Local JSON loader — pulls from the bundled component library file.

Useful for first-run offline installs and for sites that don't want to
hit the internet. The same content as circuitforge/libs/components.json
becomes searchable via the SQLite catalog.
"""

import json
import os

from .base import Loader
from ..components_db import ComponentRecord


class LocalJSONLoader(Loader):
    name = "local"
    description = "Bundled circuitforge/libs/components.json catalogue."
    requires_internet = False

    def iter_records(self, limit=None):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "libs",
                            "components.json")
        path = os.path.abspath(path)
        if not os.path.exists(path):
            return
        with open(path) as f:
            data = json.load(f)
        emitted = 0
        for c in data.get("components", []):
            yield ComponentRecord(
                source=self.name,
                source_id=c["name"],
                mpn=c.get("value", "") or "",
                manufacturer="",
                name=c["name"],
                description=c.get("description", ""),
                category=c.get("kind", ""),
                package=c.get("footprint", "") or "",
                value=str(c.get("value", "")),
                pin_count=len(c.get("pins", []) or []),
                parameters={"pins": c.get("pins", [])},
            )
            emitted += 1
            if limit is not None and emitted >= limit:
                return
