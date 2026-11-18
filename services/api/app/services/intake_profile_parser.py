"""Parse GATE intake-registry PDFs with multiple Entity NN profile blocks."""

import re
from typing import Any, Dict, List, Optional, Tuple

EIN_RE = re.compile(r"^\d{2}-\d{7}$")
IOR_RE = re.compile(r"^\d{2}-\d{7}\d{2,3}$")
DUNS_RE = re.compile(r"^\d{9}$")
PORT_RE = re.compile(r"^\d{4}$")

ENTITY_SPLIT = re.compile(r"(?=^Entity\s+\d+\s*$)", re.MULTILINE)

ENTITY_TYPE_MAP = {
    "corporation": "corporation",
    "corp": "corporation",
    "limited liability": "llc",
    "llc": "llc",
    "partnership": "partnership",
    "sole proprietor": "sole_proprietor",
    "sole propriet": "sole_proprietor",
}


def is_intake_registry_document(text: str) -> bool:
    lower = text.lower()
    return (
        "ingestion profiles" in lower
        or "intake registry" in lower
        or bool(re.search(r"^Entity\s+\d+\s*$", text, re.MULTILINE))
    )


def parse_intake_registry_entities(text: str) -> List[Dict[str, Any]]:
    """Return list of {entity_id, display_name, suggestions}."""
    # Drop schema appendix
    cut = text.find("Platform Schema & Validation Reference")
    if cut == -1:
        cut = text.find("FORM FIELD")
    body = text[:cut] if cut > 0 else text

    chunks = ENTITY_SPLIT.split(body)
    entities: List[Dict[str, Any]] = []

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk.startswith("Entity"):
            continue
        parsed = _parse_single_entity(chunk)
        if parsed:
            entities.append(parsed)

    return entities


def _parse_single_entity(chunk: str) -> Optional[Dict[str, Any]]:
    m = re.match(r"Entity\s+(\d+)\s*\n(.*)", chunk, re.DOTALL)
    if not m:
        return None

    entity_id = m.group(1)
    rest = m.group(2)
    lines = [ln.strip() for ln in rest.splitlines()]

    # Header lines before "1. COMPANY"
    header: List[str] = []
    body_start = 0
    for i, ln in enumerate(lines):
        if ln.startswith("1. COMPANY") or ln.startswith("1."):
            body_start = i
            break
        if ln:
            header.append(ln)

    display_name = header[0] if header else f"Entity {entity_id}"
    client_type = _map_entity_type(header[1] if len(header) > 1 else "")
    c_tpat = any("c-tpat" in h.lower() and "non" not in h.lower() for h in header)

    body_lines = lines[body_start:]
    fields = _parse_labeled_fields(body_lines)

    legal_name = fields.get("legal_name") or display_name
    suggestions: Dict[str, Any] = {
        "name": display_name,
        "legal_name": legal_name,
        "dba_name": fields.get("dba_name"),
        "client_type": client_type or "corporation",
        "ein": fields.get("ein"),
        "ior_number": fields.get("ior_number"),
        "duns": fields.get("duns"),
        "address_line_1": fields.get("address_line_1"),
        "city": fields.get("city"),
        "state_province": fields.get("state_province"),
        "postal_code": fields.get("postal_code"),
        "country": fields.get("country") or "US",
        "phone": fields.get("phone"),
        "email": fields.get("email"),
        "website": fields.get("website"),
        "primary_port": fields.get("primary_port"),
        "internal_code": fields.get("internal_code"),
        "c_tpat_member": c_tpat,
    }
    suggestions = {k: v for k, v in suggestions.items() if v not in (None, "", False) or k == "c_tpat_member"}

    filled = [k for k, v in suggestions.items() if v not in (None, "", False)]

    return {
        "entity_id": entity_id,
        "display_name": display_name,
        "suggestions": suggestions,
        "filled_fields": filled,
    }


def _map_entity_type(raw: str) -> Optional[str]:
    lower = raw.lower()
    for needle, mapped in ENTITY_TYPE_MAP.items():
        if needle in lower:
            return mapped
    return None


def _parse_labeled_fields(lines: List[str]) -> Dict[str, str]:
    """Map uppercase label lines to values (PDF uses label-on-own-line layout)."""
    label_to_key = {
        "LEGAL NAME": "legal_name",
        "DBA NAME": "dba_name",
        "EIN": "ein",
        "IOR NUMBER": "ior_number",
        "DUNS": "duns",
        "ADDRESS LINE 1 & 2": "address_line_1",
        "CITY": "city",
        "POSTAL CODE": "postal_code",
        "COUNTRY": "country",
        "PHONE": "phone",
        "EMAIL": "email",
        "WEBSITE": "website",
        "INTERNAL CODE": "internal_code",
    }

    normalized: List[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln == "STATE /":
            i += 1
            if i < len(lines) and lines[i] == "PROVINCE":
                i += 1
            if i < len(lines):
                normalized.append(f"__STATE__\n{lines[i]}")
                i += 1
            continue
        if ln == "PRIMARY":
            i += 1
            if i < len(lines) and lines[i] == "PORT":
                i += 1
            if i < len(lines):
                normalized.append(f"__PORT__\n{lines[i]}")
                i += 1
            continue
        if ln == "INTERNAL":
            i += 1
            if i < len(lines) and lines[i] == "CODE":
                i += 1
            if i < len(lines):
                normalized.append(f"__INTERNAL__\n{lines[i]}")
                i += 1
            continue
        normalized.append(ln)
        i += 1

    fields: Dict[str, str] = {}
    idx = 0
    while idx < len(normalized):
        line = normalized[idx]
        if line.startswith("__STATE__"):
            fields["state_province"] = line.split("\n", 1)[1].strip()
            idx += 1
            continue
        if line.startswith("__PORT__"):
            port_line = line.split("\n", 1)[1].strip()
            port_m = PORT_RE.match(port_line)
            if port_m:
                fields["primary_port"] = port_m.group(0)
            idx += 1
            continue
        if line.startswith("__INTERNAL__"):
            fields["internal_code"] = line.split("\n", 1)[1].strip()
            idx += 1
            continue

        key = label_to_key.get(line.upper())
        if not key:
            idx += 1
            continue

        value_parts: List[str] = []
        idx += 1
        while idx < len(normalized):
            nxt = normalized[idx]
            if nxt.upper() in label_to_key or nxt.startswith("__"):
                break
            if re.match(r"^\d+\.\s", nxt):
                break
            if nxt.startswith("(") and key in ("primary_port",):
                break
            value_parts.append(nxt)
            idx += 1

        value = " ".join(value_parts).strip()
        if key == "legal_name":
            value = " ".join(value_parts).replace("  ", " ").strip()
        if key == "ein" and not EIN_RE.match(value):
            em = EIN_RE.search(value)
            value = em.group(0) if em else value
        if key == "ior_number" and not IOR_RE.match(value):
            im = IOR_RE.search(value.replace(" ", ""))
            value = im.group(0) if im else value
        if key == "duns" and DUNS_RE.match(value.replace("-", "")):
            d = value.replace("-", "")
            value = d if len(d) == 9 else value
        if key == "website" and value and not value.startswith("http"):
            value = f"https://{value}"

        if value:
            fields[key] = value

    return fields
