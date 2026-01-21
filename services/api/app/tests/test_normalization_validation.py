"""Integration tests for normalization validation service."""

import pytest
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.normalization_validation import NormalizationValidation
from app.schemas.silver import SilverRecordInput, SilverRecordBatch
from app.services.normalization_validation_service import NormalizationValidationService


@pytest.fixture
def valid_record() -> SilverRecordInput:
    """Create a valid silver record input."""
    return SilverRecordInput(
        document_id="doc_001",
        record_id="rec_001",
        canonical_id="doc_001#rec_001",
        source_file_id=uuid.uuid4(),
        file_type="pdf",
        size_bytes=1024,
        normalized_payload={"content": "Sample content", "metadata": {"key": "value"}},
        title="Sample Document",
        author="Test Author",
        language="en",
        content="This is sample content",
        record_metadata={"source": "test", "version": "1.0"},
    )


@pytest.fixture
def invalid_record() -> SilverRecordInput:
    """Create an invalid record (missing required field)."""
    return SilverRecordInput(
        document_id="",  # Invalid: empty
        record_id="rec_invalid",
        source_file_id=uuid.uuid4(),
        file_type="pdf",
        size_bytes=1024,
        normalized_payload={},
    )


@pytest.fixture
def oversized_record() -> SilverRecordInput:
    """Create a record with oversized content."""
    return SilverRecordInput(
        document_id="doc_large",
        record_id="rec_large",
        source_file_id=uuid.uuid4(),
        file_type="pdf",
        size_bytes=6_000_000_000,  # Exceeds max of 5GB
        normalized_payload={"content": "x" * 10000},
    )


@pytest.mark.asyncio
async def test_validate_valid_record(
    db_session: AsyncSession, valid_record: SilverRecordInput
):
    """Test validation of a valid record."""
    batch_id = uuid.uuid4()
    result = await NormalizationValidationService.validate_record(
        db_session, batch_id, valid_record
    )

    assert result["status"] == "pass"
    assert len(result["errors"]) == 0
    assert result["record_id"] == "rec_001"
    assert result["document_id"] == "doc_001"


@pytest.mark.asyncio
async def test_validate_invalid_record(
    db_session: AsyncSession, invalid_record: SilverRecordInput
):
    """Test validation of an invalid record."""
    batch_id = uuid.uuid4()
    result = await NormalizationValidationService.validate_record(
        db_session, batch_id, invalid_record
    )

    assert result["status"] == "fail"
    assert len(result["errors"]) > 0
    # Should have error for empty document_id
    assert any(e["field"] == "document_id" for e in result["errors"])


@pytest.mark.asyncio
async def test_validate_oversized_record(
    db_session: AsyncSession, oversized_record: SilverRecordInput
):
    """Test validation of oversized record."""
    batch_id = uuid.uuid4()
    result = await NormalizationValidationService.validate_record(
        db_session, batch_id, oversized_record
    )

    assert result["status"] == "fail"
    assert len(result["errors"]) > 0
    # Should have error for size exceeding maximum
    assert any(e["field"] == "size_bytes" for e in result["errors"])


@pytest.mark.asyncio
async def test_validate_batch_mixed(
    db_session: AsyncSession,
    valid_record: SilverRecordInput,
    invalid_record: SilverRecordInput,
):
    """Test batch validation with both valid and invalid records."""
    batch_id = uuid.uuid4()
    batch = SilverRecordBatch(batch_id=batch_id, records=[valid_record, invalid_record])

    result = await NormalizationValidationService.validate_batch(
        db_session, batch_id, batch.records
    )

    assert result["total_records"] == 2
    assert result["passed_count"] == 1
    assert result["failed_count"] == 1
    assert len(result["records"]) == 2


@pytest.mark.asyncio
async def test_validate_large_batch(db_session: AsyncSession):
    """Test validation of large batch."""
    batch_id = uuid.uuid4()
    records = [
        SilverRecordInput(
            document_id=f"doc_{i}",
            record_id=f"rec_{i}",
            source_file_id=uuid.uuid4(),
            file_type="txt",
            size_bytes=512,
            normalized_payload={"index": i},
        )
        for i in range(50)
    ]

    result = await NormalizationValidationService.validate_batch(
        db_session, batch_id, records
    )

    assert result["total_records"] == 50
    assert result["passed_count"] == 50
    assert result["failed_count"] == 0


@pytest.mark.asyncio
async def test_get_batch_validation_report(
    db_session: AsyncSession, valid_record: SilverRecordInput
):
    """Test retrieving validation report for batch."""
    batch_id = uuid.uuid4()
    batch = SilverRecordBatch(batch_id=batch_id, records=[valid_record])

    # Validate batch
    await NormalizationValidationService.validate_batch(
        db_session, batch_id, batch.records
    )

    # Get report
    report = await NormalizationValidationService.get_batch_validation_report(
        db_session, batch_id
    )

    assert report["batch_id"] == batch_id
    assert report["total_records"] == 1
    assert report["passed_count"] == 1
    assert len(report["records"]) == 1


@pytest.mark.asyncio
async def test_get_failed_validations(
    db_session: AsyncSession,
    valid_record: SilverRecordInput,
    invalid_record: SilverRecordInput,
):
    """Test retrieving failed validations."""
    batch_id = uuid.uuid4()
    batch = SilverRecordBatch(batch_id=batch_id, records=[valid_record, invalid_record])

    # Validate batch
    await NormalizationValidationService.validate_batch(
        db_session, batch_id, batch.records
    )

    # Get failed validations
    records, total = await NormalizationValidationService.get_failed_validations(
        db_session, batch_id
    )

    assert total == 1
    assert len(records) == 1
    assert records[0]["status"] == "fail"


@pytest.mark.asyncio
async def test_validation_record_persistence(
    db_session: AsyncSession, valid_record: SilverRecordInput
):
    """Test that validation records are persisted to database."""
    batch_id = uuid.uuid4()

    # Validate record
    await NormalizationValidationService.validate_record(
        db_session, batch_id, valid_record
    )

    # Verify persisted in database
    from sqlalchemy import select
    stmt = select(NormalizationValidation).where(
        NormalizationValidation.batch_id == batch_id
    )
    result = await db_session.execute(stmt)
    validation_record = result.scalar_one_or_none()

    assert validation_record is not None
    assert validation_record.batch_id == batch_id
    assert validation_record.record_id == valid_record.record_id
    assert validation_record.validation_status == "pass"
