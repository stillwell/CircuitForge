"""SQLite-backed component catalog.

Schema
------

components
  id                  INTEGER PRIMARY KEY AUTOINCREMENT
  source              TEXT NOT NULL          -- 'jlcpcb' | 'kicad' | 'digikey' | 'mouser' | 'snapeda'
  source_id           TEXT NOT NULL          -- vendor's part id (unique per source)
  mpn                 TEXT                   -- manufacturer part number
  manufacturer        TEXT
  name                TEXT                   -- short name / library symbol name
  description         TEXT
  category            TEXT                   -- vendor category path
  subcategory         TEXT
  package             TEXT                   -- e.g. SOIC-8, 0805, LQFP-48
  value               TEXT
  pin_count           INTEGER
  datasheet_url       TEXT
  image_url           TEXT
  stock               INTEGER                -- inventory snapshot
  price_breaks        TEXT                   -- JSON: [{"qty":1,"price":0.012}, ...]
  parameters          TEXT                   -- JSON: free-form attributes
  symbol_lib          TEXT                   -- KiCad symbol library name
  footprint_lib       TEXT                   -- KiCad footprint library name
  updated_at          INTEGER                -- unix seconds
  UNIQUE(source, source_id)

components_fts        -- FTS5 virtual table mirroring searchable text columns

sync_log
  source              TEXT NOT NULL
  started_at          INTEGER
  finished_at         INTEGER
  records_added       INTEGER
  records_updated     INTEGER
  status              TEXT
  error               TEXT
"""

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Iterable, List, Dict, Any


SCHEMA_VERSION = 1


def default_db_path():
    env = os.environ.get("CIRCUITFORGE_DB")
    if env:
        return env
    data_dir = os.environ.get("CIRCUITFORGE_DATA_DIR",
                              os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    data_dir = os.path.abspath(data_dir)
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "components.db")


@dataclass
class ComponentRecord:
    source: str
    source_id: str
    mpn: str = ""
    manufacturer: str = ""
    name: str = ""
    description: str = ""
    category: str = ""
    subcategory: str = ""
    package: str = ""
    value: str = ""
    pin_count: int = 0
    datasheet_url: str = ""
    image_url: str = ""
    stock: int = 0
    price_breaks: list = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    symbol_lib: str = ""
    footprint_lib: str = ""

    @classmethod
    def from_row(cls, row):
        d = dict(row)
        d["price_breaks"] = json.loads(d.get("price_breaks") or "[]")
        d["parameters"] = json.loads(d.get("parameters") or "{}")
        for k in ("pin_count", "stock"):
            d[k] = d.get(k) or 0
        d.pop("updated_at", None); d.pop("id", None)
        # only kwargs we accept
        valid = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in valid})


class ComponentDB:
    """SQLite catalog with FTS5 full-text search."""

    def __init__(self, path=None):
        self.path = path or default_db_path()
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()
        # detect FTS5 availability once
        try:
            self.conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS components_fts "
                "USING fts5(name, mpn, manufacturer, description, category, "
                "package, content='components', content_rowid='id')")
            # keep FTS in sync with the base table via triggers
            self.conn.executescript("""
                CREATE TRIGGER IF NOT EXISTS components_ai
                  AFTER INSERT ON components BEGIN
                    INSERT INTO components_fts(rowid, name, mpn, manufacturer,
                                               description, category, package)
                    VALUES (new.id, new.name, new.mpn, new.manufacturer,
                            new.description, new.category, new.package);
                END;
                CREATE TRIGGER IF NOT EXISTS components_ad
                  AFTER DELETE ON components BEGIN
                    INSERT INTO components_fts(components_fts, rowid, name, mpn,
                                               manufacturer, description, category, package)
                    VALUES('delete', old.id, old.name, old.mpn,
                           old.manufacturer, old.description, old.category, old.package);
                END;
                CREATE TRIGGER IF NOT EXISTS components_au
                  AFTER UPDATE ON components BEGIN
                    INSERT INTO components_fts(components_fts, rowid, name, mpn,
                                               manufacturer, description, category, package)
                    VALUES('delete', old.id, old.name, old.mpn,
                           old.manufacturer, old.description, old.category, old.package);
                    INSERT INTO components_fts(rowid, name, mpn, manufacturer,
                                               description, category, package)
                    VALUES (new.id, new.name, new.mpn, new.manufacturer,
                            new.description, new.category, new.package);
                END;
            """)
            self.fts_available = True
        except sqlite3.OperationalError:
            self.fts_available = False

    def close(self):
        self.conn.close()

    def __enter__(self): return self
    def __exit__(self, *a): self.close()

    # ---- schema ----
    def _migrate(self):
        c = self.conn
        c.executescript(f"""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                mpn TEXT,
                manufacturer TEXT,
                name TEXT,
                description TEXT,
                category TEXT,
                subcategory TEXT,
                package TEXT,
                value TEXT,
                pin_count INTEGER DEFAULT 0,
                datasheet_url TEXT,
                image_url TEXT,
                stock INTEGER DEFAULT 0,
                price_breaks TEXT,
                parameters TEXT,
                symbol_lib TEXT,
                footprint_lib TEXT,
                updated_at INTEGER NOT NULL,
                UNIQUE(source, source_id)
            );
            CREATE INDEX IF NOT EXISTS idx_components_mpn         ON components(mpn);
            CREATE INDEX IF NOT EXISTS idx_components_mfr         ON components(manufacturer);
            CREATE INDEX IF NOT EXISTS idx_components_category    ON components(category);
            CREATE INDEX IF NOT EXISTS idx_components_package     ON components(package);
            CREATE INDEX IF NOT EXISTS idx_components_source      ON components(source);
            CREATE INDEX IF NOT EXISTS idx_components_name_lower  ON components(lower(name));
            CREATE INDEX IF NOT EXISTS idx_components_mpn_lower   ON components(lower(mpn));
            -- Covering indices for the paginated list view. Without these,
            -- "ORDER BY stock DESC, name ASC LIMIT 50" on a multi-million-row
            -- table forces a full in-memory sort (~40 s on 4M rows). The
            -- (source, stock DESC, name) form lets SQLite walk the index
            -- and stop after `limit` rows.
            CREATE INDEX IF NOT EXISTS idx_components_stock_name
                ON components(stock DESC, name ASC);
            CREATE INDEX IF NOT EXISTS idx_components_source_stock_name
                ON components(source, stock DESC, name ASC);
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                started_at INTEGER NOT NULL,
                finished_at INTEGER,
                records_added INTEGER DEFAULT 0,
                records_updated INTEGER DEFAULT 0,
                status TEXT,
                error TEXT
            );
        """)
        cur = c.execute("SELECT version FROM schema_version")
        row = cur.fetchone()
        if row is None:
            c.execute("INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))
        c.commit()

    # ---- writes ----
    def upsert(self, rec: ComponentRecord) -> bool:
        """Insert or update one record. Returns True if a new row was inserted."""
        now = int(time.time())
        c = self.conn
        cur = c.execute(
            "SELECT id FROM components WHERE source=? AND source_id=?",
            (rec.source, rec.source_id),
        )
        existing = cur.fetchone()
        params = (
            rec.source, rec.source_id, rec.mpn, rec.manufacturer, rec.name,
            rec.description, rec.category, rec.subcategory, rec.package,
            rec.value, rec.pin_count, rec.datasheet_url, rec.image_url,
            rec.stock,
            json.dumps(rec.price_breaks, separators=(",", ":")),
            json.dumps(rec.parameters, separators=(",", ":")),
            rec.symbol_lib, rec.footprint_lib, now,
        )
        if existing:
            c.execute("""
                UPDATE components SET
                    mpn=?, manufacturer=?, name=?, description=?, category=?,
                    subcategory=?, package=?, value=?, pin_count=?,
                    datasheet_url=?, image_url=?, stock=?,
                    price_breaks=?, parameters=?,
                    symbol_lib=?, footprint_lib=?, updated_at=?
                WHERE id=?
            """, params[2:] + (existing["id"],))
            inserted = False
        else:
            c.execute("""
                INSERT INTO components
                    (source, source_id, mpn, manufacturer, name, description,
                     category, subcategory, package, value, pin_count,
                     datasheet_url, image_url, stock, price_breaks,
                     parameters, symbol_lib, footprint_lib, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, params)
            inserted = True
        return inserted

    def upsert_many(self, records: Iterable[ComponentRecord], batch=2000,
                    progress=None):
        """Bulk upsert. Returns (added, updated)."""
        added = updated = 0
        batch_buf = []
        for r in records:
            batch_buf.append(r)
            if len(batch_buf) >= batch:
                a, u = self._flush_batch(batch_buf)
                added += a; updated += u
                batch_buf.clear()
                if progress:
                    progress(added + updated)
        if batch_buf:
            a, u = self._flush_batch(batch_buf)
            added += a; updated += u
            if progress:
                progress(added + updated)
        # Rebuild FTS index after bulk load
        if self.fts_available:
            self.conn.execute("INSERT INTO components_fts(components_fts) VALUES ('rebuild')")
            self.conn.commit()
        return added, updated

    def _flush_batch(self, batch):
        """Transactional flush of a list of ComponentRecord."""
        added = updated = 0
        with self.conn:
            for r in batch:
                if self.upsert(r):
                    added += 1
                else:
                    updated += 1
        return added, updated

    # ---- sync_log ----
    def start_sync(self, source) -> int:
        cur = self.conn.execute(
            "INSERT INTO sync_log(source, started_at, status) VALUES (?,?,?)",
            (source, int(time.time()), "running"))
        self.conn.commit()
        return cur.lastrowid

    def finish_sync(self, sync_id, added, updated, status="ok", error=None):
        self.conn.execute(
            "UPDATE sync_log SET finished_at=?, records_added=?, "
            "records_updated=?, status=?, error=? WHERE id=?",
            (int(time.time()), added, updated, status, error, sync_id))
        self.conn.commit()

    # ---- queries ----
    def search(self, query="", source=None, category=None, package=None,
               manufacturer=None, limit=50, offset=0):
        """Search the catalogue. Combines FTS for `query` with structured
        SQL filters for source/category/package/manufacturer."""
        clauses, args = [], []
        fts_ids = None
        if query and self.fts_available:
            # First pass: pull a generous superset of FTS-matching IDs, then
            # apply structured filters in the second pass. We multiply the
            # caller's limit so structured filters don't starve.
            fts_limit = (limit + offset) * 10 + 200
            fts_rows = self.conn.execute(
                "SELECT rowid FROM components_fts WHERE components_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (self._fts_escape(query), fts_limit)).fetchall()
            fts_ids = [r["rowid"] for r in fts_rows]
            if not fts_ids:
                return []
            placeholders = ",".join("?" for _ in fts_ids)
            clauses.append(f"id IN ({placeholders})")
            args.extend(fts_ids)
        elif query:
            # No FTS — fall back to LIKE.
            q = f"%{query}%"
            clauses.append(
                "(name LIKE ? OR mpn LIKE ? OR manufacturer LIKE ? OR description LIKE ?)")
            args.extend([q, q, q, q])
        if source:        clauses.append("source = ?");        args.append(source)
        if category:      clauses.append("category LIKE ?");   args.append(f"%{category}%")
        if package:       clauses.append("package = ?");       args.append(package)
        if manufacturer:  clauses.append("manufacturer = ?");  args.append(manufacturer)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""

        if fts_ids:
            # Preserve FTS rank order by joining on a temporary case expression
            order_case = "CASE id " + " ".join(
                f"WHEN {fid} THEN {i}" for i, fid in enumerate(fts_ids)
            ) + " END"
            rows = self.conn.execute(
                f"SELECT * FROM components {where} "
                f"ORDER BY {order_case} LIMIT ? OFFSET ?",
                args + [limit, offset]).fetchall()
        else:
            rows = self.conn.execute(
                f"SELECT * FROM components {where} "
                f"ORDER BY stock DESC, name ASC LIMIT ? OFFSET ?",
                args + [limit, offset]).fetchall()
        return [ComponentRecord.from_row(r) for r in rows]

    def get(self, source, source_id):
        row = self.conn.execute(
            "SELECT * FROM components WHERE source=? AND source_id=?",
            (source, source_id)).fetchone()
        return ComponentRecord.from_row(row) if row else None

    def get_by_id(self, id):
        row = self.conn.execute("SELECT * FROM components WHERE id=?", (id,)).fetchone()
        return ComponentRecord.from_row(row) if row else None

    def get_by_mpn(self, mpn):
        rows = self.conn.execute(
            "SELECT * FROM components WHERE lower(mpn) = lower(?)", (mpn,)).fetchall()
        return [ComponentRecord.from_row(r) for r in rows]

    def count(self, source=None):
        if source:
            row = self.conn.execute(
                "SELECT COUNT(*) AS n FROM components WHERE source=?", (source,)).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) AS n FROM components").fetchone()
        return row["n"]

    # Per-process count cache. SELECT COUNT(*) on a 4M-row table takes ~700 ms;
    # on a per-source filtered count it can be ~3 s. We cache for the lifetime
    # of the DB instance (or a TTL) since the count only changes on sync.
    _count_cache = None
    _count_cache_t = 0

    def cached_count(self, source=None, ttl_seconds=300):
        """COUNT(*) cached for `ttl_seconds`. Use this for paginator headers."""
        key = source or "__all__"
        cache = self._count_cache or {}
        now = time.time()
        entry = cache.get(key)
        if entry is not None and now - entry[1] < ttl_seconds:
            return entry[0]
        n = self.count(source=source)
        cache[key] = (n, now)
        self._count_cache = cache
        return n

    def invalidate_count_cache(self):
        self._count_cache = None

    def fast_count_estimate(self):
        """Cheap approximation: returns sqlite_sequence.seq for `components`,
        which is the maximum id ever allocated. Always >= true row count and
        usually very close. O(1) — useful for UIs that just need order of
        magnitude on a huge catalogue."""
        try:
            row = self.conn.execute(
                "SELECT seq FROM sqlite_sequence WHERE name='components'").fetchone()
            return int(row["seq"]) if row else 0
        except sqlite3.OperationalError:
            return 0

    def stats(self):
        return {
            "total": self.count(),
            "by_source": dict(self.conn.execute(
                "SELECT source, COUNT(*) AS n FROM components GROUP BY source").fetchall()),
            "top_manufacturers": dict(self.conn.execute(
                "SELECT manufacturer, COUNT(*) AS n FROM components "
                "WHERE manufacturer IS NOT NULL AND manufacturer != '' "
                "GROUP BY manufacturer ORDER BY n DESC LIMIT 20").fetchall()),
            "top_categories": dict(self.conn.execute(
                "SELECT category, COUNT(*) AS n FROM components "
                "WHERE category IS NOT NULL AND category != '' "
                "GROUP BY category ORDER BY n DESC LIMIT 20").fetchall()),
            "last_syncs": [dict(r) for r in self.conn.execute(
                "SELECT source, started_at, finished_at, records_added, "
                "records_updated, status FROM sync_log "
                "ORDER BY started_at DESC LIMIT 10").fetchall()],
            "schema_version": self.conn.execute(
                "SELECT version FROM schema_version").fetchone()["version"],
        }

    def sources(self):
        rows = self.conn.execute(
            "SELECT DISTINCT source FROM components ORDER BY source").fetchall()
        return [r["source"] for r in rows]

    def clear_source(self, source):
        with self.conn:
            self.conn.execute("DELETE FROM components WHERE source=?", (source,))

    @staticmethod
    def _fts_escape(q):
        """Escape an FTS5 MATCH query. Each token becomes a quoted prefix match
        (e.g. `LM78` → `"LM78"*`), and double-quotes inside terms are doubled."""
        toks = [t for t in q.split() if t]
        if not toks:
            return '""'
        out = []
        for t in toks:
            t = t.replace('"', '""')
            out.append(f'"{t}"*')
        return " ".join(out)
