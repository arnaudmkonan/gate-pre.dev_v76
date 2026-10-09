"""
Unit tests — Invoice Dunning Service  (Task 1.7)
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


def make_invoice(days_overdue=0, dunning_count=0, has_due_date=True, status="sent"):
    invoice = MagicMock()
    invoice.id = "inv-001"
    invoice.invoice_number = "INV-2024-001"
    invoice.status = status
    invoice.dunning_count = dunning_count
    invoice.total_amount = Decimal("1500.00")
    invoice.due_date = date.today() - timedelta(days=days_overdue) if has_due_date else None
    invoice.client = MagicMock()
    invoice.client.name = "ACME Corp"
    invoice.client.contact_email = "ap@acme.com"
    return invoice


@pytest.fixture
def db():
    return AsyncMock()


@pytest.fixture
def service(db):
    from app.services.dunning_service import DunningService
    return DunningService(db)


class TestDunningStageSelection:

    def test_0_days_overdue_no_stage(self, service):
        assert service._dunning_stage(0) is None

    def test_2_days_overdue_no_stage(self, service):
        assert service._dunning_stage(2) is None

    def test_3_days_overdue_stage1(self, service):
        stage = service._dunning_stage(3)
        assert stage is not None
        assert stage[1] == "reminder_1"

    def test_7_days_overdue_stage2(self, service):
        stage = service._dunning_stage(7)
        assert stage is not None
        assert stage[1] == "reminder_2"

    def test_14_days_overdue_final(self, service):
        stage = service._dunning_stage(14)
        assert stage is not None
        assert stage[1] == "final_notice"

    def test_20_days_overdue_still_final_notice(self, service):
        stage = service._dunning_stage(20)
        assert stage[1] == "final_notice"  # Max is final_notice


class TestDunningHelpers:

    def test_days_overdue_zero_when_not_overdue(self, service):
        invoice = make_invoice(days_overdue=0)
        assert service.days_overdue(invoice) == 0

    def test_days_overdue_positive(self, service):
        invoice = make_invoice(days_overdue=5)
        assert service.days_overdue(invoice) == 5

    def test_days_overdue_no_due_date(self, service):
        invoice = make_invoice(has_due_date=False)
        assert service.days_overdue(invoice) == 0

    def test_next_dunning_date_first_reminder(self, service):
        invoice = make_invoice(days_overdue=5)
        invoice.dunning_count = 0  # Haven't sent any yet
        next_date = service.next_dunning_date(invoice)
        expected = invoice.due_date + timedelta(days=3)
        assert next_date == expected

    def test_next_dunning_date_none_when_all_sent(self, service):
        invoice = make_invoice(days_overdue=20)
        invoice.dunning_count = 3  # All stages sent
        assert service.next_dunning_date(invoice) is None


class TestDunningScanner:

    @pytest.mark.asyncio
    async def test_no_overdue_invoices(self, service, db):
        db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        )
        result = await service.process_overdue_invoices()
        assert result["invoices_checked"] == 0
        assert result["emails_sent"] == 0

    @pytest.mark.asyncio
    async def test_overdue_invoice_triggers_email(self, service, db):
        invoice = make_invoice(days_overdue=5, dunning_count=0)
        db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[invoice]))))
        )
        with patch.object(service, "_send_dunning_email", new_callable=AsyncMock, return_value=True):
            with patch.object(service, "_mark_dunning_sent", new_callable=AsyncMock):
                result = await service.process_overdue_invoices()
        assert result["emails_sent"] == 1

    @pytest.mark.asyncio
    async def test_already_dunned_at_stage_skipped(self, service, db):
        """Invoice already received stage 1 reminder should be skipped."""
        # days_overdue=5 → stage_1 (index 0); dunning_count=1 → already sent stage_1
        invoice = make_invoice(days_overdue=5, dunning_count=1)
        db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[invoice]))))
        )
        with patch.object(service, "_send_dunning_email", new_callable=AsyncMock) as mock_email:
            result = await service.process_overdue_invoices()
        mock_email.assert_not_called()
        assert result["emails_sent"] == 0
