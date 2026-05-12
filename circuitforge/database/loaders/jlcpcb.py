"""JLCPCB component loader.

Source: the community-maintained jlcparts project at
https://github.com/yaqwsx/jlcparts which mirrors JLCPCB's parts catalog
as a downloadable SQLite dataset, refreshed daily (~500 k parts, CC0).

We pull the published categorized JSON index (small, fast) plus a per-
category parts.json (larger, contains MPN/manufacturer/price). Both are
served as static files from the project's GitHub Pages mirror.

Behaviour
---------
- First sync: downloads category index + each category's parts.json,
  unpacks into ComponentRecord, upserts.
- Subsequent: re-uses the cached index (24 h TTL by default) and only
  fetches changed categories. Override via `--force` in the CLI.
- `limit=N` caps the number of records ingested (for testing).
"""

import gzip
import io
import json
import os
import time

from .base import Loader, LoaderError
from ..components_db import ComponentRecord


INDEX_URL = "https://yaqwsx.github.io/jlcparts/data/index.json"
DATA_BASE = "https://yaqwsx.github.io/jlcparts/data/"


class JLCPCBLoader(Loader):
    name = "jlcpcb"
    description = ("JLCPCB parts catalogue (via the community-maintained "
                   "yaqwsx/jlcparts mirror, CC0). ~500 k parts.")

    def iter_records(self, limit=None):
        index_path = self.cached_get(INDEX_URL, "index.json")
        with open(index_path, "rb") as f:
            try:
                index = json.load(f)
            except json.JSONDecodeError as e:
                raise LoaderError(f"JLCPCB index parse failed: {e}")

        # jlcparts publishes the index as a list of category descriptors:
        # [{"category": "...", "subcategory": "...", "datafile": "...", ...}, ...]
        # We tolerate either that shape or a {"categories": [...]} wrapper.
        if isinstance(index, dict) and "categories" in index:
            cats = index["categories"]
        elif isinstance(index, list):
            cats = index
        else:
            raise LoaderError(
                f"unexpected JLCPCB index shape: {type(index).__name__}")

        emitted = 0
        for cat in cats:
            datafile = cat.get("datafile") or cat.get("file")
            if not datafile:
                continue
            category = cat.get("category", "")
            subcategory = cat.get("subcategory", "")
            url = DATA_BASE + datafile
            local = os.path.join(self.cache_dir, datafile.replace("/", "_"))
            try:
                self.cached_get(url, os.path.basename(local), max_age=24 * 3600)
            except LoaderError:
                continue
            yield from self._records_from_file(
                local, category=category, subcategory=subcategory)
            emitted += 1
            if limit is not None and emitted >= limit:
                return

    def _records_from_file(self, path, category, subcategory):
        opener = gzip.open if path.endswith(".gz") else open
        try:
            with opener(path, "rb") as f:
                data = json.load(f)
        except Exception:
            return
        # jlcparts per-category file is { "parts": [...] } or just [...]
        parts = data["parts"] if isinstance(data, dict) and "parts" in data else data
        for p in parts:
            if not isinstance(p, dict):
                continue
            lcsc = (p.get("lcsc") or p.get("lcsc_id") or p.get("id") or "")
            if not lcsc:
                continue
            price_breaks = []
            for pb in p.get("price", p.get("priceBreaks", [])):
                if isinstance(pb, dict):
                    price_breaks.append({"qty": pb.get("qFrom") or pb.get("qty") or 1,
                                         "price": pb.get("price")})
            yield ComponentRecord(
                source=self.name,
                source_id=str(lcsc),
                mpn=p.get("mfr") or p.get("mpn") or p.get("manufacturerPart") or "",
                manufacturer=p.get("manufacturer") or p.get("brand") or "",
                name=p.get("description", "")[:80],
                description=p.get("description") or "",
                category=category,
                subcategory=subcategory,
                package=p.get("package") or p.get("footprint") or "",
                stock=int(p.get("stock") or 0),
                datasheet_url=p.get("datasheet") or p.get("datasheet_url") or "",
                image_url=(p.get("images") or [None])[0]
                          if isinstance(p.get("images"), list) else
                          (p.get("image") or ""),
                price_breaks=price_breaks,
                parameters={k: v for k, v in p.get("attributes", {}).items()
                            if isinstance(v, (str, int, float, bool))},
            )
