"""
Celery worker for processing ingest jobs end-to-end.

This worker handles the full ingestion pipeline:
1. Read file from storage
2. Extract text content based on file type
3. Generate metadata
4. Update job status
5. Create embeddings (if OpenAI is configured)
6. Store embeddings for vector search
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from uuid import UUID

from sqlalchemy import select, and_

from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.core.config import settings
from app.models.ingest_job import IngestJob, IngestJobStatus
from app.models.raw_file import RawFile, RawFileStatus
from app.models.document_metadata import DocumentMetadata

logger = logging.getLogger(__name__)


def get_extractor_for_file_type(file_type: str):
    """Get the appropriate extractor for a file type."""
    from app.services.extractors.text_docx_extractor import TextExtractor, DocxExtractor
    from app.services.extractors.markup_json_extractor import (
        MarkupJsonExtractor,
        XmlExtractor, 
        YamlExtractor,
    )
    from app.services.extractors.spreadsheet_presentation_extractor import (
        SpreadsheetExtractor,
        PresentationExtractor,
    )
    from app.services.extractors.pdf_extractor import PDFExtractor
    from app.services.extractors.docling_extractor import DoclingExtractor
    
    # Initialize basic extractors
    text_ext = TextExtractor()
    markup_ext = MarkupJsonExtractor()
    xml_ext = XmlExtractor()
    yaml_ext = YamlExtractor()
    docx_ext = DocxExtractor()
    spreadsheet_ext = SpreadsheetExtractor()
    presentation_ext = PresentationExtractor()
    pdf_ext = PDFExtractor()
    
    # Initialize Docling (Path A Semantic Extractor)
    docling_ext = DoclingExtractor()
    
    # Use Docling if available, otherwise fallback to legacy extractors
    pdf_handler = docling_ext if docling_ext._docling_available else pdf_ext
    docx_handler = docling_ext if docling_ext._docling_available else docx_ext
    ppt_handler = docling_ext if docling_ext._docling_available else presentation_ext
    html_handler = docling_ext if docling_ext._docling_available else markup_ext
    md_handler = docling_ext if docling_ext._docling_available else markup_ext
    
    extractors = {
        "txt": text_ext,
        "md": md_handler,
        "html": html_handler,
        "json": markup_ext,
        "xml": xml_ext,
        "yml": yaml_ext,
        "yaml": yaml_ext,
        "docx": docx_handler,
        "doc": docx_handler,
        "csv": spreadsheet_ext,
        "xlsx": spreadsheet_ext,
        "xls": spreadsheet_ext,
        "pptx": ppt_handler,
        "ppt": ppt_handler,
        "pdf": pdf_handler,
    }
    
    return extractors.get(file_type.lower())


@celery_app.task(bind=True, max_retries=3)
def process_ingest_job(self, job_id: str):
    """
    Process a single ingest job through the full extraction pipeline.
    
    Args:
        job_id: UUID of the IngestJob to process
    """
    try:
        logger.info(f"Starting processing for job {job_id}")
        result = _process_job_sync(job_id)
        logger.info(f"Job {job_id} completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}")
        # Update job status to failed
        _update_job_status_sync(job_id, IngestJobStatus.FAILED, error_message=str(e))
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


def _process_job_sync(job_id: str) -> Dict[str, Any]:
    """Synchronous job processing for Celery."""
    import asyncio
    
    with get_sync_db() as session:
        # Get the job
        job_uuid = UUID(job_id)
        result = session.execute(
            select(IngestJob).where(IngestJob.id == job_uuid)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        # Update status to processing
        job.status = IngestJobStatus.PROCESSING
        job.attempts += 1
        job.last_attempted_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()
        
        logger.info(f"Processing job: {job.filename} (type: {job.file_type})")
        
        # Get file content from storage
        file_bytes = _get_file_from_storage(job.storage_path)
        
        if not file_bytes:
            raise ValueError(f"Could not read file from storage: {job.storage_path}")
        
        # Get appropriate extractor
        extractor = get_extractor_for_file_type(job.file_type)
        
        extracted_text = ""
        extracted_metadata = {
            "filename": job.filename,
            "file_size": job.size,
            "file_type": job.file_type,
        }
        
        if not extractor:
            # For unsupported types, just record that we received it
            logger.warning(f"No extractor for file type: {job.file_type}")
            extracted_text = f"[Raw file content - {len(file_bytes)} bytes]"
        else:
            # Run async extractor in sync context
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                extracted_content = loop.run_until_complete(
                    extractor.extract(file_bytes, job.filename)
                )
                loop.close()
                
                extracted_text = extracted_content.text or ""
                extracted_metadata.update(extracted_content.metadata)
                
                if extracted_content.errors:
                    logger.warning(f"Extraction warnings: {extracted_content.errors}")
            except Exception as e:
                logger.error(f"Extraction error: {e}")
                extracted_text = f"[Extraction error: {str(e)}]"
        
        # Create document metadata record
        doc_metadata = DocumentMetadata(
            job_id=job.id,
            filename=job.filename,
            file_type=job.file_type,
            size=job.size,
            ingestion_status="processing",  # Will update to completed after embeddings
            extracted_text_snippet=extracted_text[:1000] if extracted_text else None,
            raw_storage_path=job.storage_path,
            extraction_timestamp=datetime.now(timezone.utc),
            extractor_agent_version="1.0.0",
        )
        session.add(doc_metadata)
        session.flush()  # Get the doc_metadata.id
        
        # Generate embeddings if OpenAI is configured
        embedding_result = None
        if settings.openai_api_key and extracted_text and len(extracted_text.strip()) > 0:
            try:
                embedding_result = _generate_embeddings_sync(
                    text=extracted_text,
                    document_id=str(doc_metadata.id),
                    metadata={
                        "filename": job.filename,
                        "file_type": job.file_type,
                        "job_id": str(job.id),
                    }
                )
                if embedding_result:
                    doc_metadata.vector_store_id = embedding_result.get("embedding_id")
                    logger.info(f"Generated {embedding_result.get('chunk_count', 0)} embeddings for {job.filename}")
            except Exception as e:
                logger.warning(f"Embedding generation failed (non-fatal): {e}")
                # Continue without embeddings - extraction still succeeded
        else:
            if not settings.openai_api_key:
                logger.info("Skipping embeddings - OpenAI API key not configured")
        
        # Update document metadata status
        doc_metadata.ingestion_status = "completed"
        doc_metadata.compliance_status = "pending"  # Queue for compliance checks
        session.add(doc_metadata)
        
        # Update job status to completed
        job.status = IngestJobStatus.COMPLETED
        job.progress_percentage = 100
        job.extracted_metadata = extracted_metadata
        session.add(job)
        
        session.commit()
        
        # Trigger compliance checks asynchronously
        try:
            from app.workers.compliance_worker import run_compliance_checks
            run_compliance_checks.delay(str(doc_metadata.id))
            logger.info(f"Queued compliance checks for document {doc_metadata.id}")
        except Exception as e:
            logger.warning(f"Failed to queue compliance checks (non-fatal): {e}")
        
        # Trigger agent processing for entity extraction & knowledge graph
        try:
            from app.workers.agent_processor import process_with_agents
            process_with_agents.delay(str(doc_metadata.id), "standard")
            logger.info(f"Queued agent processing for document {doc_metadata.id}")
        except Exception as e:
            logger.warning(f"Failed to queue agent processing (non-fatal): {e}")
        
        result = {
            "job_id": str(job.id),
            "filename": job.filename,
            "status": "completed",
            "extracted_chars": len(extracted_text) if extracted_text else 0,
            "metadata": extracted_metadata,
        }
        
        if embedding_result:
            result["embeddings"] = embedding_result
        
        return result


def _generate_embeddings_sync(
    text: str,
    document_id: str,
    metadata: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Generate embeddings for text content.
    
    Uses OpenAI embeddings via TenantAwareEmbeddingClient.
    Chunks text if needed and stores all embeddings.
    
    Args:
        text: Text to embed
        document_id: ID of the document metadata
        metadata: Additional metadata to store with embeddings
        
    Returns:
        Dict with embedding results or None if failed
    """
    import asyncio
    from app.lib.embeddings import TenantAwareEmbeddingClient
    
    try:
        # Chunk text if too long (embeddings work best with ~500-1000 chars)
        max_chunk_size = 1000
        chunks = []
        
        if len(text) <= max_chunk_size:
            chunks = [text]
        else:
            # Simple chunking by paragraphs or sentences
            paragraphs = text.split('\n\n')
            current_chunk = ""
            
            for para in paragraphs:
                if len(current_chunk) + len(para) <= max_chunk_size:
                    current_chunk += para + "\n\n"
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = para + "\n\n"
            
            if current_chunk:
                chunks.append(current_chunk.strip())
        
        client = TenantAwareEmbeddingClient()
        embeddings = []
        
        # Generate embeddings for each chunk
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                    
                embedding, error = loop.run_until_complete(
                    client.generate_embedding(chunk, metadata=metadata)
                )
                
                if embedding:
                    embeddings.append({
                        "chunk_index": i,
                        "chunk_size": len(chunk),
                        "embedding_dims": len(embedding),
                        "content_preview": chunk[:100] + "..." if len(chunk) > 100 else chunk,
                    })
                    
                    # Store embedding in database
                    _store_embedding_sync(
                        document_id=document_id,
                        chunk_index=i,
                        embedding=embedding,
                        content=chunk,
                        metadata=metadata,
                    )
                elif error:
                    logger.warning(f"Failed to embed chunk {i}: {error}")
        finally:
            loop.close()
        
        return {
            "embedding_id": document_id,
            "chunk_count": len(embeddings),
            "total_chars": len(text),
            "chunks": embeddings,
        }
        
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None


def _store_embedding_sync(
    document_id: str,
    chunk_index: int,
    embedding: List[float],
    content: str,
    metadata: Dict[str, Any],
):
    """Store a single embedding in the database."""
    try:
        from app.models.document_embedding import DocumentEmbedding
        
        with get_sync_db() as session:
            doc_embedding = DocumentEmbedding(
                document_id=UUID(document_id),
                chunk_index=chunk_index,
                embedding=embedding,
                content_preview=content[:500] if content else None,
                embedding_metadata=metadata,
            )
            session.add(doc_embedding)
            session.commit()
            logger.debug(f"Stored embedding for document {document_id} chunk {chunk_index}")
    except Exception as e:
        logger.error(f"Failed to store embedding: {e}")
        # Don't raise - we don't want to fail the whole job for embedding storage issues


def _get_file_from_storage(storage_path: str) -> Optional[bytes]:
    """Get file content from storage."""
    try:
        # Try local storage first
        from app.services.local_storage_service import LocalStorageService
        local_storage = LocalStorageService()
        return local_storage.get_file(storage_path)
    except FileNotFoundError:
        logger.warning(f"File not found in local storage: {storage_path}")
        return None
    except Exception as e:
        logger.error(f"Error reading file from storage: {e}")
        return None


def _update_job_status_sync(job_id: str, status: IngestJobStatus, error_message: str = None):
    """Update job status synchronously."""
    try:
        with get_sync_db() as session:
            job_uuid = UUID(job_id)
            result = session.execute(
                select(IngestJob).where(IngestJob.id == job_uuid)
            )
            job = result.scalar_one_or_none()
            
            if job:
                job.status = status
                if error_message:
                    job.error_message = error_message
                session.add(job)
                session.commit()
                logger.info(f"Job {job_id} status updated to {status}")
    except Exception as e:
        logger.error(f"Error updating job status: {e}")


@celery_app.task(bind=True)
def process_pending_jobs(self):
    """
    Periodic task to find and process pending ingest jobs.
    
    This task:
    1. Finds all jobs with 'pending' status
    2. Queues them for processing
    3. Reports status
    """
    try:
        logger.info("Checking for pending ingest jobs...")
        result = _process_pending_jobs_sync()
        logger.info(f"Pending jobs processing completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Error processing pending jobs: {e}")
        raise


def _process_pending_jobs_sync() -> Dict[str, Any]:
    """Find and process pending jobs."""
    with get_sync_db() as session:
        # Get pending jobs (limit to 10 at a time to avoid overload)
        result = session.execute(
            select(IngestJob).where(
                IngestJob.status == IngestJobStatus.PENDING
            ).limit(10)
        )
        pending_jobs = result.scalars().all()
        
        logger.info(f"Found {len(pending_jobs)} pending jobs")
        
        queued_count = 0
        for job in pending_jobs:
            try:
                # Queue each job for processing
                process_ingest_job.delay(str(job.id))
                queued_count += 1
                logger.info(f"Queued job for processing: {job.filename}")
            except Exception as e:
                logger.error(f"Error queuing job {job.id}: {e}")
        
        return {
            "status": "completed",
            "pending_found": len(pending_jobs),
            "queued_for_processing": queued_count,
        }
