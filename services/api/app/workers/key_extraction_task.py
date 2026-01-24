"""
Celery task for extracting linking keys from documents.

This task should be called after document extraction completes.
It extracts identifiers (Entry#, BOL#, Container#, etc.) and
optionally triggers auto-linking to group documents into shipments.
"""
import logging
import time
from uuid import UUID
from typing import Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models import RawFile
from app.models.raw_extraction import RawExtraction
from app.models.document_key import DocumentKey

logger = logging.getLogger(__name__)

# Create async engine for Celery worker
db_url = settings.database_url or "postgresql+asyncpg://postgres:postgres@localhost:5432/doc_ingestion"
if "+asyncpg://" not in db_url:
    db_url = db_url.replace("+psycopg://", "+asyncpg://").replace("+psycopg2://", "+asyncpg://").replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(db_url, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
async def extract_document_keys(
    self,
    file_id: str,
    extraction_id: str = None,
    use_llm: bool = False,
    auto_link: bool = True
) -> Dict[str, Any]:
    """
    Extract linking keys from a document.
    
    This task extracts identifiers (Entry#, BOL#, Container#, PO#, etc.)
    from document content using regex patterns and optionally LLM.
    
    Args:
        file_id: ID of the RawFile (document)
        extraction_id: Optional ID of RawExtraction to get text from
        use_llm: Whether to use LLM for complex entity extraction
        auto_link: Whether to trigger auto-linking after key extraction
        
    Returns:
        Dictionary with extraction results
    """
    file_uuid = UUID(file_id)
    start_time = time.time()
    
    try:
        async with AsyncSessionLocal() as session:
            from app.services.key_extractor_service import KeyExtractorService
            
            # Get document text
            text_content = ""
            parsed_data = {}
            
            # Try to get extracted text from RawExtraction
            if extraction_id:
                ext_uuid = UUID(extraction_id)
                stmt = select(RawExtraction).where(RawExtraction.id == ext_uuid)
                result = await session.execute(stmt)
                extraction = result.scalar_one_or_none()
                
                if extraction:
                    text_content = extraction.extracted_text or ""
                    if extraction.raw_content and isinstance(extraction.raw_content, dict):
                        parsed_data = extraction.raw_content
            
            # If no extraction_id or extraction not found, try to find by file_id
            if not text_content:
                stmt = select(RawExtraction).where(RawExtraction.file_id == file_uuid).order_by(RawExtraction.created_at.desc()).limit(1)
                result = await session.execute(stmt)
                extraction = result.scalar_one_or_none()
                
                if extraction:
                    text_content = extraction.extracted_text or ""
                    if extraction.raw_content and isinstance(extraction.raw_content, dict):
                        parsed_data = extraction.raw_content
            
            if not text_content and not parsed_data:
                logger.warning(f"No extracted content found for file {file_id}")
                return {
                    "status": "skipped",
                    "file_id": file_id,
                    "reason": "No extracted content available"
                }
            
            # Initialize the key extractor
            extractor = KeyExtractorService(session)
            
            # Extract keys
            keys = await extractor.extract_and_save(
                document_id=file_uuid,
                text_content=text_content,
                parsed_data=parsed_data,
                use_llm=use_llm
            )
            
            elapsed = time.time() - start_time
            logger.info(f"Extracted {len(keys)} keys from file {file_id} in {elapsed:.2f}s")
            
            result = {
                "status": "success",
                "file_id": file_id,
                "keys_extracted": len(keys),
                "key_types": list(set(k.key_type for k in keys)),
                "elapsed_seconds": elapsed
            }
            
            # Trigger auto-linking if requested
            if auto_link and keys:
                link_result = await _run_auto_link(session, file_uuid, keys)
                result["auto_link"] = link_result
            
            return result
            
    except Exception as e:
        logger.error(f"Error extracting keys from file {file_id}: {e}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        else:
            return {
                "status": "failed",
                "file_id": file_id,
                "error": str(e),
                "retries": self.request.retries
            }


async def _run_auto_link(session: AsyncSession, file_id: UUID, keys: list) -> Dict[str, Any]:
    """Run auto-linking for a document with extracted keys."""
    try:
        from app.services.auto_linker_service import AutoLinkerService
        
        linker = AutoLinkerService(session)
        shipment = await linker.link_document(file_id, keys)
        
        if shipment:
            return {
                "linked": True,
                "shipment_id": str(shipment.id),
                "shipment_name": shipment.name
            }
        else:
            return {
                "linked": False,
                "reason": "No matching shipment found or created"
            }
            
    except Exception as e:
        logger.error(f"Auto-linking failed for {file_id}: {e}")
        return {
            "linked": False,
            "error": str(e)
        }


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
async def batch_extract_keys(
    self,
    file_ids: list = None,
    only_without_keys: bool = True,
    use_llm: bool = False,
    auto_link: bool = True
) -> Dict[str, Any]:
    """
    Batch extract keys from multiple documents.
    
    Args:
        file_ids: List of file IDs to process (None = all)
        only_without_keys: Only process files without existing keys
        use_llm: Whether to use LLM extraction
        auto_link: Whether to trigger auto-linking
        
    Returns:
        Summary of batch extraction
    """
    start_time = time.time()
    results = {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
        "total_keys": 0,
        "errors": []
    }
    
    try:
        async with AsyncSessionLocal() as session:
            # Build query for files to process
            query = select(RawExtraction.file_id).distinct()
            
            if file_ids:
                file_uuids = [UUID(f) for f in file_ids]
                query = query.where(RawExtraction.file_id.in_(file_uuids))
            
            if only_without_keys:
                # Subquery for files that already have keys
                has_keys_subquery = select(DocumentKey.document_id).distinct()
                query = query.where(~RawExtraction.file_id.in_(has_keys_subquery))
            
            result = await session.execute(query)
            files_to_process = [row[0] for row in result.all()]
            
            logger.info(f"Batch key extraction starting for {len(files_to_process)} files")
            
            for file_uuid in files_to_process:
                try:
                    # Process each file
                    task_result = await extract_document_keys.apply_async(
                        args=[str(file_uuid)],
                        kwargs={"use_llm": use_llm, "auto_link": auto_link}
                    ).get()
                    
                    results["processed"] += 1
                    
                    if task_result.get("status") == "success":
                        results["succeeded"] += 1
                        results["total_keys"] += task_result.get("keys_extracted", 0)
                    elif task_result.get("status") == "skipped":
                        results["skipped"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append({
                            "file_id": str(file_uuid),
                            "error": task_result.get("error", "Unknown error")
                        })
                        
                except Exception as e:
                    results["processed"] += 1
                    results["failed"] += 1
                    results["errors"].append({
                        "file_id": str(file_uuid),
                        "error": str(e)
                    })
            
            results["elapsed_seconds"] = time.time() - start_time
            return results
            
    except Exception as e:
        logger.error(f"Batch key extraction failed: {e}")
        results["errors"].append({"batch_error": str(e)})
        return results


@celery_app.task
async def run_auto_linker(
    file_ids: list = None,
    only_unlinked: bool = True
) -> Dict[str, Any]:
    """
    Run the auto-linker to group documents into shipments.
    
    Args:
        file_ids: Specific documents to process (None = all with keys)
        only_unlinked: Only process documents not already in a shipment
        
    Returns:
        Summary of linking results
    """
    try:
        async with AsyncSessionLocal() as session:
            from app.services.auto_linker_service import AutoLinkerService
            
            linker = AutoLinkerService(session)
            
            doc_uuids = None
            if file_ids:
                doc_uuids = [UUID(f) for f in file_ids]
            
            results = await linker.run_batch_linking(
                document_ids=doc_uuids,
                only_unlinked=only_unlinked
            )
            
            return results
            
    except Exception as e:
        logger.error(f"Auto-linker task failed: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }
