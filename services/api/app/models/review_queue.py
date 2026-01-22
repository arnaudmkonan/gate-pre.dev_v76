"""
Review Queue Model.

Manages the human-in-the-loop review workflow for document extractions
that need verification or correction.
"""

from sqlalchemy import Column, Index, String, Text, Float, DateTime, Integer, JSON, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class ReviewQueueItem(BaseModel):
    """
    Items in the human review queue.
    
    Documents are added to this queue when:
    - Extraction confidence is below threshold
    - Quality review agent flags issues
    - Manual escalation is requested
    """
    
    __tablename__ = "review_queue"
    
    # Reference to document
    document_id = Column(UUID(as_uuid=True), ForeignKey("document_metadata.id"), nullable=False, index=True)
    
    # Queue management
    priority = Column(Integer, nullable=False, default=0)  # Higher = more urgent
    status = Column(String(50), nullable=False, default="pending")  # pending, in_review, approved, rejected, skipped
    
    # Assignment
    assigned_to = Column(String(255), nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    
    # Review reason and context
    reason = Column(Text, nullable=False)  # Why this needs review
    reason_code = Column(String(50), nullable=True)  # low_confidence, quality_issues, flagged, etc.
    confidence_score = Column(Float, nullable=True)  # Overall confidence that triggered review
    
    # Agent results summary
    agent_results = Column(JSON, nullable=True)  # Summary of agent outputs
    issues_detected = Column(JSON, nullable=True)  # List of issues from quality agent
    
    # Review outcome
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String(255), nullable=True)
    review_notes = Column(Text, nullable=True)
    corrections_made = Column(JSON, nullable=True)  # What was corrected
    
    # Time tracking
    time_to_review_seconds = Column(Integer, nullable=True)  # How long review took
    
    __table_args__ = (
        Index("idx_review_queue_status", "status"),
        Index("idx_review_queue_priority", "priority", postgresql_using='btree', postgresql_ops={'priority': 'DESC'}),
        Index("idx_review_queue_assigned", "assigned_to"),
        Index("idx_review_queue_document", "document_id"),
        Index("idx_review_queue_pending", "status", "priority"),
    )
    
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "priority": self.priority,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "reason": self.reason,
            "reason_code": self.reason_code,
            "confidence_score": self.confidence_score,
            "issues_detected": self.issues_detected,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
            "review_notes": self.review_notes,
            "time_to_review_seconds": self.time_to_review_seconds,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    @property
    def is_pending(self) -> bool:
        return self.status == "pending"
    
    @property
    def is_assigned(self) -> bool:
        return self.assigned_to is not None


class ReviewAction(BaseModel):
    """
    Log of individual review actions for audit trail.
    """
    
    __tablename__ = "review_actions"
    
    # Reference to review item
    review_item_id = Column(UUID(as_uuid=True), ForeignKey("review_queue.id"), nullable=False, index=True)
    
    # Action details
    action = Column(String(50), nullable=False)  # assign, approve, reject, correct, skip, escalate
    actor = Column(String(255), nullable=False)  # Who performed the action
    
    # Changes made
    field_corrections = Column(JSON, nullable=True)  # {field_name: {old: X, new: Y}}
    notes = Column(Text, nullable=True)
    
    # Timestamp from BaseModel
    
    __table_args__ = (
        Index("idx_review_actions_item", "review_item_id"),
        Index("idx_review_actions_actor", "actor"),
        Index("idx_review_actions_type", "action"),
    )
    
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "review_item_id": str(self.review_item_id),
            "action": self.action,
            "actor": self.actor,
            "field_corrections": self.field_corrections,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
