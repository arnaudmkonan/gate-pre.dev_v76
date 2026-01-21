"""File type to agent mapping model."""

from sqlalchemy import Column, String, Boolean, Integer, Index
from sqlalchemy.dialects.postgresql import JSON

from app.models.base import BaseModel


class FileTypeMapping(BaseModel):
    """Model for mapping file types to processing agents."""

    __tablename__ = "file_type_mappings"

    file_type = Column(String(50), nullable=False, unique=True, index=True)
    agent_name = Column(String(255), nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    config = Column(JSON, nullable=True)  # Additional configuration for the agent

    __table_args__ = (
        Index("idx_file_type_mapping_file_type", "file_type"),
        Index("idx_file_type_mapping_is_default", "is_default"),
        Index("idx_file_type_mapping_agent_name", "agent_name"),
    )
