"""JWT auth helpers — HMAC-SHA256, access + refresh tokens.

Stdlib only (no PyJWT dependency) so the server can run on minimal images.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from functools import wraps


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(s):
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def encode(payload, secret, ttl_seconds=3600):
    header = {"alg": "HS256", "typ": "JWT"}
    body = dict(payload)
    body["iat"] = int(time.time())
    body["exp"] = body["iat"] + ttl_seconds
    h = _b64(json.dumps(header, separators=(",", ":")).encode())
    p = _b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{_b64(sig)}"


def decode(token, secret):
    try:
        h, p, sig = token.split(".")
    except ValueError:
        raise ValueError("malformed token")
    expected = hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64decode(sig)):
        raise ValueError("bad signature")
    payload = json.loads(_b64decode(p))
    if payload.get("exp", 0) < time.time():
        raise ValueError("expired")
    return payload


def require_auth(f):
    """Flask decorator — requires `Authorization: Bearer <token>` header."""
    @wraps(f)
    def wrapper(*args, **kw):
        from flask import request, current_app, jsonify, g
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing bearer token"}), 401
        token = auth[len("Bearer "):]
        try:
            g.claims = decode(token, current_app.config["JWT_SECRET"])
        except ValueError as e:
            return jsonify({"error": f"invalid token: {e}"}), 401
        return f(*args, **kw)
    return wrapper


def issue_token_pair(subject, role, secret):
    access = encode({"sub": subject, "role": role, "typ": "access"}, secret, 3600)
    refresh = encode({"sub": subject, "role": role, "typ": "refresh"}, secret, 30 * 86400)
    return access, refresh


# ---- user store --------------------------------------------------------

DEFAULT_USERS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "users.json")


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()


def load_users(path=None):
    path = path or DEFAULT_USERS_FILE
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save_users(users, path=None):
    path = path or DEFAULT_USERS_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(users, f, indent=2)


def verify_password(users, username, password):
    rec = users.get(username)
    if not rec:
        return False
    salt = bytes.fromhex(rec["salt"])
    return hmac.compare_digest(rec["pwhash"], _hash(password, salt))


def create_user(username, password, role="user"):
    salt = os.urandom(16)
    return {"salt": salt.hex(), "pwhash": _hash(password, salt), "role": role}
