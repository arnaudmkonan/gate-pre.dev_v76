"""
Invoice Dunning Service  (Task 1.7)

Sends automated payment reminder emails for overdue broker invoices.

Dunning schedule (days after invoice due date):
  - Day 3:  Friendly reminder
  - Day 7:  Second notice
  - Day 14: Final notice / escalation

Uses email_service.py for dispatch.  Idempotency is maintained via the
`last_dunning_sent_at` + `dunning_count` columns on `ClientInvoice`.
"""
import logging
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.client_billing import ClientInvoice, InvoiceStatus
from app.models.client import Client

logger = logging.getLogger(__name__)

# Dunning schedule: (days overdue, friendly name)
DUNNING_SCHEDULE = [
    (3,  "reminder_1",  "Friendly Reminder"),
    (7,  "reminder_2",  "Second Notice"),
    (14, "final_notice", "Final Notice"),
]


class DunningService:
    """Automated invoice collection reminders."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_overdue_invoices(self) -> dict:
        """
        Scan all overdue invoices and send appropriate dunning emails.

        Returns a summary dict for Celery task logging.
        """
        today = date.today()
        sent = []
        skipped = []

        # Fetch overdue / unpaid invoices with client details
        query = (
            select(ClientInvoice)
            .options(selectinload(ClientInvoice.client))
            .where(
                ClientInvoice.status.in_([
                    InvoiceStatus.SENT.value,
                    InvoiceStatus.OVERDUE.value,
                ]),
                ClientInvoice.due_date.isnot(None),
                ClientInvoice.due_date < today,
            )
        )
        result = await self.db.execute(query)
        invoices: List[ClientInvoice] = result.scalars().all()

        for invoice in invoices:
            days_overdue = (today - invoice.due_date).days
            stage = self._dunning_stage(days_overdue)
            if stage is None:
                skipped.append(str(invoice.id))
                continue

            days_threshold, stage_key, stage_name = stage

            # Idempotency: skip if we already sent this stage
            last_count = getattr(invoice, "dunning_count", 0) or 0
            last_stage_idx = DUNNING_SCHEDULE.index(stage)
            if last_count > last_stage_idx:
                skipped.append(str(invoice.id))
                continue

            ok = await self._send_dunning_email(invoice, days_overdue, stage_name)
            if ok:
                # Bump dunning_count so we don't re-send the same stage
                await self._mark_dunning_sent(invoice, last_stage_idx + 1)
                sent.append(str(invoice.id))

        logger.info(
            "Dunning run: %d invoices, %d emails sent, %d skipped",
            len(invoices), len(sent), len(skipped),
        )
        return {
            "invoices_checked": len(invoices),
            "emails_sent": len(sent),
            "skipped": len(skipped),
            "sent_invoice_ids": sent,
        }

    # ------------------------------------------------------------------
    # Pure helpers
    # ------------------------------------------------------------------

    def _dunning_stage(
        self, days_overdue: int
    ) -> Optional[tuple]:
        """
        Return the appropriate dunning stage tuple for this overdue age.

        Returns the highest threshold that has been crossed.
        Returns None if days_overdue < 3 (not yet dunnable).
        """
        applicable = [
            s for s in DUNNING_SCHEDULE if days_overdue >= s[0]
        ]
        return applicable[-1] if applicable else None

    def days_overdue(self, invoice: ClientInvoice) -> int:
        """Return how many days past due_date this invoice is (0 if not overdue)."""
        if not invoice.due_date:
            return 0
        delta = (date.today() - invoice.due_date).days
        return max(0, delta)

    def next_dunning_date(self, invoice: ClientInvoice) -> Optional[date]:
        """Return the date of the next scheduled dunning email."""
        if not invoice.due_date:
            return None
        count = getattr(invoice, "dunning_count", 0) or 0
        if count >= len(DUNNING_SCHEDULE):
            return None
        days_threshold = DUNNING_SCHEDULE[count][0]
        return invoice.due_date + timedelta(days=days_threshold)

    # ------------------------------------------------------------------
    # Email dispatch
    # ------------------------------------------------------------------

    async def _send_dunning_email(
        self,
        invoice: ClientInvoice,
        days_overdue: int,
        stage_name: str,
    ) -> bool:
        """Send a dunning email. Returns True on success."""
        try:
            from app.services.email_service import EmailService

            client = invoice.client
            recipient_email = getattr(client, "contact_email", None) or getattr(client, "email", None)
            if not recipient_email:
                logger.warning("Invoice %s: no client email found, skipping dunning", invoice.id)
                return False

            amount = invoice.total_amount or Decimal("0")
            invoice_number = invoice.invoice_number or str(invoice.id)

            subject = f"[{stage_name}] Invoice {invoice_number} — ${amount:,.2f} overdue by {days_overdue} days"
            body = (
                f"Dear {getattr(client, 'name', 'Valued Client')},\n\n"
                f"This is a {stage_name.lower()} for invoice {invoice_number} "
                f"totalling ${amount:,.2f}, which was due {days_overdue} days ago.\n\n"
                f"Please arrange payment at your earliest convenience.\n\n"
                f"If you have already paid, please disregard this notice.\n\n"
                f"Thank you,\nYour Customs Broker"
            )

            svc = EmailService()
            await svc.send_plain(
                to=recipient_email,
                subject=subject,
                body=body,
            )
            logger.info("Dunning email sent: invoice=%s stage=%s to=%s", invoice.id, stage_name, recipient_email)
            return True

        except Exception as exc:
            logger.error("Dunning email failed for invoice %s: %s", invoice.id, exc)
            return False

    async def _mark_dunning_sent(
        self, invoice: ClientInvoice, new_count: int
    ) -> None:
        """Persist the dunning count and status update."""
        try:
            # Update status to OVERDUE if not already
            invoice.status = InvoiceStatus.OVERDUE.value
            if hasattr(invoice, "dunning_count"):
                invoice.dunning_count = new_count
            if hasattr(invoice, "last_dunning_sent_at"):
                invoice.last_dunning_sent_at = datetime.now(timezone.utc)
            await self.db.commit()
        except Exception as exc:
            logger.error("Failed to persist dunning state: %s", exc)
            await self.db.rollback()
