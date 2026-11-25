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

    from app.services.shipment_pipeline_service import build_pipeline_summary_for_shipments

    pipeline_by_id = await build_pipeline_summary_for_shipments(db, list(shipment_rows))

    recent_shipments: List[Dict[str, Any]] = []
    for s in shipment_rows:
        pipe = pipeline_by_id.get(str(s.id), {})
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
                "pipeline_stage": pipe.get("current_stage"),
                "pipeline_label": pipe.get("current_label"),
                "next_action": pipe.get("next_action"),
                "review_pending": pipe.get("review_pending", 0),
                "entry_id": pipe.get("entry_id"),
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

    # Recent uploads so clerks can find "where did my file go?"
    since = datetime.now(timezone.utc) - timedelta(hours=48)
    upload_rows = (
        await db.execute(
            select(IngestJob)
            .where(IngestJob.created_at >= since)
            .order_by(IngestJob.created_at.desc())
            .limit(recent_limit)
        )
    ).scalars().all()

    recent_uploads: List[Dict[str, Any]] = []
    for job in upload_rows:
        recent_uploads.append(
            {
                "id": str(job.id),
                "filename": job.filename,
                "status": job.status,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "progress_percentage": getattr(job, "progress_percentage", None) or 0,
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
        "recent_uploads": recent_uploads,
        "continue_job": _pick_continue_job(
            recent_review=recent_review,
            recent_shipments=recent_shipments,
            recent_entries=recent_entries,
            recent_uploads=recent_uploads,
            review_pending=review_pending,
            ingest_processing=ingest_processing,
        ),
        "quick_actions": [
            {"id": "ingest", "label": "Ingest documents", "path": "/ingest-ui"},
            {"id": "review", "label": "Doc exceptions (HITL)", "path": "/review"},
            {"id": "shipments", "label": "Shipment assembly", "path": "/shipments/assembly"},
            {"id": "entries", "label": "Customs entries", "path": "/entries"},
            {
                "id": "new_entry",
                "label": "Manual entry (no shipment)",
                "path": "/entries/new",
            },
        ],
    }


def _pick_continue_job(
    *,
    recent_review: List[Dict[str, Any]],
    recent_shipments: List[Dict[str, Any]],
    recent_entries: List[Dict[str, Any]],
    recent_uploads: List[Dict[str, Any]],
    review_pending: int,
    ingest_processing: int,
) -> Optional[Dict[str, Any]]:
    """Single Continue CTA: prefer in-flight ingest, then HITL, shipment, entry."""
    if ingest_processing > 0 and recent_uploads:
        flying = next(
            (
                u
                for u in recent_uploads
                if (u.get("status") or "").lower() in ("pending", "queued", "processing")
            ),
            recent_uploads[0],
        )
        return {
            "kind": "ingest",
            "label": "Continue: watch document extract",
            "detail": flying.get("filename") or flying.get("id"),
            "path": "/ingest-ui",
        }

    if review_pending > 0 and recent_review:
        item = recent_review[0]
        return {
            "kind": "doc_exception",
            "label": "Continue: clear doc exception",
            "detail": item.get("reason") or "Document needs HITL",
            "path": f"/review/{item['id']}",
        }

    for s in recent_shipments:
        stage = (s.get("pipeline_stage") or "").lower()
        nxt = s.get("next_action") or {}
        if stage and stage not in ("ace",) and nxt.get("path"):
            # Skip completed jobs
            if stage == "ace" and (nxt.get("action") == "open_entry"):
                continue
            if nxt.get("action") == "open_entry" and "complete" in (nxt.get("label") or "").lower():
                continue
            return {
                "kind": "shipment",
                "label": f"Continue: {nxt.get('label') or s.get('pipeline_label')}",
                "detail": s.get("importer_name") or s.get("bol_number") or s.get("id"),
                "path": nxt.get("path") or f"/shipments/{s['id']}",
                "shipment_id": s.get("id"),
                "pipeline_stage": stage,
            }

    for e in recent_entries:
        status = (e.get("status") or "").lower()
        if status in ("draft", "pending_review", "ready_to_file", "validated"):
            label = "Continue: Broker OK / finish entry"
            if status == "ready_to_file":
                label = "Continue: file entry to ACE"
            return {
                "kind": "entry",
                "label": label,
                "detail": e.get("entry_number") or e.get("importer_of_record_name") or e.get("id"),
                "path": f"/entries/{e['id']}",
            }

    if recent_shipments:
        s = recent_shipments[0]
        nxt = s.get("next_action") or {}
        return {
            "kind": "shipment",
            "label": f"Continue: {nxt.get('label') or 'open shipment'}",
            "detail": s.get("importer_name") or s.get("id"),
            "path": nxt.get("path") or f"/shipments/{s['id']}",
        }
    return None
