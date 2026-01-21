from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import JSON

from app.models.role import Role
from app.models.user_role import UserRole


class RoleRepository:
    """Repository for role database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        name: str,
        organization_id: UUID,
        permissions: List[str],
        description: Optional[str] = None,
    ) -> Optional[Role]:
        """Create a new role."""
        # Check for duplicate role name in organization
        existing = await self.get_by_name_and_org(name, organization_id)
        if existing:
            return None

        role = Role(
            name=name,
            organization_id=organization_id,
            permissions=permissions,
            description=description,
        )
        self.session.add(role)
        await self.session.flush()
        return role

    async def get_by_id(self, role_id: UUID) -> Optional[Role]:
        """Get role by ID."""
        result = await self.session.execute(
            select(Role).where(Role.id == role_id)
        )
        return result.scalars().first()

    async def get_by_name_and_org(self, name: str, organization_id: UUID) -> Optional[Role]:
        """Get role by name and organization."""
        result = await self.session.execute(
            select(Role).where(
                Role.name == name,
                Role.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def list_by_org(
        self,
        organization_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[Role], int]:
        """List roles by organization with pagination."""
        total_result = await self.session.execute(
            select(func.count(Role.id)).where(Role.organization_id == organization_id)
        )
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(Role)
            .where(Role.organization_id == organization_id)
            .offset(offset)
            .limit(page_size)
            .order_by(Role.created_at.desc())
        )
        roles = result.scalars().all()
        return roles, total

    async def update(self, role_id: UUID, **kwargs) -> Optional[Role]:
        """Update role."""
        role = await self.get_by_id(role_id)
        if not role:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(role, key):
                setattr(role, key, value)

        await self.session.flush()
        return role

    async def delete(self, role_id: UUID) -> bool:
        """Delete role."""
        role = await self.get_by_id(role_id)
        if not role:
            return False

        await self.session.delete(role)
        await self.session.flush()
        return True

    async def add_permission(self, role_id: UUID, permission: str) -> bool:
        """Add permission to role."""
        role = await self.get_by_id(role_id)
        if not role:
            return False

        if permission not in role.permissions:
            role.permissions.append(permission)
            await self.session.flush()

        return True

    async def remove_permission(self, role_id: UUID, permission: str) -> bool:
        """Remove permission from role."""
        role = await self.get_by_id(role_id)
        if not role:
            return False

        if permission in role.permissions:
            role.permissions.remove(permission)
            await self.session.flush()

        return True

    async def check_permission(self, role_id: UUID, permission: str) -> bool:
        """Check if role has permission."""
        role = await self.get_by_id(role_id)
        if not role:
            return False

        return permission in role.permissions

    async def get_user_role(self, user_id: str, organization_id: UUID) -> Optional[Role]:
        """Get user's role in organization."""
        result = await self.session.execute(
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                UserRole.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def get_user_permissions(self, user_id: str, organization_id: UUID) -> List[str]:
        """Get user's permissions in organization."""
        role = await self.get_user_role(user_id, organization_id)
        if not role:
            return []

        return role.permissions

    async def has_permission(self, user_id: str, organization_id: UUID, permission: str) -> bool:
        """Check if user has permission in organization."""
        permissions = await self.get_user_permissions(user_id, organization_id)
        return permission in permissions
