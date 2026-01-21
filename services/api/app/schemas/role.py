from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator


# Permission constants
class Permissions:
    """Permission constants."""

    MANAGE_ORG = "manage_organization"
    MANAGE_ROLES = "manage_roles"
    MANAGE_USERS = "manage_users"
    MANAGE_MAPPINGS = "manage_mappings"
    MANAGE_RETRY = "manage_retry"
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_AUDIT = "view_audit"
    MANAGE_AGENTS = "manage_agents"
    VIEW_FILES = "view_files"
    MANAGE_FILES = "manage_files"

    VALID_PERMISSIONS = {
        MANAGE_ORG,
        MANAGE_ROLES,
        MANAGE_USERS,
        MANAGE_MAPPINGS,
        MANAGE_RETRY,
        VIEW_DASHBOARD,
        VIEW_AUDIT,
        MANAGE_AGENTS,
        VIEW_FILES,
        MANAGE_FILES,
    }


class RoleCreate(BaseModel):
    """Schema for creating a role."""

    name: str = Field(..., min_length=1, max_length=255, description="Role name")
    description: Optional[str] = Field(None, max_length=1000, description="Role description")
    permissions: List[str] = Field(default_factory=list, description="List of permission strings")
    organization_id: UUID = Field(..., description="Organization ID")

    @validator("name")
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Role name cannot be empty")
        return v.strip()

    @validator("permissions")
    def validate_permissions(cls, v):
        for perm in v:
            if perm not in Permissions.VALID_PERMISSIONS:
                raise ValueError(f"Invalid permission: {perm}")
        return v


class RoleUpdate(BaseModel):
    """Schema for updating a role."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    permissions: Optional[List[str]] = None

    @validator("permissions")
    def validate_permissions(cls, v):
        if v is not None:
            for perm in v:
                if perm not in Permissions.VALID_PERMISSIONS:
                    raise ValueError(f"Invalid permission: {perm}")
        return v


class RoleResponse(BaseModel):
    """Schema for role response."""

    id: UUID
    name: str
    description: Optional[str]
    organization_id: UUID
    permissions: List[str]
    is_system: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    """Schema for listing roles."""

    roles: List[RoleResponse]
    total: int
    page: int
    page_size: int


class UserRoleCreate(BaseModel):
    """Schema for assigning a role to a user."""

    user_id: str = Field(..., description="Supabase auth user ID")
    role_id: UUID = Field(..., description="Role ID")
    organization_id: UUID = Field(..., description="Organization ID")


class UserRoleResponse(BaseModel):
    """Schema for user role response."""

    id: UUID
    user_id: str
    role_id: UUID
    organization_id: UUID
    created_at: str

    class Config:
        from_attributes = True
