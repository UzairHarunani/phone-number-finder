Phone Number Finder
====================

This small utility attempts to identify a person's name from a phone number.

It supports:

- Local CSV contact lookup (primary method).
- An optional external lookup hook (e.g., NumVerify) which can provide hints but typically does not return a person's name due to privacy.

Why local-first? Identifying a person by phone number normally requires either the owner's explicit public listing, a synchronization of the user's contacts, or a paid/permissioned data provider. This tool prioritizes local contact lists.

Quick start
-----------

1. Install requirements:

```powershell
python -m pip install -r requirements.txt
```

2. Put contacts in a CSV with headers `name,phone` (see `sample_contacts.csv`).

3. Run the CLI:

```powershell
python -m phone_finder.cli --number "+1 415 555 2671" --contacts sample_contacts.csv --region US

Run as a website
-----------------

You can run a small web UI using Flask. By default it will use `sample_contacts.csv` in the current working directory.

In PowerShell:

```powershell
python -m pip install -r requirements.txt
python -m phone_finder.web
```

Then open http://127.0.0.1:5000 in your browser and enter a phone number.
```

Optional external lookup
------------------------

If you have an API key for an external provider, you can set the environment variable `NUMVERIFY_API_KEY` and the CLI will attempt a secondary lookup. Note: these providers often do not return a person's name.

Twilio Lookup (caller name)
----------------------------

If you have a Twilio account, Twilio's Lookup API can return caller-name (CNAM) for some numbers/regions. This is a paid/opt-in feature and coverage varies by country. To enable Twilio lookups set these environment variables in your Render or local environment:

```
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_auth_token
```

Then the web UI and CLI will attempt a Twilio lookup when no local contact matches. If Twilio returns a caller name the app will show it.

Yelp business lookup
---------------------

You can also try to match numbers to businesses using the Yelp Fusion Phone Search API. Yelp can return a business name for a phone number (useful for businesses, not personal numbers). To enable Yelp lookups set the environment variable:

```
YELP_API_KEY=your_yelp_api_key
```

Then in the web UI the app will try Yelp first (when present) and fall back to Twilio or NumVerify hints. The CLI exposes `--use-yelp` to force a Yelp lookup.

Get a Yelp API key at https://www.yelp.com/developers and keep the key secret (use env vars in Render or your host).

Google Places phone lookup
--------------------------

Google Places supports finding businesses by phone number using the Find Place endpoint. This is useful for businesses and organizations (not personal numbers). To enable Google lookups set:

```
GOOGLE_MAPS_API_KEY=your_key_here
```

Then the web UI will prefer Google Places (when present) and fall back to Yelp / Twilio / NumVerify. The CLI exposes `--use-google` to force a Google lookup. Get an API key at https://developers.google.com/maps/documentation/places/web-service/get-api-key and secure it in your environment.

OpenCorporates company lookup
-----------------------------

OpenCorporates maintains a global database of company records. You can try to match phone numbers to company records using their companies search endpoint. Coverage varies and matching by phone is best-effort. To enable OpenCorporates lookups set:

```
OPENCORPORATES_API_KEY=your_key_here
```

If you set this key the web UI will try OpenCorporates first for company matches, then fall back to Google/Yelp/Twilio/NumVerify. The CLI exposes `--use-opencorporates` to force a lookup. Get an API token at https://opencorporates.com/info/api and keep it secret.

Privacy and legal
-----------------

Be mindful of privacy and local laws when looking up people by phone number. This tool only performs lookups on data you supply or services you configure.
