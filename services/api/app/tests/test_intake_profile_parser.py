"""Tests for multi-entity intake registry PDF parsing."""

from app.services.intake_profile_parser import (
    is_intake_registry_document,
    parse_intake_registry_entities,
)

SAMPLE_BLOCK = """
Entity 01
Pacific Horizon Logistics Inc.
Corporation
✓ C-TPAT Certified
1. COMPANY & CUSTOMS IDENTIFIERS
LEGAL NAME
Pacific Horizon Logistics
Incorporated
DBA NAME
Horizon Tech Imports
EIN
94-3184920
IOR NUMBER
94-318492000
DUNS
081294819
2. PHYSICAL FACILITY ADDRESS
ADDRESS LINE 1 & 2
400 Harbor Scenic Dr, Suite 1200
CITY
Long Beach
STATE /
PROVINCE
CA
POSTAL CODE
90802
COUNTRY
US
3. COMMUNICATIONS & CUSTOMS CLEARANCE PREFERENCES
PHONE
+1 (562) 555-0194
EMAIL
customs@horizontechimports.com
WEBSITE
https://www.horizontechimports.com
PRIMARY
PORT
2704
(LA/LB)
INTERNAL
CODE
PHL-WST-01

Entity 02
Blue Ridge Sourcing LLC
Limited Liability Co
Non-C-TPAT
1. COMPANY & CUSTOMS IDENTIFIERS
LEGAL NAME
Blue Ridge Global Sourcing LLC
DBA NAME
Ridge Wear
EIN
56-8291044
IOR NUMBER
56-829104400
DUNS
149203847
PRIMARY
PORT
1703
(Savannah)
INTERNAL
CODE
BRS-ATL-09
"""


def test_detects_intake_registry():
    assert is_intake_registry_document(SAMPLE_BLOCK) is True
    assert is_intake_registry_document("Single W-9 for Acme Corp") is False


def test_parses_multiple_entities():
    entities = parse_intake_registry_entities(SAMPLE_BLOCK)
    assert len(entities) == 2
    e1 = entities[0]["suggestions"]
    assert e1["name"] == "Pacific Horizon Logistics Inc."
    assert e1["ein"] == "94-3184920"
    assert e1["ior_number"] == "94-318492000"
    assert e1["primary_port"] == "2704"
    assert e1["internal_code"] == "PHL-WST-01"
    assert e1["c_tpat_member"] is True

    e2 = entities[1]["suggestions"]
    assert e2["name"] == "Blue Ridge Sourcing LLC"
    assert e2["client_type"] == "llc"
    assert e2["c_tpat_member"] is False
