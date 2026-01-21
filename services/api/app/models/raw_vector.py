# RawVector is deprecated - use VectorEmbedding from vector_embedding module instead
# This module exists only for backward compatibility
from app.models.vector_embedding import VectorEmbedding as RawVector

__all__ = ["RawVector"]
