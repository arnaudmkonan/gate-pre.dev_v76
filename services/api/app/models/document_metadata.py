from sqlalchemy import Column, Index, Integer, String, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class DocumentMetadata(BaseModel):
    """Document metadata model for extracted document information."""

    __tablename__ = "document_metadata"

    job_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    size = Column(Integer, nullable=False)  # in bytes
    uploader = Column(String(255), nullable=True)
    ingestion_status = Column(String(50), nullable=False)  # pending, extracting, completed, failed
    extracted_text_snippet = Column(Text, nullable=True)  # first 1000 chars of extracted text
    detected_language = Column(String(10), nullable=True)  # ISO 639-1 code
    vector_store_id = Column(String(255), nullable=True)  # ID in vector store
    raw_storage_path = Column(String(500), nullable=True)  # path in raw storage
    extraction_timestamp = Column(DateTime(timezone=True), nullable=True)
    extractor_agent_version = Column(String(50), nullable=True)

    # Additional metadata fields
    page_count = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    title = Column(String(500), nullable=True)
    author = Column(String(255), nullable=True)
    subject = Column(String(500), nullable=True)
    keywords = Column(JSON, nullable=True)  # Array of keywords
    customer_id = Column(String(255), nullable=True, index=True)
    source = Column(String(255), nullable=True)
    tags = Column(JSON, nullable=True)  # Array of tags

    # Compliance check tracking
    compliance_status = Column(String(20), default="pending", nullable=True)  # pending, processing, completed, failed
    compliance_results = Column(JSON, nullable=True)  # HTS, OFAC, NAICS results
    compliance_checked_at = Column(DateTime(timezone=True), nullable=True)

    # Agent processing tracking (entity extraction, classification, etc.)
    agent_status = Column(String(20), default="pending", nullable=True)  # pending, processing, completed, failed
    agent_results = Column(JSON, nullable=True)  # classification, entities, summary, quality
    agent_processed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_document_metadata_job_id", "job_id"),
        Index("idx_document_metadata_vector_store_id", "vector_store_id"),
        Index("idx_document_metadata_ingestion_status", "ingestion_status"),
        Index("idx_document_metadata_customer_id", "customer_id"),
        Index("idx_document_metadata_file_type", "file_type"),
        Index("idx_document_metadata_created_at", "created_at"),
        Index("idx_document_metadata_customer_status", "customer_id", "ingestion_status"),
        Index("idx_document_metadata_compliance_status", "compliance_status"),
        Index("idx_document_metadata_agent_status", "agent_status"),
    )
