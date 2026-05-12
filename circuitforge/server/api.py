"""CircuitForge REST API.

A Flask service exposing the simulator, library, format I/O, and PCB ops
over HTTP. Mirrors the multi-tier deployment pattern used by MedPharm ERP
(run_cloud.py): JWT auth, CORS, health check, environment-driven config,
Gunicorn-ready.

Endpoints
---------
    GET  /api/v1/health
    POST /api/v1/auth/login                {username, password} → tokens
    POST /api/v1/auth/refresh              {refresh_token}      → access
    GET  /api/v1/library                   ?q=…
    GET  /api/v1/library/<name>
    POST /api/v1/simulate/op               body: SPICE deck (text or JSON)
    POST /api/v1/simulate/dc               body: {deck, source, start, stop, step}
    POST /api/v1/simulate/ac               body: {deck, fstart, fstop, ppd}
    POST /api/v1/simulate/tran             body: {deck, tstop, dt, tstart?}
    POST /api/v1/convert/spice-to-svg      body: {deck}
    POST /api/v1/pcb/gerber                body: KiCAD .kicad_pcb text → zip
    POST /api/v1/pcb/drill                 body: KiCAD .kicad_pcb text → drl
    POST /api/v1/pcb/drc                   body: KiCAD .kicad_pcb text → violations
    GET  /api/v1/qr                        → ngrok QR PNG (if configured)
    GET  /api/v1/server-config             → JSON for mobile/desktop clients
"""

import io
import json
import os
import tempfile
import zipfile

from flask import Flask, request, jsonify, send_file, g
from flask_cors import CORS

from circuitforge import __version__
from .auth import (encode, decode, require_auth, issue_token_pair,
                   load_users, save_users, verify_password, create_user)


def create_app(config=None):
    app = Flask(__name__)
    app.config["JWT_SECRET"] = os.environ.get(
        "CIRCUITFORGE_JWT_SECRET", "dev-secret-please-override")
    app.config["JWT_TTL_SECONDS"] = int(os.environ.get(
        "CIRCUITFORGE_TOKEN_TTL", 3600))
    app.config["ALLOWED_ORIGINS"] = os.environ.get(
        "CIRCUITFORGE_ALLOWED_ORIGINS", "*")
    if config:
        app.config.update(config)
    CORS(app, origins=app.config["ALLOWED_ORIGINS"])
    _register_routes(app)
    _ensure_default_user(app)
    return app


def _ensure_default_user(app):
    users = load_users()
    if not users:
        users["admin"] = create_user("admin", "admin", role="admin")
        save_users(users)
        app.logger.warning(
            "Created default admin user with password 'admin'. "
            "CHANGE THIS via POST /api/v1/auth/register.")


def _register_routes(app):

    @app.errorhandler(Exception)
    def _err(e):
        app.logger.exception("unhandled")
        return jsonify({"error": type(e).__name__, "message": str(e)}), 500

    # ---- health & config ----
    @app.route("/api/v1/health")
    def health():
        return jsonify({
            "status": "ok",
            "service": "circuitforge",
            "version": __version__,
            "endpoints": _endpoint_index(app),
        })

    @app.route("/api/v1/server-config")
    def server_config():
        public_url = _read_public_url()
        return jsonify({
            "api_base": (public_url + "/api/v1") if public_url else None,
            "version": __version__,
            "features": ["simulate", "library", "gerber", "drill", "drc", "kicad-io"],
        })

    # ---- auth ----
    @app.route("/api/v1/auth/login", methods=["POST"])
    def login():
        body = request.get_json(silent=True) or {}
        u = body.get("username", ""); p = body.get("password", "")
        users = load_users()
        if not verify_password(users, u, p):
            return jsonify({"error": "invalid credentials"}), 401
        access, refresh = issue_token_pair(u, users[u]["role"], app.config["JWT_SECRET"])
        return jsonify({"access_token": access, "refresh_token": refresh,
                        "token_type": "Bearer", "username": u,
                        "role": users[u]["role"]})

    @app.route("/api/v1/auth/refresh", methods=["POST"])
    def refresh():
        body = request.get_json(silent=True) or {}
        try:
            claims = decode(body.get("refresh_token", ""), app.config["JWT_SECRET"])
        except ValueError as e:
            return jsonify({"error": str(e)}), 401
        if claims.get("typ") != "refresh":
            return jsonify({"error": "not a refresh token"}), 401
        access = encode({"sub": claims["sub"], "role": claims["role"],
                         "typ": "access"},
                        app.config["JWT_SECRET"],
                        app.config["JWT_TTL_SECONDS"])
        return jsonify({"access_token": access, "token_type": "Bearer"})

    @app.route("/api/v1/auth/register", methods=["POST"])
    @require_auth
    def register():
        if g.claims.get("role") != "admin":
            return jsonify({"error": "admin only"}), 403
        body = request.get_json(silent=True) or {}
        u = body.get("username", ""); p = body.get("password", "")
        role = body.get("role", "user")
        if not u or not p:
            return jsonify({"error": "username and password required"}), 400
        users = load_users()
        users[u] = create_user(u, p, role=role)
        save_users(users)
        return jsonify({"created": u, "role": role})

    @app.route("/api/v1/auth/me")
    @require_auth
    def me():
        return jsonify(g.claims)

    # ---- library ----
    @app.route("/api/v1/library")
    @require_auth
    def library_search():
        from circuitforge.components.library import ComponentLibrary
        lib = ComponentLibrary().load_default()
        q = request.args.get("q", "")
        kind = request.args.get("kind")
        entries = lib.search(q, kind=kind) if q else list(lib)
        return jsonify({
            "total": len(lib),
            "matches": len(entries),
            "entries": [_lib_entry(e) for e in entries[:200]],
        })

    @app.route("/api/v1/library/<name>")
    @require_auth
    def library_get(name):
        from circuitforge.components.library import ComponentLibrary
        e = ComponentLibrary().load_default().get(name)
        if e is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(_lib_entry(e))

    # ---- simulation ----
    @app.route("/api/v1/simulate/op", methods=["POST"])
    @require_auth
    def sim_op():
        deck = _extract_deck()
        from circuitforge.simulation.spice import parse_spice
        from circuitforge.simulation import dc_operating_point
        nl, _ = parse_spice(deck)
        op = dc_operating_point(nl)
        return jsonify({"analysis": "op", "operating_point": op})

    @app.route("/api/v1/simulate/dc", methods=["POST"])
    @require_auth
    def sim_dc():
        body = request.get_json(force=True)
        from circuitforge.simulation.spice import parse_spice
        from circuitforge.simulation import Simulator
        from circuitforge.core.units import parse_value
        nl, _ = parse_spice(body["deck"])
        r = Simulator(nl).dc(body["source"],
                             parse_value(body["start"]),
                             parse_value(body["stop"]),
                             parse_value(body["step"]))
        return jsonify(_result_to_json(r))

    @app.route("/api/v1/simulate/ac", methods=["POST"])
    @require_auth
    def sim_ac():
        body = request.get_json(force=True)
        from circuitforge.simulation.spice import parse_spice
        from circuitforge.simulation import Simulator
        from circuitforge.core.units import parse_value
        nl, _ = parse_spice(body["deck"])
        r = Simulator(nl).ac(parse_value(body["fstart"]),
                             parse_value(body["fstop"]),
                             int(body.get("ppd", 20)))
        return jsonify(_result_to_json(r))

    @app.route("/api/v1/simulate/tran", methods=["POST"])
    @require_auth
    def sim_tran():
        body = request.get_json(force=True)
        from circuitforge.simulation.spice import parse_spice
        from circuitforge.simulation import Simulator
        from circuitforge.core.units import parse_value
        nl, _ = parse_spice(body["deck"])
        r = Simulator(nl).tran(parse_value(body["tstop"]),
                               parse_value(body["dt"]),
                               parse_value(body.get("tstart", "0")))
        return jsonify(_result_to_json(r))

    # ---- format I/O ----
    @app.route("/api/v1/pcb/gerber", methods=["POST"])
    @require_auth
    def pcb_gerber():
        from circuitforge.io import read_kicad_pcb, write_gerber_set
        pcb_text = _extract_deck()
        with tempfile.TemporaryDirectory() as d:
            pcb_path = os.path.join(d, "in.kicad_pcb")
            with open(pcb_path, "w") as f:
                f.write(pcb_text)
            board = read_kicad_pcb(pcb_path)
            gbr_dir = os.path.join(d, "gerbers")
            paths = write_gerber_set(board, gbr_dir)
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for p in paths:
                    z.write(p, arcname=os.path.basename(p))
            buf.seek(0)
            return send_file(buf, mimetype="application/zip",
                             as_attachment=True, download_name="gerbers.zip")

    @app.route("/api/v1/pcb/drill", methods=["POST"])
    @require_auth
    def pcb_drill():
        from circuitforge.io import read_kicad_pcb, write_excellon
        pcb_text = _extract_deck()
        with tempfile.TemporaryDirectory() as d:
            pcb_path = os.path.join(d, "in.kicad_pcb")
            with open(pcb_path, "w") as f:
                f.write(pcb_text)
            board = read_kicad_pcb(pcb_path)
            drl_path = os.path.join(d, "out.drl")
            write_excellon(board, drl_path)
            return send_file(drl_path, mimetype="text/plain",
                             as_attachment=True, download_name="drill.drl")

    @app.route("/api/v1/pcb/drc", methods=["POST"])
    @require_auth
    def pcb_drc():
        from circuitforge.io import read_kicad_pcb
        from circuitforge.pcb import DRC
        pcb_text = _extract_deck()
        with tempfile.TemporaryDirectory() as d:
            pcb_path = os.path.join(d, "in.kicad_pcb")
            with open(pcb_path, "w") as f:
                f.write(pcb_text)
            board = read_kicad_pcb(pcb_path)
            violations = DRC().run(board)
            return jsonify({
                "violations": [
                    {"severity": v.severity, "rule": v.rule,
                     "message": v.message, "location": v.location}
                    for v in violations
                ]
            })

    # ---- ngrok QR ----
    @app.route("/api/v1/qr")
    def qr():
        from .qr import generate_qr_for_config
        path = generate_qr_for_config()
        if path is None or not os.path.exists(path):
            return jsonify({"error": "no public URL available"}), 404
        return send_file(path, mimetype="image/png")


def _lib_entry(e):
    return {"name": e.name, "kind": e.kind, "description": e.description,
            "value": e.value, "footprint": e.footprint, "pins": e.pins,
            "manufacturer": e.manufacturer, "datasheet": e.datasheet}


def _extract_deck():
    """Accept body as text/plain, application/x-spice, or JSON with 'deck' key."""
    if request.is_json:
        body = request.get_json(silent=True) or {}
        return body.get("deck", "")
    return request.get_data(as_text=True)


def _result_to_json(result):
    out = {"analysis": result.analysis,
           "meta": result.meta or {}}
    if result.independent is not None:
        out["x"] = list(map(float, result.independent.real
                            if hasattr(result.independent, "real")
                            else result.independent))
    if result.operating_point:
        out["operating_point"] = result.operating_point
    if result.waveforms:
        out["waveforms"] = {}
        for k, v in result.waveforms.items():
            if hasattr(v, "real"):
                out["waveforms"][k] = list(map(float, v.real.tolist() if hasattr(v.real, "tolist") else v.real))
            else:
                out["waveforms"][k] = list(map(float, v))
    return out


def _endpoint_index(app):
    return sorted(rule.rule for rule in app.url_map.iter_rules()
                  if rule.rule.startswith("/api/"))


def _read_public_url():
    p = os.environ.get("CIRCUITFORGE_DATA_DIR",
                       os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    path = os.path.join(p, "ngrok_public_url.txt")
    if os.path.exists(path):
        return open(path).read().strip()
    return None


# ----------------------------------------------------------------------

def run(host="0.0.0.0", port=8080, debug=False):
    """Convenience: launch the API directly (uses Flask dev server)."""
    app = create_app()
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    import sys
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    run(host=host, port=port,
        debug="--debug" in sys.argv)
