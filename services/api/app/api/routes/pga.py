"""
PGA Determination API Routes  (Task C.2)

Endpoints for Partner Government Agency (PGA) compliance determination.

~30% of US imports require additional filings beyond CBP:
  FDA, EPA/TSCA, USDA/APHIS (Lacey Act), FWS (CITES), ATF, CPSC, NHTSA

Endpoints:
  GET  /api/pga/hts/{hts_code}          — Determine PGA for single HTS code
  POST /api/pga/entry/{entry_id}        — Determine PGA for all entry lines
  GET  /api/pga/agencies                — List all agency codes and descriptions
  POST /api/pga/batch                   — Determine PGA for a list of HTS codes
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entry import Entry
from app.services.pga_determination_service import PGADeterminationEngine

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/pga",
    tags=["PGA Determination"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class HTSItem(BaseModel):
    hts_code: str
    description: Optional[str] = None
    country_of_origin: Optional[str] = None


class BatchPGARequest(BaseModel):
    items: List[HTSItem]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/hts/{hts_code}")
async def get_pga_for_hts(
    hts_code: str,
    description: Optional[str] = Query(None),
    country_of_origin: Optional[str] = Query(None),
):
    """
    Determine PGA requirements for a single HTS code.

    Returns all applicable agencies, program codes, filing forms,
    and CFR citations.
    """
    engine = PGADeterminationEngine()
    determination = engine.determine(
        hts_code=hts_code,
        product_description=description,
        country_of_origin=country_of_origin,
    )
    return determination.to_dict()


@router.get("/entry/{entry_id}")
async def get_pga_for_entry(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Determine PGA requirements for all line items in an entry.

    Looks up the entry's HTS codes and returns PGA determinations
    for each line item.
    """
    result = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")

    # Build line item list from entry
    line_items = _extract_line_items(entry)
    if not line_items:
        return {
            "entry_id": str(entry_id),
            "entry_number": entry.entry_number,
            "message": "No HTS codes found on entry line items",
            "pga_required": False,
            "agencies": [],
            "determinations": {},
        }

    engine = PGADeterminationEngine()
    determinations = engine.determine_for_entry(line_items)
    all_agencies = engine.get_all_agencies(list(determinations.values()))
    pga_required = any(d.is_pga_required for d in determinations.values())

    return {
        "entry_id": str(entry_id),
        "entry_number": entry.entry_number,
        "pga_required": pga_required,
        "agencies": all_agencies,
        "line_count": len(determinations),
        "determinations": {hts: det.to_dict() for hts, det in determinations.items()},
    }


@router.post("/batch")
async def batch_pga_determination(req: BatchPGARequest):
    """
    Bulk PGA determination for a list of HTS codes.

    Useful for quoting / pre-screening before formal entry creation.
    Returns a summary and per-HTS determination.
    """
    engine = PGADeterminationEngine()
    results = {}
    all_agencies = set()

    for item in req.items:
        det = engine.determine(
            hts_code=item.hts_code,
            product_description=item.description,
            country_of_origin=item.country_of_origin,
        )
        results[item.hts_code] = det.to_dict()
        all_agencies.update(det.agencies_involved)

    return {
        "item_count": len(req.items),
        "pga_required_count": sum(1 for d in results.values() if d["is_pga_required"]),
        "agencies_involved": sorted(all_agencies),
        "determinations": results,
    }


@router.get("/agencies")
async def list_agencies():
    """
    List all PGA agencies tracked by the determination engine
    with their program codes and typical filing requirements.
    """
    return {
        "agencies": [
            {
                "code": "FDA",
                "name": "Food and Drug Administration",
                "program": "PREDICT system",
                "typical_form": "Prior Notice (food), Drug Registration, Device Registration",
                "cfr": "21 CFR Parts 1, 312, 807",
            },
            {
                "code": "EPA",
                "name": "Environmental Protection Agency",
                "program": "TSCA / Engine Certification",
                "typical_form": "TSCA Certification, EPA Form 3520-1",
                "cfr": "15 USC 2601, 40 CFR 85",
            },
            {
                "code": "USDA",
                "name": "Dept of Agriculture / APHIS",
                "program": "Lacey Act, VS, Plant Protection",
                "typical_form": "PPQ Form 505 (Lacey), VS Form 17-129 (animals)",
                "cfr": "7 CFR 93, 7 CFR 319, 16 USC 3372",
            },
            {
                "code": "FWS",
                "name": "US Fish & Wildlife Service",
                "program": "CITES / Endangered Species",
                "typical_form": "CITES Permit",
                "cfr": "50 CFR Part 14, 16 USC 1538",
            },
            {
                "code": "ATF",
                "name": "Bureau of Alcohol, Tobacco, Firearms and Explosives",
                "program": "Firearms / Munitions",
                "typical_form": "ATF Form 6 (Import Permit)",
                "cfr": "27 CFR Part 447",
            },
            {
                "code": "CPSC",
                "name": "Consumer Product Safety Commission",
                "program": "Consumer Product Safety",
                "typical_form": "Certificate of Conformity",
                "cfr": "15 USC 2063",
            },
            {
                "code": "NHTSA",
                "name": "National Highway Traffic Safety Administration",
                "program": "Federal Motor Vehicle Safety Standards",
                "typical_form": "HS-7 Declaration",
                "cfr": "49 CFR Part 591",
            },
            {
                "code": "DOE",
                "name": "Department of Energy",
                "program": "Appliance Energy Efficiency",
                "typical_form": "DOE Certification",
                "cfr": "10 CFR Parts 430, 431",
            },
        ]
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_line_items(entry: Entry) -> List[Dict[str, Any]]:
    """
    Extract HTS line items from an Entry ORM object.

    Handles both JSON line_items and structured relationships.
    """
    items = []

    # Try JSON line_items field first (most common pattern)
    if hasattr(entry, "line_items") and entry.line_items:
        raw = entry.line_items
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("hts_code"):
                    items.append({
                        "hts_code": item["hts_code"],
                        "description": item.get("description") or item.get("goods_description"),
                        "country_of_origin": item.get("country_of_origin"),
                    })

    # Fallback: single HTS code on the entry header
    if not items and hasattr(entry, "hts_code") and entry.hts_code:
        items.append({
            "hts_code": entry.hts_code,
            "description": getattr(entry, "description", None),
            "country_of_origin": getattr(entry, "country_of_origin", None),
        })

    return items
