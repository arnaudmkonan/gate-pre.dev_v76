import pytest
import pytest_asyncio
from uuid import uuid4

from app.services.search.search_service import SearchService
from app.models import RawVector, SilverMetadata, RawFile


@pytest_asyncio.fixture
async def test_vectors(session):
    """Create test vectors and metadata."""
    from sqlalchemy import text
    from uuid import uuid4

    vectors = []

    # Create test files using raw SQL to avoid schema mismatches
    for i in range(5):
        file_id = uuid4()
        await session.execute(
            text("""
                INSERT INTO raw_files (id, filename, file_type, file_size, storage_path, mime_type, status)
                VALUES (:id, :filename, :file_type, :file_size, :storage_path, :mime_type, :status)
            """),
            {
                "id": file_id,
                "filename": f"test_{i}.pdf",
                "file_type": "pdf",
                "file_size": 1024,
                "storage_path": f"s3://bucket/test_{i}.pdf",
                "mime_type": "application/pdf",
                "status": "stored",
            }
        )

        # Create vector
        embedding = [0.1 * (i + 1)] + [0.0] * 1535  # Simple test embedding
        vector = RawVector(
            file_id=file_id,
            vector=embedding,
            doc_metadata={"source": f"file_{i}"},
            provenance={
                "processor_agent_id": "test-agent",
                "extraction_version": "1.0.0"
            }
        )
        session.add(vector)

        # Create silver metadata
        metadata = SilverMetadata(
            file_id=file_id,
            title=f"Document {i}",
            author=f"Author {i}",
            document_type=["legal", "contract", "report"][i % 3],
            metadata_json={"custom": f"value_{i}"},
        )
        session.add(metadata)

        vectors.append((file_id, vector, metadata))

    await session.commit()
    return vectors


@pytest.mark.asyncio
async def test_search_with_text_query(session, test_vectors):
    """Test search with text query."""
    service = SearchService(session)

    results = await service.search(
        query="contract",
        limit=10,
    )

    assert results["results"] is not None
    assert results["total_count"] >= 0
    assert results["processing_time_ms"] > 0


@pytest.mark.asyncio
async def test_search_with_embedding(session, test_vectors):
    """Test search with pre-computed embedding."""
    service = SearchService(session)

    # Create test embedding
    test_embedding = [0.15] + [0.0] * 1535

    results = await service.search(
        embedding=test_embedding,
        limit=10,
    )

    assert results["results"] is not None
    assert results["total_count"] >= 0


@pytest.mark.asyncio
async def test_search_with_filters(session, test_vectors):
    """Test search with metadata filters."""
    service = SearchService(session)

    filters = {
        "document_type": "legal",
    }

    results = await service.search(
        query="test",
        filters=filters,
        limit=10,
    )

    assert results["results"] is not None


@pytest.mark.asyncio
async def test_search_with_pagination(session, test_vectors):
    """Test search with pagination."""
    service = SearchService(session)

    results1 = await service.search(
        query="document",
        limit=2,
        offset=0,
    )

    results2 = await service.search(
        query="document",
        limit=2,
        offset=2,
    )

    assert len(results1["results"]) <= 2
    assert len(results2["results"]) <= 2


@pytest.mark.asyncio
async def test_search_latency(session, test_vectors):
    """Test that search completes within 300ms for top-K."""
    service = SearchService(session)

    results = await service.search(
        query="test",
        limit=10,
    )

    # Should be under 300ms
    assert results["processing_time_ms"] < 300


@pytest.mark.asyncio
async def test_search_invalid_query_and_embedding_error(session):
    """Test that providing both query and embedding raises error."""
    service = SearchService(session)

    with pytest.raises(ValueError, match="Provide either"):
        await service.search(
            query="test",
            embedding=[0.1] * 1536,
        )


@pytest.mark.asyncio
async def test_search_no_query_or_embedding_error(session):
    """Test that providing neither query nor embedding raises error."""
    service = SearchService(session)

    with pytest.raises(ValueError, match="Either query or embedding"):
        await service.search()


@pytest.mark.asyncio
async def test_search_results_include_explainability(session, test_vectors):
    """Test that results include explainability data."""
    service = SearchService(session)

    results = await service.search(
        query="test",
        limit=10,
    )

    for result in results["results"]:
        assert "explainability" in result
        assert "similarity_score" in result["explainability"]
        assert "index_shard" in result["explainability"]
        assert "retriever_version" in result["explainability"]


@pytest.mark.asyncio
async def test_search_empty_query_error(session):
    """Test that empty query raises error."""
    service = SearchService(session)

    with pytest.raises(ValueError, match="empty"):
        await service.search(query="   ")


@pytest.mark.asyncio
async def test_cosine_similarity(session):
    """Test cosine similarity calculation."""
    service = SearchService(session)

    # Test vectors
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]

    # Same vector should have similarity 1.0
    sim_same = service._cosine_similarity(v1, v2)
    assert abs(sim_same - 1.0) < 0.001

    # Orthogonal vectors should have similarity 0.0
    sim_ortho = service._cosine_similarity(v1, v3)
    assert abs(sim_ortho - 0.0) < 0.001


@pytest.mark.asyncio
async def test_invalid_embedding_dimension(session):
    """Test that invalid embedding dimension raises error."""
    service = SearchService(session)

    with pytest.raises(ValueError, match="dimension mismatch"):
        await service.search(
            embedding=[0.1, 0.2, 0.3]  # Wrong dimension
        )


@pytest.mark.asyncio
async def test_invalid_embedding_type(session):
    """Test that invalid embedding type raises error."""
    service = SearchService(session)

    with pytest.raises(ValueError, match="must be a list"):
        await service.search(
            embedding="not a list"
        )
