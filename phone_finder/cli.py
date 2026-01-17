"""Simple CLI for phone number -> name lookup."""
import argparse
import os
import sys
from typing import Optional

from .lookup import load_contacts_csv, find_name_local, ExternalLookup, get_number_info


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="phone-finder")
    parser.add_argument("--number", required=True, help="Phone number to lookup")
    parser.add_argument("--contacts", default="sample_contacts.csv", help="Path to CSV contacts (name,phone)")
    parser.add_argument("--region", default="US", help="Default region for parsing numbers (e.g. US, GB)")
    parser.add_argument("--use-numverify", action="store_true", help="Attempt a NumVerify lookup if NUMVERIFY_API_KEY is set")
    parser.add_argument("--use-twilio", action="store_true", help="Attempt a Twilio Lookup (caller-name) if TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN are set")
    parser.add_argument("--use-yelp", action="store_true", help="Attempt a Yelp business lookup if YELP_API_KEY is set")
    parser.add_argument("--use-google", action="store_true", help="Attempt a Google Places phone lookup if GOOGLE_MAPS_API_KEY is set")
    parser.add_argument("--use-opencorporates", action="store_true", help="Attempt an OpenCorporates company lookup if OPENCORPORATES_API_KEY is set")
    args = parser.parse_args(argv)

    try:
        contacts = load_contacts_csv(args.contacts, default_region=args.region)
    except FileNotFoundError:
        print(f"Contacts file not found: {args.contacts}")
        return 2

    name = find_name_local(args.number, contacts, default_region=args.region)
    if name:
        print(f"Found locally: {name}")
        return 0

    # If any provider keys are available, attempt external lookups automatically.
    # Priority: OpenCorporates -> Google -> Yelp -> Twilio -> NumVerify
    ext = ExternalLookup(
        numverify_key=os.environ.get("NUMVERIFY_API_KEY"),
        twilio_sid=os.environ.get("TWILIO_ACCOUNT_SID"),
        twilio_token=os.environ.get("TWILIO_AUTH_TOKEN"),
    )

    # OpenCorporates (works unauthenticated but with rate limits)
    oc_key = os.environ.get("OPENCORPORATES_API_KEY")
    if oc_key or oc_key is None:
        ok, remote = ext.lookup_opencorporates(args.number, default_region=args.region)
        if ok and remote:
            print(f"Found company via OpenCorporates: {remote}")
            return 0

    # Google Places
    if os.environ.get("GOOGLE_MAPS_API_KEY"):
        ok, remote = ext.lookup_google(args.number, default_region=args.region)
        if ok and remote:
            print(f"Found place via Google Maps: {remote}")
            return 0

    # Yelp
    if os.environ.get("YELP_API_KEY"):
        ok, remote = ext.lookup_yelp(args.number, default_region=args.region)
        if ok and remote:
            print(f"Found business via Yelp: {remote}")
            return 0

    # Twilio
    if os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN"):
        ok, remote = ext.lookup_twilio(args.number, default_region=args.region)
        if ok and remote:
            print(f"Found via Twilio: {remote}")
            return 0

    # NumVerify (hints)
    if os.environ.get("NUMVERIFY_API_KEY"):
        ok, hint = ext.lookup_numverify(args.number, default_region=args.region)
        if ok and hint:
            print(f"External lookup hint: {hint}")
            return 0

    if args.use_yelp:
        api_key = os.environ.get("YELP_API_KEY")
        ext = ExternalLookup()
        ok, name = ext.lookup_yelp(args.number, default_region=args.region)
        if ok and name:
            print(f"Found business via Yelp: {name}")
            return 0
        elif ok and name is None:
            print("Yelp lookup returned no business for this number.")
            return 1
        else:
            print("Yelp lookup failed or was not available.")
            return 1

    if args.use_google:
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        ext = ExternalLookup()
        ok, name = ext.lookup_google(args.number, default_region=args.region)
        if ok and name:
            print(f"Found place via Google Maps: {name}")
            return 0
        elif ok and name is None:
            print("Google lookup returned no place for this number.")
            return 1
        else:
            print("Google lookup failed or was not available.")
            return 1

    if args.use_opencorporates:
        api_key = os.environ.get("OPENCORPORATES_API_KEY")
        ext = ExternalLookup()
        ok, name = ext.lookup_opencorporates(args.number, default_region=args.region)
        if ok and name:
            print(f"Found company via OpenCorporates: {name}")
            return 0
        elif ok and name is None:
            print("OpenCorporates lookup returned no company for this number.")
            return 1
        else:
            print("OpenCorporates lookup failed or was not available.")
            return 1

    if args.use_numverify:
        key = os.environ.get("NUMVERIFY_API_KEY")
        ext = ExternalLookup(numverify_key=key)
        ok, hint = ext.lookup_numverify(args.number, default_region=args.region)
        if ok and hint:
            print(f"External lookup hint: {hint}")
            return 0
        else:
            print("External lookup attempted but returned no identifying information.")
            return 1

    # No external provider requested: show free metadata about the number
    info = get_number_info(args.number, default_region=args.region)
    if "error" in info:
        print(f"Could not parse number: {info['error']}")
        return 2

    print("No match found in local contacts.")
    print("Number info:")
    for k in ("normalized", "is_valid", "is_possible", "region", "description", "carrier", "line_type", "timezones"):
        if k in info and info[k] is not None:
            print(f"  {k}: {info[k]}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
