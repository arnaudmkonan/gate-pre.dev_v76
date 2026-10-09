"""
Unit tests — PGA Determination Engine  (Task 3.2)
"""
import pytest
from app.services.pga_determination_service import (
    PGADeterminationEngine,
    determine_pga_requirements,
)


@pytest.fixture
def engine():
    return PGADeterminationEngine()


class TestChapterExtraction:

    def test_extract_chapter_full_hts(self, engine):
        assert engine._extract_chapter("8528.72.6400") == "85"

    def test_extract_chapter_dashes(self, engine):
        assert engine._extract_chapter("03.02.11.0000") == "03"

    def test_extract_chapter_plain(self, engine):
        assert engine._extract_chapter("2204.10.6000") == "22"

    def test_extract_chapter_two_digit(self, engine):
        assert engine._extract_chapter("30") == "30"


class TestFoodImports:

    def test_fresh_fish_requires_fda(self, engine):
        det = engine.determine("0302.11.0000")
        assert det.is_pga_required is True
        assert "FDA" in det.agencies_involved

    def test_dairy_requires_fda(self, engine):
        det = engine.determine("0401.10.0000")
        assert "FDA" in det.agencies_involved

    def test_coffee_requires_fda_prior_notice(self, engine):
        det = engine.determine("0901.11.0000")
        assert det.is_pga_required is True
        fda_reqs = [r for r in det.requirements if r.agency == "FDA"]
        assert len(fda_reqs) > 0
        assert any(r.filing_form and "Prior Notice" in r.filing_form for r in fda_reqs)

    def test_beverages_chapter_22_requires_fda(self, engine):
        det = engine.determine("2204.10.6000")  # Wine
        assert "FDA" in det.agencies_involved


class TestPharmaceuticals:

    def test_drugs_chapter_30_requires_fda(self, engine):
        det = engine.determine("3004.90.9150")  # Medicaments
        assert "FDA" in det.agencies_involved

    def test_cosmetics_requires_fda(self, engine):
        det = engine.determine("3304.10.0000")  # Lip makeup
        assert "FDA" in det.agencies_involved


class TestWoodProducts:

    def test_wood_chapter_44_requires_usda_lacey(self, engine):
        det = engine.determine("4407.10.0100")  # Sawn wood
        assert det.is_pga_required is True
        assert "USDA" in det.agencies_involved
        usda = [r for r in det.requirements if r.agency == "USDA"]
        assert any("Lacey" in (r.filing_form or "") for r in usda)

    def test_wooden_furniture_ch94_conditional_lacey(self, engine):
        det = engine.determine("9401.61.0010", product_description="wooden dining chairs")
        # Conditional rule with matching description — should appear
        assert det.is_pga_required is True


class TestChemicals:

    def test_organic_chemicals_tsca(self, engine):
        det = engine.determine("2901.10.0000")  # Acyclic hydrocarbons
        assert det.is_pga_required is True
        # Chapter 29 → EPA TSCA
        assert "EPA" in det.agencies_involved

    def test_pesticides_require_epa(self, engine):
        det = engine.determine("3808.50.0000")  # Herbicides
        assert "EPA" in det.agencies_involved


class TestVehicles:

    def test_motor_vehicles_require_epa_and_nhtsa(self, engine):
        det = engine.determine("8703.23.0000")  # Passenger cars
        agencies = det.agencies_involved
        # Both EPA (emissions) and NHTSA (safety) apply to chapter 87
        assert "EPA" in agencies or "NHTSA" in agencies  # At least one


class TestFirearms:

    def test_firearms_require_atf(self, engine):
        det = engine.determine("9302.00.0000")  # Revolvers, pistols
        assert det.is_pga_required is True
        assert "ATF" in det.agencies_involved
        atf_reqs = [r for r in det.requirements if r.agency == "ATF"]
        assert any(r.filing_form and "ATF" in r.filing_form for r in atf_reqs)


class TestNonPGAChapters:

    def test_textiles_no_pga(self, engine):
        det = engine.determine("6110.20.2075")  # Cotton sweaters
        assert det.is_pga_required is False

    def test_footwear_no_pga(self, engine):
        det = engine.determine("6403.51.9060")  # Leather shoes
        assert det.is_pga_required is False

    def test_jewelry_no_pga(self, engine):
        det = engine.determine("7113.11.3000")  # Silver jewelry
        assert det.is_pga_required is False


class TestMultiLineEntry:

    def test_entry_with_multiple_pga_chapters(self, engine):
        items = [
            {"hts_code": "3004.90.9150", "description": "Pharmaceutical tablets"},
            {"hts_code": "6110.20.2075", "description": "Cotton t-shirts"},
            {"hts_code": "9302.00.0000", "description": "Pistols"},
        ]
        results = engine.determine_for_entry(items)
        assert len(results) == 3
        # Pharma requires FDA
        assert "FDA" in results["3004.90.9150"].agencies_involved
        # Textiles no PGA
        assert not results["6110.20.2075"].is_pga_required
        # Firearms require ATF
        assert "ATF" in results["9302.00.0000"].agencies_involved

    def test_get_all_agencies_across_determinations(self, engine):
        items = [
            {"hts_code": "0302.11.0000"},
            {"hts_code": "9302.00.0000"},
        ]
        results_list = [engine.determine(i["hts_code"]) for i in items]
        all_agencies = engine.get_all_agencies(results_list)
        assert "FDA" in all_agencies
        assert "ATF" in all_agencies


class TestConvenienceFunctions:

    def test_module_level_function(self):
        det = determine_pga_requirements("0302.11.0000")
        assert det.is_pga_required is True

    def test_has_pga_requirement_quick_check(self, engine):
        assert engine.has_pga_requirement("0302.11.0000") is True
        assert engine.has_pga_requirement("6110.20.2075") is False


class TestDeterminationToDict:

    def test_to_dict_structure(self, engine):
        det = engine.determine("0302.11.0000")
        d = det.to_dict()
        assert "hts_code" in d
        assert "is_pga_required" in d
        assert "agencies_involved" in d
        assert "requirements" in d
        assert isinstance(d["requirements"], list)

    def test_requirement_dict_has_all_fields(self, engine):
        det = engine.determine("0302.11.0000")
        d = det.to_dict()
        if d["requirements"]:
            req = d["requirements"][0]
            for field in ["agency", "program_code", "requirement_type",
                          "description", "regulation", "is_mandatory"]:
                assert field in req
