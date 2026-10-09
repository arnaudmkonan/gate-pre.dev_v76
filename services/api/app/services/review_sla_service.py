"""
Review Queue SLA Service  (Task 1.5)

Tracks SLA deadlines on human-review items.  When a document enters
the review queue, a `deadline_at` timestamp is set based on its
`sla_hours` priority tier.  A Celery Beat task fires alerts before
and after the deadline.

SLA tiers (configurable):
  - Priority 0 (normal): 24-hour SLA
  - Priority 1 (urgent): 8-hour SLA
  - Priority 2 (critical): 4-hour SLA

Celery Beat calls `check_review_sla.delay()` every 15 minutes.
"""
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review_queue import ReviewQueueItem

logger = logging.getLogger(__name__)

# SLA hours by priority level
SLA_HOURS_BY_PRIORITY: Dict[int, float] = {
    0: 24.0,   # Normal
    1: 8.0,    # Urgent
    2: 4.0,    # Critical (e.g., ISF filing imminent)
}

DEFAULT_SLA_HOURS = 24.0


class ReviewSLAService:
    """
    Manages SLA tracking for review queue items.

    Responsibilities:
      1. Compute `deadline_at` when items enter the queue.
      2. Scan for items approaching / exceeding SLA and alert.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # SLA computation (pure, no DB)
    # ------------------------------------------------------------------

    def compute_deadline(
        self,
        priority: int,
        created_at: Optional[datetime] = None,
    ) -> datetime:
        """
        Compute the SLA deadline for a review item.

        Args:
            priority: Item priority level (0=normal, 1=urgent, 2=critical).
            created_at: Creation timestamp; defaults to now (UTC).

        Returns:
            UTC datetime by which the review must be completed.
        """
        now = created_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        hours = SLA_HOURS_BY_PRIORITY.get(priority, DEFAULT_SLA_HOURS)
        return now + timedelta(hours=hours)

    def hours_remaining(
        self,
        item: ReviewQueueItem,
        now: Optional[datetime] = None,
    ) -> Optional[float]:
        """
        Return hours remaining until SLA deadline.

        Returns None if no deadline is set.
        Returns negative value if SLA is already breached.
        """
        deadline = getattr(item, "deadline_at", None)
        if deadline is None:
            return None
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return (deadline - now).total_seconds() / 3600

    def is_breached(
        self,
        item: ReviewQueueItem,
        now: Optional[datetime] = None,
    ) -> bool:
        """Return True if the SLA deadline has already passed."""
        hrs = self.hours_remaining(item, now)
        return hrs is not None and hrs < 0

    def is_approaching(
        self,
        item: ReviewQueueItem,
        warn_hours: float = 2.0,
        now: Optional[datetime] = None,
    ) -> bool:
        """Return True if the item will breach SLA within `warn_hours`."""
        hrs = self.hours_remaining(item, now)
        return hrs is not None and 0 < hrs <= warn_hours

    # ------------------------------------------------------------------
    # Beat scanner
    # ------------------------------------------------------------------

    async def check_all_items(self) -> dict:
        """
        Scan pending review items and emit alerts for SLA violations.

        Returns a summary dict for monitoring.
        """
        query = select(ReviewQueueItem).where(
            ReviewQueueItem.status.in_(["pending", "in_review"]),
        )
        result = await self.db.execute(query)
        items: List[ReviewQueueItem] = result.scalars().all()

        approaching = []
        breached = []
        now = datetime.now(timezone.utc)

        for item in items:
            hrs = self.hours_remaining(item, now)
            if hrs is None:
                continue
            if hrs < 0:
                breached.append(str(item.id))
                await self._emit_alert(item, "sla_breached", hrs, now)
            elif hrs <= 2.0:
                approaching.append(str(item.id))
                await self._emit_alert(item, "sla_approaching", hrs, now)

        logger.info(
            "Review SLA check: %d items, %d approaching, %d breached",
            len(items), len(approaching), len(breached),
        )
        return {
            "items_scanned": len(items),
            "approaching_count": len(approaching),
            "breached_count": len(breached),
            "breached_item_ids": breached,
        }

    # ------------------------------------------------------------------
    # Alert dispatch
    # ------------------------------------------------------------------

    async def _emit_alert(
        self,
        item: ReviewQueueItem,
        alert_type: str,
        hours_remaining: float,
        now: datetime,
    ) -> None:
        """Log and optionally notify about an SLA event."""
        msg = (
            f"Review item {item.id}: {alert_type} "
            f"({hours_remaining:.1f}h remaining, priority={item.priority})"
        )
        if hours_remaining < 0:
            logger.error("REVIEW SLA BREACHED — %s", msg)
        else:
            logger.warning("REVIEW SLA APPROACHING — %s", msg)

        try:
            from app.services.notification_service import NotificationService
            if item.assigned_to:
                # We don't have a direct user_id on ReviewQueueItem today;
                # logging is the fallback until the model is linked.
                pass
        except Exception as exc:
            logger.error("Failed to send review SLA notification: %s", exc)
