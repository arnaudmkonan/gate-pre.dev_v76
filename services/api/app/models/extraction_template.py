"""
Extraction Template Model.

Stores templates for guided field extraction from documents.
Supports both visual annotation and AI-guided field extraction.
"""

from sqlalchemy import Column, Index, String, Text, Integer, Float, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class ExtractionTemplate(BaseModel):
    """
    Template defining fields to extract from specific document types.

    Supports two modes:
    - field_list: Define fields by name and description, AI finds them
    - visual: Define bounding boxes on sample document
    """

    __tablename__ = "extraction_templates"

    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    document_type = Column(String(100), nullable=False, index=True)  # invoice, contract, form, etc.
    customer_id = Column(String(255), nullable=True, index=True)  # Multi-tenant support

    # Versioning
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)

    # Template type
    template_type = Column(String(50), nullable=False, default="field_list")  # field_list or visual

    # Sample document reference
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("document_metadata.id"), nullable=True)

    # Field definitions - JSON array of field specs
    # Structure: [{field_name, display_name, field_type, description, required, validation_regex, extraction_hints, default_value, entity_type}]
    field_definitions = Column(JSON, nullable=False, default=list)

    # For visual templates - bounding box regions
    # Structure: [{page, x, y, width, height, field_name}]
    visual_regions = Column(JSON, nullable=True)

    # For AI-guided extraction
    extraction_prompt = Column(Text, nullable=True)  # Custom system prompt override
    few_shot_examples = Column(JSON, nullable=True)  # [{input, output}] for few-shot learning

    # Template matching criteria
    matching_keywords = Column(JSON, nullable=True)  # Keywords that indicate this template applies
    classification_categories = Column(JSON, nullable=True)  # Document categories this applies to
    confidence_threshold = Column(Float, nullable=False, default=0.7)  # Min confidence to auto-apply

    # Usage statistics
    usage_count = Column(Integer, nullable=False, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    avg_confidence = Column(Float, nullable=True)  # Average extraction confidence when using this template

    __table_args__ = (
        Index("idx_template_customer", "customer_id"),
        Index("idx_template_doc_type", "document_type"),
        Index("idx_template_active", "is_active"),
        Index("idx_template_type", "template_type"),
        Index("idx_template_customer_doctype", "customer_id", "document_type"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "document_type": self.document_type,
            "customer_id": self.customer_id,
            "version": self.version,
            "is_active": self.is_active,
            "template_type": self.template_type,
            "source_document_id": str(self.source_document_id) if self.source_document_id else None,
            "field_definitions": self.field_definitions,
            "field_count": len(self.field_definitions) if self.field_definitions else 0,
            "visual_regions": self.visual_regions,
            "extraction_prompt": self.extraction_prompt,
            "few_shot_examples": self.few_shot_examples,
            "matching_keywords": self.matching_keywords,
            "classification_categories": self.classification_categories,
            "confidence_threshold": self.confidence_threshold,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "avg_confidence": self.avg_confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_field_names(self) -> list:
        """Get list of field names from field definitions."""
        if not self.field_definitions:
            return []
        return [f.get("field_name") for f in self.field_definitions if f.get("field_name")]

    def get_required_fields(self) -> list:
        """Get list of required field names."""
        if not self.field_definitions:
            return []
        return [f.get("field_name") for f in self.field_definitions if f.get("required", False)]

    def build_extraction_prompt(self) -> str:
        """Build the extraction prompt from field definitions."""
        if self.extraction_prompt:
            return self.extraction_prompt

        if not self.field_definitions:
            return ""

        field_descriptions = []
        for field in self.field_definitions:
            name = field.get("field_name", "")
            display = field.get("display_name", name)
            desc = field.get("description", "")
            field_type = field.get("field_type", "string")
            required = field.get("required", False)
            hints = field.get("extraction_hints", [])

            field_line = f"- {display} ({name}): {desc}"
            if field_type != "string":
                field_line += f" [type: {field_type}]"
            if required:
                field_line += " [REQUIRED]"
            if hints:
                field_line += f" Hints: {', '.join(hints)}"
            field_descriptions.append(field_line)

        return f"""Extract the following fields from the document:

{chr(10).join(field_descriptions)}

Return the extracted values as JSON with field names as keys.
For fields not found, use null. Include confidence scores for each field."""
