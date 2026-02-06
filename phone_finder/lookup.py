import csv
import os
from typing import Dict, Optional, Tuple

import phonenumbers
from phonenumbers import PhoneNumberFormat, NumberParseException
from phonenumbers import carrier as _carrier
from phonenumbers import geocoder as _geocoder
from phonenumbers import timezone as _timezone
import requests


def normalize_number(number: str, default_region: str = "TZ") -> str:
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


def load_contacts_csv(path: str, phone_column: str = "phone", name_column: str = "name", default_region: str = "TZ") -> Dict[str, str]:
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


def find_name_local(number: str, contacts: Dict[str, str], default_region: str = "TZ") -> Optional[str]:
    """Find a name in the provided contacts mapping for the given phone number.

    Returns the name if found, otherwise None.
    """
    try:
        normalized = normalize_number(number, default_region)
    except ValueError:
        return None
    return contacts.get(normalized)


class ExternalLookup:
    """A small adapter for optional external lookups (hooks).

    Currently supports:
    - NumVerify (validation/carrier hints)
    - Twilio Lookup (caller-name when available; requires Twilio credentials and may be a paid lookup)
    """

    def __init__(self, numverify_key: Optional[str] = None, twilio_sid: Optional[str] = None, twilio_token: Optional[str] = None):
        self.numverify_key = numverify_key
        self.twilio_sid = twilio_sid
        self.twilio_token = twilio_token

    def lookup_numverify(self, number: str, default_region: str = "TZ") -> Tuple[bool, Optional[str]]:
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

    def lookup_twilio(self, number: str, default_region: str = "TZ") -> Tuple[bool, Optional[str]]:
        """Query Twilio Lookup API for caller-name (if credentials provided).

        Returns (success, name) where name is the caller name if Twilio returns it.
        Requires TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN to be available (or passed in constructor).
        """
        sid = self.twilio_sid or os.environ.get("TWILIO_ACCOUNT_SID")
        token = self.twilio_token or os.environ.get("TWILIO_AUTH_TOKEN")
        if not sid or not token:
            return False, None

    def lookup_yelp(self, number: str, default_region: str = "TZ") -> Tuple[bool, Optional[str]]:
        """Query Yelp Fusion Phone Search for businesses matching the phone number.

        Requires YELP_API_KEY in env or passed as part of the object's construction.
        Returns (success, business_name) where business_name is the top match if any.
        """
        api_key = os.environ.get("YELP_API_KEY")
        if not api_key:
            return False, None

        try:
            normalized = normalize_number(number, default_region)
        except ValueError:
            return False, None

        url = "https://api.yelp.com/v3/businesses/search/phone"
        headers = {"Authorization": f"Bearer {api_key}"}
        params = {"phone": normalized}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            businesses = data.get("businesses") or []
            if businesses:
                top = businesses[0]
                name = top.get("name")
                return True, name
            return True, None
        except Exception:
            return False, None

    def lookup_google(self, number: str, default_region: str = "TZ") -> Tuple[bool, Optional[str]]:
        """Query Google Places 'Find Place' by phone number.

        Requires GOOGLE_MAPS_API_KEY in env. Returns (success, place_name) where place_name
        is the top match if any.
        """
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return False, None

    def lookup_opencorporates(self, number: str, default_region: str = "TZ") -> Tuple[bool, Optional[str]]:
        """Query OpenCorporates companies search for the phone number.

        OpenCorporates doesn't have a dedicated phone-search endpoint, but their
        companies search can match text fields. This does a best-effort search for
        the normalized number and returns the top company's name if any.

        Requires OPENCORPORATES_API_KEY in env (optional; unauthenticated calls are rate-limited).
        """
        api_key = os.environ.get("OPENCORPORATES_API_KEY")
        try:
            normalized = normalize_number(number, default_region)
        except ValueError:
            return False, None

        url = "https://api.opencorporates.com/v0.4/companies/search"
        params = {"q": normalized}
        if api_key:
            params["api_token"] = api_key
        try:
            resp = requests.get(url, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", {}).get("companies") or []
            if not results:
                return True, None
            # Extract company name from top result
            top = results[0]
            company = top.get("company") or {}
            name = company.get("name")
            return True, name
        except Exception:
            return False, None

        try:
            normalized = normalize_number(number, default_region)
        except ValueError:
            return False, None

        url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        params = {
            "input": normalized,
            "inputtype": "phonenumber",
            "fields": "name,formatted_phone_number,place_id,business_status",
            "key": api_key,
        }
        try:
            resp = requests.get(url, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates") or []
            if candidates:
                top = candidates[0]
                name = top.get("name")
                return True, name
            return True, None
        except Exception:
            return False, None

        try:
            normalized = normalize_number(number, default_region)
        except ValueError:
            return False, None

        url = f"https://lookups.twilio.com/v1/PhoneNumbers/{normalized}"
        params = {"Type": "caller-name"}
        try:
            resp = requests.get(url, auth=(sid, token), params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            caller = data.get("caller_name") or {}
            name = caller.get("caller_name")
            if name:
                return True, name
            return True, None
        except Exception:
            return False, None


def get_number_info(number: str, default_region: str = "TZ") -> Dict[str, Optional[str]]:
    """Return free metadata for a phone number using the phonenumbers library.

    Returns a dict with keys: normalized, is_valid, is_possible, region, description,
    carrier, line_type, timezones. If parsing fails the dict will contain an 'error' key.
    """
    info: Dict[str, Optional[str]] = {}
    try:
        pn = phonenumbers.parse(number, default_region)
    except NumberParseException as e:
        return {"error": str(e)}

    try:
        info["normalized"] = phonenumbers.format_number(pn, PhoneNumberFormat.E164)
    except Exception:
        info["normalized"] = None

    info["is_possible"] = str(phonenumbers.is_possible_number(pn))
    info["is_valid"] = str(phonenumbers.is_valid_number(pn))

    # region / description
    try:
        info["region"] = phonenumbers.region_code_for_number(pn)
        info["description"] = _geocoder.description_for_number(pn, "en")
    except Exception:
        info["region"] = None
        info["description"] = None

    # carrier
    try:
        info["carrier"] = _carrier.name_for_number(pn, "en") or None
    except Exception:
        info["carrier"] = None

    # line type
    try:
        nt = phonenumbers.number_type(pn)
        # Map numeric enum to readable name
        type_map = {
            phonenumbers.PhoneNumberType.FIXED_LINE: "FIXED_LINE",
            phonenumbers.PhoneNumberType.MOBILE: "MOBILE",
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "FIXED_LINE_OR_MOBILE",
            phonenumbers.PhoneNumberType.TOLL_FREE: "TOLL_FREE",
            phonenumbers.PhoneNumberType.PREMIUM_RATE: "PREMIUM_RATE",
            phonenumbers.PhoneNumberType.SHARED_COST: "SHARED_COST",
            phonenumbers.PhoneNumberType.VOIP: "VOIP",
            phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "PERSONAL_NUMBER",
            phonenumbers.PhoneNumberType.PAGER: "PAGER",
            phonenumbers.PhoneNumberType.UAN: "UAN",
            phonenumbers.PhoneNumberType.VOICEMAIL: "VOICEMAIL",
            phonenumbers.PhoneNumberType.UNKNOWN: "UNKNOWN",
        }
        info["line_type"] = type_map.get(nt, str(nt))
    except Exception:
        info["line_type"] = None

    # timezones
    try:
        tzs = _timezone.time_zones_for_number(pn)
        info["timezones"] = ", ".join(tzs) if tzs else None
    except Exception:
        info["timezones"] = None

    return info

