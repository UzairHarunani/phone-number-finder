from flask import Flask, render_template, request
import os

from .lookup import load_contacts_csv, find_name_local, ExternalLookup


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
                    # Prefer Twilio caller-name lookup if credentials present
                    sid = os.environ.get("TWILIO_ACCOUNT_SID")
                    token = os.environ.get("TWILIO_AUTH_TOKEN")
                    numverify_key = os.environ.get("NUMVERIFY_API_KEY")
                    ext = ExternalLookup(numverify_key=numverify_key, twilio_sid=sid, twilio_token=token)

                    # Try Twilio first (may return a person's name for some numbers / regions)
                    ok, remote_name = ext.lookup_twilio(number, default_region=app.config["DEFAULT_REGION"])
                    if ok and remote_name:
                        result = {"found": True, "name": remote_name}
                    else:
                        # Next, try NumVerify for hints if available
                        ok2, hint = ext.lookup_numverify(number, default_region=app.config["DEFAULT_REGION"]) if numverify_key else (False, None)
                        result = {"found": False}

        return render_template("index.html", result=result, hint=hint, error=error, number=number)

    @app.route("/health")
    def health():
        return "ok", 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
