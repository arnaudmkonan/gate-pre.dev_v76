"""Normalize client identifier and address fields before persist or API response."""

import re
from typing import Any, Dict, Optional

EIN_RE = re.compile(r"^\d{2}-\d{7}$")
IOR_RE = re.compile(r"^\d{2}-\d{7}\d{2,3}$")
DUNS_DIGITS_RE = re.compile(r"\d{9}")
PORT_RE = re.compile(r"^\d{4}$")


def normalize_country(value: Optional[str]) -> str:
    if not value or not str(value).strip():
        return "US"
    raw = str(value).strip().upper()
    if re.fullmatch(r"[A-Z]{2}", raw):
        return raw
    if raw.startswith("US") or "UNITED STATES" in raw or raw == "U.S.":
        return "US"
    if "CANADA" in raw:
        return "CA"
    if "MEXICO" in raw:
        return "MX"
    return "US"


def normalize_ein(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    if EIN_RE.fullmatch(text):
        return text
    match = EIN_RE.search(text.replace(" ", ""))
    return match.group(0) if match else None


def normalize_ior_number(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    compact = str(value).replace(" ", "")
    if IOR_RE.fullmatch(compact):
        return compact
    match = IOR_RE.search(compact)
    if match:
        return match.group(0)
    ein = normalize_ein(value)
    return ein


def normalize_duns(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    match = DUNS_DIGITS_RE.search(digits)
    if not match:
        return None
    return match.group(0)


def normalize_primary_port(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    if PORT_RE.fullmatch(text):
        return text
    match = re.search(r"\b(\d{4})\b", text)
    return match.group(1) if match else None


def normalize_client_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy with normalized identifier/address fields."""
    out = dict(data)
    if "country" in out:
        out["country"] = normalize_country(out.get("country"))
    if out.get("ein") is not None:
        out["ein"] = normalize_ein(out.get("ein"))
    if out.get("ior_number") is not None:
        out["ior_number"] = normalize_ior_number(out.get("ior_number"))
    if out.get("duns") is not None:
        out["duns"] = normalize_duns(out.get("duns"))
    if out.get("primary_port") is not None:
        out["primary_port"] = normalize_primary_port(out.get("primary_port"))
    return out
