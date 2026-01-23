"""
Duplicate Detection API Routes.

Endpoints for checking and managing duplicate documents.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.duplicate_service import DuplicateDetectionService

router = APIRouter(prefix="/api/duplicates", tags=["duplicates"])


# Request/Response Models
class DuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    highest_confidence: float
    matches: List[dict]
    checks_performed: List[str]


class DuplicateMatch(BaseModel):
    document_id: str
    filename: str
    match_type: str
    confidence: float
    match_details: dict
    created_at: Optional[str]


# Routes
@router.post("/check-file", response_model=DuplicateCheckResponse)
async def check_file_duplicate(
    file: UploadFile = File(...),
    customer_id: Optional[str] = None,
    days_back: int = Query(default=365, le=730),
    session: AsyncSession = Depends(get_db)
):
    """
    Check if an uploaded file is a duplicate before processing.

    Performs:
    - Exact hash match (identical files)
    - Content similarity check (near-duplicates)

    Use this endpoint before uploading to warn users of duplicates.
    """
    content = await file.read()

    # Extract text for similarity check (for supported types)
    text_content = None
    if file.filename.lower().endswith(('.txt', '.csv', '.json', '.xml', '.html')):
        try:
            text_content = content.decode('utf-8', errors='ignore')
        except:
            pass
    elif file.filename.lower().endswith('.pdf'):
        # For PDFs, we'd need to extract text - skip for pre-upload check
        pass

    result = await DuplicateDetectionService.check_all_duplicates(
        session=session,
        file_content=content,
        text_content=text_content,
        customer_id=customer_id,
        days_back=days_back
    )

    return result


@router.get("/check-document/{document_id}", response_model=DuplicateCheckResponse)
async def check_document_duplicates(
    document_id: str,
    customer_id: Optional[str] = None,
    days_back: int = Query(default=365, le=730),
    session: AsyncSession = Depends(get_db)
):
    """
    Check if a processed document has duplicates based on extracted fields.

    Performs:
    - Key field matching (invoice number, receipt number)
    - Vendor + amount + date combination matching

    Use this endpoint after document processing to find potential duplicates.
    """
    from app.models.document_metadata import DocumentMetadata
    from sqlalchemy import select
    from uuid import UUID

    # Verify document exists
    doc_result = await session.execute(
        select(DocumentMetadata).where(DocumentMetadata.id == UUID(document_id))
    )
    doc = doc_result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    result = await DuplicateDetectionService.check_all_duplicates(
        session=session,
        text_content=doc.extracted_text_snippet,
        document_id=document_id,
        customer_id=customer_id or doc.customer_id,
        days_back=days_back
    )

    return result


@router.get("/by-invoice-number/{invoice_number}")
async def find_by_invoice_number(
    invoice_number: str,
    customer_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    """
    Find all documents with a specific invoice/receipt number.

    Useful for checking if an invoice number already exists before processing.
    """
    from app.models.extraction_result import ExtractionResult
    from app.models.document_metadata import DocumentMetadata
    from sqlalchemy import select, and_

    query = select(ExtractionResult).where(
        and_(
            ExtractionResult.field_name.in_(["invoice_number", "receipt_number"]),
        )
    )

    result = await session.execute(query)
    matches = []

    for ext in result.scalars().all():
        if str(ext.field_value).lower().strip() == invoice_number.lower().strip():
            # Get document info
            doc_result = await session.execute(
                select(DocumentMetadata).where(DocumentMetadata.id == ext.document_id)
            )
            doc = doc_result.scalar_one_or_none()

            if doc and (not customer_id or doc.customer_id == customer_id):
                matches.append({
                    "document_id": str(ext.document_id),
                    "filename": doc.filename,
                    "field_name": ext.field_name,
                    "invoice_number": ext.field_value,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "ingestion_status": doc.ingestion_status,
                })

    return {
        "invoice_number": invoice_number,
        "matches": matches,
        "count": len(matches),
        "is_duplicate": len(matches) > 0
    }


@router.get("/by-vendor-amount")
async def find_by_vendor_amount(
    vendor: str,
    amount: float,
    date: Optional[str] = None,
    customer_id: Optional[str] = None,
    tolerance: float = Query(default=0.01, description="Amount tolerance for matching"),
    session: AsyncSession = Depends(get_db)
):
    """
    Find documents with matching vendor and amount.

    Useful for detecting duplicate invoices even if invoice numbers differ.
    """
    from app.models.extraction_result import ExtractionResult
    from app.models.document_metadata import DocumentMetadata
    from sqlalchemy import select

    vendor_fields = ["vendor_name", "store_name", "party_a_name"]
    amount_fields = ["total_amount", "total", "contract_value"]

    # Get vendor extractions
    vendor_query = select(ExtractionResult).where(
        ExtractionResult.field_name.in_(vendor_fields)
    )
    vendor_result = await session.execute(vendor_query)

    # Group by document
    doc_vendors = {}
    for ext in vendor_result.scalars().all():
        doc_id = str(ext.document_id)
        doc_vendors[doc_id] = str(ext.field_value) if ext.field_value else ""

    # Get amounts
    amount_query = select(ExtractionResult).where(
        ExtractionResult.field_name.in_(amount_fields)
    )
    amount_result = await session.execute(amount_query)

    doc_amounts = {}
    for ext in amount_result.scalars().all():
        doc_id = str(ext.document_id)
        try:
            doc_amounts[doc_id] = float(str(ext.field_value).replace("$", "").replace(",", ""))
        except:
            pass

    # Find matches
    matches = []
    for doc_id, doc_vendor in doc_vendors.items():
        vendor_similarity = DuplicateDetectionService.text_similarity(vendor.lower(), doc_vendor.lower())
        doc_amount = doc_amounts.get(doc_id)

        if vendor_similarity >= 0.8 and doc_amount is not None:
            if abs(doc_amount - amount) <= tolerance:
                # Get document info
                from uuid import UUID
                doc_result = await session.execute(
                    select(DocumentMetadata).where(DocumentMetadata.id == UUID(doc_id))
                )
                doc = doc_result.scalar_one_or_none()

                if doc and (not customer_id or doc.customer_id == customer_id):
                    matches.append({
                        "document_id": doc_id,
                        "filename": doc.filename,
                        "vendor": doc_vendor,
                        "vendor_similarity": round(vendor_similarity, 2),
                        "amount": doc_amount,
                        "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    })

    # Sort by similarity
    matches.sort(key=lambda x: x["vendor_similarity"], reverse=True)

    return {
        "query": {"vendor": vendor, "amount": amount},
        "matches": matches[:20],
        "count": len(matches),
        "is_duplicate": len(matches) > 0
    }


@router.get("/stats")
async def get_duplicate_stats(
    customer_id: Optional[str] = None,
    days_back: int = Query(default=30, le=365),
    session: AsyncSession = Depends(get_db)
):
    """
    Get duplicate detection statistics.

    Shows how many potential duplicates were detected in the given time period.
    """
    from app.models.document_metadata import DocumentMetadata
    from sqlalchemy import select, func
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    # Count total documents
    total_query = select(func.count(DocumentMetadata.id)).where(
        DocumentMetadata.created_at >= cutoff
    )
    if customer_id:
        total_query = total_query.where(DocumentMetadata.customer_id == customer_id)

    total_result = await session.execute(total_query)
    total_docs = total_result.scalar() or 0

    # Count documents with same size (potential duplicates)
    # Group by size and filename to find likely duplicates
    dup_query = select(
        DocumentMetadata.size,
        DocumentMetadata.filename,
        func.count(DocumentMetadata.id).label("count")
    ).where(
        and_(
            DocumentMetadata.created_at >= cutoff,
            DocumentMetadata.size.isnot(None)
        )
    ).group_by(DocumentMetadata.size, DocumentMetadata.filename).having(func.count(DocumentMetadata.id) > 1)

    if customer_id:
        dup_query = dup_query.where(DocumentMetadata.customer_id == customer_id)

    dup_result = await session.execute(dup_query)
    duplicate_groups = dup_result.all()

    potential_duplicates = sum(row.count - 1 for row in duplicate_groups)

    return {
        "period_days": days_back,
        "total_documents": total_docs,
        "potential_duplicates_found": potential_duplicates,
        "duplicate_rate": round(potential_duplicates / total_docs * 100, 2) if total_docs > 0 else 0,
        "message": f"{potential_duplicates} potential duplicates found in {total_docs} documents",
        "note": "Based on same filename and file size"
    }


# Import and_ for stats endpoint
from sqlalchemy import and_
