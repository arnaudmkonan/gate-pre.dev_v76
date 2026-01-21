from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.organization import Organization


class OrganizationRepository:
    """Repository for organization database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, name: str, description: Optional[str] = None) -> Organization:
        """Create a new organization."""
        org = Organization(name=name, description=description)
        self.session.add(org)
        await self.session.flush()
        return org

    async def get_by_id(self, org_id: UUID) -> Optional[Organization]:
        """Get organization by ID."""
        result = await self.session.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalars().first()

    async def get_by_name(self, name: str) -> Optional[Organization]:
        """Get organization by name."""
        result = await self.session.execute(
            select(Organization).where(Organization.name == name)
        )
        return result.scalars().first()

    async def list_all(self, page: int = 1, page_size: int = 50) -> tuple[List[Organization], int]:
        """List all organizations with pagination."""
        total_result = await self.session.execute(select(func.count(Organization.id)))
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(Organization)
            .offset(offset)
            .limit(page_size)
            .order_by(Organization.created_at.desc())
        )
        orgs = result.scalars().all()
        return orgs, total

    async def update(self, org_id: UUID, **kwargs) -> Optional[Organization]:
        """Update organization."""
        org = await self.get_by_id(org_id)
        if not org:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(org, key):
                setattr(org, key, value)

        await self.session.flush()
        return org

    async def delete(self, org_id: UUID) -> bool:
        """Delete organization (soft delete by marking inactive)."""
        org = await self.get_by_id(org_id)
        if not org:
            return False

        org.is_active = False
        await self.session.flush()
        return True

    async def hard_delete(self, org_id: UUID) -> bool:
        """Hard delete organization."""
        org = await self.get_by_id(org_id)
        if not org:
            return False

        await self.session.delete(org)
        await self.session.flush()
        return True

    async def add_user(self, org_id: UUID, user_id: str, role_id: UUID) -> bool:
        """Add user to organization (via UserRole association)."""
        from app.models.user_role import UserRole

        org = await self.get_by_id(org_id)
        if not org:
            return False

        user_role = UserRole(user_id=user_id, role_id=role_id, organization_id=org_id)
        self.session.add(user_role)
        await self.session.flush()
        return True

    async def remove_user(self, org_id: UUID, user_id: str) -> bool:
        """Remove user from organization."""
        from app.models.user_role import UserRole

        result = await self.session.execute(
            select(UserRole).where(
                UserRole.organization_id == org_id,
                UserRole.user_id == user_id,
            )
        )
        user_role = result.scalars().first()
        if not user_role:
            return False

        await self.session.delete(user_role)
        await self.session.flush()
        return True
