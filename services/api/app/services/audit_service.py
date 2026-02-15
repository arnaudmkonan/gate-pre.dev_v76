"""Audit service for logging and tracking file operations."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum

from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, ResourceType, AuditAction

logger = logging.getLogger(__name__)

# ============================================================================
# AUDIT LOG RETENTION POLICY
# ============================================================================
# 180-day retention: Audit logs are automatically cleaned up after 180 days.
# This policy balances compliance requirements with storage efficiency.
# Logs older than 180 days are deleted to maintain database performance and
# reduce storage costs while preserving recent audit trails for investigations.
# The cleanup_old_logs() function should be called daily via a scheduled task.
# ============================================================================
AUDIT_LOG_RETENTION_DAYS = 180


class AuditService:
    """Service for creating and querying audit logs."""

    @staticmethod
    async def log_action(
        session: AsyncSession,
        resource_type: str,
        resource_id: str,
        action: str,
        actor_id: Optional[str] = None,
        changes: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict:
        """
        Log an audit action.

        Args:
            session: Database session
            resource_type: Type of resource (file, version, upload)
            resource_id: ID of the resource
            action: Action performed (create, update, delete, download)
            actor_id: User ID performing action
            changes: Dict of changes made
            ip_address: IP address of requester
            user_agent: User agent string

        Returns:
            Dict with audit log details
        """
        audit_log = AuditLog(
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            actor_id=actor_id,
            timestamp=datetime.utcnow(),
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        session.add(audit_log)
        await session.flush()

        logger.info(
            f"Audit logged: {action} on {resource_type} {resource_id} by {actor_id or 'unknown'}"
        )

        return {
            "audit_id": str(audit_log.id),
            "resource_type": audit_log.resource_type,
            "resource_id": str(audit_log.resource_id),
            "action": audit_log.action,
            "actor_id": audit_log.actor_id,
            "timestamp": audit_log.timestamp,
            "changes": audit_log.changes,
        }

    @staticmethod
    async def export_audit(
        session: AsyncSession,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict:
        """
        Export audit logs with optional filtering.

        Args:
            session: Database session
            resource_id: Filter by resource ID
            action: Filter by action
            resource_type: Filter by resource type
            limit: Number of records to return
            offset: Offset for pagination

        Returns:
            Dict with logs and total count
        """
        # Build query
        query = select(AuditLog)

        filters = []
        if resource_id:
            filters.append(AuditLog.resource_id == resource_id)
        if action:
            filters.append(AuditLog.action == action)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)

        if filters:
            query = query.where(and_(*filters))

        # Get total count
        count_result = await session.execute(select(AuditLog).where(and_(*filters) if filters else True))
        total_count = len(count_result.scalars().all())

        # Get paginated results
        query = query.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
        result = await session.execute(query)
        logs = result.scalars().all()

        return {
            "logs": [
                {
                    "audit_id": str(log.id),
                    "resource_type": log.resource_type,
                    "resource_id": str(log.resource_id),
                    "action": log.action,
                    "actor_id": log.actor_id,
                    "timestamp": log.timestamp,
                    "changes": log.changes,
                }
                for log in logs
            ],
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    async def cleanup_old_logs(session: AsyncSession) -> Dict[str, int]:
        """
        Clean up audit logs older than AUDIT_LOG_RETENTION_DAYS (180 days).

        This function should be called daily via a scheduled task to maintain
        database performance and comply with retention policies.

        Args:
            session: Database session

        Returns:
            Dict with count of deleted logs and cutoff timestamp
        """
        cutoff_date = datetime.utcnow() - timedelta(days=AUDIT_LOG_RETENTION_DAYS)

        # Delete logs older than cutoff
        delete_query = delete(AuditLog).where(AuditLog.timestamp < cutoff_date)
        result = await session.execute(delete_query)
        deleted_count = result.rowcount

        await session.commit()

        logger.info(
            f"Audit log cleanup: Deleted {deleted_count} logs older than {cutoff_date.isoformat()} "
            f"(retention policy: {AUDIT_LOG_RETENTION_DAYS} days)"
        )

        return {
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": AUDIT_LOG_RETENTION_DAYS,
        }


# ============================================================================
# Convenience functions for use in route handlers
# ============================================================================

async def audit(
    db: "AsyncSession",
    action: str,
    resource_type: str,
    resource_id: str,
    actor_id: Optional[str] = None,
    before: Optional[Dict] = None,
    after: Optional[Dict] = None,
    ip_address: Optional[str] = None,
):
    """
    Quick audit log helper — call from any route handler.

    Usage:
        from app.services.audit_service import audit

        @router.post("/{entry_id}")
        async def update_entry(entry_id: str, ..., db = Depends(get_db)):
            old_data = entry.to_dict()
            entry.status = new_status
            await audit(db, "update", "entry", entry_id,
                        actor_id=user["id"], before=old_data, after=entry.to_dict())
    """
    changes = None
    if before is not None and after is not None:
        changes = track_changes(before, after)
    elif after is not None:
        changes = {"after": after}
    elif before is not None:
        changes = {"before": before}

    return await AuditService.log_action(
        session=db,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        actor_id=actor_id,
        changes=changes,
        ip_address=ip_address,
    )


def track_changes(before: Dict, after: Dict) -> Dict:
    """
    Compare before/after dicts and return only changed fields.

    Returns: {"field_name": {"old": old_val, "new": new_val}, ...}
    """
    changes = {}
    all_keys = set(list(before.keys()) + list(after.keys()))

    for key in all_keys:
        old_val = before.get(key)
        new_val = after.get(key)
        if str(old_val) != str(new_val):
            changes[key] = {"old": str(old_val) if old_val is not None else None,
                           "new": str(new_val) if new_val is not None else None}

    return changes

