from flask import Flask, render_template, request, jsonify, current_app, url_for, redirect
import os
import sqlite3
from datetime import datetime

from .lookup import load_contacts_csv, find_name_local, ExternalLookup, get_number_info


def init_location_db(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        identifier TEXT,
        lat REAL,
        lon REAL,
        accuracy REAL,
        ip TEXT,
        user_agent TEXT,
        ts TEXT
    )
    """)
    conn.commit()
    conn.close()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DEFAULT_REGION=os.environ.get("DEFAULT_REGION", "US"),
    )
    if test_config:
        app.config.update(test_config)

    # initialize locations DB
    db_path = os.path.join(app.instance_path, "locations.db")
    init_location_db(db_path)
    app.config['LOCATION_DB'] = db_path

    @app.route("/")
    def index():
        # Accept form POST from the UI and redirect to a GET with the number
        if request.method == "POST":
            # form field name used in the page is "number"
            number = None
            if request.form:
                number = request.form.get("number")
            elif request.is_json:
                try:
                    number = request.get_json().get("number")
                except Exception:
                    number = None
            if number:
                return redirect(url_for("index", number=number))
            return redirect(url_for("index"))

        # GET: if ?number= is present, pass it into the template (template may handle lookup)
        number = request.args.get("number")
        context = {}
        if number:
            context["query_number"] = number
        return render_template("index.html", **context)

    @app.route("/track", methods=["GET"])
    def track():
        return render_template("track.html")

    @app.route("/track/report", methods=["POST"])
    def report_location():
        data = request.get_json(force=True) or {}
        identifier = (data.get("identifier") or "").strip() or None
        lat = data.get("lat")
        lon = data.get("lon")
        accuracy = data.get("accuracy")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        ua = request.headers.get("User-Agent", "")
        ts = datetime.utcnow().isoformat()

        conn = sqlite3.connect(app.config['LOCATION_DB'])
        conn.execute(
            "INSERT INTO locations (identifier, lat, lon, accuracy, ip, user_agent, ts) VALUES (?,?,?,?,?,?,?)",
            (identifier, lat, lon, accuracy, ip, ua, ts),
        )
        conn.commit()
        conn.close()
        return jsonify(success=True)

    @app.route("/track/view", methods=["GET"])
    def view_location():
        identifier = request.args.get("number") or request.args.get("identifier")
        if not identifier:
            return "Specify ?number=<id>", 400

        conn = sqlite3.connect(app.config['LOCATION_DB'])
        cur = conn.execute(
            "SELECT lat, lon, accuracy, ts FROM locations WHERE identifier = ? ORDER BY id DESC LIMIT 1",
            (identifier,),
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            return render_template("track_view.html", found=False)

        lat, lon, accuracy, ts = row
        return render_template(
            "track_view.html",
            found=True,
            identifier=identifier,
            lat=lat,
            lon=lon,
            accuracy=accuracy,
            ts=ts,
        )

    @app.route("/health")
    def health():
        return "ok", 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
