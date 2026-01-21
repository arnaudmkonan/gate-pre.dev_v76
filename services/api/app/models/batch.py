from sqlalchemy import Column, Index, Integer, String
from app.models.base import BaseModel


class Batch(BaseModel):
    """Batch processing job tracking."""

    __tablename__ = "batches"

    status = Column(String(50), default="pending", nullable=False)  # pending, processing, completed, failed
    processed_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    total_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("idx_batches_status", "status"),
        Index("idx_batches_created_at", "created_at"),
    )
