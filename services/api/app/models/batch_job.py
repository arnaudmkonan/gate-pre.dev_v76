"""
Batch Job Model.

Tracks batch uploads and bulk processing operations.
"""

from sqlalchemy import Column, Index, String, Integer, Float, DateTime, JSON, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.models.base import BaseModel


class BatchJob(BaseModel):
    """
    Tracks batch upload and processing jobs.

    A batch job can contain multiple documents uploaded together
    (e.g., from a ZIP file or multi-file upload).
    """

    __tablename__ = "batch_jobs"

    # Job identification
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    job_type = Column(String(50), nullable=False, default="upload")  # upload, reprocess, export

    # Source tracking
    source_filename = Column(String(500), nullable=True)  # Original ZIP/archive name
    source_type = Column(String(50), nullable=False, default="zip")  # zip, multi_file, folder, api
    customer_id = Column(String(255), nullable=True, index=True)

    # Status tracking
    status = Column(String(50), nullable=False, default="pending")
    # pending, extracting, processing, reviewing, completed, failed, cancelled

    # Document counts
    total_documents = Column(Integer, nullable=False, default=0)
    processed_documents = Column(Integer, nullable=False, default=0)
    successful_documents = Column(Integer, nullable=False, default=0)
    failed_documents = Column(Integer, nullable=False, default=0)

    # Review tracking
    pending_review = Column(Integer, nullable=False, default=0)
    approved_documents = Column(Integer, nullable=False, default=0)
    rejected_documents = Column(Integer, nullable=False, default=0)

    # Processing details
    document_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)  # All document IDs in batch
    failed_files = Column(JSON, nullable=True)  # [{filename, error}]
    processing_errors = Column(JSON, nullable=True)  # [{document_id, error}]

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_time_seconds = Column(Float, nullable=True)

    # Settings used for this batch
    pipeline_type = Column(String(50), nullable=False, default="standard")
    template_id = Column(UUID(as_uuid=True), nullable=True)  # Force specific template
    auto_approve_threshold = Column(Float, nullable=True)  # Auto-approve above this confidence

    # Export tracking
    export_status = Column(String(50), nullable=True)  # pending, exported, failed
    export_path = Column(String(500), nullable=True)
    exported_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_batch_job_status", "status"),
        Index("idx_batch_job_customer", "customer_id"),
        Index("idx_batch_job_type", "job_type"),
        Index("idx_batch_job_created", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "job_type": self.job_type,
            "source_filename": self.source_filename,
            "source_type": self.source_type,
            "customer_id": self.customer_id,
            "status": self.status,
            "total_documents": self.total_documents,
            "processed_documents": self.processed_documents,
            "successful_documents": self.successful_documents,
            "failed_documents": self.failed_documents,
            "pending_review": self.pending_review,
            "approved_documents": self.approved_documents,
            "rejected_documents": self.rejected_documents,
            "progress_percent": round(
                (self.processed_documents / self.total_documents * 100)
                if self.total_documents > 0 else 0, 1
            ),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "processing_time_seconds": self.processing_time_seconds,
            "export_status": self.export_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def is_complete(self) -> bool:
        """Check if all documents have been processed."""
        return self.processed_documents >= self.total_documents

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.processed_documents == 0:
            return 0.0
        return self.successful_documents / self.processed_documents


class BulkReviewSession(BaseModel):
    """
    Tracks bulk review sessions where multiple documents are reviewed together.
    """

    __tablename__ = "bulk_review_sessions"

    # Session identification
    name = Column(String(255), nullable=True)
    reviewer = Column(String(255), nullable=False)

    # Scope
    batch_job_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Review specific batch
    document_type = Column(String(100), nullable=True)  # Review specific doc type
    template_id = Column(UUID(as_uuid=True), nullable=True)  # Review specific template

    # Review items
    review_item_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)

    # Progress
    status = Column(String(50), nullable=False, default="in_progress")  # in_progress, completed, abandoned
    total_items = Column(Integer, nullable=False, default=0)
    reviewed_items = Column(Integer, nullable=False, default=0)
    approved_items = Column(Integer, nullable=False, default=0)
    rejected_items = Column(Integer, nullable=False, default=0)
    corrected_items = Column(Integer, nullable=False, default=0)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Bulk corrections applied
    bulk_corrections = Column(JSON, nullable=True)  # [{field_name, old_pattern, new_value, applied_count}]

    __table_args__ = (
        Index("idx_bulk_review_status", "status"),
        Index("idx_bulk_review_reviewer", "reviewer"),
        Index("idx_bulk_review_batch", "batch_job_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "reviewer": self.reviewer,
            "batch_job_id": str(self.batch_job_id) if self.batch_job_id else None,
            "document_type": self.document_type,
            "status": self.status,
            "total_items": self.total_items,
            "reviewed_items": self.reviewed_items,
            "approved_items": self.approved_items,
            "rejected_items": self.rejected_items,
            "corrected_items": self.corrected_items,
            "progress_percent": round(
                (self.reviewed_items / self.total_items * 100)
                if self.total_items > 0 else 0, 1
            ),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
