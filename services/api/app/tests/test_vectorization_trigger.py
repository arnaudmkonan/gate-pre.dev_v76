"""Integration tests for vectorization trigger service."""

import pytest
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import SilverRecord, VectorEmbedding
from app.services.vectorization_trigger_service import VectorizationTriggerService


@pytest.fixture
async def silver_record(db_session: AsyncSession) -> SilverRecord:
    """Create a sample silver record for testing."""
    record = SilverRecord(
        file_id=uuid.uuid4(),
        title="Test Document",
        author="Test Author",
        language="en",
        content="This is test content",
        file_type="pdf",
        size_bytes=1024,
        processing_status="completed",
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    return record


@pytest.fixture
async def silver_batch(db_session: AsyncSession) -> tuple[uuid.UUID, list[SilverRecord]]:
    """Create a batch of silver records."""
    batch_id = uuid.uuid4()
    records = []

    for i in range(3):
        record = SilverRecord(
            file_id=uuid.uuid4(),
            batch_id=batch_id,
            title=f"Document {i}",
            language="en",
            content=f"Content {i}",
            file_type="pdf",
            size_bytes=1024 * (i + 1),
            processing_status="completed",
        )
        db_session.add(record)
        records.append(record)

    await db_session.commit()
    for record in records:
        await db_session.refresh(record)

    return batch_id, records


@pytest.mark.asyncio
async def test_trigger_vectorization_new_record(
    db_session: AsyncSession, silver_record: SilverRecord
):
    """Test triggering vectorization for a new record."""
    result = await VectorizationTriggerService.trigger_vectorization(
        db_session, silver_record.id
    )

    assert result["status"] == "queued"
    assert result["record_id"] == silver_record.id
    assert "message" in result


@pytest.mark.asyncio
async def test_trigger_vectorization_already_embedded(
    db_session: AsyncSession, silver_record: SilverRecord
):
    """Test triggering vectorization for already-vectorized record."""
    # Create embedding for this record
    embedding = VectorEmbedding(
        file_id=silver_record.file_id,
        embedding=[0.1] * 1536,
        metadata={"test": "data"},
    )
    db_session.add(embedding)
    await db_session.commit()

    result = await VectorizationTriggerService.trigger_vectorization(
        db_session, silver_record.id
    )

    assert result["status"] == "already_embedded"
    assert result["embedding_id"] == embedding.id


@pytest.mark.asyncio
async def test_trigger_vectorization_nonexistent_record(db_session: AsyncSession):
    """Test triggering vectorization for non-existent record."""
    fake_id = uuid.uuid4()
    result = await VectorizationTriggerService.trigger_vectorization(
        db_session, fake_id
    )

    assert result["status"] == "failed"
    assert "not found" in result["message"]


@pytest.mark.asyncio
async def test_trigger_batch_vectorization(
    db_session: AsyncSession, silver_batch: tuple[uuid.UUID, list[SilverRecord]]
):
    """Test triggering vectorization for a batch."""
    batch_id, records = silver_batch

    result = await VectorizationTriggerService.trigger_batch_vectorization(
        db_session, batch_id
    )

    assert result["batch_id"] == batch_id
    assert result["total_records"] == 3
    assert result["queued_count"] == 3
    assert result["already_embedded_count"] == 0
    assert result["failed_count"] == 0
    assert result["processing_time_ms"] >= 0


@pytest.mark.asyncio
async def test_trigger_batch_vectorization_with_existing(
    db_session: AsyncSession, silver_batch: tuple[uuid.UUID, list[SilverRecord]]
):
    """Test batch vectorization where some records are already vectorized."""
    batch_id, records = silver_batch

    # Add embedding for first record
    embedding = VectorEmbedding(
        file_id=records[0].file_id,
        embedding=[0.1] * 1536,
    )
    db_session.add(embedding)
    await db_session.commit()

    result = await VectorizationTriggerService.trigger_batch_vectorization(
        db_session, batch_id
    )

    assert result["total_records"] == 3
    assert result["queued_count"] == 2
    assert result["already_embedded_count"] == 1


@pytest.mark.asyncio
async def test_trigger_batch_vectorization_with_limit(
    db_session: AsyncSession, silver_batch: tuple[uuid.UUID, list[SilverRecord]]
):
    """Test batch vectorization with record limit."""
    batch_id, records = silver_batch

    result = await VectorizationTriggerService.trigger_batch_vectorization(
        db_session, batch_id, limit=2
    )

    assert result["total_records"] == 2  # Limited to 2
    assert result["queued_count"] == 2


@pytest.mark.asyncio
async def test_get_vectorization_status_embedded(
    db_session: AsyncSession, silver_record: SilverRecord
):
    """Test getting vectorization status for embedded record."""
    # Add embedding
    embedding = VectorEmbedding(
        file_id=silver_record.file_id,
        embedding=[0.1] * 1536,
        section_index=0,
    )
    db_session.add(embedding)
    await db_session.commit()

    status = await VectorizationTriggerService.get_vectorization_status(
        db_session, silver_record.id
    )

    assert status["status"] == "embedded"
    assert status["embedding_count"] == 1
    assert len(status["embeddings"]) == 1


@pytest.mark.asyncio
async def test_get_vectorization_status_pending(
    db_session: AsyncSession, silver_record: SilverRecord
):
    """Test getting vectorization status for pending record."""
    status = await VectorizationTriggerService.get_vectorization_status(
        db_session, silver_record.id
    )

    assert status["status"] == "pending"
    assert status["embedding_count"] == 0


@pytest.mark.asyncio
async def test_get_vectorization_status_not_found(db_session: AsyncSession):
    """Test getting status for non-existent record."""
    fake_id = uuid.uuid4()
    status = await VectorizationTriggerService.get_vectorization_status(
        db_session, fake_id
    )

    assert status["status"] == "not_found"


@pytest.mark.asyncio
async def test_trigger_file_vectorization(
    db_session: AsyncSession, silver_record: SilverRecord
):
    """Test triggering vectorization for a file."""
    result = await VectorizationTriggerService.trigger_file_vectorization(
        db_session, silver_record.file_id
    )

    assert result["status"] == "queued"
    assert result["file_id"] == silver_record.file_id


@pytest.mark.asyncio
async def test_get_pending_vectorization(
    db_session: AsyncSession, silver_batch: tuple[uuid.UUID, list[SilverRecord]]
):
    """Test retrieving pending vectorization records."""
    batch_id, records = silver_batch

    # Queue all records for vectorization
    await VectorizationTriggerService.trigger_batch_vectorization(
        db_session, batch_id
    )

    # Get pending records
    pending_records, total = await VectorizationTriggerService.get_pending_vectorization(
        db_session, limit=10
    )

    assert total == 3
    assert len(pending_records) == 3


@pytest.mark.asyncio
async def test_get_pending_vectorization_with_pagination(
    db_session: AsyncSession, silver_batch: tuple[uuid.UUID, list[SilverRecord]]
):
    """Test pagination of pending vectorization records."""
    batch_id, records = silver_batch

    # Queue all records
    await VectorizationTriggerService.trigger_batch_vectorization(
        db_session, batch_id
    )

    # Get first page (limit 2)
    page1, total1 = await VectorizationTriggerService.get_pending_vectorization(
        db_session, limit=2, offset=0
    )

    # Get second page
    page2, total2 = await VectorizationTriggerService.get_pending_vectorization(
        db_session, limit=2, offset=2
    )

    assert total1 == 3
    assert total2 == 3
    assert len(page1) == 2
    assert len(page2) == 1


@pytest.mark.asyncio
async def test_vectorization_status_update_on_queue(
    db_session: AsyncSession, silver_record: SilverRecord
):
    """Test that record status is updated when queued."""
    # Queue for vectorization
    await VectorizationTriggerService.trigger_vectorization(
        db_session, silver_record.id
    )

    # Verify status was updated
    stmt = select(SilverRecord).where(SilverRecord.id == silver_record.id)
    result = await db_session.execute(stmt)
    updated_record = result.scalar_one()

    assert updated_record.processing_status == "vectorization_pending"
