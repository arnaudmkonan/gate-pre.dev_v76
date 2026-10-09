"""
Bond Sufficiency Alert Service  (Task 1.4)

Scans active customs bonds and fires proactive notifications when
utilisation crosses configurable thresholds.

CBP requires brokers to maintain sufficient bond coverage. Bond exhaustion
stops ALL entries from being filed until a new/rider bond is obtained.

Thresholds:
  - WARNING  at 80% utilisation
  - CRITICAL at 95% utilisation (effectively exhausted)

Celery Beat calls `check_bond_sufficiency.delay()` daily at 08:00 UTC.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker_management import BrokerBond, BondStatus

logger = logging.getLogger(__name__)

WARNING_THRESHOLD = Decimal("0.80")   # 80% utilisation → warning
CRITICAL_THRESHOLD = Decimal("0.95")  # 95% utilisation → critical


class BondSufficiencyService:
    """
    Checks each active continuous bond's utilisation and emits
    in-app / email notifications when thresholds are breached.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Core scanner
    # ------------------------------------------------------------------

    async def check_all_bonds(self) -> dict:
        """
        Scan all active bonds and fire alerts where needed.

        Returns a summary dict suitable for Celery task logging.
        """
        query = select(BrokerBond).where(
            BrokerBond.status == BondStatus.ACTIVE.value,
        )
        result = await self.db.execute(query)
        bonds: List[BrokerBond] = result.scalars().all()

        warnings = []
        criticals = []

        for bond in bonds:
            utilisation = self.calculate_utilisation(bond)
            if utilisation is None:
                continue

            if utilisation >= CRITICAL_THRESHOLD:
                criticals.append(str(bond.id))
                await self._emit_alert(bond, "critical", utilisation)
            elif utilisation >= WARNING_THRESHOLD:
                warnings.append(str(bond.id))
                await self._emit_alert(bond, "warning", utilisation)

        logger.info(
            "Bond sufficiency check: %d bonds, %d warnings, %d criticals",
            len(bonds), len(warnings), len(criticals),
        )
        return {
            "bonds_checked": len(bonds),
            "warnings": len(warnings),
            "criticals": len(criticals),
            "warning_bond_ids": warnings,
            "critical_bond_ids": criticals,
        }

    # ------------------------------------------------------------------
    # Computation helpers (pure, easy to unit-test)
    # ------------------------------------------------------------------

    def calculate_utilisation(self, bond: BrokerBond) -> Optional[Decimal]:
        """
        Return utilisation ratio [0, 1] for a bond.

        Returns None if the bond has no amount set (misconfigured bond).
        """
        if not bond.bond_amount or bond.bond_amount == 0:
            return None

        utilized = bond.current_utilization or Decimal("0")
        return (utilized / bond.bond_amount).quantize(Decimal("0.0001"))

    def is_sufficient(self, bond: BrokerBond) -> bool:
        """Return True if the bond has sufficient remaining capacity."""
        util = self.calculate_utilisation(bond)
        return util is None or util < WARNING_THRESHOLD

    def get_remaining_capacity(self, bond: BrokerBond) -> Optional[Decimal]:
        """Return dollar amount of remaining bond capacity."""
        if not bond.bond_amount:
            return None
        utilized = bond.current_utilization or Decimal("0")
        return bond.bond_amount - utilized

    # ------------------------------------------------------------------
    # Alert dispatch
    # ------------------------------------------------------------------

    async def _emit_alert(
        self,
        bond: BrokerBond,
        severity: str,
        utilisation: Decimal,
    ) -> None:
        """Fire an in-app notification about bond utilisation."""
        pct = float(utilisation * 100)
        remaining = self.get_remaining_capacity(bond)
        msg = (
            f"Bond #{bond.bond_number or bond.id}: "
            f"{pct:.1f}% utilised "
            f"(${remaining:,.2f} remaining)"
        )
        logger.warning("BOND SUFFICIENCY %s — %s", severity.upper(), msg)

        try:
            from app.services.notification_service import NotificationService

            # Notify the bond's primary contact if we can retrieve a user_id.
            # In practice bonds are linked to a broker license; fallback to
            # logging when no user is addressable.
            if hasattr(bond, "primary_contact_user_id") and bond.primary_contact_user_id:
                svc = NotificationService(self.db)
                await svc.notify(
                    user_id=bond.primary_contact_user_id,
                    notification_type="bond_sufficiency_alert",
                    title=f"Bond utilisation {severity}: {pct:.0f}%",
                    body=msg,
                    data={
                        "bond_id": str(bond.id),
                        "bond_number": bond.bond_number,
                        "utilisation_pct": round(pct, 1),
                        "remaining_amount": str(remaining),
                        "severity": severity,
                    },
                    channel="both",
                )
        except Exception as exc:
            logger.error("Failed to send bond alert: %s", exc)
