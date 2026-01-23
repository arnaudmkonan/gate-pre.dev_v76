"""
Feedback Metrics Model.

Tracks extraction accuracy and correction patterns to enable
continuous learning and improvement of extraction templates.
"""

from sqlalchemy import Column, Index, String, Integer, Float, DateTime, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class TemplateFieldMetrics(BaseModel):
    """
    Tracks extraction accuracy metrics per template field.

    Used to identify which fields need improvement and to
    calibrate confidence thresholds based on actual performance.
    """

    __tablename__ = "template_field_metrics"

    # Template and field identification
    template_id = Column(UUID(as_uuid=True), ForeignKey("extraction_templates.id"), nullable=False, index=True)
    field_name = Column(String(255), nullable=False)

    # Extraction counts
    total_extractions = Column(Integer, nullable=False, default=0)
    correct_extractions = Column(Integer, nullable=False, default=0)  # Approved without correction
    corrected_extractions = Column(Integer, nullable=False, default=0)  # Required human correction
    missed_extractions = Column(Integer, nullable=False, default=0)  # Field not found but should have been

    # Accuracy metrics (calculated)
    accuracy_rate = Column(Float, nullable=True)  # correct / total
    correction_rate = Column(Float, nullable=True)  # corrected / total

    # Confidence calibration
    avg_model_confidence = Column(Float, nullable=True)  # Average confidence score from model
    avg_actual_accuracy = Column(Float, nullable=True)  # Actual accuracy rate
    confidence_calibration = Column(Float, nullable=True)  # Difference between model confidence and actual accuracy

    # Common correction patterns
    common_corrections = Column(JSON, nullable=True)  # [{original, corrected, count}]

    # Time-based tracking
    last_updated = Column(DateTime(timezone=True), nullable=True)
    period_start = Column(DateTime(timezone=True), nullable=True)  # Start of measurement period

    __table_args__ = (
        Index("idx_field_metrics_template", "template_id"),
        Index("idx_field_metrics_field", "field_name"),
        Index("idx_field_metrics_template_field", "template_id", "field_name", unique=True),
        Index("idx_field_metrics_accuracy", "accuracy_rate"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "template_id": str(self.template_id),
            "field_name": self.field_name,
            "total_extractions": self.total_extractions,
            "correct_extractions": self.correct_extractions,
            "corrected_extractions": self.corrected_extractions,
            "missed_extractions": self.missed_extractions,
            "accuracy_rate": self.accuracy_rate,
            "correction_rate": self.correction_rate,
            "avg_model_confidence": self.avg_model_confidence,
            "avg_actual_accuracy": self.avg_actual_accuracy,
            "confidence_calibration": self.confidence_calibration,
            "common_corrections": self.common_corrections,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FewShotExample(BaseModel):
    """
    Stores few-shot examples generated from human corrections.

    These examples are used to improve future extractions by
    showing the model high-quality input/output pairs.
    """

    __tablename__ = "few_shot_examples"

    # Template association
    template_id = Column(UUID(as_uuid=True), ForeignKey("extraction_templates.id"), nullable=False, index=True)

    # Source tracking
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("document_metadata.id"), nullable=True)
    source_extraction_id = Column(UUID(as_uuid=True), ForeignKey("extraction_results.id"), nullable=True)
    source_review_id = Column(UUID(as_uuid=True), ForeignKey("review_queue.id"), nullable=True)

    # Example content
    input_text = Column(Text, nullable=False)  # Document content snippet
    expected_output = Column(JSON, nullable=False)  # Expected extraction result
    field_name = Column(String(255), nullable=True)  # Specific field this example helps with

    # Quality metrics
    quality_score = Column(Float, nullable=False, default=1.0)  # How good is this example
    times_used = Column(Integer, nullable=False, default=0)  # How many times used in prompts
    success_rate = Column(Float, nullable=True)  # Success rate when this example is used

    # Status
    is_active = Column(String(20), nullable=False, default="active")  # active, deprecated, archived
    created_by = Column(String(255), nullable=True)  # Reviewer who made the correction
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_few_shot_template", "template_id"),
        Index("idx_few_shot_field", "field_name"),
        Index("idx_few_shot_quality", "quality_score"),
        Index("idx_few_shot_active", "is_active"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "template_id": str(self.template_id),
            "source_document_id": str(self.source_document_id) if self.source_document_id else None,
            "input_text": self.input_text[:500] + "..." if len(self.input_text) > 500 else self.input_text,
            "expected_output": self.expected_output,
            "field_name": self.field_name,
            "quality_score": self.quality_score,
            "times_used": self.times_used,
            "success_rate": self.success_rate,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CorrectionLog(BaseModel):
    """
    Detailed log of every correction made during review.

    Used for pattern analysis and generating few-shot examples.
    """

    __tablename__ = "correction_logs"

    # References
    review_item_id = Column(UUID(as_uuid=True), ForeignKey("review_queue.id"), nullable=False, index=True)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey("extraction_results.id"), nullable=False, index=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("extraction_templates.id"), nullable=True, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("document_metadata.id"), nullable=False, index=True)

    # Field details
    field_name = Column(String(255), nullable=False)
    field_type = Column(String(50), nullable=True)  # string, date, money, etc.

    # Values
    original_value = Column(JSON, nullable=True)
    corrected_value = Column(JSON, nullable=False)
    original_confidence = Column(Float, nullable=True)

    # Context
    document_snippet = Column(Text, nullable=True)  # Surrounding text
    correction_type = Column(String(50), nullable=False)  # value_change, missing_value, wrong_format, etc.

    # Reviewer info
    reviewer = Column(String(255), nullable=False)
    review_notes = Column(Text, nullable=True)

    # Analysis flags
    used_for_training = Column(String(20), nullable=False, default="no")  # yes, no, pending, skipped
    pattern_identified = Column(String(255), nullable=True)  # Type of pattern this represents

    __table_args__ = (
        Index("idx_correction_log_review", "review_item_id"),
        Index("idx_correction_log_template", "template_id"),
        Index("idx_correction_log_field", "field_name"),
        Index("idx_correction_log_type", "correction_type"),
        Index("idx_correction_log_training", "used_for_training"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "review_item_id": str(self.review_item_id),
            "extraction_id": str(self.extraction_id),
            "template_id": str(self.template_id) if self.template_id else None,
            "document_id": str(self.document_id),
            "field_name": self.field_name,
            "field_type": self.field_type,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "original_confidence": self.original_confidence,
            "correction_type": self.correction_type,
            "reviewer": self.reviewer,
            "used_for_training": self.used_for_training,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
