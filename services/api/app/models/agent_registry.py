from enum import Enum
from sqlalchemy import Column, Index, String, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.models.base import BaseModel


class AgentStatus(str, Enum):
    """Agent status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"


class AgentRegistry(BaseModel):
    """Registry of ingestion agents and their file type mappings."""

    __tablename__ = "agent_registry"

    agent_id = Column(String(255), unique=True, nullable=False)
    agent_name = Column(String(255), nullable=False)
    handler_name = Column(String(255), nullable=False)  # Handler method/function name
    status = Column(String(20), default=AgentStatus.ACTIVE, nullable=False)
    priority = Column(String(50), default="normal", nullable=False)  # low, normal, high

    # File type mappings
    file_extensions = Column(ARRAY(String), nullable=False)  # e.g., ['pdf', 'docx']
    mime_types = Column(ARRAY(String), nullable=False)  # e.g., ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']

    # Configuration metadata
    agent_metadata = Column(JSON, nullable=True)  # Agent-specific config
    supports_content_sniffer = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_agent_registry_agent_id", "agent_id"),
        Index("idx_agent_registry_status", "status"),
        Index("idx_agent_registry_file_extensions", "file_extensions"),
        Index("idx_agent_registry_mime_types", "mime_types"),
    )
