"""
Deadline & Alert Worker  (Tasks 1.1, 1.4, 1.5, 1.7)

Celery tasks for time-sensitive deadline checks:
  - ISF filing deadlines          (check_isf_deadlines)
  - Customs bond sufficiency      (check_bond_sufficiency)
  - Review queue SLA              (check_review_sla)
  - Overdue invoice dunning       (check_overdue_invoices)

All tasks are registered in celery_app.py beat_schedule.
"""
import logging

from celery import shared_task

from app.core.database import SyncSessionLocal  # sync session for Celery workers

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TASK 1.1 — ISF Deadline Alerts
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def check_isf_deadlines(self):
    """
    Scan ISF filings for 72h / 48h / 24h deadline alerts.

    Runs every 30 minutes via Celery Beat.
    """
    from app.services.isf_deadline_service import ISFDeadlineService

    try:
        with SyncSessionLocal() as session:
            # Wrap sync session for the async-style service
            from sqlalchemy.ext.asyncio import AsyncSession
            import asyncio

            async def _run():
                from app.core.database import get_async_session_from_sync
                async with get_async_session_from_sync() as async_session:
                    svc = ISFDeadlineService(async_session)
                    return await svc.check_all_deadlines()

            result = asyncio.run(_run())
            logger.info("check_isf_deadlines result: %s", result)
            return result

    except Exception as exc:
        logger.error("check_isf_deadlines failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# TASK A.3 — Poll ACE SFTP response folder (every 15 min)
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def poll_ace_responses(self):
    """
    Poll the CBP ACE SFTP response folder for entries awaiting a response.

    For each entry in 'filing' or 'transmitted' status, calls
    ACETransmitter.check_response() which:
      1. Downloads the matching response file from the SFTP folder
      2. Parses the CBP code (AE/AC/RJ/WO) via ACEResponseParser
      3. Auto-advances the entry status in the database

    Schedule: every 15 minutes via Celery Beat.
    """
    from app.services.ace_transmitter import ACETransmitter, TransmissionMode
    from sqlalchemy import select
    from app.models.entry import Entry, EntryStatus

    try:
        import asyncio

        async def _run():
            from app.core.database import get_async_session_from_sync
            async with get_async_session_from_sync() as async_session:
                # Find all 'filing' entries awaiting an ACE reply
                result = await async_session.execute(
                    select(Entry).where(
                        Entry.status.in_([
                            EntryStatus.FILING.value,
                            "transmitted",
                            "pending_cbp_response",
                        ])
                    )
                )
                entries = result.scalars().all()

                transmitter = ACETransmitter(async_session, mode=TransmissionMode.LIVE)
                responses = []
                for entry in entries:
                    try:
                        result = await transmitter.check_response(entry.id)
                        responses.append({
                            "entry_number": entry.entry_number,
                            "status": result.status.value,
                            "message": result.message,
                        })
                    except Exception as exc:
                        logger.warning(
                            "poll_ace_responses: error checking %s: %s",
                            entry.entry_number, exc,
                        )

                return {
                    "entries_checked": len(entries),
                    "responses": responses,
                }

        result = asyncio.run(_run())
        logger.info("poll_ace_responses: %s", result)
        return result

    except Exception as exc:
        logger.error("poll_ace_responses failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# TASK 1.4 — Bond Sufficiency Alerts
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def check_bond_sufficiency(self):
    """
    Scan active bonds for utilisation at 80% (warning) / 95% (critical).

    Runs daily at 08:00 UTC via Celery Beat.
    """
    from app.services.bond_sufficiency_service import BondSufficiencyService

    try:
        import asyncio

        async def _run():
            from app.core.database import get_async_session_from_sync
            async with get_async_session_from_sync() as async_session:
                svc = BondSufficiencyService(async_session)
                return await svc.check_all_bonds()

        result = asyncio.run(_run())
        logger.info("check_bond_sufficiency result: %s", result)
        return result

    except Exception as exc:
        logger.error("check_bond_sufficiency failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# TASK 1.5 — Review Queue SLA
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_review_sla(self):
    """
    Scan pending review queue items for SLA breaches.

    Runs every 15 minutes via Celery Beat.
    """
    from app.services.review_sla_service import ReviewSLAService

    try:
        import asyncio

        async def _run():
            from app.core.database import get_async_session_from_sync
            async with get_async_session_from_sync() as async_session:
                svc = ReviewSLAService(async_session)
                return await svc.check_all_items()

        result = asyncio.run(_run())
        logger.info("check_review_sla result: %s", result)
        return result

    except Exception as exc:
        logger.error("check_review_sla failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# TASK 1.7 — Overdue Invoice Dunning
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def check_overdue_invoices(self):
    """
    Scan invoices overdue >3 days and send dunning emails.

    Schedule: 3-day, 7-day, 14-day reminder cadence.
    Runs daily at 09:00 UTC via Celery Beat.
    """
    from app.services.dunning_service import DunningService

    try:
        import asyncio

        async def _run():
            from app.core.database import get_async_session_from_sync
            async with get_async_session_from_sync() as async_session:
                svc = DunningService(async_session)
                return await svc.process_overdue_invoices()

        result = asyncio.run(_run())
        logger.info("check_overdue_invoices result: %s", result)
        return result

    except Exception as exc:
        logger.error("check_overdue_invoices failed: %s", exc)
        raise self.retry(exc=exc)
