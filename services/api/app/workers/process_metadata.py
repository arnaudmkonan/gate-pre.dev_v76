import logging
from celery import shared_task
from uuid import UUID

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_metadata(
    self,
    batch_data: list[dict],
):
    """
    Celery task to process and normalize metadata.

    Args:
        batch_data: List of raw metadata dicts to normalize

    Returns:
        Results dict with successful and failed counts
    """
    try:
        from app.core.database import SessionLocal
        from app.services.metadata.metadata_normalizer import MetadataNormalizer
        from app.models import SilverMetadata

        with SessionLocal() as session:
            successful = []
            failed = []

            for data in batch_data:
                try:
                    # Normalize metadata
                    normalized = MetadataNormalizer.transform(data)

                    # Validate field types
                    MetadataNormalizer.validate_field_types(normalized)

                    # Handle missing optional fields
                    normalized = MetadataNormalizer.handle_missing_optional_fields(normalized)

                    # Create silver metadata record
                    silver_record = SilverMetadata(
                        file_id=normalized.file_id,
                        title=normalized.title,
                        author=normalized.author,
                        date=normalized.dates[0] if normalized.dates else None,
                        document_type=normalized.document_type,
                        metadata_json=normalized.custom_metadata,
                        mapping_version=normalized.mapping_version,
                    )

                    session.add(silver_record)
                    session.commit()

                    successful.append(str(normalized.file_id))
                    logger.info(f"Processed metadata for file {normalized.file_id}")

                except ValueError as e:
                    logger.error(f"Validation failed for file {data.get('file_id')}: {e}")
                    failed.append({
                        "file_id": str(data.get("file_id", "unknown")),
                        "error": str(e),
                        "error_type": "validation"
                    })
                except Exception as e:
                    logger.error(f"Failed to process metadata for {data.get('file_id')}: {e}")
                    failed.append({
                        "file_id": str(data.get("file_id", "unknown")),
                        "error": str(e),
                        "error_type": "processing"
                    })

            logger.info(f"Batch metadata processing: {len(successful)} successful, {len(failed)} failed")

            return {
                "status": "completed",
                "successful_count": len(successful),
                "failed_count": len(failed),
                "successful_ids": successful,
                "failed_records": failed,
            }

    except Exception as e:
        logger.error(f"Batch metadata processing task failed: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
