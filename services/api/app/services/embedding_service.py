"""Service for generating and managing embeddings."""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

try:
    from langchain_openai import OpenAIEmbeddings
except ImportError:
    from langchain.embeddings.openai import OpenAIEmbeddings

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings using OpenAI API."""

    def __init__(self):
        """Initialize embedding service."""
        self.embeddings_model = OpenAIEmbeddings(
            openai_api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
        )

        # Text splitter for chunking large documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )

    async def generate_embeddings(
        self,
        text: str,
        silver_record_id: UUID,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate embeddings for text content.

        Args:
            text: Text to embed
            silver_record_id: ID of the silver record
            metadata: Optional metadata to associate with embeddings

        Returns:
            List of embedding objects with metadata
        """
        if not text or len(text.strip()) == 0:
            logger.warning(f"Empty text for silver record {silver_record_id}")
            return []

        try:
            # Split text into chunks
            chunks = self.text_splitter.split_text(text)

            embeddings = []

            for chunk_idx, chunk in enumerate(chunks):
                # Generate embedding for chunk
                embedding_vector = await self._embed_text(chunk)

                embeddings.append({
                    "silver_record_id": str(silver_record_id),
                    "section_index": chunk_idx,
                    "content_preview": chunk[:500],  # Store preview
                    "embedding": embedding_vector,
                    "metadata": {
                        **(metadata or {}),
                        "chunk_index": chunk_idx,
                        "chunk_length": len(chunk),
                    },
                })

            logger.info(
                f"Generated {len(embeddings)} embeddings for silver record {silver_record_id}"
            )
            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []

    async def _embed_text(self, text: str) -> List[float]:
        """
        Generate embedding vector for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (list of floats)
        """
        try:
            # Use synchronous API for now (Langchain's OpenAIEmbeddings is sync)
            embedding = self.embeddings_model.embed_query(text)
            return embedding
        except Exception as e:
            logger.error(f"Error embedding text: {e}")
            raise

    async def search_similar(
        self,
        query_embedding: List[float],
        stored_embeddings: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find similar embeddings using cosine similarity.

        Args:
            query_embedding: Query embedding vector
            stored_embeddings: List of stored embeddings with vectors
            top_k: Number of top results to return

        Returns:
            List of similar embeddings with similarity scores
        """
        try:
            import numpy as np

            # Calculate cosine similarity
            query_vec = np.array(query_embedding)
            similarities = []

            for embedding in stored_embeddings:
                stored_vec = np.array(embedding.get("embedding", []))
                if len(stored_vec) == 0:
                    continue

                # Cosine similarity
                similarity = np.dot(query_vec, stored_vec) / (
                    np.linalg.norm(query_vec) * np.linalg.norm(stored_vec) + 1e-10
                )
                similarities.append({
                    **embedding,
                    "similarity_score": float(similarity),
                })

            # Sort by similarity and return top_k
            similarities.sort(key=lambda x: x["similarity_score"], reverse=True)
            return similarities[:top_k]

        except Exception as e:
            logger.error(f"Error searching similar embeddings: {e}")
            return []

    @staticmethod
    def get_embedding_dimension() -> int:
        """Get embedding dimension for the configured model."""
        # OpenAI text-embedding-3-small: 1536
        # OpenAI text-embedding-3-large: 3072
        if settings.openai_embedding_model == "text-embedding-3-small":
            return 1536
        elif settings.openai_embedding_model == "text-embedding-3-large":
            return 3072
        else:
            return 1536  # Default to small model dimension


# Singleton instance
_embedding_service = None


async def get_embedding_service() -> EmbeddingService:
    """Get or create embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
