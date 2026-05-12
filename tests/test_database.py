"""ComponentDB + LocalJSONLoader tests."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestComponentDB(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "components.db")

    def test_create_and_upsert(self):
        from circuitforge.database import ComponentDB, ComponentRecord
        db = ComponentDB(self.db_path)
        rec = ComponentRecord(source="test", source_id="X1",
                              mpn="ABC123", manufacturer="Acme",
                              name="Widget", description="A widget",
                              category="passive", package="0805",
                              stock=42, price_breaks=[{"qty": 1, "price": 0.05}])
        self.assertTrue(db.upsert(rec))           # inserted
        self.assertFalse(db.upsert(rec))          # update on second call
        self.assertEqual(db.count(), 1)
        got = db.get("test", "X1")
        self.assertEqual(got.mpn, "ABC123")
        self.assertEqual(got.stock, 42)
        self.assertEqual(got.price_breaks[0]["price"], 0.05)
        db.close()

    def test_search_like_and_fts(self):
        from circuitforge.database import ComponentDB, ComponentRecord
        db = ComponentDB(self.db_path)
        for i, mpn in enumerate(["LM7805", "LM7812", "LM358", "LM741", "NE555"]):
            db.upsert(ComponentRecord(source="test", source_id=str(i),
                                      mpn=mpn, manufacturer="TI",
                                      name=mpn, description=f"chip {mpn}",
                                      category="integrated", package="DIP-8"))
        results = db.search("LM78")
        names = [r.mpn for r in results]
        self.assertIn("LM7805", names)
        self.assertIn("LM7812", names)
        results = db.search("", manufacturer="TI")
        self.assertEqual(len(results), 5)
        db.close()

    def test_local_loader_round_trip(self):
        from circuitforge.database import ComponentDB
        from circuitforge.database.loaders import LocalJSONLoader
        db = ComponentDB(self.db_path)
        loader = LocalJSONLoader()
        added, _ = loader.sync(db, limit=10)
        self.assertGreater(added, 0)
        self.assertGreaterEqual(db.count("local"), added)
        stats = db.stats()
        self.assertEqual(stats["by_source"]["local"], db.count("local"))
        self.assertGreater(len(stats["last_syncs"]), 0)
        db.close()

    def test_sync_log_records(self):
        from circuitforge.database import ComponentDB
        from circuitforge.database.loaders import LocalJSONLoader
        db = ComponentDB(self.db_path)
        LocalJSONLoader().sync(db, limit=3)
        rows = db.conn.execute(
            "SELECT source, status, records_added FROM sync_log").fetchall()
        self.assertGreater(len(rows), 0)
        self.assertEqual(rows[-1]["status"], "ok")
        db.close()

    def test_loaders_registry(self):
        from circuitforge.database import LOADERS, get_loader
        for name in ("jlcpcb", "kicad", "digikey", "mouser", "octopart", "local"):
            self.assertIn(name, LOADERS)
        loader = get_loader("local")()
        self.assertEqual(loader.name, "local")
        with self.assertRaises(Exception):
            get_loader("nonsense-source")


class TestLoaderAvailability(unittest.TestCase):
    def test_keyed_loaders_not_available_without_env(self):
        for k in ("DIGIKEY_CLIENT_ID", "DIGIKEY_CLIENT_SECRET",
                  "MOUSER_API_KEY", "NEXAR_TOKEN"):
            os.environ.pop(k, None)
        from circuitforge.database.loaders import (DigiKeyLoader, MouserLoader,
                                                   OctopartLoader, LocalJSONLoader)
        self.assertFalse(DigiKeyLoader().is_available())
        self.assertFalse(MouserLoader().is_available())
        self.assertFalse(OctopartLoader().is_available())
        self.assertTrue(LocalJSONLoader().is_available())


if __name__ == "__main__":
    unittest.main()
