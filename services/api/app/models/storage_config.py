from sqlalchemy import Boolean, Column, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class StorageConfig(BaseModel):
    """Storage configuration model."""

    __tablename__ = "storage_config"

    provider = Column(String(50), nullable=False)  # 'supabase', 's3'
    endpoint = Column(String(500), nullable=False)
    bucket_name = Column(String(255), nullable=False)
    region = Column(String(100), nullable=False)
    access_key = Column(Text, nullable=False)  # Encrypted in application layer
    secret_key = Column(Text, nullable=False)  # Encrypted in application layer
    max_file_size_mb = Column(Integer, default=100, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_storage_config_is_active", "is_active"),
        Index("idx_storage_config_provider", "provider"),
    )
