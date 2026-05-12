"""Browser portal for CircuitForge.

A self-contained Flask app — login, deck editor, simulation runner, waveform
viewer, library browser, PCB export. No external CDNs at runtime (Plotly is
served locally if vendored; otherwise rendered via inline canvas).
"""

import os
import secrets

from flask import (Flask, request, jsonify, render_template, redirect,
                   url_for, session, flash, send_file, abort)

from circuitforge import resources


def create_app(config=None):
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(__file__), "templates"),
                static_folder=os.path.join(os.path.dirname(__file__), "static"))
    app.secret_key = os.environ.get("CIRCUITFORGE_SESSION_SECRET",
                                    secrets.token_hex(32))
    app.config["JWT_SECRET"] = os.environ.get("CIRCUITFORGE_JWT_SECRET",
                                              "dev-secret-please-override")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    if config:
        app.config.update(config)

    @app.route("/")
    def index():
        if not session.get("user"):
            return redirect(url_for("login"))
        return render_template("index.html", user=session["user"])

    @app.route("/login", methods=["GET", "POST"])
    def login():
        from circuitforge.server.auth import load_users, verify_password
        if request.method == "POST":
            users = load_users()
            u = request.form.get("username", "")
            p = request.form.get("password", "")
            if verify_password(users, u, p):
                session["user"] = u
                session["role"] = users[u]["role"]
                return redirect(url_for("index"))
            flash("Invalid credentials.", "error")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/simulate", methods=["POST"])
    def simulate():
        if not session.get("user"):
            return jsonify({"error": "not authenticated"}), 401
        deck = request.form.get("deck", "")
        analysis = request.form.get("analysis", "op")
        try:
            from circuitforge.simulation.spice import parse_spice
            from circuitforge.simulation import Simulator
            from circuitforge.core.units import parse_value
            nl, _ = parse_spice(deck)
            sim = Simulator(nl)
            if analysis == "op":
                r = sim.op()
                return jsonify({"analysis": "op",
                                "operating_point": r.operating_point})
            if analysis == "dc":
                r = sim.dc(request.form["source"],
                           parse_value(request.form["start"]),
                           parse_value(request.form["stop"]),
                           parse_value(request.form["step"]))
            elif analysis == "ac":
                r = sim.ac(parse_value(request.form["fstart"]),
                           parse_value(request.form["fstop"]),
                           int(request.form.get("ppd", 20)))
            elif analysis == "tran":
                r = sim.tran(parse_value(request.form["tstop"]),
                             parse_value(request.form["dt"]))
            else:
                return jsonify({"error": "unknown analysis"}), 400
            return jsonify({
                "analysis": r.analysis,
                "x": list(map(float, r.independent)),
                "waveforms": {k: [float(getattr(v, "real", v)) for v in arr]
                              for k, arr in r.waveforms.items()},
                "nets": sorted(r.waveforms.keys()),
            })
        except Exception as e:
            return jsonify({"error": str(e), "type": type(e).__name__}), 400

    @app.route("/library")
    def library():
        if not session.get("user"):
            return redirect(url_for("login"))
        # Prefer the DB-backed catalog if it has any rows; fall back to JSON.
        try:
            from circuitforge.database import ComponentDB, vendor_links
            from dataclasses import asdict
            with ComponentDB() as db:
                total = db.count()
                if total > 0:
                    page = max(1, int(request.args.get("page", 1)))
                    page_size = 50
                    q = request.args.get("q", "")
                    src = request.args.get("source") or None
                    rows = db.search(q, source=src,
                                     limit=page_size, offset=(page - 1) * page_size)
                    payload = []
                    for r in rows:
                        d = asdict(r)
                        d["vendor_links"] = vendor_links(r)
                        payload.append(d)
                    return render_template(
                        "library.html",
                        entries=None,
                        db_rows=payload,
                        sources=db.sources(),
                        page=page, page_size=page_size,
                        total=total, query=q, selected_source=src)
        except Exception:
            pass
        from circuitforge.components.library import ComponentLibrary
        lib = ComponentLibrary().load_default()
        q = request.args.get("q", "")
        entries = lib.search(q) if q else list(lib)
        entries = sorted(entries, key=lambda e: (e.kind, e.name))
        return render_template("library.html", entries=entries,
                               total=len(lib), query=q,
                               db_rows=None, sources=[], page=1, page_size=999,
                               selected_source=None)

    @app.route("/help")
    def help_page():
        return render_template("help.html")

    @app.route("/images/<path:name>")
    def image(name):
        p = resources.path(name)
        if not p:
            abort(404)
        return send_file(p)

    return app


def run(host="0.0.0.0", port=5000, debug=False):
    create_app().run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    import sys
    debug = "--debug" in sys.argv
    run(debug=debug)
