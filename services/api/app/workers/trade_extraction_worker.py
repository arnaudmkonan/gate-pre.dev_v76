"""
Trade Document Extraction Worker

Celery worker for extracting structured data from trade/customs documents
using the specialized TradeDocumentExtractionService.

This worker produces high-quality extractions optimized for:
- Medallion architecture (Bronze → Silver → Gold)
- Drawback automation  
- Compliance screening
"""
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List
from uuid import UUID

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_sync_db, AsyncSessionLocal
from app.models.document_metadata import DocumentMetadata
from app.models.extraction_result import ExtractionResult

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2)
def extract_trade_document(self, document_id: str) -> Dict[str, Any]:
    """
    Extract structured data from a trade document using the specialized prompt.
    
    Args:
        document_id: UUID of the DocumentMetadata record
        
    Returns:
        Dict with extraction results including document_type, parties, shipment, cargo, financials
    """
    try:
        logger.info(f"Starting trade document extraction for {document_id}")
        result = _run_extraction_sync(document_id)
        logger.info(f"Trade document extraction completed for {document_id}")
        
        # Trigger shipment assembly after successful extraction
        if result.get("status") == "success":
            try:
                from app.workers.shipment_assembly_worker import process_shipment_assembly
                process_shipment_assembly.delay(document_id)
                logger.info(f"Triggered shipment assembly for {document_id}")
            except Exception as e:
                logger.warning(f"Failed to trigger shipment assembly: {e}")
        
        return result
    except Exception as e:
        logger.error(f"Trade document extraction failed for {document_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=2)
def extract_trade_documents_batch(self, document_ids: List[str]) -> Dict[str, Any]:
    """
    Extract structured data from multiple trade documents.
    
    Args:
        document_ids: List of document UUIDs
        
    Returns:
        Dict with batch results
    """
    logger.info(f"Starting batch trade document extraction for {len(document_ids)} documents")
    
    results = {
        "total": len(document_ids),
        "successful": 0,
        "failed": 0,
        "documents": {}
    }
    
    for doc_id in document_ids:
        try:
            result = _run_extraction_sync(doc_id)
            results["documents"][doc_id] = result
            if result.get("status") == "success":
                results["successful"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            logger.error(f"Extraction failed for {doc_id}: {e}")
            results["documents"][doc_id] = {"status": "error", "error": str(e)}
            results["failed"] += 1
    
    logger.info(f"Batch extraction completed: {results['successful']}/{results['total']} successful")
    return results


def _run_extraction_sync(document_id: str) -> Dict[str, Any]:
    """Synchronous wrapper for the async extraction pipeline."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run_extraction_async(document_id))
    finally:
        loop.close()


async def _run_extraction_async(document_id: str) -> Dict[str, Any]:
    """Run the trade document extraction pipeline."""
    from app.services.trade_document_extraction_service import get_trade_extraction_service
    
    # Get document from database
    with get_sync_db() as session:
        doc_uuid = UUID(document_id)
        result = session.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            return {"status": "error", "error": f"Document {document_id} not found"}
        
        content = doc.extracted_text_snippet or ""
        filename = doc.filename
        file_type = doc.file_type
        
        if not content or len(content.strip()) < 50:
            return {"status": "skipped", "reason": "content_too_short"}
    
    # Run extraction using the trade document service
    service = get_trade_extraction_service()
    extraction = await service.extract_document(
        document_text=content,
        filename=filename,
        file_type=file_type
    )
    
    if extraction.get("status") != "success":
        return extraction
    
    # Store results in database
    await _store_extraction_results(document_id, extraction, service)
    
    return {
        "status": "success",
        "document_id": document_id,
        "document_type": extraction.get("document_metadata", {}).get("document_type"),
        "parties_count": len([p for p in extraction.get("parties", {}).values() if p]),
        "cargo_items_count": len(extraction.get("cargo", {}).get("items", [])),
        "has_financials": bool(extraction.get("financials", {}).get("invoice_number")),
        "has_customs_entry": bool(extraction.get("customs_entry", {}).get("entry_number")),
        "extraction": extraction
    }


async def _store_extraction_results(document_id: str, extraction: Dict, service) -> None:
    """Store the extraction results in the database."""
    from app.services.entity_resolution_service import EntityResolutionService
    
    doc_uuid = UUID(document_id)
    
    # Map to Bronze layer records
    bronze_records = service.map_to_bronze_layer(extraction)
    
    with get_sync_db() as session:
        # Store Bronze layer extractions
        for record in bronze_records:
            try:
                extraction_record = ExtractionResult(
                    document_id=doc_uuid,
                    extraction_type="trade_document",
                    field_name=record["field_name"],
                    field_value=record.get("field_value"),
                    raw_value=str(record.get("field_value")) if record.get("field_value") else None,
                    confidence=record.get("confidence", 0.9),
                    agent_name="trade_document_extractor",
                    status="auto",
                    # Store full metadata in extraction_metadata
                    extraction_metadata=record.get("metadata")
                )
                session.add(extraction_record)
            except Exception as e:
                logger.warning(f"Failed to store extraction for {record.get('field_name')}: {e}")
        
        # Update document metadata with document type
        doc_meta = extraction.get("document_metadata", {})
        result = session.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
        )
        doc = result.scalar_one_or_none()
        if doc:
            doc.detected_language = doc_meta.get("document_type", "unknown")
            doc.agent_status = "completed"
            doc.agent_processed_at = datetime.now(timezone.utc)
            doc.agent_results = {
                "trade_extraction": {
                    "document_type": doc_meta.get("document_type"),
                    "confidence": doc_meta.get("confidence_score"),
                    "parties": len([p for p in extraction.get("parties", {}).values() if p]),
                    "cargo_items": len(extraction.get("cargo", {}).get("items", [])),
                }
            }
        
        session.commit()
        logger.info(f"Stored {len(bronze_records)} extractions for document {document_id}")
    
    # Trigger entity resolution for Silver layer
    try:
        async with AsyncSessionLocal() as async_session:
            result = await EntityResolutionService.resolve_document_entities(
                async_session, document_id
            )
            logger.info(f"Entity resolution for {document_id}: {result}")
    except Exception as e:
        logger.warning(f"Entity resolution failed for {document_id}: {e}")


@celery_app.task(bind=True)
def reprocess_with_trade_extraction(self) -> Dict[str, Any]:
    """
    Periodic task to reprocess documents using the new trade document extraction.
    
    Finds documents that:
    - Have content
    - Haven't been processed with trade_document_extractor yet
    - Are likely trade documents (based on filename or initial classification)
    """
    logger.info("Checking for documents to reprocess with trade extraction...")
    
    trade_document_keywords = [
        'invoice', 'bl', 'bol', 'bill', 'lading', 'packing', 'arrival',
        'customs', 'entry', 'certificate', 'origin', 'manifest'
    ]
    
    with get_sync_db() as session:
        # Find documents with content that haven't been processed by trade extractor
        query = select(DocumentMetadata).where(
            DocumentMetadata.extracted_text_snippet.isnot(None),
        ).limit(20)
        
        result = session.execute(query)
        docs = result.scalars().all()
        
        queued = 0
        for doc in docs:
            # Check if filename suggests trade document
            filename_lower = (doc.filename or "").lower()
            is_trade_doc = any(kw in filename_lower for kw in trade_document_keywords)
            
            # Check if already processed by trade extractor
            agent_results = doc.agent_results or {}
            already_processed = "trade_extraction" in agent_results
            
            if is_trade_doc and not already_processed:
                extract_trade_document.delay(str(doc.id))
                queued += 1
                logger.info(f"Queued trade extraction for {doc.filename}")
        
        return {
            "status": "completed",
            "documents_checked": len(docs),
            "documents_queued": queued
        }
