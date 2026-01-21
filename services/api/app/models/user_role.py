from sqlalchemy import Column, String, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class UserRole(BaseModel):
    """User-Role association model for RBAC."""

    __tablename__ = "user_roles"

    user_id = Column(String(255), nullable=False)  # Supabase auth user ID
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        Index("idx_user_role_user_id", "user_id"),
        Index("idx_user_role_role_id", "role_id"),
        Index("idx_user_role_organization_id", "organization_id"),
        Index("idx_user_role_user_org", "user_id", "organization_id"),
        UniqueConstraint("user_id", "role_id", "organization_id", name="uq_user_role_org"),
    )
