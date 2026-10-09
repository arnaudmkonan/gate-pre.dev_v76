"""
Unit tests — CBP Form 3461 Generator  (Task 2.3)
"""
import pytest
from decimal import Decimal
from datetime import date
from app.services.cbp3461_generator import CBP3461Generator, CBP3461Data


@pytest.fixture
def gen():
    return CBP3461Generator()


def make_valid_data(**overrides) -> CBP3461Data:
    data = CBP3461Data(
        entry_type="01",
        entry_date=date.today(),
        port_of_entry="2704",  # LA/Long Beach
        filer_code="ABC",
        importer_of_record_number="12-3456789",
        importer_name="ACME Imports LLC",
        master_bill_of_lading="MAEU1234567890",
        total_entered_value=Decimal("25000.00"),
        carrier_code="MAEU",
        vessel_name="Ever Given",
    )
    for k, v in overrides.items():
        setattr(data, k, v)
    return data


class TestCBP3461Validation:

    def test_valid_data_passes(self, gen):
        data = make_valid_data()
        errors = gen.validate(data)
        assert errors == []

    def test_missing_entry_type(self, gen):
        data = make_valid_data(entry_type=None)
        errors = gen.validate(data)
        assert any("entry_type" in e for e in errors)

    def test_invalid_entry_type(self, gen):
        data = make_valid_data(entry_type="99")
        errors = gen.validate(data)
        assert any("Unknown entry_type" in e for e in errors)

    def test_missing_ior_number(self, gen):
        data = make_valid_data(importer_of_record_number=None)
        errors = gen.validate(data)
        assert any("importer_of_record_number" in e for e in errors)

    def test_missing_port_of_entry(self, gen):
        data = make_valid_data(port_of_entry=None)
        errors = gen.validate(data)
        assert any("port_of_entry" in e for e in errors)

    def test_missing_bill_of_lading(self, gen):
        data = make_valid_data(master_bill_of_lading=None)
        errors = gen.validate(data)
        assert any("master_bill" in e for e in errors)

    def test_zero_value_fails(self, gen):
        data = make_valid_data(total_entered_value=Decimal("0"))
        errors = gen.validate(data)
        assert any("value" in e for e in errors)

    def test_missing_filer_code(self, gen):
        data = make_valid_data(filer_code=None)
        errors = gen.validate(data)
        assert any("filer_code" in e for e in errors)


class TestCBP3461EntryTypes:

    def test_consumption_type(self, gen):
        data = make_valid_data(entry_type="01")
        assert gen.ENTRY_TYPE_LABELS["01"] == "Consumption"

    def test_de_minimis_informal(self, gen):
        data = make_valid_data(entry_type="11", total_entered_value=Decimal("750.00"))
        assert gen.is_informal_entry(data) is True

    def test_value_under_800_is_informal(self, gen):
        data = make_valid_data(entry_type="01", total_entered_value=Decimal("799.99"))
        assert gen.is_informal_entry(data) is True

    def test_value_over_800_not_informal(self, gen):
        data = make_valid_data(entry_type="01", total_entered_value=Decimal("801.00"))
        assert gen.is_informal_entry(data) is False

    def test_ftz_type(self, gen):
        data = make_valid_data(entry_type="06")
        assert gen.ENTRY_TYPE_LABELS["06"] == "FTZ - Admission"


class TestCBP3461ToDict:

    def test_to_dict_contains_form_type(self, gen):
        data = make_valid_data()
        result = gen.to_dict(data)
        assert result["form"] == "CBP-3461"

    def test_to_dict_includes_all_key_fields(self, gen):
        data = make_valid_data()
        result = gen.to_dict(data)
        for key in ["entry_type", "port_of_entry", "filer_code",
                    "importer_of_record_number", "master_bill_of_lading",
                    "total_entered_value"]:
            assert key in result

    def test_to_dict_entry_type_label(self, gen):
        data = make_valid_data(entry_type="01")
        result = gen.to_dict(data)
        assert result["entry_type_label"] == "Consumption"

    def test_to_dict_serialises_decimal_as_str(self, gen):
        data = make_valid_data(total_entered_value=Decimal("12345.67"))
        result = gen.to_dict(data)
        assert result["total_entered_value"] == "12345.67"


class TestCBP3461PDFGeneration:

    def test_generate_pdf_returns_bytes(self, gen):
        """Skip if reportlab not installed."""
        pytest.importorskip("reportlab")
        data = make_valid_data()
        pdf = gen.generate_pdf(data)
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"  # Valid PDF magic number

    def test_generate_pdf_raises_without_reportlab(self, gen, monkeypatch):
        """Ensure helpful error when reportlab is absent."""
        import app.services.cbp3461_generator as mod
        monkeypatch.setattr(mod, "REPORTLAB_AVAILABLE", False)
        data = make_valid_data()
        with pytest.raises(RuntimeError, match="reportlab"):
            gen.generate_pdf(data)
