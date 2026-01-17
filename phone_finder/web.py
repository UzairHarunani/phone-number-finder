from flask import Flask, render_template, request
import os

from .lookup import load_contacts_csv, find_name_local, ExternalLookup, get_number_info


def create_app(test_config=None):
    # Templates are located in package folder phone_finder/templates
    package_dir = os.path.dirname(__file__)
    templates_dir = os.path.join(package_dir, "templates")
    app = Flask(__name__, template_folder=templates_dir)

    app.config.from_mapping(
        CONTACTS_PATH=os.environ.get("CONTACTS_PATH", os.path.join(os.getcwd(), "sample_contacts.csv")),
        DEFAULT_REGION=os.environ.get("DEFAULT_REGION", "US"),
    )

    if test_config:
        app.config.update(test_config)

    @app.route("/", methods=("GET", "POST"))
    def index():
        result = None
        hint = None
        error = None
        number = ""

        if request.method == "POST":
            number = (request.form.get("number") or "").strip()
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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
