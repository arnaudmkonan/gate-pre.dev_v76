"""
Unit tests — POA Service  (Task 2.1)
"""
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock


def make_poa(status="active", expiry_days_from_now=None, poa_type="general"):
    return {
        "id": "poa-001",
        "client_id": "client-001",
        "status": status,
        "poa_type": poa_type,
        "grantor_name": "John Smith",
        "expiry_date": (
            (date.today() + timedelta(days=expiry_days_from_now)).isoformat()
            if expiry_days_from_now is not None else None
        ),
    }


@pytest.fixture
def db():
    return AsyncMock()


@pytest.fixture
def service(db):
    from app.services.poa_service import POAService
    return POAService(db)


class TestPOAValidation:

    def test_active_poa_with_no_expiry_is_valid(self, service):
        poa = make_poa(status="active", expiry_days_from_now=None)
        assert service.is_valid(poa) is True

    def test_active_poa_with_future_expiry_is_valid(self, service):
        poa = make_poa(status="active", expiry_days_from_now=30)
        assert service.is_valid(poa) is True

    def test_active_poa_with_past_expiry_is_invalid(self, service):
        poa = make_poa(status="active", expiry_days_from_now=-1)
        assert service.is_valid(poa) is False

    def test_draft_poa_is_invalid(self, service):
        poa = make_poa(status="draft")
        assert service.is_valid(poa) is False

    def test_revoked_poa_is_invalid(self, service):
        poa = make_poa(status="revoked")
        assert service.is_valid(poa) is False

    def test_expired_status_poa_is_invalid(self, service):
        poa = make_poa(status="expired")
        assert service.is_valid(poa) is False


class TestPOAExpiryDays:

    def test_no_expiry_returns_none(self, service):
        poa = make_poa(expiry_days_from_now=None)
        assert service.days_until_expiry(poa) is None

    def test_30_days_until_expiry(self, service):
        poa = make_poa(expiry_days_from_now=30)
        days = service.days_until_expiry(poa)
        assert days == 30

    def test_negative_when_expired(self, service):
        poa = make_poa(expiry_days_from_now=-5)
        days = service.days_until_expiry(poa)
        assert days == -5

    def test_requires_renewal_within_30_days(self, service):
        poa = make_poa(expiry_days_from_now=15)
        assert service.requires_renewal(poa, warn_days=30) is True

    def test_does_not_require_renewal_when_far_out(self, service):
        poa = make_poa(expiry_days_from_now=90)
        assert service.requires_renewal(poa, warn_days=30) is False


class TestCanFileEntry:

    def test_no_poas_blocks_filing(self, service):
        from uuid import uuid4
        ok, reason = service.can_file_entry(uuid4(), [])
        assert ok is False
        assert "Power of Attorney" in reason

    def test_active_poa_allows_filing(self, service):
        from uuid import uuid4
        poa = make_poa(status="active", expiry_days_from_now=60)
        ok, reason = service.can_file_entry(uuid4(), [poa])
        assert ok is True
        assert reason == ""

    def test_only_expired_poas_blocks_filing(self, service):
        from uuid import uuid4
        poa = make_poa(status="active", expiry_days_from_now=-1)
        ok, reason = service.can_file_entry(uuid4(), [poa])
        assert ok is False

    def test_one_valid_one_expired_allows_filing(self, service):
        """If at least one valid POA exists, filing should be allowed."""
        from uuid import uuid4
        expired = make_poa(status="active", expiry_days_from_now=-1)
        active = make_poa(status="active", expiry_days_from_now=60)
        ok, reason = service.can_file_entry(uuid4(), [expired, active])
        assert ok is True


class TestPOARecordBuilder:

    def test_build_requires_client_id(self, service):
        with pytest.raises(ValueError, match="client_id"):
            service.build_poa_record({"grantor_name": "John", "poa_type": "general"})

    def test_build_requires_grantor_name(self, service):
        with pytest.raises(ValueError, match="grantor_name"):
            service.build_poa_record({"client_id": "abc", "poa_type": "general"})

    def test_build_valid_data_returns_dict(self, service):
        data = {
            "client_id": "client-uuid",
            "poa_type": "general",
            "grantor_name": "Jane Doe",
        }
        record = service.build_poa_record(data)
        assert record["status"] == "draft"
        assert record["poa_type"] == "general"
        assert record["grantor_name"] == "Jane Doe"

    def test_build_defaults_to_general_poa_type(self, service):
        data = {
            "client_id": "abc",
            "poa_type": "general",
            "grantor_name": "Corp Inc",
        }
        record = service.build_poa_record(data)
        assert record["poa_type"] == "general"
