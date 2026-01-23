import logging
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.silver_records import Party, Product, Address
from app.models.gold_records import Shipment, CommercialInvoice, InvoiceLine
from app.schemas.data_fabric import (
    PartyResponse, PartyListResponse,
    ProductResponse, ProductListResponse,
    ShipmentResponse, ShipmentListResponse,
    CommercialInvoiceResponse, InvoiceListResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-fabric", tags=["data-fabric"])

# --- Silver Layer Endpoints ---

@router.get("/silver/parties", response_model=PartyListResponse)
async def list_parties(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    party_type: str = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """List Silver Layer Parties."""
    query = select(Party).options(selectinload(Party.addresses))
    
    if search:
        query = query.where(Party.canonical_name.ilike(f"%{search}%"))
    if party_type:
        query = query.where(Party.party_type == party_type)
        
    # Count total
    count_query = select(func.count(Party.id))
    if search:
        count_query = count_query.where(Party.canonical_name.ilike(f"%{search}%"))
    if party_type:
        count_query = count_query.where(Party.party_type == party_type)
        
    total = (await session.execute(count_query)).scalar() or 0
    
    # Pagination
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Party.created_at.desc())
    
    result = await session.execute(query)
    items = result.scalars().all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@router.get("/silver/products", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """List Silver Layer Products."""
    query = select(Product)
    
    if search:
        query = query.where(Product.description.ilike(f"%{search}%"))
        
    count_query = select(func.count(Product.id))
    if search:
        count_query = count_query.where(Product.description.ilike(f"%{search}%"))
        
    total = (await session.execute(count_query)).scalar() or 0
    
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Product.created_at.desc())
    
    result = await session.execute(query)
    items = result.scalars().all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }

# --- Gold Layer Endpoints ---

@router.get("/gold/shipments")
async def list_shipments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    reference: str = Query(None),
    status: str = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """List Gold Layer Shipments."""
    query = select(Shipment).options(
        selectinload(Shipment.shipper),
        selectinload(Shipment.consignee),
        selectinload(Shipment.invoices)
    )
    
    if reference:
        query = query.where(Shipment.reference_num.ilike(f"%{reference}%"))
    if status:
        query = query.where(Shipment.status == status)
        
    count_query = select(func.count(Shipment.id))
    if reference:
        count_query = count_query.where(Shipment.reference_num.ilike(f"%{reference}%"))
    if status:
        count_query = count_query.where(Shipment.status == status)

    total = (await session.execute(count_query)).scalar() or 0
    
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Shipment.created_at.desc())
    
    result = await session.execute(query)
    items = result.scalars().all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@router.get("/gold/invoices")
async def list_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    invoice_num: str = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """List Gold Layer Invoices."""
    query = select(CommercialInvoice).options(
        selectinload(CommercialInvoice.vendor),
        selectinload(CommercialInvoice.buyer),
        selectinload(CommercialInvoice.lines).selectinload(InvoiceLine.product)
    )
    
    if invoice_num:
        query = query.where(CommercialInvoice.invoice_num.ilike(f"%{invoice_num}%"))
        
    count_query = select(func.count(CommercialInvoice.id))
    if invoice_num:
        count_query = count_query.where(CommercialInvoice.invoice_num.ilike(f"%{invoice_num}%"))
        
    total = (await session.execute(count_query)).scalar() or 0
    
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(CommercialInvoice.created_at.desc())
    
    result = await session.execute(query)
    items = result.scalars().all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }

# --- Golden Record Endpoints ---

from app.services.golden_record_service import GoldenRecordService
from pydantic import BaseModel

class MergeRequest(BaseModel):
    survivor_id: str
    victim_id: str

class DuplicateCandidate(BaseModel):
    entity_type: str
    entity_1: dict
    entity_2: dict
    similarity: float
    match_reason: str

@router.get("/golden-records/stats")
async def get_golden_record_stats(
    session: AsyncSession = Depends(get_db),
):
    """Get statistics about Golden Records."""
    return await GoldenRecordService.get_golden_record_stats(session)

@router.get("/golden-records/duplicates/parties")
async def find_party_duplicates(
    limit: int = Query(50, ge=1, le=200),
    min_similarity: float = Query(0.85, ge=0.5, le=1.0),
    session: AsyncSession = Depends(get_db),
):
    """Find potential duplicate Party records."""
    return await GoldenRecordService.find_party_duplicates(session, limit, min_similarity)

@router.get("/golden-records/duplicates/products")
async def find_product_duplicates(
    limit: int = Query(50, ge=1, le=200),
    min_similarity: float = Query(0.85, ge=0.5, le=1.0),
    session: AsyncSession = Depends(get_db),
):
    """Find potential duplicate Product records."""
    return await GoldenRecordService.find_product_duplicates(session, limit, min_similarity)

@router.post("/golden-records/merge/parties")
async def merge_parties(
    request: MergeRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Merge two Party records into one.
    
    The survivor absorbs the victim's aliases and links.
    """
    try:
        survivor_uuid = UUID(request.survivor_id)
        victim_uuid = UUID(request.victim_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    
    result = await GoldenRecordService.merge_parties(session, survivor_uuid, victim_uuid)
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result

@router.post("/golden-records/merge/products")
async def merge_products(
    request: MergeRequest,
    session: AsyncSession = Depends(get_db),
):
    """Merge two Product records into one."""
    try:
        survivor_uuid = UUID(request.survivor_id)
        victim_uuid = UUID(request.victim_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    
    result = await GoldenRecordService.merge_products(session, survivor_uuid, victim_uuid)
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result

@router.post("/golden-records/split/parties/{party_id}")
async def split_party(
    party_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Undo a party merge by clearing the golden_record_id."""
    result = await GoldenRecordService.split_party(session, party_id)
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result

