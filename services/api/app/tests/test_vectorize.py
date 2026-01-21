"""Integration tests for vectorization."""

import pytest
from uuid import uuid4

from app.lib.embeddings import TenantAwareEmbeddingClient


@pytest.mark.asyncio
async def test_embedding_client_initialization():
    """Test initializing embedding client."""
    client = TenantAwareEmbeddingClient(tenant_id="test_tenant")

    assert client.tenant_id == "test_tenant"
    assert client.config.model == "text-embedding-3-small"
    assert client.config.max_retries == 3


@pytest.mark.asyncio
async def test_generate_mock_embedding():
    """Test generating mock embedding when OpenAI unavailable."""
    client = TenantAwareEmbeddingClient()

    # Force use of mock embedding
    client.embeddings = None

    embedding, error = await client.generate_embedding("test content")

    assert embedding is not None
    assert error is None
    assert len(embedding) == 1536  # Default embedding dimension


@pytest.mark.asyncio
async def test_embedding_empty_text():
    """Test that empty text returns error."""
    client = TenantAwareEmbeddingClient()

    embedding, error = await client.generate_embedding("")

    assert embedding is None
    assert error is not None
    assert "empty" in error.lower()


@pytest.mark.asyncio
async def test_embedding_batch():
    """Test generating embeddings for multiple texts."""
    client = TenantAwareEmbeddingClient()
    client.embeddings = None  # Use mock

    texts = ["text 1", "text 2", "text 3"]
    embeddings, error = await client.generate_embeddings_batch(texts)

    assert len(embeddings) == 3
    assert error is None
    for embedding in embeddings:
        assert len(embedding) == 1536


@pytest.mark.asyncio
async def test_embedding_batch_empty():
    """Test batch with empty list."""
    client = TenantAwareEmbeddingClient()

    embeddings, error = await client.generate_embeddings_batch([])

    assert embeddings == []
    assert error is None


def test_is_retriable_error():
    """Test error classification."""
    client = TenantAwareEmbeddingClient()

    # Retriable errors
    assert client._is_retriable_error("Rate limit exceeded")
    assert client._is_retriable_error("Connection timeout")
    assert client._is_retriable_error("Error 429: Too Many Requests")
    assert client._is_retriable_error("503 Service Unavailable")

    # Non-retriable errors
    assert not client._is_retriable_error("Invalid API key")
    assert not client._is_retriable_error("Bad request: invalid format")
    assert not client._is_retriable_error("Record not found")


def test_mock_embedding_deterministic():
    """Test that mock embedding is deterministic for same input."""
    client = TenantAwareEmbeddingClient()

    text = "consistent test"
    embedding1 = client._mock_embedding(text)
    embedding2 = client._mock_embedding(text)

    assert embedding1 == embedding2
    assert len(embedding1) == 1536


def test_mock_embedding_different():
    """Test that different texts produce different embeddings."""
    client = TenantAwareEmbeddingClient()

    text1 = "first text"
    text2 = "second text"

    embedding1 = client._mock_embedding(text1)
    embedding2 = client._mock_embedding(text2)

    # Embeddings should be different
    assert embedding1 != embedding2
    # But same length
    assert len(embedding1) == len(embedding2)


def test_embedding_initialization_default_tenant():
    """Test client initializes with default tenant."""
    client = TenantAwareEmbeddingClient()

    assert client.tenant_id == "default"


def test_embedding_config():
    """Test embedding configuration."""
    from app.lib.embeddings import EmbeddingConfig

    config = EmbeddingConfig(
        model="text-embedding-3-large",
        max_retries=5,
        retry_delay=2,
    )

    assert config.model == "text-embedding-3-large"
    assert config.max_retries == 5
    assert config.retry_delay == 2
