"""
Shipment Assembly Worker

Celery worker that analyzes documents after processing and
creates shipment suggestions or auto-assembles shipments.
"""
import logging
from typing import Dict, Any, List
from uuid import UUID

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.models.document_metadata import DocumentMetadata
from app.models.shipment_suggestions import ClientAssemblyPreference, AssemblyMode
from app.services.shipment_assembly_service import ShipmentAssemblyServiceSync

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2)
def process_shipment_assembly(self, document_id: str) -> Dict[str, Any]:
    """
    Analyze a document and create shipment suggestions.
    
    Called after document extraction completes. Looks for other documents
    with matching identifiers and creates shipment suggestions.
    
    Args:
        document_id: UUID of the processed document
        
    Returns:
        Dict with assembly results
    """
    try:
        logger.info(f"Processing shipment assembly for document {document_id}")
        return _run_assembly_sync(document_id)
    except Exception as e:
        logger.error(f"Shipment assembly failed for {document_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True)
def process_batch_assembly(self, document_ids: List[str]) -> Dict[str, Any]:
    """
    Analyze multiple documents for shipment assembly.
    
    Args:
        document_ids: List of document UUIDs to analyze
        
    Returns:
        Dict with batch assembly results
    """
    logger.info(f"Processing batch shipment assembly for {len(document_ids)} documents")
    
    try:
        with get_sync_db() as session:
            doc_uuids = [UUID(d) for d in document_ids]
            
            # Get client assembly mode (default to manual)
            client_id = "default"
            pref = session.execute(
                select(ClientAssemblyPreference).where(
                    ClientAssemblyPreference.client_id == client_id
                )
            ).scalar_one_or_none()
            
            auto_mode = pref and pref.assembly_mode == AssemblyMode.AUTO
            
            # Run assembly
            suggestions = ShipmentAssemblyServiceSync.analyze_and_create_suggestions(
                session=session,
                document_ids=doc_uuids,
                auto_mode=auto_mode
            )
            
            return {
                "status": "success",
                "documents_processed": len(document_ids),
                "suggestions_created": len(suggestions),
                "auto_mode": auto_mode,
                "suggestions": [
                    {
                        "id": str(s.id),
                        "master_bl": s.master_bl,
                        "document_count": len(s.document_ids) if s.document_ids else 0,
                        "status": s.status.value if s.status else "pending"
                    }
                    for s in suggestions
                ]
            }
    except Exception as e:
        logger.error(f"Batch shipment assembly failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def _run_assembly_sync(document_id: str) -> Dict[str, Any]:
    """Run shipment assembly synchronously."""
    with get_sync_db() as session:
        doc_uuid = UUID(document_id)
        
        # Get the document
        result = session.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            return {"status": "error", "error": "Document not found"}
        
        # Get client assembly mode
        client_id = "default"  # Would get from document context
        pref = session.execute(
            select(ClientAssemblyPreference).where(
                ClientAssemblyPreference.client_id == client_id
            )
        ).scalar_one_or_none()
        
        auto_mode = pref and pref.assembly_mode == AssemblyMode.AUTO
        
        # Find related documents (within last 30 days, same tenant)
        from datetime import datetime, timedelta, timezone
        from app.models.extraction_result import ExtractionResult
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        
        # Get extraction results for this document to find linking identifiers
        extractions = session.execute(
            select(ExtractionResult).where(
                ExtractionResult.document_id == doc_uuid
            )
        ).scalars().all()
        
        # Extract identifiers
        master_bl = None
        container = None
        
        for ext in extractions:
            field = ext.field_name.lower()
            if "master_bl" in field or "master_bol" in field:
                master_bl = ext.field_value
            if "container" in field:
                container = ext.field_value
        
        if not master_bl and not container:
            return {
                "status": "no_identifiers",
                "message": "No linking identifiers found in document"
            }
        
        # Find other documents with same identifiers
        related_doc_ids = set()
        related_doc_ids.add(doc_uuid)
        
        if master_bl:
            # Find documents with same master BL
            related = session.execute(
                select(ExtractionResult.document_id).where(
                    ExtractionResult.field_value == master_bl,
                    ExtractionResult.document_id != doc_uuid
                ).distinct()
            ).scalars().all()
            related_doc_ids.update(related)
        
        if container:
            related = session.execute(
                select(ExtractionResult.document_id).where(
                    ExtractionResult.field_value == container,
                    ExtractionResult.document_id != doc_uuid
                ).distinct()
            ).scalars().all()
            related_doc_ids.update(related)
        
        if len(related_doc_ids) < 2:
            return {
                "status": "no_matches",
                "message": "No related documents found",
                "identifiers": {
                    "master_bl": master_bl,
                    "container": container
                }
            }
        
        # Create suggestions for the group
        suggestions = ShipmentAssemblyServiceSync.analyze_and_create_suggestions(
            session=session,
            document_ids=list(related_doc_ids),
            auto_mode=auto_mode
        )
        
        return {
            "status": "success",
            "document_id": document_id,
            "related_documents": len(related_doc_ids) - 1,
            "suggestions_created": len(suggestions),
            "auto_mode": auto_mode,
            "suggestions": [
                {
                    "id": str(s.id),
                    "master_bl": s.master_bl,
                    "status": s.status.value if s.status else "pending"
                }
                for s in suggestions
            ]
        }


@celery_app.task(bind=True)
def auto_assemble_all_documents(self) -> Dict[str, Any]:
    """
    Periodic task to analyze all unlinked documents and create suggestions.
    
    Runs in the background to catch any documents that weren't processed
    by the after-processing trigger.
    """
    logger.info("Running auto-assembly for all unlinked documents...")
    
    try:
        with get_sync_db() as session:
            from app.models.gold_records import ShipmentDocument
            from sqlalchemy import not_, exists
            
            # Find documents not in any shipment
            subquery = select(ShipmentDocument.document_id)
            query = select(DocumentMetadata.id).where(
                not_(DocumentMetadata.id.in_(subquery)),
                DocumentMetadata.extracted_text_snippet.isnot(None)
            ).limit(200)
            
            result = session.execute(query)
            unlinked_doc_ids = [r[0] for r in result.all()]
            
            if not unlinked_doc_ids:
                return {
                    "status": "no_documents",
                    "message": "No unlinked documents found"
                }
            
            # Get client assembly mode
            client_id = "default"
            pref = session.execute(
                select(ClientAssemblyPreference).where(
                    ClientAssemblyPreference.client_id == client_id
                )
            ).scalar_one_or_none()
            
            auto_mode = pref and pref.assembly_mode == AssemblyMode.AUTO
            
            # Run assembly
            suggestions = ShipmentAssemblyServiceSync.analyze_and_create_suggestions(
                session=session,
                document_ids=unlinked_doc_ids,
                auto_mode=auto_mode
            )
            
            return {
                "status": "success",
                "documents_analyzed": len(unlinked_doc_ids),
                "suggestions_created": len(suggestions),
                "auto_mode": auto_mode
            }
            
    except Exception as e:
        logger.error(f"Auto-assembly failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
