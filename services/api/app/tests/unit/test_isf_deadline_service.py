"""
Unit tests — ISF Deadline Service  (Task 1.1)
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


def make_isf(
    status="draft",
    hours_until_departure=None,
    isf_number=None,
    isf_id=None,
):
    """Build a lightweight ISF mock."""
    isf = MagicMock()
    isf.id = isf_id or "isf-uuid-001"
    isf.isf_number = isf_number or "ISF-2024-001"
    isf.status = status
    isf.importer_id = None  # No notifications in unit tests

    if hours_until_departure is not None:
        isf.estimated_departure = datetime.now(timezone.utc) + timedelta(
            hours=hours_until_departure
        )
    else:
        isf.estimated_departure = None
    return isf


@pytest.fixture
def db():
    return AsyncMock()


@pytest.fixture
def service(db):
    from app.services.isf_deadline_service import ISFDeadlineService
    return ISFDeadlineService(db)


class TestISFDeadlineServiceHelpers:

    def test_hours_until_deadline_no_departure(self, service):
        """ISF with no estimated_departure returns None."""
        isf = make_isf(hours_until_departure=None)
        assert service.hours_until_deadline(isf) is None

    def test_hours_until_deadline_72h_before_departure(self, service):
        """48h before departure → 24h before deadline."""
        # Departure in 48h → deadline = 48h - 24h = 24h remaining
        isf = make_isf(hours_until_departure=48)
        hours = service.hours_until_deadline(isf)
        assert hours is not None
        assert abs(hours - 24.0) < 0.1

    def test_hours_until_deadline_exactly_at_deadline(self, service):
        """Departure in exactly 24h → 0h remaining on deadline."""
        isf = make_isf(hours_until_departure=24)
        hours = service.hours_until_deadline(isf)
        assert hours is not None
        assert abs(hours) < 0.1  # Essentially 0

    def test_hours_until_deadline_after_departure(self, service):
        """Departure 2h ago → negative hours (overdue)."""
        isf = make_isf(hours_until_departure=-2)
        hours = service.hours_until_deadline(isf)
        assert hours is not None
        assert hours < 0

    def test_is_overdue_true_when_deadline_passed(self, service):
        isf = make_isf(hours_until_departure=-2)
        assert service.is_overdue(isf) is True

    def test_is_overdue_false_when_departure_ahead(self, service):
        isf = make_isf(hours_until_departure=100)
        assert service.is_overdue(isf) is False

    def test_is_overdue_false_when_no_departure(self, service):
        isf = make_isf(hours_until_departure=None)
        assert service.is_overdue(isf) is False

    def test_needs_alert_within_24h_window(self, service):
        """ISF with 23h to deadline should need a 24h alert."""
        from app.models.isf_filing import ISFStatus
        isf = make_isf(hours_until_departure=47, status=ISFStatus.DRAFT.value)
        assert service.needs_alert(isf, window_hours=24) is True

    def test_needs_alert_outside_window(self, service):
        """ISF with 50h to deadline is outside 24h window."""
        from app.models.isf_filing import ISFStatus
        isf = make_isf(hours_until_departure=74, status="draft")
        assert service.needs_alert(isf, window_hours=24) is False

    def test_needs_alert_already_confirmed(self, service):
        """Filed/confirmed ISF should never trigger alerts."""
        from app.models.isf_filing import ISFStatus
        isf = make_isf(hours_until_departure=20, status=ISFStatus.MATCHED.value)
        assert service.needs_alert(isf, window_hours=48) is False


class TestISFDeadlineClassification:

    def test_classify_24h_window(self, service):
        result = service._classify_alert(hours_remaining=20, status="draft")
        assert result == "isf_deadline_24h"

    def test_classify_48h_window(self, service):
        result = service._classify_alert(hours_remaining=40, status="draft")
        assert result == "isf_deadline_48h"

    def test_classify_72h_window(self, service):
        result = service._classify_alert(hours_remaining=65, status="draft")
        assert result == "isf_deadline_72h"

    def test_classify_overdue(self, service):
        result = service._classify_alert(hours_remaining=-5, status="draft")
        assert result == "isf_deadline_missed"

    def test_classify_outside_all_windows(self, service):
        result = service._classify_alert(hours_remaining=100, status="draft")
        assert result is None


class TestISFDeadlineScannerIntegration:

    @pytest.mark.asyncio
    async def test_check_all_deadlines_empty(self, service, db):
        """No ISFs → result with zeros."""
        db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
        result = await service.check_all_deadlines()
        assert result["scanned"] == 0
        assert result["alerts_sent"] == 0
        assert result["overdue_count"] == 0

    @pytest.mark.asyncio
    async def test_check_all_deadlines_with_overdue(self, service, db):
        """Overdue ISF shows up in overdue_count."""
        overdue_isf = make_isf(hours_until_departure=-5)
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[overdue_isf]))
                )
            )
        )
        with patch.object(service, "_emit_alert", new_callable=AsyncMock) as mock_emit:
            mock_emit.return_value = {}
            result = await service.check_all_deadlines()
        assert result["overdue_count"] == 1
