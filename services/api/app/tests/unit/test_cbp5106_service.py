"""
Unit tests — CBP Form 5106 Service  (Task 2.2)
"""
import pytest
from app.services.cbp5106_service import CBP5106Service


@pytest.fixture
def service():
    return CBP5106Service()


VALID_BUSINESS = {
    "entity_type": "corporation",
    "legal_name": "ACME Imports LLC",
    "ein": "12-3456789",
    "address_line1": "100 Trade St",
    "city": "Los Angeles",
    "state": "CA",
    "zip_code": "90001",
    "country_code": "US",
    "contact_name": "Alice Smith",
    "contact_phone": "555-123-4567",
}

VALID_INDIVIDUAL = {
    "entity_type": "individual",
    "first_name": "Bob",
    "last_name": "Jones",
    "ssn_or_tin": "123-45-6789",
    "address_line1": "200 Main St",
    "city": "Miami",
    "state": "FL",
    "zip_code": "33101",
    "country_code": "US",
}


class TestCBP5106Validation:

    def test_valid_business_has_no_errors(self, service):
        errors = service.validate(VALID_BUSINESS)
        assert errors == []

    def test_valid_individual_has_no_errors(self, service):
        errors = service.validate(VALID_INDIVIDUAL)
        assert errors == []

    def test_missing_ein_produces_error(self, service):
        data = {**VALID_BUSINESS, "ein": ""}
        errors = service.validate(data)
        assert any("ein" in e.lower() for e in errors)

    def test_bad_ein_format_produces_error(self, service):
        data = {**VALID_BUSINESS, "ein": "123456789"}  # Missing dash
        errors = service.validate(data)
        assert any("EIN" in e for e in errors)

    def test_valid_ein_format_accepted(self, service):
        data = {**VALID_BUSINESS, "ein": "98-7654321"}
        errors = service.validate(data)
        assert errors == []

    def test_invalid_ssn_format(self, service):
        data = {**VALID_INDIVIDUAL, "ssn_or_tin": "123456789"}  # No dashes
        errors = service.validate(data)
        assert any("SSN" in e for e in errors)

    def test_invalid_zip_code(self, service):
        data = {**VALID_BUSINESS, "zip_code": "ABCDE"}
        errors = service.validate(data)
        assert any("ZIP" in e for e in errors)

    def test_valid_zip_with_plus4(self, service):
        data = {**VALID_BUSINESS, "zip_code": "90001-1234"}
        errors = service.validate(data)
        assert errors == []

    def test_missing_legal_name(self, service):
        data = {**VALID_BUSINESS}
        del data["legal_name"]
        errors = service.validate(data)
        assert any("legal_name" in e for e in errors)


class TestCBP5106PacketGeneration:

    def test_build_packet_valid_data(self, service):
        packet = service.build_5106_packet(VALID_BUSINESS)
        assert packet["form_type"] == "5106"
        assert packet["legal_name"] == "ACME Imports LLC"
        assert packet["ein"] == "12-3456789"
        assert packet["status"] == "pending_cbp_review"

    def test_build_packet_raises_on_invalid(self, service):
        bad_data = {"entity_type": "corporation"}  # Missing required fields
        with pytest.raises(ValueError, match="5106 validation failed"):
            service.build_5106_packet(bad_data)

    def test_generate_ior_number_strips_dash(self, service):
        ior = service.generate_ior_number("12-3456789")
        assert ior == "123456789"

    def test_packet_excludes_none_values(self, service):
        packet = service.build_5106_packet(VALID_BUSINESS)
        # None values should be filtered out
        assert None not in packet.values()


class TestEINSSNValidators:

    def test_valid_ein_formats(self, service):
        assert service._validate_ein("12-3456789") is True
        assert service._validate_ein("00-1234567") is True

    def test_invalid_ein_formats(self, service):
        assert service._validate_ein("123456789") is False
        assert service._validate_ein("1-23456789") is False
        assert service._validate_ein("12-345678") is False
        assert service._validate_ein("AB-1234567") is False

    def test_valid_ssn_formats(self, service):
        assert service._validate_ssn("123-45-6789") is True

    def test_invalid_ssn_formats(self, service):
        assert service._validate_ssn("123456789") is False
        assert service._validate_ssn("12-45-6789") is False
