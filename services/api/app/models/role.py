from sqlalchemy import Column, String, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.models.base import BaseModel


class Role(BaseModel):
    """Role model for role-based access control."""

    __tablename__ = "roles"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    permissions = Column(JSON, nullable=False, default=dict)  # List of permission strings
    is_system = Column(String(20), default="false", nullable=False)  # "true" for system roles

    __table_args__ = (
        Index("idx_role_organization_id", "organization_id"),
        Index("idx_role_name", "name"),
        UniqueConstraint("name", "organization_id", name="uq_role_name_org_id"),
    )
