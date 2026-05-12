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
        prefs = session.get("library_prefs") or {}
        default_page_size = int(prefs.get("page_size", 25))
        default_source = prefs.get("default_source", "") or None
        count_mode = prefs.get("count_mode", "fast")
        # Prefer the DB-backed catalog if it has any rows; fall back to JSON.
        try:
            from circuitforge.database import ComponentDB, vendor_links
            from dataclasses import asdict
            db = ComponentDB()
            # Avoid the slow exact COUNT(*) on page load — use fast estimate
            # for "DB has anything?" gate, exact count only when user asks.
            est = db.fast_count_estimate()
            if est > 0:
                page = max(1, int(request.args.get("page", 1)))
                try:
                    page_size = int(request.args.get("page_size", default_page_size))
                except (TypeError, ValueError):
                    page_size = default_page_size
                page_size = max(10, min(200, page_size))
                q = request.args.get("q", "")
                src = request.args.get("source") or default_source
                # Fetch one extra row to know whether a next page exists,
                # without paying for a separate COUNT.
                rows = db.search(q, source=src,
                                 limit=page_size + 1,
                                 offset=(page - 1) * page_size)
                has_next = len(rows) > page_size
                rows = rows[:page_size]
                payload = []
                for r in rows:
                    d = asdict(r)
                    d["vendor_links"] = vendor_links(r)
                    payload.append(d)

                # Total count: cached for 5 min so paginator headers don't
                # repeatedly run the expensive query. Use estimate by
                # default — user can opt into exact via settings.
                if count_mode == "exact" or request.args.get("count") == "exact":
                    total = db.cached_count(source=src)
                    total_is_exact = True
                else:
                    total = est
                    total_is_exact = False
                sources = db.sources()
                db.close()
                return render_template(
                    "library.html",
                    entries=None,
                    db_rows=payload,
                    sources=sources,
                    page=page, page_size=page_size,
                    has_next=has_next,
                    total=total, total_is_exact=total_is_exact,
                    query=q, selected_source=src,
                    page_size_options=[10, 25, 50, 100, 200],
                )
            db.close()
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

    @app.route("/settings/library", methods=["GET", "POST"])
    def library_settings():
        if not session.get("user"):
            return redirect(url_for("login"))
        if request.method == "POST":
            prefs = session.get("library_prefs") or {}
            ps = request.form.get("page_size", "25")
            try:
                ps = int(ps)
            except ValueError:
                ps = 25
            prefs["page_size"] = max(10, min(200, ps))
            prefs["default_source"] = request.form.get("default_source") or ""
            prefs["count_mode"] = request.form.get("count_mode", "fast")
            prefs["sort"] = request.form.get("sort", "stock")
            session["library_prefs"] = prefs
            flash("Library settings saved.", "message")
            return redirect(url_for("library"))
        prefs = session.get("library_prefs") or {}
        sources = []
        try:
            from circuitforge.database import ComponentDB
            with ComponentDB() as db:
                sources = db.sources()
        except Exception:
            pass
        return render_template("library_settings.html",
                               prefs=prefs, sources=sources)

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
