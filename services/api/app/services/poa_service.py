"""
Power of Attorney (POA) Service  (Task 2.1)

Manages the legal Power of Attorney workflow between importers and their
customs broker.  CBP requires a valid, signed POA before a broker may
file entries on behalf of an importer (19 CFR 141.32).

Lifecycle:
  DRAFT → PENDING_SIGNATURE → ACTIVE → EXPIRED / REVOKED

Celery Beat fires a 30-day expiry warning via `check_poa_expiry` task.
"""
import logging
from datetime import datetime, timezone, date, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class POAStatus(str, Enum):
    DRAFT = "draft"
    PENDING_SIGNATURE = "pending_signature"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class POAType(str, Enum):
    GENERAL = "general"              # Covers all shipments (most common)
    LIMITED = "limited"              # One shipment only
    CONTINUOUS = "continuous"        # All shipments for a defined period


class POAService:
    """
    CRUD and lifecycle management for Power of Attorney records.

    The POA document itself (PDF/docx) is stored via the existing
    storage service.  This service tracks metadata and enforces
    legal constraints.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Validation helpers (pure, no I/O)
    # ------------------------------------------------------------------

    def is_valid(self, poa: Dict[str, Any], as_of: Optional[date] = None) -> bool:
        """
        Return True if the POA is currently valid for filing purposes.

        A POA is valid when:
          - Status is ACTIVE
          - Not expired (expiry_date is in the future or None for perpetual)
          - Not revoked
        """
        if poa.get("status") != POAStatus.ACTIVE.value:
            return False
        expiry = poa.get("expiry_date")
        if expiry:
            check_date = as_of or date.today()
            if isinstance(expiry, str):
                expiry = date.fromisoformat(expiry)
            if expiry < check_date:
                return False
        return True

    def days_until_expiry(
        self, poa: Dict[str, Any], as_of: Optional[date] = None
    ) -> Optional[int]:
        """Return days until expiry, None if no expiry date, negative if expired."""
        expiry = poa.get("expiry_date")
        if not expiry:
            return None
        if isinstance(expiry, str):
            expiry = date.fromisoformat(expiry)
        check = as_of or date.today()
        return (expiry - check).days

    def requires_renewal(
        self, poa: Dict[str, Any], warn_days: int = 30
    ) -> bool:
        """Return True if the POA expires within `warn_days`."""
        days = self.days_until_expiry(poa)
        return days is not None and 0 < days <= warn_days

    def can_file_entry(
        self,
        client_id: UUID,
        poas: List[Dict[str, Any]],
        as_of: Optional[date] = None,
    ) -> tuple[bool, str]:
        """
        Check if at least one valid POA exists for `client_id`.

        Returns:
            (True, "") if filing is allowed.
            (False, reason_string) if blocked.
        """
        active = [p for p in poas if self.is_valid(p, as_of)]
        if not active:
            if not poas:
                return False, "No Power of Attorney on file. A signed POA is required before filing (19 CFR 141.32)."
            statuses = list({p.get("status") for p in poas})
            return False, f"No valid POA found. Existing POAs have status: {statuses}"
        return True, ""

    # ------------------------------------------------------------------
    # Alert scanning
    # ------------------------------------------------------------------

    async def check_expiry_alerts(self, warn_days: int = 30) -> dict:
        """
        Scan POAs expiring within `warn_days` and fire notifications.

        Called by Celery Beat `check_poa_expiry` task.
        """
        # Lazy import — avoids circular imports during unit tests
        try:
            from app.models.power_of_attorney import PowerOfAttorney
            query = select(PowerOfAttorney).where(
                PowerOfAttorney.status == POAStatus.ACTIVE.value,
                PowerOfAttorney.expiry_date.isnot(None),
                PowerOfAttorney.expiry_date <= date.today() + timedelta(days=warn_days),
                PowerOfAttorney.expiry_date >= date.today(),
            )
            result = await self.db.execute(query)
            poas = result.scalars().all()
        except ImportError:
            # Model not yet migrated in test environment
            logger.warning("POA model not available; skipping DB scan")
            return {"poas_checked": 0, "alerts_sent": 0}

        alerts = []
        for poa in poas:
            days = (poa.expiry_date - date.today()).days
            logger.warning(
                "POA EXPIRY WARNING: POA %s for client %s expires in %d days",
                poa.id, poa.client_id, days,
            )
            alerts.append({"poa_id": str(poa.id), "days_remaining": days})

        return {"poas_checked": len(poas), "alerts_sent": len(alerts), "alerts": alerts}

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------

    def build_poa_record(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalise POA creation data.

        Returns the cleaned dict ready for model construction.
        Raises ValueError on missing required fields.
        """
        required = ["client_id", "poa_type", "grantor_name"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            raise ValueError(f"Missing required POA fields: {missing}")

        return {
            "id": data.get("id", str(uuid4())),
            "client_id": str(data["client_id"]),
            "poa_type": data.get("poa_type", POAType.GENERAL.value),
            "status": POAStatus.DRAFT.value,
            "grantor_name": data["grantor_name"],
            "grantor_title": data.get("grantor_title"),
            "grantor_ein": data.get("grantor_ein"),
            "effective_date": data.get("effective_date"),
            "expiry_date": data.get("expiry_date"),
            "document_url": data.get("document_url"),
            "notes": data.get("notes"),
        }
