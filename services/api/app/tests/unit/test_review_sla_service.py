"""
Unit tests — Review Queue SLA Service  (Task 1.5)
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock


def make_item(priority=0, deadline_hours_from_now=None, status="pending"):
    item = MagicMock()
    item.id = "review-item-001"
    item.priority = priority
    item.status = status
    item.assigned_to = None
    if deadline_hours_from_now is not None:
        item.deadline_at = datetime.now(timezone.utc) + timedelta(hours=deadline_hours_from_now)
    else:
        item.deadline_at = None
    return item


@pytest.fixture
def db():
    return AsyncMock()


@pytest.fixture
def service(db):
    from app.services.review_sla_service import ReviewSLAService
    return ReviewSLAService(db)


class TestSLADeadlineComputation:

    def test_priority_0_gets_24h_sla(self, service):
        deadline = service.compute_deadline(priority=0)
        now = datetime.now(timezone.utc)
        hours = (deadline - now).total_seconds() / 3600
        assert abs(hours - 24.0) < 0.05

    def test_priority_1_gets_8h_sla(self, service):
        deadline = service.compute_deadline(priority=1)
        now = datetime.now(timezone.utc)
        hours = (deadline - now).total_seconds() / 3600
        assert abs(hours - 8.0) < 0.05

    def test_priority_2_gets_4h_sla(self, service):
        deadline = service.compute_deadline(priority=2)
        now = datetime.now(timezone.utc)
        hours = (deadline - now).total_seconds() / 3600
        assert abs(hours - 4.0) < 0.05

    def test_unknown_priority_defaults_to_24h(self, service):
        deadline = service.compute_deadline(priority=99)
        now = datetime.now(timezone.utc)
        hours = (deadline - now).total_seconds() / 3600
        assert abs(hours - 24.0) < 0.05

    def test_custom_created_at(self, service):
        created = datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc)
        deadline = service.compute_deadline(priority=1, created_at=created)
        assert deadline == datetime(2024, 1, 15, 16, 0, tzinfo=timezone.utc)  # +8h


class TestSLAHoursRemaining:

    def test_no_deadline_returns_none(self, service):
        item = make_item(deadline_hours_from_now=None)
        assert service.hours_remaining(item) is None

    def test_positive_hours_remaining(self, service):
        item = make_item(deadline_hours_from_now=5)
        hrs = service.hours_remaining(item)
        assert hrs is not None
        assert abs(hrs - 5.0) < 0.1

    def test_negative_hours_when_breached(self, service):
        item = make_item(deadline_hours_from_now=-3)
        hrs = service.hours_remaining(item)
        assert hrs is not None
        assert hrs < 0


class TestSLABreachDetection:

    def test_is_breached_true_when_overdue(self, service):
        item = make_item(deadline_hours_from_now=-1)
        assert service.is_breached(item) is True

    def test_is_breached_false_when_time_remaining(self, service):
        item = make_item(deadline_hours_from_now=10)
        assert service.is_breached(item) is False

    def test_is_breached_false_when_no_deadline(self, service):
        item = make_item(deadline_hours_from_now=None)
        assert service.is_breached(item) is False

    def test_is_approaching_within_2h(self, service):
        item = make_item(deadline_hours_from_now=1.5)
        assert service.is_approaching(item, warn_hours=2.0) is True

    def test_is_approaching_false_when_far_away(self, service):
        item = make_item(deadline_hours_from_now=10)
        assert service.is_approaching(item, warn_hours=2.0) is False

    def test_is_approaching_false_when_already_breached(self, service):
        item = make_item(deadline_hours_from_now=-1)
        assert service.is_approaching(item, warn_hours=2.0) is False


class TestSLAScanner:

    @pytest.mark.asyncio
    async def test_empty_queue_returns_zeros(self, service, db):
        db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        )
        result = await service.check_all_items()
        assert result["items_scanned"] == 0
        assert result["approaching_count"] == 0
        assert result["breached_count"] == 0

    @pytest.mark.asyncio
    async def test_breached_item_counted(self, service, db):
        breached = make_item(deadline_hours_from_now=-2)
        db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[breached]))))
        )
        result = await service.check_all_items()
        assert result["breached_count"] == 1
        assert str(breached.id) in result["breached_item_ids"]

    @pytest.mark.asyncio
    async def test_healthy_item_no_alert(self, service, db):
        healthy = make_item(deadline_hours_from_now=20)
        db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[healthy]))))
        )
        result = await service.check_all_items()
        assert result["approaching_count"] == 0
        assert result["breached_count"] == 0
