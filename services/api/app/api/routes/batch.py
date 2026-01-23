"""
Batch Processing API Routes.

Endpoints for batch uploads, bulk review operations, and batch exports.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Body
from fastapi.responses import StreamingResponse
from typing import List, Optional
from pydantic import BaseModel
from io import BytesIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db as get_async_db
from app.services.batch_service import BatchService

router = APIRouter(prefix="/batch", tags=["batch"])


# ===== Request/Response Models =====

class CreateBatchJobRequest(BaseModel):
    name: str
    description: Optional[str] = None
    job_type: str = "upload"
    customer_id: Optional[str] = None
    pipeline_type: str = "standard"
    template_id: Optional[str] = None
    auto_approve_threshold: Optional[float] = None


class BulkApproveRequest(BaseModel):
    review_item_ids: List[str]
    reviewer: str


class BulkCorrectRequest(BaseModel):
    corrections: List[dict]  # [{extraction_id, corrected_value}]
    reviewer: str


class CreateBulkReviewRequest(BaseModel):
    reviewer: str
    review_item_ids: List[str]
    name: Optional[str] = None
    batch_job_id: Optional[str] = None
    document_type: Optional[str] = None
    template_id: Optional[str] = None


class FindSimilarRequest(BaseModel):
    field_name: str
    field_value: str
    template_id: Optional[str] = None
    status: str = "auto"


# ===== Batch Job Endpoints =====

@router.post("/jobs")
async def create_batch_job(
    request: CreateBatchJobRequest,
    session: AsyncSession = Depends(get_async_db)
):
    """Create a new batch job for tracking uploads."""
    batch_job = await BatchService.create_batch_job(
        session=session,
        name=request.name,
        description=request.description,
        job_type=request.job_type,
        customer_id=request.customer_id,
        pipeline_type=request.pipeline_type,
        template_id=request.template_id,
        auto_approve_threshold=request.auto_approve_threshold,
    )
    return batch_job.to_dict()


@router.get("/jobs")
async def list_batch_jobs(
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = Query(default=50, le=100),
    offset: int = 0,
    session: AsyncSession = Depends(get_async_db)
):
    """List batch jobs with optional filters."""
    jobs = await BatchService.list_batch_jobs(
        session=session,
        status=status,
        customer_id=customer_id,
        job_type=job_type,
        limit=limit,
        offset=offset,
    )
    return {
        "jobs": [j.to_dict() for j in jobs],
        "count": len(jobs),
    }


@router.get("/jobs/{batch_job_id}")
async def get_batch_job(
    batch_job_id: str,
    session: AsyncSession = Depends(get_async_db)
):
    """Get a specific batch job."""
    job = await BatchService.get_batch_job(session, batch_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    return job.to_dict()


@router.get("/jobs/{batch_job_id}/documents")
async def get_batch_documents(
    batch_job_id: str,
    include_extractions: bool = False,
    session: AsyncSession = Depends(get_async_db)
):
    """Get all documents in a batch with their status."""
    documents = await BatchService.get_batch_documents(
        session=session,
        batch_job_id=batch_job_id,
        include_extractions=include_extractions,
    )
    return {
        "batch_job_id": batch_job_id,
        "documents": documents,
        "count": len(documents),
    }


# ===== Batch Upload Endpoints =====

@router.post("/upload")
async def upload_batch(
    file: UploadFile = File(...),
    name: str = Query(...),
    description: Optional[str] = None,
    customer_id: Optional[str] = None,
    pipeline_type: str = "standard",
    template_id: Optional[str] = None,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Upload a ZIP file containing multiple documents for batch processing.

    The ZIP file will be extracted and each document will be processed
    through the ingestion and agent pipeline.
    """
    if not file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")

    # Create batch job first
    batch_job = await BatchService.create_batch_job(
        session=session,
        name=name,
        description=description,
        source_filename=file.filename,
        source_type="zip",
        customer_id=customer_id,
        pipeline_type=pipeline_type,
        template_id=template_id,
    )

    # Read file content
    content = await file.read()

    try:
        # Process the ZIP file
        result = await BatchService.process_zip_upload(
            session=session,
            zip_content=content,
            batch_job_id=str(batch_job.id),
            storage_service=None,  # TODO: inject storage service
        )

        # Queue documents for agent processing
        from app.workers.agent_processor import process_with_agents
        for doc_id in result.get("document_ids", []):
            process_with_agents.delay(doc_id, pipeline_type)

        return {
            "batch_job_id": str(batch_job.id),
            "status": "processing",
            **result,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process ZIP: {str(e)}")


@router.post("/upload/multifile")
async def upload_multifile(
    files: List[UploadFile] = File(...),
    name: str = Query(...),
    description: Optional[str] = None,
    customer_id: Optional[str] = None,
    pipeline_type: str = "standard",
    session: AsyncSession = Depends(get_async_db)
):
    """
    Upload multiple individual files for batch processing.

    Alternative to ZIP upload for smaller batches.
    """
    if len(files) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 files per batch")

    # Create batch job
    batch_job = await BatchService.create_batch_job(
        session=session,
        name=name,
        description=description,
        source_type="multi_file",
        customer_id=customer_id,
        pipeline_type=pipeline_type,
    )

    # Process each file
    from app.models.document_metadata import DocumentMetadata
    from app.services.extractors.pdf_extractor import PDFExtractor
    import mimetypes

    pdf_extractor = PDFExtractor(enable_ocr=False)
    document_ids = []
    failed_files = []

    for file in files:
        try:
            content = await file.read()
            mime_type, _ = mimetypes.guess_type(file.filename)
            file_ext = file.filename.split('.')[-1].lower() if '.' in file.filename else 'unknown'

            # Extract text content based on file type
            extracted_text = ""
            if file_ext == 'pdf':
                try:
                    extracted_text = await pdf_extractor.extract_text(content)
                except Exception as e:
                    pass  # Continue without text
            elif file_ext in ['txt', 'csv', 'json', 'xml', 'html', 'htm']:
                try:
                    extracted_text = content.decode('utf-8', errors='ignore')
                except Exception:
                    pass

            doc = DocumentMetadata(
                filename=file.filename,
                file_type=file_ext,
                size=len(content),
                mime_type=mime_type,
                job_id=batch_job.id,
                ingestion_status="pending",
                extracted_text_snippet=extracted_text[:10000] if extracted_text else None,
            )

            session.add(doc)
            await session.flush()
            document_ids.append(doc.id)

        except Exception as e:
            failed_files.append({"filename": file.filename, "error": str(e)})

    # Update batch job
    batch_job.document_ids = document_ids
    batch_job.total_documents = len(files)
    batch_job.successful_documents = len(document_ids)
    batch_job.failed_documents = len(failed_files)
    batch_job.failed_files = failed_files if failed_files else None
    batch_job.status = "processing"

    await session.commit()

    # Queue for agent processing
    from app.workers.agent_processor import process_with_agents
    for doc_id in document_ids:
        process_with_agents.delay(str(doc_id), pipeline_type)

    return {
        "batch_job_id": str(batch_job.id),
        "status": "processing",
        "total_files": len(files),
        "successful": len(document_ids),
        "failed": len(failed_files),
        "failed_files": failed_files,
    }


# ===== Bulk Review Endpoints =====

@router.post("/review/session")
async def create_bulk_review_session(
    request: CreateBulkReviewRequest,
    session: AsyncSession = Depends(get_async_db)
):
    """Create a bulk review session for reviewing multiple items together."""
    bulk_session = await BatchService.create_bulk_review_session(
        session=session,
        reviewer=request.reviewer,
        review_item_ids=request.review_item_ids,
        name=request.name,
        batch_job_id=request.batch_job_id,
        document_type=request.document_type,
        template_id=request.template_id,
    )
    return bulk_session.to_dict()


@router.post("/review/bulk-approve")
async def bulk_approve(
    request: BulkApproveRequest,
    session: AsyncSession = Depends(get_async_db)
):
    """Approve multiple review items at once."""
    result = await BatchService.bulk_approve(
        session=session,
        review_item_ids=request.review_item_ids,
        reviewer=request.reviewer,
    )
    return result


@router.post("/review/bulk-correct")
async def bulk_correct(
    request: BulkCorrectRequest,
    session: AsyncSession = Depends(get_async_db)
):
    """Apply corrections to multiple extractions at once."""
    result = await BatchService.bulk_correct(
        session=session,
        corrections=request.corrections,
        reviewer=request.reviewer,
    )
    return result


@router.post("/review/find-similar")
async def find_similar_extractions(
    request: FindSimilarRequest,
    session: AsyncSession = Depends(get_async_db)
):
    """Find extractions with similar values for potential bulk correction."""
    extractions = await BatchService.find_similar_extractions(
        session=session,
        field_name=request.field_name,
        field_value=request.field_value,
        template_id=request.template_id,
        status=request.status,
    )
    return {
        "field_name": request.field_name,
        "field_value": request.field_value,
        "similar_extractions": [e.to_dict() for e in extractions],
        "count": len(extractions),
    }


# ===== Batch Export Endpoints =====

@router.get("/jobs/{batch_job_id}/export")
async def export_batch(
    batch_job_id: str,
    format: str = "csv",
    include_reviewed_only: bool = True,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Export all extractions from a batch to CSV.

    Returns a downloadable file containing all extracted data.
    """
    try:
        content, filename = await BatchService.export_batch(
            session=session,
            batch_job_id=batch_job_id,
            format=format,
            include_reviewed_only=include_reviewed_only,
        )

        return StreamingResponse(
            BytesIO(content),
            media_type="text/csv" if format == "csv" else "application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
