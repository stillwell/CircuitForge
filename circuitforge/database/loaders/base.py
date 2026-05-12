"""Base class for component-database loaders."""

import os
import sys
import time
import urllib.request
import urllib.error
from typing import Iterable, Optional


class LoaderError(RuntimeError):
    pass


class Loader:
    """Abstract base. Subclasses implement `iter_records()` and `name`.

    Sync flow:
        loader = SomeLoader()
        added, updated = loader.sync(db, limit=None, progress=print)
    """

    name = "base"
    description = ""
    requires_internet = True
    user_agent = "CircuitForge/0.1 (+https://github.com/stillwell/CircuitForge)"

    def __init__(self, cache_dir=None, http_timeout=60):
        self.cache_dir = cache_dir or os.path.join(
            os.environ.get("CIRCUITFORGE_DATA_DIR",
                           os.path.join(os.path.dirname(__file__),
                                        "..", "..", "..", "data")),
            "loader_cache", self.name)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.http_timeout = http_timeout

    # ---- subclass hooks ----
    def iter_records(self, limit=None):
        """Yield ComponentRecord objects. Must be implemented by subclasses."""
        raise NotImplementedError

    def is_available(self):
        """Return True if this loader is configured/can run. Override for
        loaders that need API keys."""
        return True

    # ---- shared helpers ----
    def http_get(self, url, dest_path=None, retries=3, backoff=2.0,
                 progress=None, accept=None, headers=None):
        """Download a URL with retries. If dest_path given, stream to disk.

        Returns the local path (if dest_path) or the in-memory bytes.
        """
        req_headers = {"User-Agent": self.user_agent}
        if accept:
            req_headers["Accept"] = accept
        if headers:
            req_headers.update(headers)
        last_err = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=req_headers)
                with urllib.request.urlopen(req, timeout=self.http_timeout) as resp:
                    total = int(resp.headers.get("Content-Length") or 0)
                    if dest_path:
                        tmp = dest_path + ".part"
                        downloaded = 0
                        with open(tmp, "wb") as f:
                            while True:
                                chunk = resp.read(65536)
                                if not chunk:
                                    break
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress and total:
                                    progress(downloaded, total)
                        os.replace(tmp, dest_path)
                        return dest_path
                    return resp.read()
            except (urllib.error.URLError, urllib.error.HTTPError,
                    TimeoutError, ConnectionResetError) as e:
                last_err = e
                if attempt + 1 < retries:
                    time.sleep(backoff ** attempt)
        raise LoaderError(f"http_get({url}) failed after {retries} retries: {last_err}")

    def cached_get(self, url, filename, max_age=86400, progress=None):
        """Download to cache_dir/filename unless still fresh."""
        path = os.path.join(self.cache_dir, filename)
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age:
            return path
        return self.http_get(url, dest_path=path, progress=progress)

    # ---- entry point ----
    def sync(self, db, limit=None, progress=None):
        """Stream records into the DB. Returns (added, updated)."""
        if not self.is_available():
            raise LoaderError(
                f"loader '{self.name}' is not configured (likely missing API key)")
        sync_id = db.start_sync(self.name)
        try:
            added, updated = db.upsert_many(
                self.iter_records(limit=limit), progress=progress)
            db.finish_sync(sync_id, added, updated, status="ok")
            return added, updated
        except Exception as e:
            db.finish_sync(sync_id, 0, 0, status="error", error=str(e))
            raise
