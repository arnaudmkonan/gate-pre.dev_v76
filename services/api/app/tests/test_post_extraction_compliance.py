"""
Comprehensive tests for Post-Extraction Compliance Integration.

Tests cover:
- PostExtractionService unit tests
- HTS code validation
- OFAC SDN party screening
- NAICS code classification
- Integration with template extraction workflow
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.post_extraction_service import (
    PostExtractionService,
    PostExtractionServiceSync,
    PostExtractionResult,
    HTSValidationResult,
    PartyScreeningResult,
    NAICSClassificationResult,
    RiskLevel,
    ComplianceCheckType,
)


# ==================== Test Data ====================

SAMPLE_COMMERCIAL_INVOICE_EXTRACTION = {
    "extractions": [
        {
            "field_name": "invoice_number",
            "value": "INV-2024-001",
            "found": True,
            "confidence": 0.95,
        },
        {
            "field_name": "seller_name",
            "value": "Acme Trading Co.",
            "found": True,
            "confidence": 0.92,
        },
        {
            "field_name": "buyer_name",
            "value": "Global Imports LLC",
            "found": True,
            "confidence": 0.90,
        },
        {
            "field_name": "importer_of_record_name",
            "value": "US Import Corp",
            "found": True,
            "confidence": 0.88,
        },
        {
            "field_name": "country_of_origin",
            "value": "China",
            "found": True,
            "confidence": 0.95,
        },
        {
            "field_name": "total_amount",
            "value": 15000.00,
            "found": True,
            "confidence": 0.98,
        },
        {
            "field_name": "line_items",
            "value": [
                {
                    "item_description": "Electronic Components",
                    "hs_code": "8471.30.01",
                    "quantity": 100,
                    "unit_price": 150.00,
                },
                {
                    "item_description": "Steel Parts",
                    "hs_code": "7208.10.15",
                    "quantity": 50,
                    "unit_price": 200.00,
                },
            ],
            "found": True,
            "confidence": 0.85,
        },
    ],
    "template_name": "Commercial Invoice",
    "fields_found": 7,
    "fields_total": 10,
}

SAMPLE_CUSTOMS_ENTRY_EXTRACTION = {
    "extractions": [
        {
            "field_name": "entry_number",
            "value": "ABC12345678",
            "found": True,
            "confidence": 0.98,
        },
        {
            "field_name": "importer_of_record_name",
            "value": "Samsung Electronics America",
            "found": True,
            "confidence": 0.95,
        },
        {
            "field_name": "consignee_name",
            "value": "Best Buy Stores",
            "found": True,
            "confidence": 0.90,
        },
        {
            "field_name": "exporting_country",
            "value": "Korea",
            "found": True,
            "confidence": 0.95,
        },
        {
            "field_name": "line_items",
            "value": [
                {
                    "hts_number": "8528.71.00",
                    "description": "Television receivers",
                    "entered_value": 50000.00,
                    "duty_rate": "25%",
                },
            ],
            "found": True,
            "confidence": 0.88,
        },
    ],
    "template_name": "Customs Entry (CBP 7501)",
    "fields_found": 5,
    "fields_total": 15,
}


# ==================== Unit Tests for HTS Validation ====================

class TestHTSValidation:
    """Tests for HTS code validation functionality."""

    def test_valid_hts_format_recognition(self):
        """Test that valid HTS code formats are recognized."""
        service = PostExtractionService.__new__(PostExtractionService)

        valid_codes = [
            "8471.30.01",
            "7208.10.15",
            "8528.71.00",
            "8471300100",
            "7208101500",
        ]

        for code in valid_codes:
            normalized = service._normalize_hts_code(code)
            assert service._is_valid_hts_format(normalized), f"Code {code} should be valid"

    def test_invalid_hts_format_detection(self):
        """Test that invalid HTS code formats are detected."""
        service = PostExtractionService.__new__(PostExtractionService)

        invalid_codes = [
            "ABC",
            "12",
            "1234567890123",  # Too long
            "ABCD.EF.GH",
        ]

        for code in invalid_codes:
            normalized = service._normalize_hts_code(code)
            assert not service._is_valid_hts_format(normalized), f"Code {code} should be invalid"

    def test_hts_normalization(self):
        """Test HTS code normalization removes non-digits."""
        service = PostExtractionService.__new__(PostExtractionService)

        test_cases = [
            ("8471.30.01", "84713001"),
            ("8471-30-01", "84713001"),
            ("8471 30 01", "84713001"),
            ("8471.30.0100", "8471300100"),
        ]

        for input_code, expected in test_cases:
            result = service._normalize_hts_code(input_code)
            assert result == expected, f"Expected {expected}, got {result}"


class TestHTSCodeExtraction:
    """Tests for extracting HTS codes from template results."""

    def test_extract_hts_from_line_items(self):
        """Test HTS code extraction from line items."""
        service = PostExtractionService.__new__(PostExtractionService)
        service.HTS_FIELDS = PostExtractionService.HTS_FIELDS

        extractions = SAMPLE_COMMERCIAL_INVOICE_EXTRACTION["extractions"]
        hts_codes = service._extract_hts_codes(extractions)

        assert len(hts_codes) == 2
        assert "8471.30.01" in hts_codes
        assert "7208.10.15" in hts_codes

    def test_extract_hts_from_customs_entry(self):
        """Test HTS code extraction from customs entry line items."""
        service = PostExtractionService.__new__(PostExtractionService)
        service.HTS_FIELDS = PostExtractionService.HTS_FIELDS

        extractions = SAMPLE_CUSTOMS_ENTRY_EXTRACTION["extractions"]
        hts_codes = service._extract_hts_codes(extractions)

        assert len(hts_codes) == 1
        assert "8528.71.00" in hts_codes

    def test_extract_hts_deduplication(self):
        """Test that duplicate HTS codes are removed."""
        service = PostExtractionService.__new__(PostExtractionService)
        service.HTS_FIELDS = PostExtractionService.HTS_FIELDS

        extractions = [
            {
                "field_name": "line_items",
                "value": [
                    {"hs_code": "8471.30.01"},
                    {"hs_code": "8471.30.01"},  # Duplicate
                    {"hs_code": "7208.10.15"},
                ],
                "found": True,
            },
        ]

        hts_codes = service._extract_hts_codes(extractions)

        assert len(hts_codes) == 2
        assert hts_codes.count("8471.30.01") == 1


# ==================== Unit Tests for Party Extraction ====================

class TestPartyExtraction:
    """Tests for extracting parties from template results."""

    def test_extract_parties_from_commercial_invoice(self):
        """Test party extraction from commercial invoice."""
        service = PostExtractionService.__new__(PostExtractionService)
        service.PARTY_FIELDS = PostExtractionService.PARTY_FIELDS

        extractions = SAMPLE_COMMERCIAL_INVOICE_EXTRACTION["extractions"]
        extraction_map = service._build_extraction_map(extractions)
        parties = service._extract_parties(extraction_map)

        party_names = [p[0] for p in parties]
        party_types = [p[1] for p in parties]

        assert "Acme Trading Co." in party_names
        assert "Global Imports LLC" in party_names
        assert "US Import Corp" in party_names
        assert "seller" in party_types
        assert "buyer" in party_types
        assert "importer" in party_types

    def test_extract_parties_from_customs_entry(self):
        """Test party extraction from customs entry."""
        service = PostExtractionService.__new__(PostExtractionService)
        service.PARTY_FIELDS = PostExtractionService.PARTY_FIELDS

        extractions = SAMPLE_CUSTOMS_ENTRY_EXTRACTION["extractions"]
        extraction_map = service._build_extraction_map(extractions)
        parties = service._extract_parties(extraction_map)

        party_names = [p[0] for p in parties]

        assert "Samsung Electronics America" in party_names
        assert "Best Buy Stores" in party_names

    def test_party_name_cleaning(self):
        """Test party name cleaning removes common suffixes."""
        service = PostExtractionService.__new__(PostExtractionService)

        test_cases = [
            ("Acme Corp", "Acme"),
            ("Global Trading LLC", "Global Trading"),
            ("Samsung Inc.", "Samsung"),
            ("Best Buy Ltd.", "Best Buy"),
            ("Simple Name", "Simple Name"),
        ]

        for input_name, expected in test_cases:
            result = service._clean_party_name(input_name)
            assert result == expected, f"Expected '{expected}', got '{result}'"


# ==================== Unit Tests for OFAC Screening ====================

class TestOFACScreening:
    """Tests for OFAC SDN screening functionality."""

    def test_risk_level_determination_critical(self):
        """Test critical risk level for confirmed match."""
        service = PostExtractionService.__new__(PostExtractionService)

        screening_result = {
            "risk_level": "confirmed_match",
            "matches": [{"score": 0.99}],
        }

        risk = service._determine_risk_level(screening_result)
        assert risk == RiskLevel.CRITICAL

    def test_risk_level_determination_high(self):
        """Test high risk level for high-scoring possible match."""
        service = PostExtractionService.__new__(PostExtractionService)

        screening_result = {
            "risk_level": "possible_match",
            "matches": [{"score": 0.96}],
        }

        risk = service._determine_risk_level(screening_result)
        assert risk == RiskLevel.HIGH

    def test_risk_level_determination_medium(self):
        """Test medium risk level for medium-scoring possible match."""
        service = PostExtractionService.__new__(PostExtractionService)

        screening_result = {
            "risk_level": "possible_match",
            "matches": [{"score": 0.88}],
        }

        risk = service._determine_risk_level(screening_result)
        assert risk == RiskLevel.MEDIUM

    def test_risk_level_determination_clear(self):
        """Test clear risk level for no matches."""
        service = PostExtractionService.__new__(PostExtractionService)

        screening_result = {
            "risk_level": "clear",
            "matches": [],
        }

        risk = service._determine_risk_level(screening_result)
        assert risk == RiskLevel.CLEAR


# ==================== Unit Tests for NAICS Classification ====================

class TestNAICSClassification:
    """Tests for NAICS code classification functionality."""

    def test_extract_product_descriptions(self):
        """Test product description extraction from extractions."""
        service = PostExtractionService.__new__(PostExtractionService)

        extractions = SAMPLE_COMMERCIAL_INVOICE_EXTRACTION["extractions"]
        descriptions = service._extract_product_descriptions(extractions)

        assert len(descriptions) == 2
        assert "Electronic Components" in descriptions
        assert "Steel Parts" in descriptions

    def test_search_term_extraction(self):
        """Test key term extraction from text."""
        service = PostExtractionService.__new__(PostExtractionService)

        text = "Electronic components for computer manufacturing and steel parts"
        terms = service._extract_search_terms(text)

        # Should filter out stop words and short words
        assert "electronic" in terms
        assert "components" in terms
        assert "computer" in terms
        assert "manufacturing" in terms
        assert "steel" in terms
        assert "for" not in terms
        assert "and" not in terms


# ==================== Unit Tests for Overall Risk Calculation ====================

class TestOverallRiskCalculation:
    """Tests for overall risk level calculation."""

    def test_overall_risk_from_screenings(self):
        """Test overall risk calculation considers party screenings."""
        service = PostExtractionService.__new__(PostExtractionService)

        result = PostExtractionResult(
            document_id="test-doc",
            template_name="Test Template",
        )
        result.party_screenings = [
            PartyScreeningResult(
                party_name="Test Party",
                party_type="seller",
                risk_level=RiskLevel.HIGH,
                matches_found=2,
            ),
        ]
        result.hts_validations = []

        risk = service._calculate_overall_risk(result)
        assert risk == RiskLevel.HIGH

    def test_overall_risk_from_hts_validation(self):
        """Test overall risk considers HTS validation failures."""
        service = PostExtractionService.__new__(PostExtractionService)

        result = PostExtractionResult(
            document_id="test-doc",
            template_name="Test Template",
        )
        result.party_screenings = []
        result.hts_validations = [
            HTSValidationResult(
                hts_code="1234.56.78",
                is_valid=False,
                found_in_database=False,
            ),
        ]

        risk = service._calculate_overall_risk(result)
        assert risk == RiskLevel.LOW

    def test_overall_risk_clear_when_all_pass(self):
        """Test overall risk is clear when all checks pass."""
        service = PostExtractionService.__new__(PostExtractionService)

        result = PostExtractionResult(
            document_id="test-doc",
            template_name="Test Template",
        )
        result.party_screenings = [
            PartyScreeningResult(
                party_name="Safe Company",
                party_type="seller",
                risk_level=RiskLevel.CLEAR,
                matches_found=0,
            ),
        ]
        result.hts_validations = [
            HTSValidationResult(
                hts_code="8471.30.01",
                is_valid=True,
                found_in_database=True,
            ),
        ]

        risk = service._calculate_overall_risk(result)
        assert risk == RiskLevel.CLEAR


# ==================== Unit Tests for Extraction Map Building ====================

class TestExtractionMapBuilding:
    """Tests for building extraction field maps."""

    def test_build_extraction_map(self):
        """Test building extraction map from results."""
        service = PostExtractionService.__new__(PostExtractionService)

        extractions = [
            {"field_name": "Invoice_Number", "value": "INV-001", "found": True},
            {"field_name": "seller_name", "value": "Acme", "found": True},
            {"field_name": "missing_field", "value": None, "found": False},
        ]

        result = service._build_extraction_map(extractions)

        assert result["invoice_number"] == "INV-001"
        assert result["seller_name"] == "Acme"
        assert "missing_field" not in result


# ==================== Data Class Tests ====================

class TestDataClasses:
    """Tests for data class serialization."""

    def test_hts_validation_result_to_dict(self):
        """Test HTSValidationResult serialization."""
        result = HTSValidationResult(
            hts_code="8471.30.01",
            is_valid=True,
            found_in_database=True,
            description="Computers",
            duty_rate="Free",
            duty_rate_percent=0.0,
            chapter=84,
        )

        data = result.to_dict()

        assert data["hts_code"] == "8471.30.01"
        assert data["is_valid"] is True
        assert data["description"] == "Computers"
        assert data["duty_rate"] == "Free"

    def test_party_screening_result_to_dict(self):
        """Test PartyScreeningResult serialization."""
        result = PartyScreeningResult(
            party_name="Test Company",
            party_type="seller",
            risk_level=RiskLevel.MEDIUM,
            matches_found=2,
            matches=[{"name": "Match 1", "score": 0.85}],
            screened_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        )

        data = result.to_dict()

        assert data["party_name"] == "Test Company"
        assert data["party_type"] == "seller"
        assert data["risk_level"] == "medium"
        assert data["matches_found"] == 2
        assert len(data["matches"]) == 1

    def test_post_extraction_result_to_dict(self):
        """Test PostExtractionResult serialization."""
        result = PostExtractionResult(
            document_id="doc-123",
            template_name="Commercial Invoice",
            overall_risk_level=RiskLevel.LOW,
            processed_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        )
        result.issues_found = [{"type": "invalid_hts", "description": "Test"}]

        data = result.to_dict()

        assert data["document_id"] == "doc-123"
        assert data["template_name"] == "Commercial Invoice"
        assert data["overall_risk_level"] == "low"
        assert len(data["issues_found"]) == 1


# ==================== Sync Service Tests ====================

class TestPostExtractionServiceSync:
    """Tests for synchronous version of PostExtractionService."""

    def test_sync_service_inherits_helper_methods(self):
        """Test that sync service has all helper methods."""
        assert hasattr(PostExtractionServiceSync, "_build_extraction_map")
        assert hasattr(PostExtractionServiceSync, "_extract_hts_codes")
        assert hasattr(PostExtractionServiceSync, "_extract_parties")
        assert hasattr(PostExtractionServiceSync, "_extract_product_descriptions")
        assert hasattr(PostExtractionServiceSync, "_calculate_overall_risk")

    def test_sync_service_party_fields(self):
        """Test that sync service has party fields."""
        assert PostExtractionServiceSync.PARTY_FIELDS == PostExtractionService.PARTY_FIELDS

    def test_sync_service_hts_fields(self):
        """Test that sync service has HTS fields."""
        assert PostExtractionServiceSync.HTS_FIELDS == PostExtractionService.HTS_FIELDS


# ==================== Integration-style Tests (without DB) ====================

class TestComplianceWorkflow:
    """Integration-style tests for the compliance workflow."""

    def test_full_extraction_processing_structure(self):
        """Test that full processing returns expected structure."""
        # Create a mock result to verify structure
        result = PostExtractionResult(
            document_id="test-doc-123",
            template_name="Commercial Invoice",
            processed_at=datetime.now(timezone.utc),
        )

        # Add sample data
        result.hts_validations = [
            HTSValidationResult(
                hts_code="8471.30.01",
                is_valid=True,
                found_in_database=True,
                description="Computers",
                duty_rate="Free",
            )
        ]
        result.party_screenings = [
            PartyScreeningResult(
                party_name="Acme Trading",
                party_type="seller",
                risk_level=RiskLevel.CLEAR,
                matches_found=0,
            )
        ]
        result.naics_classifications = [
            NAICSClassificationResult(
                suggested_codes=[{"naics_code": "334", "title": "Computer Manufacturing"}],
                confidence=0.75,
                based_on="Product descriptions (2 items)",
            )
        ]

        # Verify to_dict produces valid structure
        data = result.to_dict()

        assert "document_id" in data
        assert "template_name" in data
        assert "hts_validations" in data
        assert "party_screenings" in data
        assert "naics_classifications" in data
        assert "overall_risk_level" in data
        assert "processed_at" in data

    def test_issues_aggregation(self):
        """Test that issues are properly aggregated."""
        result = PostExtractionResult(
            document_id="test-doc",
            template_name="Test",
        )

        # Add multiple issues
        result.issues_found = [
            {
                "type": "invalid_hts",
                "severity": "medium",
                "description": "HTS code not found",
            },
            {
                "type": "ofac_match",
                "severity": "high",
                "description": "OFAC match found",
            },
        ]

        data = result.to_dict()

        assert len(data["issues_found"]) == 2
        assert data["issues_found"][0]["type"] == "invalid_hts"
        assert data["issues_found"][1]["type"] == "ofac_match"


# ==================== Edge Case Tests ====================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_extractions(self):
        """Test handling of empty extraction results."""
        service = PostExtractionService.__new__(PostExtractionService)
        service.PARTY_FIELDS = PostExtractionService.PARTY_FIELDS
        service.HTS_FIELDS = PostExtractionService.HTS_FIELDS

        extractions = []

        hts_codes = service._extract_hts_codes(extractions)
        extraction_map = service._build_extraction_map(extractions)
        parties = service._extract_parties(extraction_map)
        descriptions = service._extract_product_descriptions(extractions)

        assert hts_codes == []
        assert extraction_map == {}
        assert parties == []
        assert descriptions == []

    def test_malformed_line_items(self):
        """Test handling of malformed line items."""
        service = PostExtractionService.__new__(PostExtractionService)
        service.HTS_FIELDS = PostExtractionService.HTS_FIELDS

        extractions = [
            {
                "field_name": "line_items",
                "value": [
                    {"hs_code": None},  # None value
                    {"other_field": "value"},  # Missing hs_code
                    "not_a_dict",  # Not a dict
                ],
                "found": True,
            },
        ]

        # Should not raise and should return empty list
        hts_codes = service._extract_hts_codes(extractions)
        assert hts_codes == []

    def test_party_name_with_only_whitespace(self):
        """Test handling of party names with only whitespace."""
        service = PostExtractionService.__new__(PostExtractionService)
        service.PARTY_FIELDS = PostExtractionService.PARTY_FIELDS

        extraction_map = {
            "seller_name": "   ",
            "buyer_name": "",
        }

        parties = service._extract_parties(extraction_map)
        assert parties == []

    def test_hts_code_edge_formats(self):
        """Test HTS code handling with edge case formats."""
        service = PostExtractionService.__new__(PostExtractionService)

        edge_cases = [
            ("", False),
            (".", False),
            ("....", False),
            ("1234", True),  # 4 digits is valid
            ("12345678901", False),  # 11 digits is too long
        ]

        for code, expected_valid in edge_cases:
            normalized = service._normalize_hts_code(code)
            result = service._is_valid_hts_format(normalized)
            assert result == expected_valid, f"Code '{code}' validity should be {expected_valid}"


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
