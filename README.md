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

Privacy and legal
-----------------

Be mindful of privacy and local laws when looking up people by phone number. This tool only performs lookups on data you supply or services you configure.
