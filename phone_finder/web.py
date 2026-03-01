from flask import Flask, render_template, request
import os
import sqlite3
from datetime import datetime
from flask import current_app, request, jsonify

from .lookup import load_contacts_csv, find_name_local, ExternalLookup, get_number_info


def init_location_db(db_path):
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
    )""")
    conn.commit()
    conn.close()


def create_app(test_config=None):
    # Templates are located in package folder phone_finder/templates
    package_dir = os.path.dirname(__file__)
    templates_dir = os.path.join(package_dir, "templates")
    app = Flask(__name__, template_folder=templates_dir)

    app.config.from_mapping(
        # If CONTACTS_PATH is not set, we will not attempt local CSV lookups.
        CONTACTS_PATH=os.environ.get("CONTACTS_PATH", ""),
        DEFAULT_REGION=os.environ.get("DEFAULT_REGION", "US"),
    )

    if test_config:
        app.config.update(test_config)

    db_path = os.path.join(app.instance_path, "locations.db")
    os.makedirs(app.instance_path, exist_ok=True)
    init_location_db(db_path)
    app.config['LOCATION_DB'] = db_path

    @app.route("/", methods=("GET", "POST"))
    def index():
        result = None
        hint = None
        error = None
        number = ""

        if request.method == "POST":
            number = (request.form.get("number") or "").strip()
            contacts = {}
            if app.config.get("CONTACTS_PATH"):
                try:
                    contacts = load_contacts_csv(app.config["CONTACTS_PATH"], default_region=app.config["DEFAULT_REGION"])
                except FileNotFoundError:
                    contacts = {}
                    error = f"Contacts file not found: {app.config['CONTACTS_PATH']}"

            if not error:
                name = find_name_local(number, contacts, default_region=app.config["DEFAULT_REGION"])
                if name:
                    result = {"found": True, "name": name}
                else:
                    # Prepare external lookup clients from environment
                    sid = os.environ.get("TWILIO_ACCOUNT_SID")
                    token = os.environ.get("TWILIO_AUTH_TOKEN")
                    numverify_key = os.environ.get("NUMVERIFY_API_KEY")
                    ext = ExternalLookup(numverify_key=numverify_key, twilio_sid=sid, twilio_token=token)

                    oc_key = os.environ.get("OPENCORPORATES_API_KEY")
                    yelp_key = os.environ.get("YELP_API_KEY")

                    # Try providers in priority order until we find a name
                    # 1) OpenCorporates (company)
                    if oc_key:
                        ok, remote_name = ext.lookup_opencorporates(number, default_region=app.config["DEFAULT_REGION"])
                        if ok and remote_name:
                            result = {"found": True, "name": remote_name}

                    # 2) Yelp Fusion (business)
                    if not result and yelp_key:
                        ok, remote_name = ext.lookup_yelp(number, default_region=app.config["DEFAULT_REGION"])
                        if ok and remote_name:
                            result = {"found": True, "name": remote_name}

                    # 4) Twilio CNAM (if credentials present)
                    if not result and sid and token:
                        ok, remote_name = ext.lookup_twilio(number, default_region=app.config["DEFAULT_REGION"])
                        if ok and remote_name:
                            result = {"found": True, "name": remote_name}

                    # 5) NumVerify (best-effort hints)
                    if not result and numverify_key:
                        ok, hint = ext.lookup_numverify(number, default_region=app.config["DEFAULT_REGION"])

                    # If still no exact name, return metadata
                    if not result:
                        result = {"found": False}
                        meta = get_number_info(number, default_region=app.config["DEFAULT_REGION"])
                        result["meta"] = meta

        return render_template("index.html", result=result, hint=hint, error=error, number=number)

    @app.route("/health")
    def health():
        return "ok", 200

    # new endpoint: serve tracking page
    @app.route("/track", methods=["GET"])
    def track_page():
        return render_template("track.html")

    # new endpoint: receive reports
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

        db_path = current_app.config.get("LOCATION_DB")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO locations (identifier, lat, lon, accuracy, ip, user_agent, ts) VALUES (?,?,?,?,?,?,?)",
            (identifier, lat, lon, accuracy, ip, ua, ts),
        )
        conn.commit()
        conn.close()
        return jsonify(success=True)

    # new endpoint: view last known location for identifier
    @app.route("/track/view", methods=["GET"])
    def view_location():
        identifier = request.args.get("number") or request.args.get("identifier")
        if not identifier:
            return "Specify ?number=<id>", 400
        db_path = current_app.config.get("LOCATION_DB")
        conn = sqlite3.connect(db_path)
        cur = conn.execute(
            "SELECT lat, lon, accuracy, ts FROM locations WHERE identifier = ? ORDER BY id DESC LIMIT 1",
            (identifier,),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return render_template("track_view.html", found=False)
        lat, lon, accuracy, ts = row
        return render_template("track_view.html", found=True, lat=lat, lon=lon, accuracy=accuracy, ts=ts, identifier=identifier)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
