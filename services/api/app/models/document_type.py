"""Catalog of customs document types for missing-doc requests and labeling."""
from sqlalchemy import Boolean, Column, Integer, String, Text

from app.models.base import BaseModel


class DocumentType(BaseModel):
    """
    Broker-facing document type catalog.

    Powers Request Missing Document dropdowns and default importer instructions.
    """

    __tablename__ = "document_types"

    code = Column(String(100), unique=True, nullable=False, index=True)
    label = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True)
    request_instructions = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=100)
    is_active = Column(Boolean, nullable=False, default=True)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "code": self.code,
            "label": self.label,
            "category": self.category,
            "request_instructions": self.request_instructions,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
        }
