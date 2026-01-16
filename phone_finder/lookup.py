import csv
import os
from typing import Dict, Optional, Tuple

import phonenumbers
from phonenumbers import PhoneNumberFormat, NumberParseException
import requests


def normalize_number(number: str, default_region: str = "US") -> str:
    """Parse and return an E.164 formatted phone number.

    Raises ValueError if the number cannot be parsed.
    """
    try:
        pn = phonenumbers.parse(number, default_region)
        if not phonenumbers.is_possible_number(pn) and not phonenumbers.is_valid_number(pn):
            # still try to format; downstream code may ignore invalids
            pass
        return phonenumbers.format_number(pn, PhoneNumberFormat.E164)
    except NumberParseException as e:
        raise ValueError(f"Could not parse phone number '{number}': {e}")


def load_contacts_csv(path: str, phone_column: str = "phone", name_column: str = "name", default_region: str = "US") -> Dict[str, str]:
    """Load contacts from a CSV file and return a mapping of normalized phone -> name.

    CSV must contain headers. Rows with unparseable numbers are skipped.
    """
    contacts: Dict[str, str] = {}
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if phone_column not in row or name_column not in row:
                continue
            raw_phone = row[phone_column].strip()
            name = row[name_column].strip()
            if not raw_phone:
                continue
            try:
                normalized = normalize_number(raw_phone, default_region)
                contacts[normalized] = name
            except ValueError:
                # skip unparseable numbers
                continue
    return contacts


def find_name_local(number: str, contacts: Dict[str, str], default_region: str = "US") -> Optional[str]:
    """Find a name in the provided contacts mapping for the given phone number.

    Returns the name if found, otherwise None.
    """
    try:
        normalized = normalize_number(number, default_region)
    except ValueError:
        return None
    return contacts.get(normalized)


class ExternalLookup:
    """A small adapter for optional external lookups (hooks)."""

    def __init__(self, numverify_key: Optional[str] = None):
        self.numverify_key = numverify_key

    def lookup_numverify(self, number: str, default_region: str = "US") -> Tuple[bool, Optional[str]]:
        """Query NumVerify (if key provided).

        Returns (success, hint). Note: NumVerify does not return a person's name; this returns carrier/line type hints.
        """
        if not self.numverify_key:
            return False, None
        try:
            normalized = normalize_number(number, default_region)
        except ValueError:
            return False, None

        url = "http://apilayer.net/api/validate"
        params = {"access_key": self.numverify_key, "number": normalized}
        try:
            resp = requests.get(url, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            hints = []
            if data.get("carrier"):
                hints.append(f"carrier={data['carrier']}")
            if data.get("line_type"):
                hints.append(f"line_type={data['line_type']}")
            if data.get("country_name"):
                hints.append(f"country={data['country_name']}")
            hint = "; ".join(hints) if hints else None
            return True, hint
        except Exception:
            return False, None
