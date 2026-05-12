"""JLCPCB component loader.

Source: the community-maintained jlcparts project at
https://github.com/yaqwsx/jlcparts which mirrors JLCPCB's parts catalog
as a SQLite cache, rebuilt daily and published as a multi-volume zip on
the project's GitHub Pages site.

File layout (as of the project's current GitHub Pages output)
-------------------------------------------------------------
    cache.zip        — trailing volume + central directory (~7 MB)
    cache.z01..z0N   — 50 MB chunks (the project grows; we auto-probe N)

These are stitched back together with `zip -s 0 cache.zip --out single.zip`
and `unzip` (both Info-Zip tools) to recover `cache.sqlite3`, the
canonical SQLite database. We then iterate the `components` table.

Behaviour
---------
- First sync: downloads all volumes into the per-loader cache dir,
  reassembles, extracts the SQLite, and streams rows.
- Subsequent: re-uses cached volumes (24-h TTL by default) and the
  extracted SQLite. Pass `--clear` on the CLI to wipe DB rows for this
  source, or delete `data/loader_cache/jlcpcb/` to force a fresh fetch.
- `limit=N` caps the records emitted, but does not bound the download
  itself — the whole catalog is fetched before iteration starts.

Optional environment knobs
--------------------------
    JLCPCB_BASE_URL      override the URL prefix (default:
                         https://yaqwsx.github.io/jlcparts/data/)
    JLCPCB_MAX_VOLUMES   cap the volume-probe (default: 20)
    JLCPCB_SKIP_DOWNLOAD if set to "1", reuse whatever's already in the
                         cache dir (offline sync from a previous fetch).
"""

import json
import os
import sqlite3
import subprocess

from .base import Loader, LoaderError
from ..components_db import ComponentRecord


DEFAULT_BASE = "https://yaqwsx.github.io/jlcparts/data/"


class JLCPCBLoader(Loader):
    name = "jlcpcb"
    description = ("JLCPCB parts catalogue (via the community-maintained "
                   "yaqwsx/jlcparts mirror, CC0). ~600 k parts; "
                   "downloads ~400 MB split-zip SQLite cache.")

    def iter_records(self, limit=None):
        base = os.environ.get("JLCPCB_BASE_URL", DEFAULT_BASE).rstrip("/") + "/"
        # The archive grows over time; was 8 volumes when this loader was
        # first written, was 40 at last check. Allow a healthy upper bound
        # and override via JLCPCB_MAX_VOLUMES if it ever exceeds.
        max_volumes = int(os.environ.get("JLCPCB_MAX_VOLUMES", "80"))
        sqlite_path = os.path.join(self.cache_dir, "cache.sqlite3")

        if os.environ.get("JLCPCB_SKIP_DOWNLOAD", "0") != "1":
            self._download_volumes(base, max_volumes)
            self._extract(sqlite_path)

        if not os.path.exists(sqlite_path):
            raise LoaderError(
                f"expected {sqlite_path} after extract — see "
                f"data/loader_cache/jlcpcb/extract.log")

        yield from self._iter_from_sqlite(sqlite_path, limit=limit)

    # ---- download ----
    def _download_volumes(self, base, max_volumes):
        """Fetch cache.zip and cache.z01..cache.zNN, auto-probing N."""
        # tail
        self.cached_get(base + "cache.zip", "cache.zip", max_age=24 * 3600)
        # volumes — probe until first 404
        for i in range(1, max_volumes + 1):
            vname = f"cache.z{i:02d}"
            try:
                self.cached_get(base + vname, vname, max_age=24 * 3600)
            except LoaderError as e:
                # 404 means we've passed the last volume. Anything else is a real error.
                if "404" in str(e):
                    return
                raise

    # ---- extract ----
    def _extract(self, sqlite_target):
        """Reassemble the split zip and extract cache.sqlite3.

        The upstream format is a PKZip-spanned archive
        (`cache.z01..cache.zNN` then `cache.zip` for the trailing volume
        with the central directory). Info-Zip's `zip -s 0` doesn't
        round-trip this layout correctly, so we use the simpler
        `cat volumes... > single.zip` then `unzip` — unzip emits a
        "bad zipfile offset" warning at each volume boundary but auto-
        recovers and decompresses the payload intact.
        """
        cache = self.cache_dir
        single = os.path.join(cache, "_joined.zip")
        log = os.path.join(cache, "extract.log")
        cache_zip = os.path.join(cache, "cache.zip")

        # Skip re-extract if the SQLite is already newer than cache.zip
        if (os.path.exists(sqlite_target) and os.path.exists(cache_zip) and
                os.path.getmtime(sqlite_target) >= os.path.getmtime(cache_zip)):
            return

        volumes = sorted([n for n in os.listdir(cache)
                          if n.startswith("cache.z") and n != "cache.zip"])
        if not volumes:
            raise LoaderError(
                "no cache.z* volumes in loader_cache/jlcpcb/ — download failed")
        # 1. cat z01..zNN + cache.zip into one stream
        with open(single, "wb") as out, open(log, "w") as logf:
            logf.write(f"reassembling from {len(volumes)} volumes + cache.zip\n")
            for vol in volumes + ["cache.zip"]:
                src = os.path.join(cache, vol)
                logf.write(f"  + {vol} ({os.path.getsize(src)} B)\n")
                with open(src, "rb") as f:
                    while True:
                        chunk = f.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)

        joined_size = os.path.getsize(single)
        min_expected = int(os.environ.get("JLCPCB_MIN_ARCHIVE_BYTES",
                                          str(500 * 1024 * 1024)))
        if joined_size < min_expected:
            raise LoaderError(
                f"reassembled archive is only {joined_size // (1024*1024)} MB; "
                f"expected at least {min_expected // (1024*1024)} MB. Volume "
                f"set is incomplete — raise JLCPCB_MAX_VOLUMES or clear "
                f"data/loader_cache/jlcpcb/ and retry.")

        # 2. extract cache.sqlite3 from the assembled archive
        with open(log, "a") as logf:
            logf.write(f"\nunzip {single} -> {cache}\n")
            r = subprocess.run(
                ["unzip", "-o", "-j", "_joined.zip", "*.sqlite3", "-d", "."],
                cwd=cache, stdout=logf, stderr=subprocess.STDOUT)
        # unzip returns 1 on the "bad zipfile offset" warnings even though
        # the file extracted successfully — so we check by looking for the
        # SQLite, not by the return code.

        if not os.path.exists(sqlite_target):
            # Some upstream builds nest or rename the file. Find it.
            for name in os.listdir(cache):
                if name.endswith(".sqlite3"):
                    if name != os.path.basename(sqlite_target):
                        os.replace(os.path.join(cache, name), sqlite_target)
                    break

        if not os.path.exists(sqlite_target):
            raise LoaderError(
                f"unzip did not produce {sqlite_target} — see extract.log "
                f"(unzip exit code was {r.returncode}). The archive may be "
                f"corrupted; delete data/loader_cache/jlcpcb/ and retry.")

        # Reassembled archive is huge — free the disk
        try:
            os.remove(single)
        except OSError:
            pass

    # ---- iterate ----
    def _iter_from_sqlite(self, path, limit=None):
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            schema = self._inspect_schema(con)
            yield from self._iter_components(con, schema, limit=limit)
        finally:
            con.close()

    def _inspect_schema(self, con):
        """Map out which tables and columns are present so we can be tolerant
        of upstream schema drift."""
        tables = {r["name"] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        out = {"tables": tables, "components_cols": set()}
        comp_table = "components" if "components" in tables else (
                     "parts" if "parts" in tables else None)
        if comp_table:
            out["components_table"] = comp_table
            out["components_cols"] = {r["name"] for r in con.execute(
                f"PRAGMA table_info({comp_table})")}
        out["has_manufacturers"] = "manufacturers" in tables
        out["has_categories"] = "categories" in tables
        return out

    def _iter_components(self, con, schema, limit=None):
        if "components_table" not in schema:
            raise LoaderError(
                "JLCPCB SQLite has no components/parts table — schema "
                "upstream may have changed. Tables: "
                f"{sorted(schema['tables'])}")
        ct = schema["components_table"]
        cols = schema["components_cols"]

        # Build a SELECT that's tolerant of optional columns
        wants = [
            "lcsc", "mfr", "basic", "description", "datasheet", "stock",
            "price", "package", "joints", "extra", "attributes",
            "category_id", "manufacturer_id", "subcategory_id",
        ]
        select = ", ".join(f"c.{w}" for w in wants if w in cols)
        join, mfr_select, cat_select = "", "", ""
        if schema["has_manufacturers"]:
            join += " LEFT JOIN manufacturers m ON m.id = c.manufacturer_id"
            mfr_select = ", m.name AS mfr_name"
        if schema["has_categories"]:
            join += " LEFT JOIN categories cat ON cat.id = c.category_id"
            cat_select = (", cat.category AS cat_name, "
                          "cat.subcategory AS sub_name")

        sql = f"SELECT {select}{mfr_select}{cat_select} FROM {ct} c{join}"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"

        for row in con.execute(sql):
            d = dict(row)
            lcsc = d.get("lcsc")
            if lcsc is None:
                continue
            try:
                price_breaks = json.loads(d.get("price") or "[]")
                if not isinstance(price_breaks, list):
                    price_breaks = []
                price_breaks = [
                    {"qty": pb.get("qFrom") or pb.get("qty") or 1,
                     "price": pb.get("price")}
                    for pb in price_breaks if isinstance(pb, dict)
                ]
            except (ValueError, TypeError):
                price_breaks = []
            params = {}
            for key in ("attributes", "extra"):
                try:
                    blob = json.loads(d.get(key) or "{}")
                    if isinstance(blob, dict):
                        params.update({k: v for k, v in blob.items()
                                       if isinstance(v, (str, int, float, bool))})
                except (ValueError, TypeError):
                    pass
            yield ComponentRecord(
                source=self.name,
                source_id=f"C{lcsc}",
                mpn=str(d.get("mfr") or ""),
                manufacturer=str(d.get("mfr_name") or ""),
                name=str(d.get("mfr") or f"C{lcsc}")[:80],
                description=str(d.get("description") or ""),
                category=str(d.get("cat_name") or ""),
                subcategory=str(d.get("sub_name") or ""),
                package=str(d.get("package") or ""),
                pin_count=int(d.get("joints") or 0),
                datasheet_url=str(d.get("datasheet") or ""),
                stock=int(d.get("stock") or 0),
                price_breaks=price_breaks,
                parameters=params,
            )
