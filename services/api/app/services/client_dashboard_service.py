"""
Client Portal Dashboard Service.

Provides dashboard data for client portal users:
- Entry summary cards
- Recent entries
- Shipments in transit
- Pending actions
- Notifications

Task 5.2 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from collections import defaultdict

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entry import Entry, EntryStatus
from app.models.client import Client
from app.models.client_portal import ClientUser


class ClientDashboardService:
    """Service for client portal dashboard."""
    
    def __init__(self, db: AsyncSession, user: ClientUser):
        self.db = db
        self.user = user
        self.client_id = user.client_id
    
    async def get_dashboard(self) -> Dict[str, Any]:
        """Get complete dashboard data."""
        return {
            "summary": await self.get_summary_cards(),
            "recent_entries": await self.get_recent_entries(limit=10),
            "shipments_in_transit": await self.get_shipments_in_transit(),
            "pending_actions": await self.get_pending_actions(),
            "alerts": await self.get_alerts(),
            "quick_stats": await self.get_quick_stats(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def get_summary_cards(self) -> Dict[str, Any]:
        """
        Get summary cards for dashboard.
        
        Shows counts by status category.
        """
        # Get entry counts by status
        query = select(
            Entry.status,
            func.count(Entry.id)
        ).where(
            Entry.client_id == self.client_id
        ).group_by(Entry.status)
        
        result = await self.db.execute(query)
        status_counts = {row[0]: row[1] for row in result.all()}
        
        # Group into categories
        pending_statuses = [EntryStatus.DRAFT.value, EntryStatus.PENDING_REVIEW.value]
        in_progress_statuses = [EntryStatus.FILED.value, EntryStatus.ACCEPTED.value, EntryStatus.UNDER_EXAM.value]
        released_statuses = [EntryStatus.RELEASED.value]
        issue_statuses = [EntryStatus.REJECTED.value, EntryStatus.ON_HOLD.value]
        
        pending = sum(status_counts.get(s, 0) for s in pending_statuses)
        in_progress = sum(status_counts.get(s, 0) for s in in_progress_statuses)
        released = sum(status_counts.get(s, 0) for s in released_statuses)
        issues = sum(status_counts.get(s, 0) for s in issue_statuses)
        
        total = sum(status_counts.values())
        
        return {
            "pending": {
                "count": pending,
                "label": "Pending",
                "description": "Entries awaiting review or filing",
            },
            "in_progress": {
                "count": in_progress,
                "label": "In Progress",
                "description": "Entries filed and being processed",
            },
            "released": {
                "count": released,
                "label": "Released",
                "description": "Entries released by CBP",
            },
            "issues": {
                "count": issues,
                "label": "Needs Attention",
                "description": "Entries with issues or on hold",
            },
            "total": total,
            "status_breakdown": status_counts,
        }
    
    async def get_recent_entries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most recent entries."""
        query = (
            select(Entry)
            .where(Entry.client_id == self.client_id)
            .order_by(Entry.entry_date.desc().nullslast(), Entry.created_at.desc())
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        return [
            {
                "id": str(entry.id),
                "entry_number": entry.entry_number,
                "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
                "entry_type": entry.entry_type,
                "port_of_entry": entry.port_of_entry,
                "status": entry.status,
                "total_value": float(entry.total_value or 0),
                "total_duty": float(entry.total_duty or 0),
                "description": entry.merchandise_description,
            }
            for entry in entries
        ]
    
    async def get_shipments_in_transit(self) -> List[Dict[str, Any]]:
        """Get shipments that are in transit (filed but not released)."""
        in_transit_statuses = [
            EntryStatus.FILED.value,
            EntryStatus.ACCEPTED.value,
        ]
        
        query = (
            select(Entry)
            .where(
                and_(
                    Entry.client_id == self.client_id,
                    Entry.status.in_(in_transit_statuses),
                )
            )
            .order_by(Entry.estimated_arrival_date.asc().nullslast())
            .limit(20)
        )
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        return [
            {
                "id": str(entry.id),
                "entry_number": entry.entry_number,
                "status": entry.status,
                "port_of_entry": entry.port_of_entry,
                "carrier_code": entry.carrier_code,
                "vessel_name": entry.vessel_name,
                "estimated_arrival": entry.estimated_arrival_date.isoformat() if entry.estimated_arrival_date else None,
            }
            for entry in entries
        ]
    
    async def get_pending_actions(self) -> List[Dict[str, Any]]:
        """Get items requiring client action."""
        actions = []
        
        # Check for entries pending approval
        approval_query = select(func.count(Entry.id)).where(
            and_(
                Entry.client_id == self.client_id,
                Entry.status == EntryStatus.PENDING_REVIEW.value,
            )
        )
        result = await self.db.execute(approval_query)
        approval_count = result.scalar() or 0
        
        if approval_count > 0:
            actions.append({
                "type": "approval_needed",
                "count": approval_count,
                "title": "Entries Pending Approval",
                "description": f"{approval_count} entries need your review and approval",
                "action_url": "/entries?status=pending_review",
            })
        
        # Check for entries on hold
        hold_query = select(func.count(Entry.id)).where(
            and_(
                Entry.client_id == self.client_id,
                Entry.status == EntryStatus.ON_HOLD.value,
            )
        )
        result = await self.db.execute(hold_query)
        hold_count = result.scalar() or 0
        
        if hold_count > 0:
            actions.append({
                "type": "on_hold",
                "count": hold_count,
                "title": "Entries On Hold",
                "description": f"{hold_count} entries are on hold and may require action",
                "action_url": "/entries?status=on_hold",
            })
        
        # Check for entries under exam
        exam_query = select(func.count(Entry.id)).where(
            and_(
                Entry.client_id == self.client_id,
                Entry.status == EntryStatus.UNDER_EXAM.value,
            )
        )
        result = await self.db.execute(exam_query)
        exam_count = result.scalar() or 0
        
        if exam_count > 0:
            actions.append({
                "type": "under_exam",
                "count": exam_count,
                "title": "Entries Under Exam",
                "description": f"{exam_count} entries are being examined by CBP",
                "action_url": "/entries?status=under_exam",
            })
        
        return actions
    
    async def get_alerts(self) -> List[Dict[str, Any]]:
        """Get alerts and notifications for client."""
        alerts = []
        
        # Alert: Rejected entries
        rejected_query = select(func.count(Entry.id)).where(
            and_(
                Entry.client_id == self.client_id,
                Entry.status == EntryStatus.REJECTED.value,
            )
        )
        result = await self.db.execute(rejected_query)
        rejected_count = result.scalar() or 0
        
        if rejected_count > 0:
            alerts.append({
                "type": "error",
                "title": "Rejected Entries",
                "message": f"{rejected_count} entries have been rejected and need attention",
                "action_url": "/entries?status=rejected",
            })
        
        # Alert: Recent releases (last 7 days)
        week_ago = date.today() - timedelta(days=7)
        recent_release_query = select(func.count(Entry.id)).where(
            and_(
                Entry.client_id == self.client_id,
                Entry.status == EntryStatus.RELEASED.value,
                Entry.release_date >= week_ago,
            )
        )
        result = await self.db.execute(recent_release_query)
        recent_releases = result.scalar() or 0
        
        if recent_releases > 0:
            alerts.append({
                "type": "success",
                "title": "Recent Releases",
                "message": f"{recent_releases} entries released in the last 7 days",
                "action_url": "/entries?status=released",
            })
        
        return alerts
    
    async def get_quick_stats(self) -> Dict[str, Any]:
        """Get quick statistics."""
        # This month
        today = date.today()
        month_start = today.replace(day=1)
        
        # Entries this month
        month_query = select(func.count(Entry.id)).where(
            and_(
                Entry.client_id == self.client_id,
                Entry.entry_date >= month_start,
            )
        )
        result = await self.db.execute(month_query)
        entries_this_month = result.scalar() or 0
        
        # Total value this month
        value_query = select(func.sum(Entry.total_value)).where(
            and_(
                Entry.client_id == self.client_id,
                Entry.entry_date >= month_start,
            )
        )
        result = await self.db.execute(value_query)
        value_this_month = float(result.scalar() or 0)
        
        # Total duty this month
        duty_query = select(func.sum(Entry.total_duty)).where(
            and_(
                Entry.client_id == self.client_id,
                Entry.entry_date >= month_start,
            )
        )
        result = await self.db.execute(duty_query)
        duty_this_month = float(result.scalar() or 0)
        
        return {
            "current_month": today.strftime("%B %Y"),
            "entries_this_month": entries_this_month,
            "value_this_month": value_this_month,
            "duty_this_month": duty_this_month,
        }
    
    async def get_entry_detail(self, entry_id: UUID) -> Optional[Dict[str, Any]]:
        """Get entry detail for client portal (read-only)."""
        query = (
            select(Entry)
            .options(selectinload(Entry.lines))
            .where(
                and_(
                    Entry.id == entry_id,
                    Entry.client_id == self.client_id,  # Security check
                )
            )
        )
        
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            return None
        
        return {
            "id": str(entry.id),
            "entry_number": entry.entry_number,
            "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
            "entry_type": entry.entry_type,
            "port_of_entry": entry.port_of_entry,
            "status": entry.status,
            "total_value": float(entry.total_value or 0),
            "total_duty": float(entry.total_duty or 0),
            "mpf_amount": float(entry.mpf_amount or 0),
            "hmf_amount": float(entry.hmf_amount or 0),
            "total_fees": float(
                (entry.total_duty or 0) +
                (entry.mpf_amount or 0) +
                (entry.hmf_amount or 0)
            ),
            "description": entry.merchandise_description,
            "consignee_name": entry.consignee_name,
            "manufacturer_name": entry.manufacturer_name,
            "country_of_origin": entry.country_of_origin,
            "transport_mode": entry.transport_mode,
            "vessel_name": entry.vessel_name,
            "carrier_code": entry.carrier_code,
            "release_date": entry.release_date.isoformat() if entry.release_date else None,
            "line_count": len(entry.lines) if entry.lines else 0,
            "lines": [
                {
                    "line_number": line.line_number,
                    "hts_code": line.hts_code,
                    "description": line.description,
                    "country_of_origin": line.country_of_origin,
                    "quantity": float(line.quantity or 0),
                    "unit": line.unit_of_measure,
                    "entered_value": float(line.entered_value or 0),
                    "duty_rate": float(line.duty_rate or 0),
                    "duty_amount": float(line.duty_amount or 0),
                }
                for line in (entry.lines or [])
            ],
            "can_approve": self.user.can_approve_entry() and entry.status == EntryStatus.PENDING_REVIEW.value,
        }
    
    async def approve_entry(self, entry_id: UUID, notes: Optional[str] = None) -> Entry:
        """Approve an entry (client approval)."""
        if not self.user.can_approve_entry():
            raise PermissionError("User does not have permission to approve entries")
        
        query = select(Entry).where(
            and_(
                Entry.id == entry_id,
                Entry.client_id == self.client_id,
                Entry.status == EntryStatus.PENDING_REVIEW.value,
            )
        )
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            raise ValueError("Entry not found or cannot be approved")
        
        # Update status
        entry.status = EntryStatus.READY_TO_FILE.value if hasattr(EntryStatus, 'READY_TO_FILE') else EntryStatus.FILED.value
        entry.client_approved_at = datetime.now(timezone.utc)
        entry.client_approved_by = str(self.user.id)
        
        await self.db.commit()
        await self.db.refresh(entry)
        
        return entry
    
    async def request_entry_changes(
        self,
        entry_id: UUID,
        change_notes: str,
    ) -> Entry:
        """Request changes to an entry before approval."""
        if not self.user.can_approve_entry():
            raise PermissionError("User does not have permission to request changes")
        
        query = select(Entry).where(
            and_(
                Entry.id == entry_id,
                Entry.client_id == self.client_id,
                Entry.status == EntryStatus.PENDING_REVIEW.value,
            )
        )
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            raise ValueError("Entry not found or cannot be modified")
        
        # Store change request
        existing_notes = entry.internal_notes or ""
        entry.internal_notes = f"{existing_notes}\n\n[CLIENT CHANGE REQUEST - {datetime.now(timezone.utc).isoformat()}]\n{change_notes}"
        entry.status = EntryStatus.DRAFT.value  # Send back to draft
        
        await self.db.commit()
        await self.db.refresh(entry)
        
        return entry
