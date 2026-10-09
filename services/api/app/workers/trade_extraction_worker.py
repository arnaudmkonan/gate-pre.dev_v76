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
    from app.services.extractors.trade_field_extractor import TradeFieldExtractor
    
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
    
    # Try LLM-based extraction first (higher quality)
    extraction = None
    service = get_trade_extraction_service()
    
    try:
        extraction = await service.extract_document(
            document_text=content,
            filename=filename,
            file_type=file_type
        )
    except Exception as e:
        logger.warning(f"LLM extraction failed for {document_id}, will use regex fallback: {e}")
    
    # Fall back to regex-based extraction if LLM failed or returned error
    if not extraction or extraction.get("status") != "success":
        llm_error = extraction.get("error", "unknown") if extraction else "LLM not available"
        logger.info(f"Using regex-based extraction for {document_id} (LLM: {llm_error})")
        extraction = TradeFieldExtractor.extract_fields(content, filename)
    
    if extraction.get("status") != "success":
        return extraction
    
    # Store results in database
    await _store_extraction_results(document_id, extraction, service)
    
    return {
        "status": "success",
        "document_id": document_id,
        "extraction_method": extraction.get("extraction_method", "llm"),
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
    if extraction.get("extraction_method") == "regex":
        # For regex extractions, build bronze records directly
        bronze_records = _build_bronze_records_from_regex(extraction)
    else:
        # For LLM extractions, use the service mapper
        bronze_records = service.map_to_bronze_layer(extraction)
    
    with get_sync_db() as session:
        # Store Bronze layer extractions
        stored_count = 0
        for record in bronze_records:
            try:
                extraction_record = ExtractionResult(
                    document_id=doc_uuid,
                    extraction_type=record.get("extraction_type", "trade_document"),
                    field_name=record["field_name"],
                    field_value=record.get("field_value"),
                    raw_value=str(record.get("field_value")) if record.get("field_value") else None,
                    confidence=record.get("confidence", 0.9),
                    agent_name=record.get("agent_name", "trade_document_extractor"),
                    status="auto",
                    extraction_metadata=record.get("metadata")
                )
                session.add(extraction_record)
                stored_count += 1
            except Exception as e:
                logger.warning(f"Failed to store extraction for {record.get('field_name')}: {e}")
        
        # Update document metadata with document type
        doc_meta = extraction.get("document_metadata", {})
        result = session.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
        )
        doc = result.scalar_one_or_none()
        if doc:
            doc.agent_status = "completed"
            doc.agent_processed_at = datetime.now(timezone.utc)
            doc.agent_results = {
                "trade_extraction": {
                    "document_type": doc_meta.get("document_type"),
                    "confidence": doc_meta.get("confidence_score"),
                    "extraction_method": extraction.get("extraction_method", "llm"),
                    "parties": len([p for p in extraction.get("parties", {}).values() if p]),
                    "cargo_items": len(extraction.get("cargo", {}).get("items", [])),
                    "fields_extracted": stored_count,
                }
            }
        
        session.commit()
        logger.info(f"Stored {stored_count} extractions for document {document_id}")
    
    # Trigger entity resolution for Silver layer
    try:
        async with AsyncSessionLocal() as async_session:
            result = await EntityResolutionService.resolve_document_entities(
                async_session, document_id
            )
            logger.info(f"Entity resolution for {document_id}: {result}")
    except Exception as e:
        logger.warning(f"Entity resolution failed for {document_id}: {e}")


def _build_bronze_records_from_regex(extraction: Dict) -> List[Dict]:
    """Build bronze layer records from regex extraction results."""
    records = []
    
    # Document type
    doc_meta = extraction.get("document_metadata", {})
    if doc_meta.get("document_type"):
        records.append({
            "field_name": "document_type",
            "field_value": doc_meta["document_type"],
            "confidence": doc_meta.get("confidence_score", 0.5),
            "extraction_type": "regex",
            "agent_name": "regex_trade_extractor",
        })
    
    # Shipment identifiers
    shipment = extraction.get("shipment", {})
    for field in ["master_bl_number", "house_bl_number", "booking_number"]:
        if shipment.get(field):
            records.append({
                "field_name": field,
                "field_value": shipment[field],
                "confidence": 0.9,
                "extraction_type": "regex",
                "agent_name": "regex_trade_extractor",
            })
    
    # Container numbers
    for i, container in enumerate(shipment.get("containers", [])):
        if container.get("number"):
            records.append({
                "field_name": f"container_{i+1}",
                "field_value": container["number"],
                "confidence": 0.95,
                "extraction_type": "regex",
                "agent_name": "regex_trade_extractor",
                "metadata": container,
            })
    
    # Port info
    for key, value in shipment.items():
        if key.startswith("port_") and value:
            records.append({
                "field_name": key,
                "field_value": value,
                "confidence": 0.85,
                "extraction_type": "regex",
                "agent_name": "regex_trade_extractor",
            })
    
    # Parties
    for role, party_data in extraction.get("parties", {}).items():
        if party_data and isinstance(party_data, dict) and party_data.get("name"):
            records.append({
                "field_name": role,
                "field_value": party_data["name"],
                "confidence": 0.85,
                "extraction_type": "regex",
                "agent_name": "regex_trade_extractor",
                "metadata": party_data,
            })
    
    # Cargo items
    for i, item in enumerate(extraction.get("cargo", {}).get("items", [])):
        if item.get("description") or item.get("hts_code_10_digit"):
            records.append({
                "field_name": f"cargo_item_{i+1}",
                "field_value": item.get("description", f"HTS {item.get('hts_code_10_digit', '')}"),
                "confidence": 0.8,
                "extraction_type": "regex",
                "agent_name": "regex_trade_extractor",
                "metadata": {
                    "hts_code": item.get("hts_code_10_digit"),
                    "hs_code": item.get("hs_code"),
                    "country_of_origin": item.get("country_of_origin"),
                },
            })
    
    # Financial fields
    financials = extraction.get("financials", {})
    if financials.get("invoice_number"):
        records.append({
            "field_name": "invoice_number",
            "field_value": financials["invoice_number"],
            "confidence": 0.9,
            "extraction_type": "regex",
            "agent_name": "regex_trade_extractor",
        })
    if financials.get("total_invoice_value"):
        records.append({
            "field_name": "total_invoice_value",
            "field_value": str(financials["total_invoice_value"]),
            "confidence": 0.8,
            "extraction_type": "regex",
            "agent_name": "regex_trade_extractor",
            "metadata": {"currency": financials.get("currency")},
        })
    
    # Customs entry
    customs = extraction.get("customs_entry", {})
    if customs.get("entry_number"):
        records.append({
            "field_name": "entry_number",
            "field_value": customs["entry_number"],
            "confidence": 0.9,
            "extraction_type": "regex",
            "agent_name": "regex_trade_extractor",
            "metadata": customs,
        })
    
    return records


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
