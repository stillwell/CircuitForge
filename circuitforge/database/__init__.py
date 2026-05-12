"""Component database — SQLite-backed catalog of ICs and components.

Bulk-loaded from public sources (JLCPCB / jlcparts, KiCad official symbol
and footprint libraries, DigiKey, Mouser) and queried by CLI, REST, and
the web portal.

Stdlib-only: `sqlite3`, `urllib.request`, `csv`, `json`, `subprocess`.
"""

from .components_db import ComponentDB, ComponentRecord, default_db_path
from .loaders import LOADERS, get_loader

__all__ = ["ComponentDB", "ComponentRecord", "default_db_path",
           "LOADERS", "get_loader"]
