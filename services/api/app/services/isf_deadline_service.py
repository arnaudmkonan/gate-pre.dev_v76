"""
ISF Deadline Alert Service  (Task 1.1)

Scans ISFFiling records and fires proactive notifications:
  - 48 hours before the 24-hour pre-loading cutoff (i.e., 72h before
    vessel loading / estimated departure)
  - 24 hours before cutoff  (last chance to file)
  - ISF not yet filed when vessel has departed (penalty window open)

Celery Beat calls `check_isf_deadlines.delay()` every 30 minutes.

CBP rule: ISF must be filed ≥ 24 hours before vessel loads at foreign port.
Penalty: $5,000 per violation (per CBP 19 CFR 149.6).
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.isf_filing import ISFFiling, ISFStatus

logger = logging.getLogger(__name__)

# Alert windows (hours before vessel departure)
ALERT_WINDOWS_HOURS = [72, 48, 24]   # Alert when this many hours remain
ALERT_NOTIFICATION_TYPES = {
    72: "isf_deadline_72h",
    48: "isf_deadline_48h",
    24: "isf_deadline_24h",
    0: "isf_deadline_missed",
}


class ISFDeadlineService:
    """
    Scans pending ISF filings and emits deadline notifications.

    Architecture note: the service is intentionally stateless and side-effect
    free aside from DB writes and notification dispatch.  The Celery task
    that calls it passes in an already-open session.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_all_deadlines(self) -> dict:
        """
        Check all unfiled ISFs against their estimated departure dates.

        Returns a summary dict for logging / monitoring.
        """
        now = datetime.now(timezone.utc)
        alerts_sent: List[dict] = []
        overdue: List[str] = []

        # Fetch all ISFs that are still DRAFT or SUBMITTED but NOT confirmed
        query = select(ISFFiling).where(
            ISFFiling.status.in_([
                ISFStatus.DRAFT.value,
                ISFStatus.SUBMITTED.value,
            ]),
            ISFFiling.estimated_departure.isnot(None),
        )
        result = await self.db.execute(query)
        isfs: List[ISFFiling] = result.scalars().all()

        for isf in isfs:
            dep = isf.estimated_departure
            if dep.tzinfo is None:
                dep = dep.replace(tzinfo=timezone.utc)

            # Deadline = 24 hours before departure
            filing_deadline = dep - timedelta(hours=24)
            hours_remaining = (filing_deadline - now).total_seconds() / 3600

            alert_type = self._classify_alert(hours_remaining, isf.status)
            if alert_type:
                detail = await self._emit_alert(isf, alert_type, hours_remaining, now)
                if alert_type == "isf_deadline_missed":
                    overdue.append(str(isf.id))
                else:
                    alerts_sent.append(detail)

        logger.info(
            "ISF deadline check: %d ISFs scanned, %d alerts, %d overdue",
            len(isfs), len(alerts_sent), len(overdue),
        )
        return {
            "scanned": len(isfs),
            "alerts_sent": len(alerts_sent),
            "overdue_count": len(overdue),
            "overdue_isf_ids": overdue,
        }

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def hours_until_deadline(
        self, isf: ISFFiling, now: Optional[datetime] = None
    ) -> Optional[float]:
        """Return hours until the ISF filing deadline, None if no departure set."""
        if not isf.estimated_departure:
            return None
        now = now or datetime.now(timezone.utc)
        dep = isf.estimated_departure
        if dep.tzinfo is None:
            dep = dep.replace(tzinfo=timezone.utc)
        deadline = dep - timedelta(hours=24)
        return (deadline - now).total_seconds() / 3600

    def is_overdue(self, isf: ISFFiling, now: Optional[datetime] = None) -> bool:
        """Return True if the ISF filing deadline has already passed."""
        hours = self.hours_until_deadline(isf, now)
        return hours is not None and hours < 0

    def needs_alert(
        self, isf: ISFFiling, window_hours: int, now: Optional[datetime] = None
    ) -> bool:
        """
        Return True if the ISF is within `window_hours` of its deadline
        and has not yet been filed.
        """
        if isf.status not in (ISFStatus.DRAFT.value, ISFStatus.SUBMITTED.value):
            return False
        hours = self.hours_until_deadline(isf, now)
        if hours is None:
            return False
        return 0 < hours <= window_hours

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _classify_alert(self, hours_remaining: float, status: str) -> Optional[str]:
        """Map hours remaining to an alert type key."""
        if hours_remaining < 0:
            return "isf_deadline_missed"
        for window in sorted(ALERT_WINDOWS_HOURS):
            if hours_remaining <= window:
                return f"isf_deadline_{window}h"
        return None

    async def _emit_alert(
        self,
        isf: ISFFiling,
        alert_type: str,
        hours_remaining: float,
        now: datetime,
    ) -> dict:
        """
        Emit an in-app notification for an ISF deadline.

        In production this calls NotificationService.notify(); here it logs
        so tests can assert on the log output without a full DB fixture.
        """
        msg = (
            f"ISF {isf.isf_number or isf.id}: "
            f"{alert_type.replace('_', ' ').upper()} "
            f"({hours_remaining:.1f}h remaining)"
        )
        logger.warning("ISF DEADLINE ALERT — %s", msg)

        # Lazy import to avoid circular dependency in tests
        try:
            from app.services.notification_service import NotificationService

            if isf.importer_id:
                svc = NotificationService(self.db)
                await svc.notify(
                    user_id=isf.importer_id,
                    notification_type=alert_type,
                    title=f"ISF deadline {'MISSED' if hours_remaining < 0 else 'approaching'}",
                    body=msg,
                    data={
                        "isf_id": str(isf.id),
                        "isf_number": isf.isf_number,
                        "hours_remaining": round(hours_remaining, 1),
                        "filing_deadline": (
                            isf.estimated_departure - timedelta(hours=24)
                        ).isoformat() if isf.estimated_departure else None,
                    },
                )
        except Exception as exc:
            logger.error("Failed to send ISF deadline notification: %s", exc)

        return {
            "isf_id": str(isf.id),
            "alert_type": alert_type,
            "hours_remaining": round(hours_remaining, 1),
        }
