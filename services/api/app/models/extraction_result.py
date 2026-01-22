"""
Extraction Result Model.

Stores individual extracted fields from documents with confidence scores
and review status for the human-in-the-loop workflow.
"""

from sqlalchemy import Column, Index, String, Text, Float, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class ExtractionResult(BaseModel):
    """
    Stores individual extracted fields from documents.
    
    Each row represents a single extracted piece of data,
    such as a person name, date, or monetary amount.
    """
    
    __tablename__ = "extraction_results"
    
    # Link to parent document
    document_id = Column(UUID(as_uuid=True), ForeignKey("document_metadata.id"), nullable=False, index=True)
    
    # Extraction details
    extraction_type = Column(String(50), nullable=False)  # entity, classification, summary, etc.
    field_name = Column(String(255), nullable=False)  # person, organization, date, total_amount, etc.
    field_value = Column(JSON, nullable=False)  # The extracted value (can be string, number, object)
    raw_value = Column(Text, nullable=True)  # Original text as found in document
    normalized_value = Column(Text, nullable=True)  # Standardized/normalized form
    
    # Confidence and source
    confidence = Column(Float, nullable=False, default=0.0)
    agent_name = Column(String(100), nullable=True)  # Which agent extracted this
    context_snippet = Column(Text, nullable=True)  # Surrounding text for context
    
    # Review workflow
    status = Column(String(50), nullable=False, default="auto")  # auto, pending_review, reviewed, corrected, rejected
    reviewed_by = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    correction_value = Column(JSON, nullable=True)  # Value after human correction
    correction_notes = Column(Text, nullable=True)
    
    # Position in document (optional)
    page_number = Column(String(50), nullable=True)  # e.g., "1", "1-5", "all"
    position_info = Column(JSON, nullable=True)  # {x, y, width, height} if applicable
    
    __table_args__ = (
        Index("idx_extraction_results_document", "document_id"),
        Index("idx_extraction_results_type", "extraction_type"),
        Index("idx_extraction_results_field", "field_name"),
        Index("idx_extraction_results_status", "status"),
        Index("idx_extraction_results_confidence", "confidence"),
        Index("idx_extraction_results_doc_field", "document_id", "field_name"),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "extraction_type": self.extraction_type,
            "field_name": self.field_name,
            "field_value": self.field_value,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "confidence": self.confidence,
            "agent_name": self.agent_name,
            "status": self.status,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "correction_value": self.correction_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    @property
    def final_value(self):
        """Get the final value (corrected if available, otherwise original)."""
        if self.correction_value is not None:
            return self.correction_value
        return self.field_value
    
    @property
    def needs_review(self) -> bool:
        """Check if this extraction needs human review."""
        return self.status in ("pending_review", "auto") and self.confidence < 0.90


class FieldMappingTemplate(BaseModel):
    """
    Template for mapping extracted fields to export columns.
    
    Allows customers to define how extracted data should be
    exported to Excel/CSV with custom column names and transformations.
    """
    
    __tablename__ = "field_mapping_templates"
    
    # Template identification
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    customer_id = Column(String(255), nullable=True, index=True)  # null = global template
    document_type = Column(String(100), nullable=True)  # invoice, contract, etc.
    
    # Mapping configuration
    mappings = Column(JSON, nullable=False)
    """
    Example mappings structure:
    [
        {
            "source_field": "entities.organization",
            "target_column": "Customer Name",
            "transform": "none",
            "default_value": ""
        },
        {
            "source_field": "entities.money.total",
            "target_column": "Invoice Total",
            "transform": "currency_number",
            "default_value": "0.00"
        }
    ]
    """
    
    # Settings
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    include_confidence = Column(Boolean, default=False)  # Include confidence scores in export
    include_metadata = Column(Boolean, default=False)  # Include document metadata
    
    __table_args__ = (
        Index("idx_field_mapping_customer", "customer_id"),
        Index("idx_field_mapping_doc_type", "document_type"),
        Index("idx_field_mapping_default", "is_default"),
    )
    
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "customer_id": self.customer_id,
            "document_type": self.document_type,
            "mappings": self.mappings,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
