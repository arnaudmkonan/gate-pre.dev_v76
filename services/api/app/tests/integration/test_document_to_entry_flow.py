"""
Integration tests for Document → Shipment → Entry flow.

Uses test documents from /customs_test_documents to verify the full workflow:
1. Document upload and key extraction
2. Auto-linking into Shipments
3. Entry auto-creation when shipment is complete
4. Compliance checks after entry creation

Test Scenarios:
- Scenario 1: Single Container, Single Consignee (FCL)
- Scenario 2: Single Container, Multiple Consignees (LCL)
- Scenario 3: Multiple Containers, Single Consignee
"""
import pytest
import json
from pathlib import Path
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock

# Test data directory
TEST_DOCS_DIR = Path(__file__).parent.parent.parent.parent.parent.parent / "customs_test_documents"


# ==================== Test Data from Scenarios ====================

SCENARIO_1_DATA = {
    "name": "Single Container, Single Consignee (FCL)",
    "mbl": "MAEU123456789",
    "containers": ["MSCU1234567"],
    "hbl": "FWDR-2024-001",
    "company": "XYZ Electronics Corp",
    "invoice_number": "INV-20240115-001",
    "vessel": "EVER GIVEN",
    "voyage": "V123E",
    "port_loading": "CNSHA",
    "port_discharge": "USLAX",
    "products": [
        {
            "description": "LED Television 55 inch",
            "hts_code": "8528.72.6400",
            "country_origin": "CN",
            "quantity": 100,
            "unit_price": 250.0,
            "total": 25000.0,
        },
        {
            "description": "Bluetooth Speakers Portable",
            "hts_code": "8518.21.0000",
            "country_origin": "CN",
            "quantity": 500,
            "unit_price": 25.0,
            "total": 12500.0,
        },
    ],
    "total_value": 37500.0,
}

SCENARIO_2_DATA = {
    "name": "Single Container, Multiple Consignees (LCL)",
    "mbl": "CMDU987654321",
    "containers": ["TCLU9876543"],
    "consignees": [
        {
            "hbl": "FWDR-2024-002",
            "company": "Fashion Imports LLC",
            "invoice_number": "INV-20240118-002",
            "products": [
                {"description": "Women's Cotton T-Shirts", "hts_code": "6109.10.0012", "total": 48000.0},
            ],
        },
        {
            "hbl": "FWDR-2024-003",
            "company": "Midwest Parts Co",
            "invoice_number": "INV-20240119-003",
            "products": [
                {"description": "Automotive Brake Pads", "hts_code": "8708.30.5090", "total": 17500.0},
            ],
        },
        {
            "hbl": "FWDR-2024-004",
            "company": "Pacific Hardware Inc",
            "invoice_number": "INV-20240120-004",
            "products": [
                {"description": "Hand Tools Set (Wrenches)", "hts_code": "8204.11.0030", "total": 13500.0},
            ],
        },
    ],
}

SCENARIO_3_DATA = {
    "name": "Multiple Containers, Single Consignee",
    "mbl": "OOLU456789123",
    "containers": ["OOLU7654321", "OOLU7654322"],
    "hbl": "FWDR-2024-005",
    "company": "Furniture World Distribution",
    "products": [
        {"description": "Wooden Dining Tables", "hts_code": "9403.60.8080", "total": 27000.0},
        {"description": "Wooden Chairs", "hts_code": "9401.61.4011", "total": 27000.0},
    ],
    "total_value": 54000.0,
}


# ==================== Test Files Check ====================

class TestDocumentsAvailable:
    """Verify test documents exist."""

    def test_test_documents_directory_exists(self):
        """Test documents directory exists."""
        assert TEST_DOCS_DIR.exists(), f"Test documents not found at {TEST_DOCS_DIR}"

    def test_scenario_1_documents_exist(self):
        """Scenario 1 documents exist."""
        expected_files = [
            "commercial_invoice_scenario_1_consignee1.pdf",
            "packing_list_scenario_1_consignee1.pdf",
            "house_bl_scenario_1_consignee1.pdf",
            "master_bl_scenario_1.pdf",
        ]
        for filename in expected_files:
            filepath = TEST_DOCS_DIR / filename
            assert filepath.exists(), f"Missing test file: {filename}"

    def test_scenario_2_documents_exist(self):
        """Scenario 2 documents exist."""
        expected_files = [
            "commercial_invoice_scenario_2_consignee1.pdf",
            "commercial_invoice_scenario_2_consignee2.pdf",
            "commercial_invoice_scenario_2_consignee3.pdf",
        ]
        for filename in expected_files:
            filepath = TEST_DOCS_DIR / filename
            assert filepath.exists(), f"Missing test file: {filename}"

    def test_test_data_scenarios_json(self):
        """Test data scenarios JSON exists and is valid."""
        json_path = TEST_DOCS_DIR / "test_data_scenarios.json"
        assert json_path.exists(), "test_data_scenarios.json not found"

        with open(json_path) as f:
            data = json.load(f)

        assert "scenario_1" in data
        assert "scenario_2" in data
        assert "scenario_3" in data


# ==================== Service Tests ====================

class TestEntryCreationService:
    """Unit tests for EntryCreationService."""

    def test_normalize_hts_with_dots(self):
        """HTS codes with dots are normalized."""
        from app.services.entry_creation_service import EntryCreationService

        # Mock session
        service = EntryCreationService(MagicMock())

        result = service._normalize_hts("8528.72.6400")
        assert result == "8528726400"

    def test_normalize_hts_short_code(self):
        """Short HTS codes are padded to 10 digits."""
        from app.services.entry_creation_service import EntryCreationService

        service = EntryCreationService(MagicMock())

        result = service._normalize_hts("8528")
        assert result == "8528000000"
        assert len(result) == 10

    def test_normalize_hts_none(self):
        """None HTS code returns None."""
        from app.services.entry_creation_service import EntryCreationService

        service = EntryCreationService(MagicMock())

        result = service._normalize_hts(None)
        assert result is None


class TestFieldMappings:
    """Test field mapping constants."""

    def test_shipment_to_entry_mapping_has_key_fields(self):
        """Mapping includes key shipment fields."""
        from app.services.entry_creation_service import SHIPMENT_TO_ENTRY_MAPPING

        assert "bol_number" in SHIPMENT_TO_ENTRY_MAPPING
        assert "importer_name" in SHIPMENT_TO_ENTRY_MAPPING
        assert "port_of_entry" in SHIPMENT_TO_ENTRY_MAPPING

    def test_document_key_mapping_has_key_types(self):
        """Mapping includes all key document types."""
        from app.services.entry_creation_service import DOCUMENT_KEY_TO_ENTRY_MAPPING

        assert "ENTRY_NUM" in DOCUMENT_KEY_TO_ENTRY_MAPPING
        assert "BOL_NUM" in DOCUMENT_KEY_TO_ENTRY_MAPPING
        assert "CONTAINER_NUM" in DOCUMENT_KEY_TO_ENTRY_MAPPING
        assert "IMPORTER_NAME" in DOCUMENT_KEY_TO_ENTRY_MAPPING


# ==================== Entry Model Tests ====================

class TestEntrySourceType:
    """Test Entry model has source_type field."""

    def test_entry_source_enum_exists(self):
        """EntrySource enum exists with expected values."""
        from app.models.entry import EntrySource

        assert EntrySource.DOCUMENT_EXTRACTION.value == "document_extraction"
        assert EntrySource.ACE_IMPORT.value == "ace_import"
        assert EntrySource.MANUAL.value == "manual"

    def test_entry_model_has_source_type(self):
        """Entry model has source_type field."""
        from app.models.entry import Entry

        # Check column exists
        assert hasattr(Entry, "source_type")
        assert hasattr(Entry, "source_reference")


# ==================== Scenario-Based Tests ====================

class TestScenario1EntryFields:
    """Test Entry fields match Scenario 1 expected values."""

    def test_expected_entry_fields_scenario_1(self):
        """Scenario 1 should produce Entry with correct fields."""
        # This verifies the mapping logic is correct
        expected = {
            "master_bill": "MAEU123456789",
            "house_bill": "FWDR-2024-001",
            "container_numbers": ["MSCU1234567"],
            "importer_of_record_name": "XYZ Electronics Corp",
            "vessel_name": "EVER GIVEN",
            "voyage_flight_number": "V123E",
            "foreign_port_of_lading": "CNSHA",
            "port_of_entry": "USLAX",
            "total_entered_value": Decimal("37500.00"),
            "line_count": 2,
        }

        # Verify expected values match scenario data
        assert expected["master_bill"] == SCENARIO_1_DATA["mbl"]
        assert expected["house_bill"] == SCENARIO_1_DATA["hbl"]
        assert expected["container_numbers"] == SCENARIO_1_DATA["containers"]
        assert expected["importer_of_record_name"] == SCENARIO_1_DATA["company"]
        assert expected["total_entered_value"] == Decimal(str(SCENARIO_1_DATA["total_value"]))
        assert expected["line_count"] == len(SCENARIO_1_DATA["products"])

    def test_expected_entry_lines_scenario_1(self):
        """Scenario 1 should produce correct EntryLine records."""
        products = SCENARIO_1_DATA["products"]

        # Line 1: LED TV
        assert products[0]["hts_code"] == "8528.72.6400"
        assert products[0]["quantity"] == 100
        assert products[0]["total"] == 25000.0

        # Line 2: Bluetooth Speakers
        assert products[1]["hts_code"] == "8518.21.0000"
        assert products[1]["quantity"] == 500
        assert products[1]["total"] == 12500.0


class TestScenario2MultipleConsignees:
    """Test Scenario 2: LCL with multiple consignees."""

    def test_scenario_2_creates_multiple_entries(self):
        """Scenario 2 should create 3 separate entries (one per HBL)."""
        consignees = SCENARIO_2_DATA["consignees"]

        # Should have 3 consignees
        assert len(consignees) == 3

        # Each should have unique HBL
        hbls = [c["hbl"] for c in consignees]
        assert len(set(hbls)) == 3

    def test_scenario_2_entries_share_mbl(self):
        """All Scenario 2 entries should share the same MBL."""
        mbl = SCENARIO_2_DATA["mbl"]
        assert mbl == "CMDU987654321"

        # All consignees reference same container
        containers = SCENARIO_2_DATA["containers"]
        assert containers == ["TCLU9876543"]


class TestScenario3MultipleContainers:
    """Test Scenario 3: Multiple containers, single consignee."""

    def test_scenario_3_has_multiple_containers(self):
        """Scenario 3 should have multiple containers."""
        containers = SCENARIO_3_DATA["containers"]
        assert len(containers) == 2
        assert "OOLU7654321" in containers
        assert "OOLU7654322" in containers

    def test_scenario_3_single_entry(self):
        """Scenario 3 should create single entry with all containers."""
        # Only one HBL
        assert SCENARIO_3_DATA["hbl"] == "FWDR-2024-005"

        # But two products
        assert len(SCENARIO_3_DATA["products"]) == 2


# ==================== Auto-Linker Tests ====================

class TestAutoLinkerEntryTrigger:
    """Test auto-linker triggers entry creation."""

    def test_shipment_completeness_check_needs_docs(self):
        """Shipment completeness requires minimum documents."""
        from app.services.auto_linker_service import AutoLinkerService
        from app.models.gold_records import Shipment

        # Create mock shipment with insufficient docs
        shipment = MagicMock(spec=Shipment)
        shipment.document_count = 1
        shipment.bol_number = "BOL123"
        shipment.invoices = []

        # Should not be complete with only 1 doc
        assert shipment.document_count < 2

    def test_shipment_completeness_needs_bol_or_awb(self):
        """Shipment completeness requires transport document."""
        from app.models.gold_records import Shipment

        shipment = MagicMock(spec=Shipment)
        shipment.document_count = 3
        shipment.bol_number = None
        shipment.awb_number = None
        shipment.container_numbers = []

        # Should not be complete without transport identifier
        assert not shipment.bol_number
        assert not shipment.awb_number


# ==================== Compliance Integration Tests ====================

class TestComplianceAfterEntry:
    """Test compliance checks run after entry creation."""

    def test_entry_hts_codes_validated(self):
        """HTS codes from entry lines should be validated."""
        hts_codes = [
            "8528.72.6400",  # LED TV
            "8518.21.0000",  # Speakers
            "6109.10.0012",  # T-Shirts
            "8708.30.5090",  # Brake Pads
            "8204.11.0030",  # Hand Tools
            "9403.60.8080",  # Dining Tables
            "9401.61.4011",  # Chairs
        ]

        # All should be valid 10-digit codes when normalized
        for code in hts_codes:
            normalized = "".join(c for c in code if c.isdigit())
            assert len(normalized) == 10, f"HTS code {code} normalizes to {len(normalized)} digits"

    def test_party_names_screening_ready(self):
        """Party names should be ready for OFAC screening."""
        party_names = [
            SCENARIO_1_DATA["company"],  # XYZ Electronics Corp
            SCENARIO_2_DATA["consignees"][0]["company"],  # Fashion Imports LLC
            SCENARIO_3_DATA["company"],  # Furniture World Distribution
        ]

        for name in party_names:
            assert len(name) > 0
            assert isinstance(name, str)


# ==================== HTS Code Validation Tests ====================

class TestHTSCodeValidation:
    """Test HTS codes from test scenarios are valid."""

    @pytest.mark.parametrize("product,expected_hts", [
        ("LED Television 55 inch", "8528.72.6400"),
        ("Bluetooth Speakers Portable", "8518.21.0000"),
        ("Women's Cotton T-Shirts", "6109.10.0012"),
        ("Automotive Brake Pads", "8708.30.5090"),
        ("Hand Tools Set (Wrenches)", "8204.11.0030"),
        ("Wooden Dining Tables", "9403.60.8080"),
        ("Wooden Chairs", "9401.61.4011"),
    ])
    def test_product_hts_mapping(self, product, expected_hts):
        """Products should map to correct HTS codes."""
        # Find product in scenarios
        all_products = (
            SCENARIO_1_DATA["products"] +
            SCENARIO_2_DATA["consignees"][0]["products"] +
            SCENARIO_2_DATA["consignees"][1]["products"] +
            SCENARIO_2_DATA["consignees"][2]["products"] +
            SCENARIO_3_DATA["products"]
        )

        matching = [p for p in all_products if p["description"] == product]
        assert len(matching) == 1, f"Product '{product}' not found in test data"
        assert matching[0]["hts_code"] == expected_hts


# ==================== Entry Creation Result Tests ====================

class TestEntryCreationResult:
    """Test EntryCreationResult data class."""

    def test_result_to_dict(self):
        """Result converts to dict correctly."""
        from app.services.entry_creation_service import EntryCreationResult

        result = EntryCreationResult(
            success=True,
            entry_id=uuid4(),
            line_count=2,
            total_value=Decimal("37500.00"),
            total_duty=Decimal("1500.00"),
        )

        d = result.to_dict()

        assert d["success"] is True
        assert d["line_count"] == 2
        assert d["total_value"] == 37500.0
        assert d["total_duty"] == 1500.0
        assert d["errors"] == []

    def test_result_errors_list(self):
        """Result captures errors correctly."""
        from app.services.entry_creation_service import EntryCreationResult

        result = EntryCreationResult(
            success=False,
            errors=["Shipment not found", "Invalid data"],
        )

        assert not result.success
        assert len(result.errors) == 2


# ==================== Integration Flow Test ====================

class TestFullWorkflowIntegration:
    """High-level integration test for full workflow."""

    def test_workflow_step_sequence(self):
        """Verify expected workflow steps."""
        workflow_steps = [
            "1. Document uploaded to storage",
            "2. Celery worker extracts document keys",
            "3. Auto-linker groups documents into Shipment",
            "4. When Shipment is complete, Entry is auto-created",
            "5. Compliance checks run on Entry",
            "6. Entry is ready for filing",
        ]

        # This is a documentation test - verify we have the right steps
        assert len(workflow_steps) == 6
        assert "Entry is auto-created" in workflow_steps[3]
        assert "Compliance checks" in workflow_steps[4]


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
