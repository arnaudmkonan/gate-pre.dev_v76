import logging
from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.services.entity_resolution_service import EntityResolutionService
import asyncio

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def process_entity_resolution(self, document_id: str):
    """
    Celery task to run entity resolution for a document.
    """
    try:
        logger.info(f"Starting entity resolution for document {document_id}")
        
        # Sync wrapper for async service
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _run_resolution_service(document_id)
            )
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Entity resolution failed for {document_id}: {e}")
        raise self.retry(exc=e, countdown=60)


async def _run_resolution_service(document_id: str):
    """Async execution of entity resolution."""
    from app.services.gold_layer_service import GoldLayerService
    
    with get_sync_db() as session:
        # 1. Resolve Bronze -> Silver
        resolution_result = await EntityResolutionService.resolve_document_entities(session, document_id)
        
        # 2. Populate Gold Layer
        gold_result = await GoldLayerService.create_gold_records(session, document_id)
        
        return {
            "entity_resolution": resolution_result,
            "gold_layer": gold_result
        }
