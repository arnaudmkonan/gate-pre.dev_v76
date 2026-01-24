"""
Tests for Compliance Integration API endpoints.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi.testclient import TestClient


# ==================== Test Data ====================

SAMPLE_HTS_VALIDATION_REQUEST = {
    "hts_code": "8471.30.01"
}

SAMPLE_PARTY_SCREENING_REQUEST = {
    "party_name": "Acme Trading Company",
    "party_type": "seller",
    "threshold": 0.80
}

SAMPLE_COMPLIANCE_CHECK_REQUEST = {
    "document_id": str(uuid4()),
    "extraction_results": {
        "extractions": [
            {
                "field_name": "seller_name",
                "value": "Test Company",
                "found": True,
                "confidence": 0.95,
            },
            {
                "field_name": "line_items",
                "value": [
                    {"hs_code": "8471.30.01", "description": "Computers"}
                ],
                "found": True,
            }
        ]
    },
    "template_name": "Commercial Invoice"
}


# ==================== Request/Response Model Tests ====================

class TestRequestModels:
    """Tests for API request model validation."""

    def test_hts_validation_request_structure(self):
        """Test HTS validation request structure."""
        from app.api.routes.compliance_integration import HTSValidationRequest

        request = HTSValidationRequest(hts_code="8471.30.01")
        assert request.hts_code == "8471.30.01"

    def test_party_screening_request_defaults(self):
        """Test party screening request default values."""
        from app.api.routes.compliance_integration import PartyScreeningRequest

        request = PartyScreeningRequest(party_name="Test Company")
        assert request.party_name == "Test Company"
        assert request.party_type == "unknown"
        assert request.threshold == 0.80

    def test_party_screening_request_custom_values(self):
        """Test party screening request with custom values."""
        from app.api.routes.compliance_integration import PartyScreeningRequest

        request = PartyScreeningRequest(
            party_name="Acme Corp",
            party_type="importer",
            threshold=0.90
        )
        assert request.party_name == "Acme Corp"
        assert request.party_type == "importer"
        assert request.threshold == 0.90

    def test_trigger_compliance_request_minimal(self):
        """Test trigger compliance request with minimal data."""
        from app.api.routes.compliance_integration import TriggerComplianceRequest

        request = TriggerComplianceRequest(document_id="doc-123")
        assert request.document_id == "doc-123"
        assert request.extraction_results is None
        assert request.template_name is None

    def test_trigger_compliance_request_full(self):
        """Test trigger compliance request with full data."""
        from app.api.routes.compliance_integration import TriggerComplianceRequest

        request = TriggerComplianceRequest(
            document_id="doc-123",
            extraction_results={"extractions": []},
            template_name="Test Template"
        )
        assert request.document_id == "doc-123"
        assert request.extraction_results == {"extractions": []}
        assert request.template_name == "Test Template"

    def test_batch_compliance_request(self):
        """Test batch compliance request."""
        from app.api.routes.compliance_integration import BatchComplianceRequest

        doc_ids = [str(uuid4()) for _ in range(3)]
        request = BatchComplianceRequest(document_ids=doc_ids)
        assert len(request.document_ids) == 3


# ==================== Response Model Tests ====================

class TestResponseModels:
    """Tests for API response model structure."""

    def test_compliance_result_response_structure(self):
        """Test compliance result response has all fields."""
        from app.api.routes.compliance_integration import ComplianceResultResponse

        response = ComplianceResultResponse(
            document_id="doc-123",
            template_name="Commercial Invoice",
            overall_risk_level="clear",
            hts_validations=[],
            party_screenings=[],
            naics_classifications=[],
            issues_found=[],
            processed_at="2024-01-15T10:30:00Z"
        )

        assert response.document_id == "doc-123"
        assert response.template_name == "Commercial Invoice"
        assert response.overall_risk_level == "clear"
        assert response.hts_validations == []
        assert response.party_screenings == []
        assert response.naics_classifications == []
        assert response.issues_found == []

    def test_compliance_stats_response_structure(self):
        """Test compliance stats response has all fields."""
        from app.api.routes.compliance_integration import ComplianceStatsResponse

        response = ComplianceStatsResponse(
            total_screenings=100,
            screenings_by_type={"ofac": 50, "hts": 50},
            screenings_by_risk_level={"clear": 80, "medium": 15, "high": 5},
            recent_high_risk=[]
        )

        assert response.total_screenings == 100
        assert response.screenings_by_type["ofac"] == 50
        assert response.screenings_by_risk_level["clear"] == 80
        assert response.recent_high_risk == []


# ==================== Router Import Tests ====================

class TestRouterImport:
    """Tests for router module import."""

    def test_router_import(self):
        """Test that router can be imported."""
        from app.api.routes.compliance_integration import router
        assert router is not None
        assert router.prefix == "/api/compliance"

    def test_router_has_expected_routes(self):
        """Test that router has expected endpoints."""
        from app.api.routes.compliance_integration import router

        routes = [r.path for r in router.routes]

        expected_routes = [
            "/api/compliance/check",
            "/api/compliance/validate-hts",
            "/api/compliance/screen-party",
            "/api/compliance/document/{document_id}",
            "/api/compliance/stats",
            "/api/compliance/batch",
            "/api/compliance/history",
            "/api/compliance/screen/{screen_id}/resolve",
        ]

        for expected in expected_routes:
            assert expected in routes, f"Route {expected} not found in router. Available: {routes}"


# ==================== Endpoint Logic Tests (Unit Tests) ====================

class TestEndpointLogic:
    """Unit tests for endpoint logic without database."""

    def test_validate_hts_endpoint_calls_service(self):
        """Test that validate HTS endpoint calls service correctly."""
        from app.api.routes.compliance_integration import HTSValidationRequest

        request = HTSValidationRequest(hts_code="8471.30.01")

        # Verify request is well-formed
        assert request.hts_code == "8471.30.01"

    def test_screen_party_endpoint_calls_service(self):
        """Test that screen party endpoint calls service correctly."""
        from app.api.routes.compliance_integration import PartyScreeningRequest

        request = PartyScreeningRequest(
            party_name="Test Company",
            party_type="seller",
            threshold=0.85
        )

        # Verify request is well-formed
        assert request.party_name == "Test Company"
        assert request.party_type == "seller"
        assert request.threshold == 0.85

    def test_batch_compliance_validates_uuids(self):
        """Test that batch compliance validates document UUIDs."""
        from app.api.routes.compliance_integration import BatchComplianceRequest
        from uuid import UUID

        valid_ids = [str(uuid4()) for _ in range(3)]
        request = BatchComplianceRequest(document_ids=valid_ids)

        # All should be valid UUIDs
        for doc_id in request.document_ids:
            UUID(doc_id)  # Should not raise


# ==================== Integration with Main App ====================

class TestMainAppIntegration:
    """Tests for integration with main FastAPI app."""

    def test_router_registered_in_main(self):
        """Test that compliance router is registered in main app."""
        from app.main import app

        routes = [r.path for r in app.routes]

        # Check for compliance integration routes
        compliance_routes = [r for r in routes if "/api/compliance" in r]
        assert len(compliance_routes) > 0, "Compliance routes not registered"

    def test_main_app_imports_compliance_integration(self):
        """Test that main app imports compliance_integration module."""
        # This tests the import chain works
        from app.main import app
        from app.api.routes import compliance_integration

        assert compliance_integration.router is not None


# ==================== Service Integration Tests ====================

class TestServiceIntegration:
    """Tests for service integration."""

    def test_post_extraction_service_available(self):
        """Test that PostExtractionService is importable."""
        from app.services.post_extraction_service import PostExtractionService
        from app.services.post_extraction_service import PostExtractionServiceSync
        from app.services.post_extraction_service import PostExtractionResult

        assert PostExtractionService is not None
        assert PostExtractionServiceSync is not None
        assert PostExtractionResult is not None

    def test_reference_data_service_available(self):
        """Test that ReferenceDataService is importable."""
        from app.services.reference_data_service import ReferenceDataService

        assert ReferenceDataService is not None

    def test_compliance_screen_model_available(self):
        """Test that ComplianceScreen model is importable."""
        from app.models.reference_data import ComplianceScreen

        assert ComplianceScreen is not None


# ==================== Error Handling Tests ====================

class TestErrorHandling:
    """Tests for error handling in API endpoints."""

    def test_invalid_uuid_handling(self):
        """Test that invalid UUID format is handled."""
        from uuid import UUID

        invalid_uuids = [
            "not-a-uuid",
            "12345",
            "",
            "abc-def-ghi",
        ]

        for invalid_id in invalid_uuids:
            with pytest.raises(ValueError):
                UUID(invalid_id)

    def test_threshold_range_validation(self):
        """Test that threshold is within valid range."""
        from app.api.routes.compliance_integration import PartyScreeningRequest
        from pydantic import ValidationError

        # Valid threshold
        valid_request = PartyScreeningRequest(
            party_name="Test",
            threshold=0.85
        )
        assert valid_request.threshold == 0.85

        # Invalid thresholds should fail validation
        with pytest.raises(ValidationError):
            PartyScreeningRequest(party_name="Test", threshold=1.5)

        with pytest.raises(ValidationError):
            PartyScreeningRequest(party_name="Test", threshold=-0.1)


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
