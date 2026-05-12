"""KiCad official symbol + footprint library loader.

Sources:
    https://gitlab.com/kicad/libraries/kicad-symbols
    https://gitlab.com/kicad/libraries/kicad-footprints

(The GitHub mirrors at github.com/KiCad/* are also recognised.) Both are
git repositories. We do a shallow clone into the cache dir, walk the
`.kicad_sym` files, and index every contained symbol as a component
record.

The repos are large (~200 MB + 1 GB) so this loader is not enabled by
default. Call with `limit` to test before a full sync.
"""

import os
import re
import shutil
import subprocess

from .base import Loader, LoaderError
from ..components_db import ComponentRecord
from circuitforge.io.sexpr import parse, SExprError


KICAD_SYMBOL_REPO = "https://gitlab.com/kicad/libraries/kicad-symbols.git"
KICAD_FOOTPRINT_REPO = "https://gitlab.com/kicad/libraries/kicad-footprints.git"


class KiCadLoader(Loader):
    name = "kicad"
    description = ("Official KiCad symbol + footprint libraries "
                   "(github.com/KiCad/kicad-symbols + kicad-footprints).")

    def is_available(self):
        return shutil.which("git") is not None

    def iter_records(self, limit=None):
        if not self.is_available():
            raise LoaderError("kicad loader needs `git` on PATH")

        sym_dir = os.path.join(self.cache_dir, "kicad-symbols")
        fp_dir = os.path.join(self.cache_dir, "kicad-footprints")
        self._git_clone_or_pull(KICAD_SYMBOL_REPO, sym_dir)
        # footprint repo is huge; we only fetch it on explicit request via env var
        if os.environ.get("CIRCUITFORGE_KICAD_FOOTPRINTS", "0") == "1":
            self._git_clone_or_pull(KICAD_FOOTPRINT_REPO, fp_dir)

        emitted = 0
        for root, _, files in os.walk(sym_dir):
            for fn in files:
                if not fn.endswith(".kicad_sym"):
                    continue
                lib_name = fn[:-len(".kicad_sym")]
                path = os.path.join(root, fn)
                for rec in self._parse_symbol_file(path, lib_name):
                    yield rec
                    emitted += 1
                    if limit is not None and emitted >= limit:
                        return

    # ---- helpers ----
    def _git_clone_or_pull(self, url, target):
        if os.path.isdir(os.path.join(target, ".git")):
            subprocess.run(["git", "-C", target, "pull", "--ff-only", "--quiet"],
                           check=False, timeout=300)
        else:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            subprocess.run(["git", "clone", "--depth", "1", "--quiet", url, target],
                           check=True, timeout=900)

    def _parse_symbol_file(self, path, lib_name):
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
            tree = parse(text)
        except (SExprError, OSError):
            return
        if not isinstance(tree, list) or not tree or tree[0] != "kicad_symbol_lib":
            return
        for item in tree[1:]:
            if not (isinstance(item, list) and item and item[0] == "symbol"):
                continue
            name = item[1] if len(item) > 1 and isinstance(item[1], str) else None
            if not name:
                continue
            # symbol properties live as nested ("property" "Name" "Value" ...) lists
            props = {}
            pin_count = 0
            for sub in item[2:]:
                if isinstance(sub, list) and sub and sub[0] == "property" and len(sub) >= 3:
                    props[str(sub[1]).lower()] = str(sub[2])
                elif isinstance(sub, list) and sub and sub[0] == "symbol":
                    # nested unit symbol — count its pins
                    for inner in sub[2:]:
                        if isinstance(inner, list) and inner and inner[0] == "pin":
                            pin_count += 1
                elif isinstance(sub, list) and sub and sub[0] == "pin":
                    pin_count += 1
            yield ComponentRecord(
                source=self.name,
                source_id=f"{lib_name}:{name}",
                mpn=props.get("mpn", ""),
                manufacturer=props.get("manufacturer", ""),
                name=name,
                description=props.get("description", ""),
                category=lib_name,
                subcategory="",
                package=props.get("footprint", "").split(":")[-1],
                value=props.get("value", ""),
                pin_count=pin_count,
                datasheet_url=props.get("datasheet", ""),
                symbol_lib=lib_name,
                footprint_lib=props.get("footprint", ""),
            )
