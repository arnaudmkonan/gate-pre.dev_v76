import pytest
import pytest_asyncio
import uuid
import time
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RawVector, RawFile
from app.schemas.vector_store import RawVectorCreate
from app.services.vector.raw_vector_service import RawVectorService


@pytest_asyncio.fixture
async def test_file(session: AsyncSession):
    """Create a test file for vector storage."""
    file = RawFile(
        filename="test.pdf",
        file_type="pdf",
        file_size=1024,
        storage_path="s3://bucket/test.pdf",
        mime_type="application/pdf",
        status="stored",
    )
    session.add(file)
    await session.flush()
    await session.refresh(file)
    return file


@pytest.mark.asyncio
async def test_store_vector_success(session: AsyncSession, test_file):
    """Test successful vector storage."""
    service = RawVectorService(session)

    payload = RawVectorCreate(
        file_id=test_file.id,
        vector=[0.1, 0.2, 0.3],  # Simplified for test
        metadata={
            "source_path": "s3://bucket/test.pdf",
            "mime_type": "application/pdf",
            "timestamp": "2024-01-13T12:00:00Z"
        },
        provenance={
            "processor_agent_id": "pdf-extractor-v1",
            "extraction_version": "1.0.0"
        }
    )

    result = await service.store(payload)

    assert result.file_id == test_file.id
    assert result.vector == [0.1, 0.2, 0.3]
    assert result.provenance["processor_agent_id"] == "pdf-extractor-v1"
    assert result.id is not None


@pytest.mark.asyncio
async def test_store_vector_missing_provenance(session: AsyncSession, test_file):
    """Test that missing provenance fields cause rejection."""
    service = RawVectorService(session)

    payload = RawVectorCreate(
        file_id=test_file.id,
        vector=[0.1, 0.2, 0.3],
        metadata={},
        provenance={}  # Missing required fields
    )

    with pytest.raises(ValueError, match="processor_agent_id"):
        await service.store(payload)


@pytest.mark.asyncio
async def test_store_vector_duplicate_rejection(session: AsyncSession, test_file):
    """Test that duplicate file_id is rejected with unique constraint error."""
    service = RawVectorService(session)

    payload = RawVectorCreate(
        file_id=test_file.id,
        vector=[0.1, 0.2, 0.3],
        metadata={},
        provenance={
            "processor_agent_id": "agent-v1",
            "extraction_version": "1.0.0"
        }
    )

    # First insert should succeed
    await service.store(payload)

    # Second insert should fail with unique constraint error
    with pytest.raises(ValueError, match="already exists"):
        await service.store(payload)


@pytest.mark.asyncio
async def test_get_vector_by_file_id(session: AsyncSession, test_file):
    """Test retrieval of vector by file_id."""
    service = RawVectorService(session)

    payload = RawVectorCreate(
        file_id=test_file.id,
        vector=[0.1, 0.2, 0.3],
        metadata={"source": "test"},
        provenance={
            "processor_agent_id": "agent-v1",
            "extraction_version": "1.0.0"
        }
    )

    stored = await service.store(payload)
    retrieved = await service.get_by_file_id(test_file.id)

    assert retrieved.id == stored.id
    assert retrieved.file_id == test_file.id
    assert retrieved.vector == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_get_vector_not_found(session: AsyncSession):
    """Test that getting non-existent vector raises error."""
    service = RawVectorService(session)
    non_existent_id = uuid.uuid4()

    with pytest.raises(ValueError, match="not found"):
        await service.get_by_file_id(non_existent_id)


@pytest.mark.asyncio
async def test_upsert_insert_new(session: AsyncSession, test_file):
    """Test upsert inserts new vector if not exists."""
    service = RawVectorService(session)

    payload = RawVectorCreate(
        file_id=test_file.id,
        vector=[0.1, 0.2, 0.3],
        metadata={"source": "test"},
        provenance={
            "processor_agent_id": "agent-v1",
            "extraction_version": "1.0.0"
        }
    )

    result = await service.upsert(payload)
    assert result.file_id == test_file.id


@pytest.mark.asyncio
async def test_upsert_update_existing(session: AsyncSession, test_file):
    """Test upsert updates existing vector."""
    service = RawVectorService(session)

    # Initial insert
    payload1 = RawVectorCreate(
        file_id=test_file.id,
        vector=[0.1, 0.2, 0.3],
        metadata={"source": "test1"},
        provenance={
            "processor_agent_id": "agent-v1",
            "extraction_version": "1.0.0"
        }
    )
    stored1 = await service.upsert(payload1)

    # Upsert with new vector
    payload2 = RawVectorCreate(
        file_id=test_file.id,
        vector=[0.4, 0.5, 0.6],
        metadata={"source": "test2"},
        provenance={
            "processor_agent_id": "agent-v2",
            "extraction_version": "2.0.0"
        }
    )
    stored2 = await service.upsert(payload2)

    # Should be same ID but updated data
    assert stored1.id == stored2.id
    assert stored2.vector == [0.4, 0.5, 0.6]
    assert stored2.provenance["extraction_version"] == "2.0.0"


@pytest.mark.asyncio
async def test_ensure_provenance_valid(session: AsyncSession, test_file):
    """Test provenance validation returns true for valid provenance."""
    service = RawVectorService(session)

    payload = RawVectorCreate(
        file_id=test_file.id,
        vector=[0.1, 0.2, 0.3],
        metadata={},
        provenance={
            "processor_agent_id": "agent-v1",
            "extraction_version": "1.0.0"
        }
    )

    await service.store(payload)
    is_valid = await service.ensure_provenance(test_file.id)

    assert is_valid is True


@pytest.mark.asyncio
async def test_ensure_provenance_invalid(session: AsyncSession, test_file):
    """Test provenance validation returns false for missing provenance."""
    service = RawVectorService(session)
    non_existent_id = uuid.uuid4()

    is_valid = await service.ensure_provenance(non_existent_id)

    assert is_valid is False


@pytest.mark.asyncio
async def test_retrieval_performance(session: AsyncSession):
    """Test that retrieval is within 200ms for 100 records."""
    # Create 100 test files and vectors
    test_files = []
    for i in range(100):
        file = RawFile(
            filename=f"test_{i}.pdf",
            file_type="pdf",
            file_size=1024,
            storage_path=f"s3://bucket/test_{i}.pdf",
            mime_type="application/pdf",
            status="stored",
        )
        session.add(file)
        await session.flush()  # Flush after each insert to avoid bulk insert issues
        test_files.append(file)

    await session.commit()

    service = RawVectorService(session)

    # Store vectors
    for file in test_files:
        payload = RawVectorCreate(
            file_id=file.id,
            vector=[0.1, 0.2, 0.3],
            metadata={},
            provenance={
                "processor_agent_id": "agent-v1",
                "extraction_version": "1.0.0"
            }
        )
        await service.store(payload)

    # Test retrieval performance
    start_time = time.time()
    for file in test_files:
        await service.get_by_file_id(file.id)
    end_time = time.time()

    total_ms = (end_time - start_time) * 1000
    avg_ms = total_ms / len(test_files)

    print(f"Total time: {total_ms:.2f}ms, Avg per retrieval: {avg_ms:.2f}ms")
    # Should be well under 200ms per retrieval
    assert avg_ms < 50  # Conservative threshold for test
