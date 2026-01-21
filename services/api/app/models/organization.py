from sqlalchemy import Column, String, Text, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class Organization(BaseModel):
    """Organization model for multi-tenancy support."""

    __tablename__ = "organizations"

    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    org_metadata = Column(String(1024), nullable=True)  # JSON metadata

    __table_args__ = (
        Index("idx_organization_name", "name"),
        Index("idx_organization_is_active", "is_active"),
    )
