"""Simple CLI for phone number -> name lookup."""
import argparse
import os
import sys
from typing import Optional

from .lookup import load_contacts_csv, find_name_local, ExternalLookup


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="phone-finder")
    parser.add_argument("--number", required=True, help="Phone number to lookup")
    parser.add_argument("--contacts", default="sample_contacts.csv", help="Path to CSV contacts (name,phone)")
    parser.add_argument("--region", default="US", help="Default region for parsing numbers (e.g. US, GB)")
    parser.add_argument("--use-numverify", action="store_true", help="Attempt a NumVerify lookup if NUMVERIFY_API_KEY is set")
    parser.add_argument("--use-twilio", action="store_true", help="Attempt a Twilio Lookup (caller-name) if TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN are set")
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

    if args.use_twilio:
        sid = os.environ.get("TWILIO_ACCOUNT_SID")
        token = os.environ.get("TWILIO_AUTH_TOKEN")
        ext = ExternalLookup(twilio_sid=sid, twilio_token=token)
        ok, name = ext.lookup_twilio(args.number, default_region=args.region)
        if ok and name:
            print(f"Found via Twilio: {name}")
            return 0
        elif ok and name is None:
            print("Twilio lookup returned no caller name for this number.")
            return 1
        else:
            # fallback to NumVerify if requested
            if args.use_numverify:
                key = os.environ.get("NUMVERIFY_API_KEY")
                ext = ExternalLookup(numverify_key=key, twilio_sid=sid, twilio_token=token)
                ok, hint = ext.lookup_numverify(args.number, default_region=args.region)
                if ok and hint:
                    print(f"External lookup hint: {hint}")
                    return 0
            print("External lookup attempted but returned no identifying information.")
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

    print("No match found in local contacts. Try --use-numverify or provide a larger contact list.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
