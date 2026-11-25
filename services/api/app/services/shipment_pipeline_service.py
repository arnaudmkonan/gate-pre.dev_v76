"""
Shipment job pipeline — stages a boutique clerk walks for one file.

Docs → Review (HITL if needed) → Assembled → ISF (ocean) → Entry → ACE
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.gold_records import Shipment, ShipmentDocument, ShipmentStatus
from app.models.isf_filing import ISFFiling
from app.models.review_queue import ReviewQueueItem


STAGE_ORDER = ("docs", "review", "assembled", "isf", "entry", "ace")

STAGE_LABELS = {
    "docs": "Documents",
    "review": "Doc review",
    "assembled": "Assembled",
    "isf": "ISF 10+2",
    "entry": "7501 / Entry",
    "ace": "ACE",
}


def _mode_needs_isf(shipment: Shipment) -> bool:
    """Ocean (BOL present, no AWB) needs ISF; pure air can skip."""
    if shipment.awb_number and not shipment.bol_number:
        return False
    if shipment.bol_number:
        return True
    # Unknown mode — keep ISF in the rail as optional/pending until entry
    return True


async def build_shipment_pipeline(
    db: AsyncSession,
    shipment: Shipment,
) -> Dict[str, Any]:
    ship_id = shipment.id
    doc_count = int(shipment.document_count or 0)

    # Pending HITL on linked documents
    review_pending = 0
    doc_ids_res = await db.execute(
        select(ShipmentDocument.document_id).where(ShipmentDocument.shipment_id == ship_id)
    )
    doc_ids = [d for d in doc_ids_res.scalars().all() if d]
    if doc_ids:
        pending_ids = (
            await db.execute(
                select(ReviewQueueItem.id)
                .where(
                    ReviewQueueItem.document_id.in_(doc_ids),
                    ReviewQueueItem.status.in_(["pending", "in_review"]),
                )
                .limit(50)
            )
        ).scalars().all()
        review_pending = len(list(pending_ids))

    isf_row = (
        await db.execute(
            select(ISFFiling)
            .where(ISFFiling.shipment_id == ship_id)
            .order_by(ISFFiling.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    entry = (
        await db.execute(
            select(Entry).where(Entry.shipment_id == ship_id).limit(1)
        )
    ).scalar_one_or_none()

    needs_isf = _mode_needs_isf(shipment)
    status = (shipment.status or "").lower()
    # Treat as assembled once docs are linked and HITL is clear, or downstream work exists
    assembled = (
        status
        in {
            ShipmentStatus.COMPLETE.value,
            ShipmentStatus.READY_FOR_AUDIT.value,
            ShipmentStatus.IN_AUDIT.value,
            ShipmentStatus.ARCHIVED.value,
        }
        or doc_count >= 1
        or bool(isf_row)
        or bool(entry)
    )

    ace_done_statuses = {
        "filed",
        "submitted",
        "accepted",
        "released",
        "liquidated",
        "filing",
    }
    entry_status = (entry.status or "").lower() if entry else ""
    ace_status = (entry.ace_status or "").lower() if entry else ""
    ace_done = bool(
        entry
        and (
            entry_status in ace_done_statuses
            or ace_status in {"submitted", "accepted", "released", "liquidated", "hold"}
        )
    )

    # Build raw completion flags first, then assign a single current stage
    docs_done = doc_count > 0
    review_done = docs_done and review_pending == 0
    assembled_done = assembled and review_done
    isf_done = (not needs_isf) or bool(isf_row)
    entry_done = bool(entry) and (
        ace_done or entry_status in {"ready_to_file", "validated", "accepted", "released", "filed"}
    )
    # Entry "in progress" counts as started
    entry_started = bool(entry)

    def _pick_current() -> str:
        if not docs_done:
            return "docs"
        if not review_done:
            return "review"
        if not assembled_done:
            return "assembled"
        if needs_isf and not isf_done:
            return "isf"
        if not entry_started:
            return "entry"
        if not ace_done:
            # Entry exists but not filed — stay on entry until ready, then ace
            if entry_status in {"draft", "pending_review", "validated"} and entry_status not in {
                "ready_to_file"
            }:
                return "entry"
            return "ace"
        return "ace"

    current_id = _pick_current()

    stages: List[Dict[str, Any]] = []

    def _state_for(stage_id: str, done: bool, skipped: bool = False) -> str:
        if skipped:
            return "skipped"
        if done and stage_id != current_id:
            return "done"
        if stage_id == current_id:
            return "current"
        # stages before current that aren't done shouldn't happen; after → todo
        order = list(STAGE_ORDER)
        if order.index(stage_id) < order.index(current_id):
            return "done"
        return "todo"

    stages.append(
        {
            "id": "docs",
            "label": STAGE_LABELS["docs"],
            "state": _state_for("docs", docs_done),
            "detail": f"{doc_count} linked" if doc_count else "No documents yet",
            "href": None,
        }
    )
    stages.append(
        {
            "id": "review",
            "label": STAGE_LABELS["review"],
            "state": _state_for("review", review_done),
            "detail": (
                f"{review_pending} item(s) need HITL"
                if review_pending
                else ("No open document exceptions" if docs_done else "Waiting on documents")
            ),
            "href": "/review" if review_pending else None,
            "pending_count": review_pending,
        }
    )
    stages.append(
        {
            "id": "assembled",
            "label": STAGE_LABELS["assembled"],
            "state": _state_for("assembled", assembled_done),
            "detail": status.replace("_", " ") if assembled_done else "Partial — request missing docs or continue",
            "href": None,
        }
    )
    stages.append(
        {
            "id": "isf",
            "label": STAGE_LABELS["isf"],
            "state": _state_for("isf", isf_done, skipped=not needs_isf),
            "detail": (
                "Not required (air)"
                if not needs_isf
                else (
                    f"{isf_row.status or 'draft'} · {isf_row.isf_number or str(isf_row.id)[:8]}"
                    if isf_row
                    else "Generate ISF draft"
                )
            ),
            "href": None,
            "isf_id": str(isf_row.id) if isf_row else None,
        }
    )
    stages.append(
        {
            "id": "entry",
            "label": STAGE_LABELS["entry"],
            "state": _state_for(
                "entry",
                entry_done or (entry_started and ace_done),
            ),
            "detail": (
                f"{entry.entry_number or 'draft'} · {entry.status}"
                if entry
                else "Prepare / create official entry"
            ),
            "href": f"/entries/{entry.id}" if entry else None,
            "entry_id": str(entry.id) if entry else None,
            "entry_number": entry.entry_number if entry else None,
            "entry_status": entry.status if entry else None,
        }
    )
    stages.append(
        {
            "id": "ace",
            "label": STAGE_LABELS["ace"],
            "state": _state_for("ace", ace_done),
            "detail": (
                ace_status or entry_status
                if ace_done
                else ("Validate → ready to file → submit" if entry else "Create entry first")
            ),
            "href": f"/entries/{entry.id}" if entry else None,
        }
    )

    # If everything past entry is done, mark ace current as done visually
    if ace_done:
        for s in stages:
            if s["id"] == "ace":
                s["state"] = "done"
            elif s["state"] == "current" and s["id"] != "ace":
                pass
        current_id = "ace"
        # All complete — keep ace as done, no open current
        if all(s["state"] in ("done", "skipped") for s in stages):
            current_id = "ace"

    if ace_done:
        next_action = {
            "label": "Job complete — view entry / ACE",
            "action": "open_entry",
            "path": f"/entries/{entry.id}" if entry else f"/shipments/{ship_id}",
        }
        current_id = "ace"
    else:
        next_action = _next_action(
            current_id=current_id or "docs",
            needs_isf=needs_isf,
            has_entry=bool(entry),
            entry_id=str(entry.id) if entry else None,
            shipment_id=str(ship_id),
            review_pending=review_pending,
        )

    return {
        "shipment_id": str(ship_id),
        "needs_isf": needs_isf,
        "current_stage": current_id or "docs",
        "stages": stages,
        "next_action": next_action,
        "links": {
            "entry_id": str(entry.id) if entry else None,
            "entry_number": entry.entry_number if entry else None,
            "isf_id": str(isf_row.id) if isf_row else None,
            "review_pending": review_pending,
        },
    }


def _next_action(
    *,
    current_id: str,
    needs_isf: bool,
    has_entry: bool,
    entry_id: Optional[str],
    shipment_id: str,
    review_pending: int,
) -> Dict[str, Any]:
    if current_id == "docs":
        return {
            "label": "Ingest or request missing documents",
            "action": "ingest_or_request",
            "path": f"/shipments/{shipment_id}",
        }
    if current_id == "review":
        return {
            "label": f"Clear document review ({review_pending})" if review_pending else "Open review queue",
            "action": "review",
            "path": "/review",
        }
    if current_id == "assembled":
        return {
            "label": "Finish assembly / request docs",
            "action": "assemble",
            "path": f"/shipments/{shipment_id}",
        }
    if current_id == "isf":
        return {
            "label": "Generate ISF (10+2)",
            "action": "generate_isf",
            "path": f"/shipments/{shipment_id}",
        }
    if current_id == "entry":
        if has_entry and entry_id:
            return {
                "label": "Continue official entry",
                "action": "open_entry",
                "path": f"/entries/{entry_id}",
            }
        return {
            "label": "Prepare 7501 & create entry",
            "action": "prepare_entry",
            "path": f"/entries/prep/{shipment_id}",
        }
    if current_id == "ace":
        # Caller may still set current_id=ace when already done — distinguish via path only
        return {
            "label": "File / monitor ACE",
            "action": "ace",
            "path": f"/entries/{entry_id}" if entry_id else f"/shipments/{shipment_id}",
        }
    return {
        "label": "Open shipment",
        "action": "open",
        "path": f"/shipments/{shipment_id}",
    }


async def build_pipeline_summary_for_shipments(
    db: AsyncSession,
    shipments: List[Shipment],
) -> Dict[str, Dict[str, Any]]:
    """Lightweight pipeline snapshot for workbench lists (batched)."""
    if not shipments:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for s in shipments:
        pipe = await build_shipment_pipeline(db, s)
        out[str(s.id)] = {
            "current_stage": pipe["current_stage"],
            "current_label": STAGE_LABELS.get(pipe["current_stage"], pipe["current_stage"]),
            "next_action": pipe["next_action"],
            "needs_isf": pipe["needs_isf"],
            "review_pending": pipe["links"]["review_pending"],
            "entry_id": pipe["links"]["entry_id"],
        }
    return out


async def get_shipment_pipeline(db: AsyncSession, shipment_id: UUID) -> Optional[Dict[str, Any]]:
    result = await db.execute(select(Shipment).where(Shipment.id == shipment_id))
    shipment = result.scalar_one_or_none()
    if not shipment:
        return None
    return await build_shipment_pipeline(db, shipment)
