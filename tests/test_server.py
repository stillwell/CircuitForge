"""REST API + auth smoke tests."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAuthTokens(unittest.TestCase):
    def test_round_trip(self):
        from circuitforge.server.auth import encode, decode
        tok = encode({"sub": "alice", "role": "admin"}, "s3cret", ttl_seconds=60)
        claims = decode(tok, "s3cret")
        self.assertEqual(claims["sub"], "alice")
        self.assertEqual(claims["role"], "admin")
        with self.assertRaises(ValueError):
            decode(tok, "wrong-secret")

    def test_password_hash(self):
        from circuitforge.server.auth import create_user, verify_password
        users = {"u": create_user("u", "hunter2")}
        self.assertTrue(verify_password(users, "u", "hunter2"))
        self.assertFalse(verify_password(users, "u", "wrong"))


class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import flask  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("flask not installed")
        cls.tmpdir = tempfile.mkdtemp()
        os.environ["CIRCUITFORGE_JWT_SECRET"] = "test-secret"
        # write a known user store
        from circuitforge.server.auth import create_user, save_users, DEFAULT_USERS_FILE
        cls._original_users_path = DEFAULT_USERS_FILE
        import circuitforge.server.auth as a
        a.DEFAULT_USERS_FILE = os.path.join(cls.tmpdir, "users.json")
        save_users({"admin": create_user("admin", "admin", role="admin")})
        from circuitforge.server.api import create_app
        cls.app = create_app().test_client()

    def test_health(self):
        r = self.app.get("/api/v1/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["service"], "circuitforge")
        self.assertIn("/api/v1/health", r.get_json()["endpoints"])

    def test_login(self):
        r = self.app.post("/api/v1/auth/login",
                          json={"username": "admin", "password": "admin"})
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertIn("access_token", body)
        self.assertEqual(body["role"], "admin")

    def test_bad_login(self):
        r = self.app.post("/api/v1/auth/login",
                          json={"username": "admin", "password": "nope"})
        self.assertEqual(r.status_code, 401)

    def test_library_requires_auth(self):
        r = self.app.get("/api/v1/library")
        self.assertEqual(r.status_code, 401)

    def test_library_with_auth(self):
        r = self.app.post("/api/v1/auth/login",
                          json={"username": "admin", "password": "admin"})
        tok = r.get_json()["access_token"]
        r = self.app.get("/api/v1/library",
                         headers={"Authorization": f"Bearer {tok}"})
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertGreater(body["total"], 50)

    def test_simulate_op(self):
        r = self.app.post("/api/v1/auth/login",
                          json={"username": "admin", "password": "admin"})
        tok = r.get_json()["access_token"]
        deck = "Divider\nV1 vin 0 5\nR1 vin mid 10k\nR2 mid 0 10k\n.end\n"
        r = self.app.post("/api/v1/simulate/op",
                          data=deck,
                          headers={"Authorization": f"Bearer {tok}",
                                   "Content-Type": "text/plain"})
        self.assertEqual(r.status_code, 200)
        op = r.get_json()["operating_point"]
        self.assertAlmostEqual(op["mid"], 2.5, places=3)

    def test_simulate_tran(self):
        r = self.app.post("/api/v1/auth/login",
                          json={"username": "admin", "password": "admin"})
        tok = r.get_json()["access_token"]
        deck = ("RC\nV1 in 0 1\nR1 in out 1k\nC1 out 0 1u\n.end\n")
        r = self.app.post("/api/v1/simulate/tran",
                          json={"deck": deck, "tstop": "5m", "dt": "10u"},
                          headers={"Authorization": f"Bearer {tok}"})
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["analysis"], "tran")
        self.assertGreater(body["waveforms"]["out"][-1], 0.95)


if __name__ == "__main__":
    unittest.main()
