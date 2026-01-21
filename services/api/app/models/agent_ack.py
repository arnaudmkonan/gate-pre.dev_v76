from enum import Enum
from sqlalchemy import Column, Index, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class AgentAckStatus(str, Enum):
    """Agent acknowledgement status enum."""

    PENDING = "pending"  # Dispatched to agent, awaiting ACK
    ACKNOWLEDGED = "acknowledged"  # Agent acknowledged processing
    COMPLETED = "completed"  # Agent completed processing
    FAILED = "failed"  # Agent reported failure


class AgentAck(BaseModel):
    """Track agent acknowledgements for dispatched files."""

    __tablename__ = "agent_ack"

    file_id = Column(UUID(as_uuid=True), nullable=False)  # Foreign key to ingest_jobs
    agent_id = Column(String(255), ForeignKey("agent_registry.agent_id"), nullable=False)
    status = Column(String(20), default=AgentAckStatus.PENDING, nullable=False)

    # Timestamps
    dispatched_at = Column(DateTime(timezone=True), nullable=False)
    ack_timestamp = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Agent metadata and response
    agent_metadata = Column(JSON, nullable=True)  # Data from agent's ACK
    error_details = Column(JSON, nullable=True)  # If failed, capture error

    __table_args__ = (
        Index("idx_agent_ack_file_id", "file_id"),
        Index("idx_agent_ack_agent_id", "agent_id"),
        Index("idx_agent_ack_status", "status"),
        Index("idx_agent_ack_dispatched_at", "dispatched_at"),
        Index("idx_agent_ack_file_agent", "file_id", "agent_id"),
    )
