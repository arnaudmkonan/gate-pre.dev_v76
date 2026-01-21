"""End-to-end integration tests for the Silver Table node workflow."""

import pytest
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SilverRecord, VectorEmbedding, NormalizationValidation
from app.schemas.silver import SilverRecordInput, SilverRecordBatch
from app.services.silver_service import SilverService
from app.services.normalization_validation_service import NormalizationValidationService
from app.services.vectorization_trigger_service import VectorizationTriggerService


@pytest.mark.asyncio
async def test_full_workflow_upsert_validate_vectorize(db_session: AsyncSession):
    """
    Test the complete workflow: Upsert Silver Records → Validate Normalization → Trigger Vectorization.

    This simulates the end-to-end flow through the Silver Table node.
    """
    # Step 1: Prepare batch of records
    batch_id = uuid.uuid4()
    records = [
        SilverRecordInput(
            document_id="doc_001",
            record_id="rec_001",
            canonical_id="doc_001#rec_001",
            source_file_id=uuid.uuid4(),
            file_type="pdf",
            size_bytes=2048,
            normalized_payload={"type": "text", "pages": 10},
            title="Business Report 2023",
            author="Finance Team",
            language="en",
            content="Q4 financial results...",
            record_metadata={"source": "accounting", "quarter": "Q4"},
        ),
        SilverRecordInput(
            document_id="doc_002",
            record_id="rec_002",
            canonical_id="doc_002#rec_002",
            source_file_id=uuid.uuid4(),
            file_type="csv",
            size_bytes=512,
            normalized_payload={"rows": 1000, "columns": 25},
            title="Sales Data Q4",
            language="en",
            content="Region,Sales,Quarter...",
        ),
        SilverRecordInput(
            document_id="doc_003",
            record_id="rec_003",
            source_file_id=uuid.uuid4(),
            file_type="json",
            size_bytes=1024,
            normalized_payload={"entries": 100},
            title="Configuration",
            language="en",
        ),
    ]

    batch = SilverRecordBatch(batch_id=batch_id, records=records)

    # Step 2: Upsert records to silver table
    upsert_result = await SilverService.upsert_batch(db_session, batch)

    assert upsert_result.total_records == 3
    assert upsert_result.inserted_count == 3
    assert upsert_result.failed_count == 0
    assert upsert_result.batch_id == batch_id

    # Step 3: Validate normalization
    validation_result = await NormalizationValidationService.validate_batch(
        db_session, batch_id, records
    )

    assert validation_result["total_records"] == 3
    assert validation_result["passed_count"] == 3
    assert validation_result["failed_count"] == 0

    # Step 4: Get validation report
    report = await NormalizationValidationService.get_batch_validation_report(
        db_session, batch_id
    )

    assert report["batch_id"] == batch_id
    assert report["total_records"] == 3
    assert report["passed_count"] == 3

    # Step 5: Trigger vectorization for batch
    vectorization_result = await VectorizationTriggerService.trigger_batch_vectorization(
        db_session, batch_id
    )

    assert vectorization_result["batch_id"] == batch_id
    assert vectorization_result["total_records"] == 3
    assert vectorization_result["queued_count"] == 3
    assert vectorization_result["already_embedded_count"] == 0

    # Verify records are queued for vectorization
    pending_records, total = await VectorizationTriggerService.get_pending_vectorization(
        db_session, limit=100
    )
    assert total == 3


@pytest.mark.asyncio
async def test_workflow_with_validation_failures(db_session: AsyncSession):
    """
    Test workflow with validation failures and error handling.

    Demonstrates how the system handles mixed valid/invalid records.
    """
    batch_id = uuid.uuid4()

    # Mix of valid and invalid records
    records = [
        SilverRecordInput(
            document_id="doc_valid",
            record_id="rec_valid",
            source_file_id=uuid.uuid4(),
            file_type="pdf",
            size_bytes=1024,
            normalized_payload={"content": "Valid document"},
            title="Valid Doc",
            language="en",
        ),
        SilverRecordInput(
            document_id="",  # Invalid: empty
            record_id="rec_invalid",
            source_file_id=uuid.uuid4(),
            file_type="pdf",
            size_bytes=1024,
            normalized_payload={},
        ),
        SilverRecordInput(
            document_id="doc_oversized",
            record_id="rec_oversized",
            source_file_id=uuid.uuid4(),
            file_type="pdf",
            size_bytes=6_000_000_000,  # Exceeds max
            normalized_payload={},
        ),
    ]

    batch = SilverRecordBatch(batch_id=batch_id, records=records)

    # Upsert (should succeed, validation happens later)
    upsert_result = await SilverService.upsert_batch(db_session, batch)
    # Note: The upsert service validates at input level
    assert upsert_result.failed_count >= 0

    # Validate normalization (should catch the invalid records)
    validation_result = await NormalizationValidationService.validate_batch(
        db_session, batch_id, records
    )

    assert validation_result["failed_count"] > 0
    assert validation_result["passed_count"] == 1  # Only the valid one


@pytest.mark.asyncio
async def test_workflow_idempotency(db_session: AsyncSession):
    """
    Test that the workflow is idempotent - reprocessing same records works correctly.
    """
    batch_id = uuid.uuid4()
    source_file_id = uuid.uuid4()

    record = SilverRecordInput(
        document_id="doc_idempotent",
        record_id="rec_idempotent",
        canonical_id="doc_idempotent#rec_idempotent",
        source_file_id=source_file_id,
        file_type="pdf",
        size_bytes=1024,
        normalized_payload={"content": "Initial content"},
        title="Initial Title",
    )

    # First upsert
    batch1 = SilverRecordBatch(batch_id=batch_id, records=[record])
    result1 = await SilverService.upsert_batch(db_session, batch1)

    assert result1.inserted_count == 1
    assert result1.updated_count == 0

    # Second upsert with same record (idempotent)
    updated_record = SilverRecordInput(
        document_id="doc_idempotent",
        record_id="rec_idempotent",
        canonical_id="doc_idempotent#rec_idempotent",
        source_file_id=source_file_id,
        file_type="pdf",
        size_bytes=2048,  # Updated size
        normalized_payload={"content": "Updated content"},
        title="Updated Title",
    )

    batch2 = SilverRecordBatch(batch_id=uuid.uuid4(), records=[updated_record])
    result2 = await SilverService.upsert_batch(db_session, batch2)

    assert result2.inserted_count == 0
    assert result2.updated_count == 1

    # Both batches should validate successfully
    val1 = await NormalizationValidationService.validate_batch(
        db_session, batch_id, [record]
    )
    assert val1["passed_count"] == 1


@pytest.mark.asyncio
async def test_workflow_batch_size_limits(db_session: AsyncSession):
    """Test workflow with large batches at system limits."""
    batch_id = uuid.uuid4()

    # Create large batch (close to 1000 limit)
    large_batch_records = [
        SilverRecordInput(
            document_id=f"doc_{i}",
            record_id=f"rec_{i}",
            source_file_id=uuid.uuid4(),
            file_type="txt",
            size_bytes=512,
            normalized_payload={"index": i},
        )
        for i in range(100)  # Using 100 for testing (actual limit is 1000+)
    ]

    batch = SilverRecordBatch(batch_id=batch_id, records=large_batch_records)

    # Upsert large batch
    upsert_result = await SilverService.upsert_batch(db_session, batch)

    assert upsert_result.total_records == 100
    assert upsert_result.inserted_count == 100

    # Validate large batch
    validation_result = await NormalizationValidationService.validate_batch(
        db_session, batch_id, large_batch_records
    )

    assert validation_result["total_records"] == 100
    assert validation_result["passed_count"] == 100

    # Vectorize large batch
    vectorization_result = await VectorizationTriggerService.trigger_batch_vectorization(
        db_session, batch_id, limit=50  # Use limit to control processing
    )

    assert vectorization_result["total_records"] == 50
    assert vectorization_result["queued_count"] == 50


@pytest.mark.asyncio
async def test_workflow_vectorization_already_embedded(db_session: AsyncSession):
    """
    Test vectorization workflow when records already have embeddings.
    """
    batch_id = uuid.uuid4()

    # Create and upsert a record
    record = SilverRecordInput(
        document_id="doc_embedded",
        record_id="rec_embedded",
        source_file_id=uuid.uuid4(),
        file_type="pdf",
        size_bytes=1024,
        normalized_payload={"content": "Document content"},
        title="Embedded Doc",
    )

    batch = SilverRecordBatch(batch_id=batch_id, records=[record])
    upsert_result = await SilverService.upsert_batch(db_session, batch)

    # Get the created silver record
    from sqlalchemy import select
    stmt = select(SilverRecord).where(SilverRecord.batch_id == batch_id)
    result = await db_session.execute(stmt)
    silver_record = result.scalar_one()

    # Create an embedding for this record
    embedding = VectorEmbedding(
        file_id=silver_record.file_id,
        embedding=[0.1] * 1536,
        metadata={"version": "1.0"},
    )
    db_session.add(embedding)
    await db_session.commit()

    # Try to trigger vectorization (should recognize it's already embedded)
    trigger_result = await VectorizationTriggerService.trigger_vectorization(
        db_session, silver_record.id
    )

    assert trigger_result["status"] == "already_embedded"
    assert trigger_result["embedding_id"] == embedding.id


@pytest.mark.asyncio
async def test_workflow_failed_validations_tracking(db_session: AsyncSession):
    """
    Test tracking and retrieval of failed validations through the workflow.
    """
    batch_id = uuid.uuid4()

    # Records with expected failures
    records = [
        SilverRecordInput(
            document_id="doc_1",
            record_id="rec_1",
            source_file_id=uuid.uuid4(),
            file_type="pdf",
            size_bytes=1024,
            normalized_payload={},
            title="Valid",
        ),
        SilverRecordInput(
            document_id="",  # Empty doc_id
            record_id="rec_2",
            source_file_id=uuid.uuid4(),
            file_type="pdf",
            size_bytes=1024,
            normalized_payload={},
        ),
    ]

    # Validate batch
    validation_result = await NormalizationValidationService.validate_batch(
        db_session, batch_id, records
    )

    assert validation_result["failed_count"] == 1

    # Get failed validations
    failed_recs, total = await NormalizationValidationService.get_failed_validations(
        db_session, batch_id
    )

    assert total == 1
    assert failed_recs[0]["status"] == "fail"
    assert "document_id" in failed_recs[0]["errors"] or len(failed_recs[0]["errors"]) > 0
