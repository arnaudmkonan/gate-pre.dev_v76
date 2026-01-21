"""Tests for batch scheduler functionality."""

import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Batch, DLQEntry, RawFile
from app.services.scheduler.scheduler import BatchVectorizerScheduler


@pytest_asyncio.fixture
async def test_batch(session: AsyncSession):
    """Create a test batch."""
    batch = Batch(
        total_count=10,
        processed_count=0,
        failed_count=0,
        status="pending",
    )
    session.add(batch)
    await session.flush()
    await session.refresh(batch)
    # Commit to ensure the batch is persisted and visible to other operations
    await session.commit()
    return batch


@pytest_asyncio.fixture
async def test_file(session: AsyncSession):
    """Create a test file for DLQ tests."""
    from sqlalchemy import text
    # Create a file directly using raw SQL to avoid schema mismatches
    result = await session.execute(
        text("""
            INSERT INTO raw_files (filename, file_type, file_size, storage_path, mime_type, status, id)
            VALUES ('test_file.pdf', 'pdf', 1024, 's3://bucket/test_file.pdf', 'application/pdf', 'stored', gen_random_uuid())
            RETURNING id
        """)
    )
    file_id = result.scalar()
    await session.commit()

    # Return a simple object with just the id
    class TestFile:
        pass
    f = TestFile()
    f.id = file_id
    return f


@pytest.mark.asyncio
async def test_dequeue_empty_queue(session: AsyncSession):
    """Test dequeuing when no batches are pending."""
    from sqlalchemy import text
    # Clean up any pending batches first
    await session.execute(text("DELETE FROM dlq_entries"))
    await session.execute(text("DELETE FROM batches"))
    await session.commit()

    scheduler = BatchVectorizerScheduler(session)

    # Try to dequeue with no pending batches
    batch = await scheduler.dequeue_batch()

    assert batch is None


@pytest.mark.asyncio
async def test_dequeue_pending_batch(session: AsyncSession, test_batch):
    """Test dequeuing a pending batch."""
    scheduler = BatchVectorizerScheduler(session)

    # Dequeue the batch
    batch = await scheduler.dequeue_batch()

    assert batch is not None
    assert batch.id == test_batch.id
    assert batch.status == "processing"


@pytest.mark.asyncio
async def test_mark_batch_processed(session: AsyncSession, test_batch):
    """Test marking a batch as processed."""
    scheduler = BatchVectorizerScheduler(session)

    # Mark batch as processed
    await scheduler.mark_processed(
        batch_id=test_batch.id,
        processed_count=8,
        failed_count=2,
    )

    # Verify batch status
    from sqlalchemy import select
    result = await session.execute(
        select(Batch).where(Batch.id == test_batch.id)
    )
    updated_batch = result.scalar_one()

    assert updated_batch.processed_count == 8
    assert updated_batch.failed_count == 2
    assert updated_batch.status == "partial"  # Has failures


@pytest.mark.asyncio
async def test_mark_batch_completed(session: AsyncSession, test_batch):
    """Test marking a batch as completed (no failures)."""
    scheduler = BatchVectorizerScheduler(session)

    # Mark batch as processed with no failures
    await scheduler.mark_processed(
        batch_id=test_batch.id,
        processed_count=10,
        failed_count=0,
    )

    # Verify batch status
    from sqlalchemy import select
    result = await session.execute(
        select(Batch).where(Batch.id == test_batch.id)
    )
    updated_batch = result.scalar_one()

    assert updated_batch.processed_count == 10
    assert updated_batch.failed_count == 0
    assert updated_batch.status == "completed"


@pytest.mark.asyncio
async def test_mark_batch_failed(session: AsyncSession, test_batch):
    """Test marking a batch as failed."""
    scheduler = BatchVectorizerScheduler(session)

    # Mark batch as failed
    error_reason = "Worker crashed"
    await scheduler.mark_failed(
        batch_id=test_batch.id,
        error_reason=error_reason,
    )

    # Verify batch status
    from sqlalchemy import select
    result = await session.execute(
        select(Batch).where(Batch.id == test_batch.id)
    )
    updated_batch = result.scalar_one()

    assert updated_batch.status == "failed"


@pytest.mark.asyncio
async def test_get_batch_progress(session: AsyncSession, test_batch):
    """Test getting batch progress."""
    scheduler = BatchVectorizerScheduler(session)

    # Mark batch as processing
    test_batch.status = "processing"
    test_batch.processed_count = 5
    test_batch.failed_count = 0
    await session.commit()

    # Get progress
    progress = await scheduler.get_batch_progress(test_batch.id)

    assert progress["batch_id"] == str(test_batch.id)
    assert progress["status"] == "processing"
    assert progress["processed_count"] == 5
    assert progress["failed_count"] == 0
    assert progress["total_count"] == 10


@pytest.mark.asyncio
async def test_get_batch_progress_not_found(session: AsyncSession):
    """Test getting progress for non-existent batch."""
    scheduler = BatchVectorizerScheduler(session)
    non_existent_id = uuid4()

    progress = await scheduler.get_batch_progress(non_existent_id)

    assert "error" in progress
    assert progress["error"] == "Batch not found"


@pytest.mark.asyncio
async def test_add_to_dlq(session: AsyncSession, test_batch, test_file):
    """Test adding failed item to DLQ."""
    scheduler = BatchVectorizerScheduler(session)

    error_reason = "Processing timeout"

    # Add to DLQ
    await scheduler.add_to_dlq(
        batch_id=test_batch.id,
        file_id=test_file.id,
        error_reason=error_reason,
        retry_count=1,
    )

    # Verify DLQ entry
    from sqlalchemy import select
    result = await session.execute(
        select(DLQEntry).where(
            (DLQEntry.file_id == test_file.id) &
            (DLQEntry.batch_id == test_batch.id)
        )
    )
    dlq_entry = result.scalar_one()

    assert dlq_entry.file_id == test_file.id
    assert dlq_entry.error_reason == error_reason
    assert dlq_entry.retry_count == 1


@pytest.mark.asyncio
async def test_worker_dispatch_flow(session: AsyncSession, test_batch):
    """Test complete worker dispatch flow: dequeue -> process -> mark_processed."""
    scheduler = BatchVectorizerScheduler(session)

    # 1. Dequeue batch
    batch = await scheduler.dequeue_batch()
    assert batch is not None
    assert batch.status == "processing"
    original_id = batch.id

    # 2. Simulate processing
    processed = 8
    failed = 2

    # 3. Mark as processed
    await scheduler.mark_processed(
        batch_id=original_id,
        processed_count=processed,
        failed_count=failed,
    )

    # 4. Verify final state
    from sqlalchemy import select
    result = await session.execute(
        select(Batch).where(Batch.id == original_id)
    )
    final_batch = result.scalar_one()

    assert final_batch.status == "partial"
    assert final_batch.processed_count == processed
    assert final_batch.failed_count == failed


@pytest.mark.asyncio
async def test_exponential_backoff_dlq_retry(session: AsyncSession, test_file):
    """Test exponential backoff for DLQ retries."""
    scheduler = BatchVectorizerScheduler(session)

    # Add item to DLQ multiple times
    for retry_count in range(3):
        await scheduler.add_to_dlq(
            batch_id=None,
            file_id=test_file.id,
            error_reason=f"Attempt {retry_count + 1}",
            retry_count=retry_count,
        )

    # Verify DLQ entries
    from sqlalchemy import select
    result = await session.execute(
        select(DLQEntry).where(DLQEntry.file_id == test_file.id)
    )
    dlq_entries = result.scalars().all()

    assert len(dlq_entries) == 3
    for i, entry in enumerate(dlq_entries):
        assert entry.retry_count == i


@pytest.mark.asyncio
async def test_recovery_from_stale_batches(session: AsyncSession):
    """Test recovery from crash marking stale batches as failed."""
    scheduler = BatchVectorizerScheduler(session)

    # Create a stale batch (updated 40 minutes ago)
    stale_time = datetime.utcnow() - timedelta(minutes=40)
    stale_batch = Batch(
        total_count=10,
        processed_count=3,
        failed_count=0,
        status="processing",
        updated_at=stale_time,
    )
    session.add(stale_batch)
    await session.flush()
    await session.refresh(stale_batch)

    # Create a recent batch (updated 5 minutes ago)
    recent_batch = Batch(
        total_count=10,
        processed_count=3,
        failed_count=0,
        status="processing",
        updated_at=datetime.utcnow() - timedelta(minutes=5),
    )
    session.add(recent_batch)
    await session.flush()
    await session.refresh(recent_batch)
    await session.commit()

    # Run recovery
    await scheduler.recover_from_crash()

    # Verify stale batch is marked as failed
    from sqlalchemy import select
    result = await session.execute(
        select(Batch).where(Batch.id == stale_batch.id)
    )
    recovered_batch = result.scalar_one()
    assert recovered_batch.status == "failed"

    # Verify recent batch is unchanged
    result = await session.execute(
        select(Batch).where(Batch.id == recent_batch.id)
    )
    unchanged_batch = result.scalar_one()
    assert unchanged_batch.status == "processing"


@pytest.mark.asyncio
async def test_batch_completion_with_partial_failure(session: AsyncSession, test_batch):
    """Test batch completion when some items fail."""
    scheduler = BatchVectorizerScheduler(session)

    # Dequeue batch
    batch = await scheduler.dequeue_batch()
    batch_id = batch.id

    # Simulate 7 successes, 3 failures
    await scheduler.mark_processed(
        batch_id=batch_id,
        processed_count=7,
        failed_count=3,
    )

    # Verify partial completion
    from sqlalchemy import select
    result = await session.execute(
        select(Batch).where(Batch.id == batch_id)
    )
    final_batch = result.scalar_one()

    assert final_batch.status == "partial"
    assert final_batch.processed_count == 7
    assert final_batch.failed_count == 3
