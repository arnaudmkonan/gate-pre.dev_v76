import logging
from app.core.celery_app import celery_app
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
        # asyncio.run() owns loop lifecycle; avoids "Future attached to a different loop"
        # / "Event loop is closed" errors under Celery prefork workers.
        return asyncio.run(_run_resolution_service(document_id))
    except Exception as e:
        logger.error(f"Entity resolution failed for {document_id}: {e}")
        raise self.retry(exc=e, countdown=60)


async def _run_resolution_service(document_id: str):
    """Async execution of entity resolution."""
    from app.core.database import AsyncSessionLocal
    from app.services.gold_layer_service import GoldLayerService
    
    async with AsyncSessionLocal() as session:
        # 1. Resolve Bronze -> Silver
        resolution_result = await EntityResolutionService.resolve_document_entities(session, document_id)
        
        # 2. Populate Gold Layer
        gold_result = await GoldLayerService.create_gold_records(session, document_id)
        
        await session.commit()
        
        return {
            "entity_resolution": resolution_result,
            "gold_layer": gold_result
        }

