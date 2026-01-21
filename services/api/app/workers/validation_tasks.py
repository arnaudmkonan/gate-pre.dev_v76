"""Celery tasks for validation workflows."""

import logging
from uuid import UUID

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.normalization_validation import NormalizationValidation
from app.services.validation_engine import ValidationEngine, ValidationResult
from app.services.validation_reporting import ValidationReportingService
from app.services.silver_service import SilverService
from app.schemas.silver import SilverRecordInput, SilverRecordBatch

logger = logging.getLogger(__name__)


@celery_app.task(
    name="validate_batch",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    default_retry_delay=60,
)
def validate_batch(
    self,
    batch_id: str,
    records: list,
    upsert_if_valid: bool = True,
    custom_rules: dict = None,
):
    """
    Celery task to validate a batch of records.

    Validates records against schema and rules, stores results,
    and optionally upserts valid records to silver table.

    Args:
        batch_id: UUID of batch being validated
        records: List of records to validate
        upsert_if_valid: Whether to upsert valid records to silver
        custom_rules: Optional custom validation rules

    Returns:
        Dict with validation summary and upsert results
    """
    try:
        batch_uuid = UUID(batch_id)

        # Validate each record
        results: list[ValidationResult] = []
        for record in records:
            result = ValidationEngine.validate_record(
                record,
                custom_rules=custom_rules,
            )
            results.append(result)

        # Store validation results
        async def store_and_upsert():
            async with AsyncSessionLocal() as session:
                # Store validation results
                await ValidationReportingService.store_validation_results(
                    session, batch_uuid, results
                )

                # Upsert valid records if requested
                upserted_count = 0
                if upsert_if_valid:
                    valid_results = [r for r in results if r.is_valid]
                    if valid_results:
                        # Convert ValidationResults to SilverRecordInput
                        silver_records = []
                        for idx, record in enumerate(records):
                            if results[idx].is_valid:
                                silver_records.append(
                                    SilverRecordInput(
                                        document_id=record.get("document_id"),
                                        record_id=record.get("record_id"),
                                        source_file_id=record.get("source_file_id"),
                                        file_type=record.get("file_type", "unknown"),
                                        size_bytes=record.get("size_bytes", 0),
                                        normalized_payload=record.get(
                                            "normalized_payload", {}
                                        ),
                                        title=record.get("title"),
                                        author=record.get("author"),
                                        language=record.get("language"),
                                        content=record.get("content"),
                                        extraction_date=record.get("extraction_date"),
                                        document_date=record.get("document_date"),
                                        record_metadata=record.get("record_metadata"),
                                    )
                                )

                        if silver_records:
                            batch = SilverRecordBatch(
                                batch_id=batch_uuid, records=silver_records
                            )
                            upsert_result = await SilverService.upsert_batch(
                                session, batch
                            )
                            upserted_count = upsert_result.inserted_count

                await session.commit()

                return {
                    "batch_id": batch_id,
                    "total_records": len(records),
                    "valid_count": sum(1 for r in results if r.is_valid),
                    "invalid_count": sum(1 for r in results if not r.is_valid),
                    "warning_count": sum(1 for r in results if r.warnings),
                    "upserted_count": upserted_count,
                    "status": "success",
                }

        # Run async function in event loop
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(store_and_upsert())
            logger.info(f"Validation task completed: {result}")
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Validation task failed: {e}")
        # Retry with exponential backoff
        self.retry(exc=e)


@celery_app.task(
    name="validate_and_upsert",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
)
def validate_and_upsert(
    self,
    batch_id: str,
    records: list,
    custom_rules: dict = None,
):
    """
    Combined task to validate records and immediately upsert valid ones.

    Args:
        batch_id: Batch ID
        records: Records to process
        custom_rules: Custom validation rules

    Returns:
        Combined result with validation and upsert details
    """
    return validate_batch(batch_id, records, upsert_if_valid=True, custom_rules=custom_rules)
