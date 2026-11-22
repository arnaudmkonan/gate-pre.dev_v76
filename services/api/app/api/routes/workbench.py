"""
Broker workbench summary API.

Aggregates the queues and counts entry writers need on first login —
not platform/Celery ops (those stay on /api/admin/dashboard).
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.entry import Entry, EntryStatus
from app.models.gold_records import Shipment, ShipmentStatus
from app.models.ingest_job import IngestJob, IngestJobStatus
from app.models.review_queue import ReviewQueueItem

router = APIRouter(
    prefix="/api/workbench",
    tags=["Workbench"],
    dependencies=[Depends(get_current_user)],
)


async def _count(db: AsyncSession, stmt) -> int:
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


@router.get("/summary")
async def get_workbench_summary(
    recent_limit: int = Query(8, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Single payload for the broker home dashboard.
    """
    # --- Attention counters ---
    review_pending = await _count(
        db,
        select(func.count(ReviewQueueItem.id)).where(
            ReviewQueueItem.status.in_(["pending", "in_review"])
        ),
    )
    shipments_partial = await _count(
        db,
        select(func.count(Shipment.id)).where(
            Shipment.status == ShipmentStatus.PARTIAL.value
        ),
    )
    shipments_ready = await _count(
        db,
        select(func.count(Shipment.id)).where(
            Shipment.status.in_(
                [
                    ShipmentStatus.COMPLETE.value,
                    ShipmentStatus.READY_FOR_AUDIT.value,
                ]
            )
        ),
    )
    entries_draft = await _count(
        db,
        select(func.count(Entry.id)).where(Entry.status == EntryStatus.DRAFT.value),
    )
    entries_ready = await _count(
        db,
        select(func.count(Entry.id)).where(
            Entry.status == EntryStatus.READY_TO_FILE.value
        ),
    )
    ingest_processing = await _count(
        db,
        select(func.count(IngestJob.id)).where(
            IngestJob.status.in_(
                [
                    IngestJobStatus.PENDING.value,
                    IngestJobStatus.QUEUED.value,
                    IngestJobStatus.PROCESSING.value,
                ]
            )
        ),
    )
    ingest_failed = await _count(
        db,
        select(func.count(IngestJob.id)).where(
            IngestJob.status == IngestJobStatus.FAILED.value
        ),
    )

    # --- Recent lists ---
    review_rows = (
        await db.execute(
            select(ReviewQueueItem)
            .where(ReviewQueueItem.status.in_(["pending", "in_review"]))
            .order_by(ReviewQueueItem.priority.desc(), ReviewQueueItem.created_at.asc())
            .limit(recent_limit)
        )
    ).scalars().all()

    recent_review: List[Dict[str, Any]] = []
    for item in review_rows:
        recent_review.append(
            {
                "id": str(item.id),
                "document_id": str(item.document_id) if item.document_id else None,
                "status": item.status,
                "priority": item.priority,
                "reason": item.reason,
                "reason_code": item.reason_code,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
        )

    shipment_rows = (
        await db.execute(
            select(Shipment)
            .order_by(Shipment.updated_at.desc().nullslast(), Shipment.created_at.desc())
            .limit(recent_limit)
        )
    ).scalars().all()

    recent_shipments: List[Dict[str, Any]] = []
    for s in shipment_rows:
        recent_shipments.append(
            {
                "id": str(s.id),
                "name": s.name,
                "status": s.status,
                "bol_number": s.bol_number,
                "entry_number": s.entry_number,
                "importer_name": s.importer_name,
                "document_count": s.document_count or 0,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
        )

    entry_rows = (
        await db.execute(
            select(Entry)
            .where(
                Entry.status.in_(
                    [
                        EntryStatus.DRAFT.value,
                        EntryStatus.READY_TO_FILE.value,
                        "in_review",
                        "validated",
                    ]
                )
            )
            .order_by(Entry.updated_at.desc().nullslast(), Entry.created_at.desc())
            .limit(recent_limit)
        )
    ).scalars().all()

    recent_entries: List[Dict[str, Any]] = []
    for e in entry_rows:
        recent_entries.append(
            {
                "id": str(e.id),
                "entry_number": e.entry_number,
                "status": e.status,
                "importer_of_record_name": e.importer_of_record_name,
                "port_of_entry": e.port_of_entry,
                "updated_at": e.updated_at.isoformat() if e.updated_at else None,
            }
        )

    needs_attention = (
        review_pending
        + shipments_partial
        + entries_draft
        + entries_ready
        + ingest_failed
    )

    live_ace = bool(settings.ace_sftp_enabled and (settings.ace_sftp_host or "").strip())
    ace_mode = (
        "live_sftp"
        if live_ace
        else ("simulation" if settings.ace_allow_simulation else "export_only")
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "broker": {
            "name": settings.broker_name,
            "filer_code": settings.broker_filer_code or None,
            "ace_mode": ace_mode,
            "imap_configured": bool(settings.email_imap_host and settings.email_imap_user),
            "smtp_configured": bool(settings.smtp_host and settings.smtp_username),
        },
        "attention": {
            "total": needs_attention,
            "review_pending": review_pending,
            "shipments_partial": shipments_partial,
            "shipments_ready_for_prep": shipments_ready,
            "entries_draft": entries_draft,
            "entries_ready_to_file": entries_ready,
            "ingest_processing": ingest_processing,
            "ingest_failed": ingest_failed,
        },
        "recent_review": recent_review,
        "recent_shipments": recent_shipments,
        "recent_entries": recent_entries,
        "quick_actions": [
            {"id": "ingest", "label": "Ingest documents", "path": "/ingest-ui"},
            {"id": "review", "label": "Open review queue", "path": "/review"},
            {"id": "shipments", "label": "Shipment assembly", "path": "/shipments/assembly"},
            {"id": "entries", "label": "Customs entries", "path": "/entries"},
            {"id": "new_entry", "label": "New official entry", "path": "/entries/new"},
        ],
    }
