from app.services.client_field_normalization import (
    normalize_client_payload,
    normalize_country,
    normalize_duns,
)


def test_normalize_country_strips_section_headers():
    assert normalize_country("US CONTACT INFORMATION & CUSTOMS PREFERENCES") == "US"
    assert normalize_country("US") == "US"


def test_normalize_duns_extracts_nine_digits():
    assert normalize_duns("619284055 PHYSICAL ADDRESS") == "619284055"
    assert normalize_duns("08-129-4819") == "081294819"


def test_normalize_client_payload():
    raw = {
        "country": "US CONTACT INFORMATION & CUSTOMS PREFERENCES",
        "duns": "619284055 PHYSICAL ADDRESS",
        "ein": "74-6019284",
        "primary_port": "2304 (Laredo)",
    }
    out = normalize_client_payload(raw)
    assert out["country"] == "US"
    assert out["duns"] == "619284055"
    assert out["primary_port"] == "2304"
