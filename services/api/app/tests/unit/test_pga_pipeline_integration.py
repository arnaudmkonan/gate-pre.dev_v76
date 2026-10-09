"""
Tests for Task C — PGA pipeline integration into post_extraction_service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service():
    from app.services.post_extraction_service import PostExtractionService
    db = MagicMock()
    svc = PostExtractionService(db)
    return svc


def _make_extractions(hts_code: str, party: str = ""):
    extractions = [
        {"field_name": "hts_code", "value": hts_code, "found": True},
    ]
    if party:
        extractions.append({"field_name": "seller_name", "value": party, "found": True})
    return {"extractions": extractions}


# ---------------------------------------------------------------------------
# PGA in compliance pipeline
# ---------------------------------------------------------------------------

class TestPGAInCompliancePipeline:
    @pytest.mark.asyncio
    async def test_fda_hts_raises_pga_issue(self):
        """Chapter 02 (Meat — FDA) should produce a pga_required issue."""
        svc = _make_service()

        # Stub the DB-dependent steps so only PGA runs
        svc.validate_hts_code = AsyncMock(
            return_value=MagicMock(is_valid=True, to_dict=lambda: {})
        )
        svc.screen_party = AsyncMock(
            return_value=MagicMock(
                risk_level=MagicMock(value="clear"),
                matches_found=0,
                to_dict=lambda: {},
            )
        )
        svc.classify_naics = AsyncMock(
            return_value=MagicMock(to_dict=lambda: {})
        )

        ext = _make_extractions("0201.10.0000")  # Meat — Chapter 2 FDA
        result = await svc.process_extraction_results(
            document_id=str(uuid4()),
            extraction_results=ext,
        )

        pga_issues = [i for i in result.issues_found if i["type"] == "pga_required"]
        assert len(pga_issues) >= 1
        assert "FDA" in pga_issues[0]["pga_agencies"]

    @pytest.mark.asyncio
    async def test_textile_hts_no_pga_issue(self):
        """Chapter 52 (Cotton textiles) should NOT produce a pga_required issue."""
        svc = _make_service()

        svc.validate_hts_code = AsyncMock(
            return_value=MagicMock(is_valid=True, to_dict=lambda: {})
        )
        svc.screen_party = AsyncMock(
            return_value=MagicMock(
                risk_level=MagicMock(value="clear"),
                matches_found=0,
                to_dict=lambda: {},
            )
        )
        svc.classify_naics = AsyncMock(
            return_value=MagicMock(to_dict=lambda: {})
        )

        ext = _make_extractions("5201.00.1800")  # Cotton, not carded — no PGA
        result = await svc.process_extraction_results(
            document_id=str(uuid4()),
            extraction_results=ext,
        )

        pga_issues = [i for i in result.issues_found if i["type"] == "pga_required"]
        assert len(pga_issues) == 0

    @pytest.mark.asyncio
    async def test_motor_vehicle_hts_raises_nhtsa(self):
        """Chapter 87 (Motor vehicles) should flag NHTSA."""
        svc = _make_service()

        svc.validate_hts_code = AsyncMock(
            return_value=MagicMock(is_valid=True, to_dict=lambda: {})
        )
        svc.screen_party = AsyncMock(
            return_value=MagicMock(
                risk_level=MagicMock(value="clear"),
                matches_found=0,
                to_dict=lambda: {},
            )
        )
        svc.classify_naics = AsyncMock(
            return_value=MagicMock(to_dict=lambda: {})
        )

        ext = _make_extractions("8703.23.0050")  # Passenger cars — chapter 87 NHTSA
        result = await svc.process_extraction_results(
            document_id=str(uuid4()),
            extraction_results=ext,
        )

        pga_issues = [i for i in result.issues_found if i["type"] == "pga_required"]
        assert len(pga_issues) >= 1
        agencies = {a for issue in pga_issues for a in issue["pga_agencies"]}
        assert "NHTSA" in agencies

    @pytest.mark.asyncio
    async def test_pga_failure_does_not_crash_pipeline(self):
        """If PGA engine raises, the rest of the pipeline should still complete."""
        svc = _make_service()

        svc.validate_hts_code = AsyncMock(
            return_value=MagicMock(is_valid=True, to_dict=lambda: {})
        )
        svc.screen_party = AsyncMock(
            return_value=MagicMock(
                risk_level=MagicMock(value="clear"),
                matches_found=0,
                to_dict=lambda: {},
            )
        )
        svc.classify_naics = AsyncMock(
            return_value=MagicMock(to_dict=lambda: {})
        )

        ext = _make_extractions("0201.10.0000")
        # The engine is imported lazily inside the method, so patch it at its source
        with patch(
            "app.services.pga_determination_service.PGADeterminationEngine.determine",
            side_effect=RuntimeError("Engine failure"),
        ):
            with patch(
                "app.services.post_extraction_service.logger"
            ):
                # Should not raise
                result = await svc.process_extraction_results(
                    document_id=str(uuid4()),
                    extraction_results=ext,
                )
        # Pipeline still returns a result
        assert result is not None
        assert result.document_id is not None


# ---------------------------------------------------------------------------
# PGA determination engine isolation tests (belt-and-suspenders)
# ---------------------------------------------------------------------------

class TestPGAEngineIsolation:
    def test_firearms_chapter_93_atf(self):
        from app.services.pga_determination_service import PGADeterminationEngine
        engine = PGADeterminationEngine()
        det = engine.determine("9302.00.0000")
        assert det.is_pga_required
        assert "ATF" in det.agencies_involved

    def test_pesticide_chapter_38_epa(self):
        from app.services.pga_determination_service import PGADeterminationEngine
        engine = PGADeterminationEngine()
        det = engine.determine("3808.91.2500")
        assert det.is_pga_required
        assert "EPA" in det.agencies_involved

    def test_non_pga_chapter_returns_clean(self):
        from app.services.pga_determination_service import PGADeterminationEngine
        engine = PGADeterminationEngine()
        det = engine.determine("6101.20.0010")  # Wool overcoats — no PGA
        assert det.is_pga_required is False
        assert len(det.agencies_involved) == 0

    def test_pga_issue_has_required_fields(self):
        from app.services.pga_determination_service import PGADeterminationEngine
        engine = PGADeterminationEngine()
        det = engine.determine("0301.11.0000")  # Live fish — FDA
        d = det.to_dict()
        assert "is_pga_required" in d
        assert "agencies_involved" in d
        assert "requirements" in d
        assert isinstance(d["requirements"], list)
