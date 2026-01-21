from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.role import Role
from app.repositories.role_repo import RoleRepository
from app.repositories.organization_repo import OrganizationRepository
from app.schemas.role import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleListResponse,
    UserRoleCreate,
    UserRoleResponse,
    Permissions,
)
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/admin/roles", tags=["Admin - Roles"])


async def get_role_repo(session: AsyncSession = Depends(get_db)) -> RoleRepository:
    """Get role repository."""
    return RoleRepository(session)


async def get_org_repo(session: AsyncSession = Depends(get_db)) -> OrganizationRepository:
    """Get organization repository."""
    return OrganizationRepository(session)


@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    repo: RoleRepository = Depends(get_role_repo),
    org_repo: OrganizationRepository = Depends(get_org_repo),
    session: AsyncSession = Depends(get_db),
):
    """Create a new role."""
    # Verify organization exists
    org = await org_repo.get_by_id(role_data.organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check for duplicate role name in organization
    existing = await repo.get_by_name_and_org(role_data.name, role_data.organization_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{role_data.name}' already exists in this organization",
        )

    role = await repo.create(
        name=role_data.name,
        organization_id=role_data.organization_id,
        permissions=role_data.permissions,
        description=role_data.description,
    )

    # Log audit
    await AuditService.log_action(
        session=session,
        resource_type="role",
        resource_id=str(role.id),
        action="create",
        changes={
            "name": role.name,
            "organization_id": str(role.organization_id),
            "permissions": role.permissions,
        },
    )
    await session.commit()

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        organization_id=role.organization_id,
        permissions=role.permissions,
        is_system=role.is_system,
        created_at=role.created_at.isoformat(),
        updated_at=role.updated_at.isoformat(),
    )


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: UUID,
    repo: RoleRepository = Depends(get_role_repo),
):
    """Get role by ID."""
    role = await repo.get_by_id(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        organization_id=role.organization_id,
        permissions=role.permissions,
        is_system=role.is_system,
        created_at=role.created_at.isoformat(),
        updated_at=role.updated_at.isoformat(),
    )


@router.get("/", response_model=RoleListResponse)
async def list_roles(
    org_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    repo: RoleRepository = Depends(get_role_repo),
):
    """List roles with optional organization filter."""
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="org_id query parameter is required",
        )

    roles, total = await repo.list_by_org(org_id, page=page, page_size=page_size)

    return RoleListResponse(
        roles=[
            RoleResponse(
                id=role.id,
                name=role.name,
                description=role.description,
                organization_id=role.organization_id,
                permissions=role.permissions,
                is_system=role.is_system,
                created_at=role.created_at.isoformat(),
                updated_at=role.updated_at.isoformat(),
            )
            for role in roles
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    role_data: RoleUpdate,
    repo: RoleRepository = Depends(get_role_repo),
    session: AsyncSession = Depends(get_db),
):
    """Update role."""
    role = await repo.get_by_id(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    # Check for duplicate role name in organization
    if role_data.name and role_data.name != role.name:
        existing = await repo.get_by_name_and_org(role_data.name, role.organization_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role '{role_data.name}' already exists in this organization",
            )

    update_data = role_data.dict(exclude_unset=True)
    role = await repo.update(role_id, **update_data)

    # Log audit
    await AuditService.log_action(
        session=session,
        resource_type="role",
        resource_id=str(role_id),
        action="update",
        changes=update_data,
    )
    await session.commit()

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        organization_id=role.organization_id,
        permissions=role.permissions,
        is_system=role.is_system,
        created_at=role.created_at.isoformat(),
        updated_at=role.updated_at.isoformat(),
    )


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    repo: RoleRepository = Depends(get_role_repo),
    session: AsyncSession = Depends(get_db),
):
    """Delete role."""
    role = await repo.get_by_id(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    org_id = role.organization_id
    await repo.delete(role_id)

    # Log audit
    await AuditService.log_action(
        session=session,
        resource_type="role",
        resource_id=str(role_id),
        action="delete",
        changes={"organization_id": str(org_id)},
    )
    await session.commit()


@router.post("/{role_id}/permissions/{permission}", status_code=status.HTTP_200_OK)
async def add_permission_to_role(
    role_id: UUID,
    permission: str,
    repo: RoleRepository = Depends(get_role_repo),
    session: AsyncSession = Depends(get_db),
):
    """Add permission to role."""
    if permission not in Permissions.VALID_PERMISSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid permission: {permission}",
        )

    role = await repo.get_by_id(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    success = await repo.add_permission(role_id, permission)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add permission",
        )

    # Log audit
    await AuditService.log_action(
        session=session,
        resource_type="role",
        resource_id=str(role_id),
        action="add_permission",
        changes={"permission": permission},
    )
    await session.commit()

    return {"status": "success", "message": f"Permission '{permission}' added to role"}


@router.delete("/{role_id}/permissions/{permission}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_permission_from_role(
    role_id: UUID,
    permission: str,
    repo: RoleRepository = Depends(get_role_repo),
    session: AsyncSession = Depends(get_db),
):
    """Remove permission from role."""
    role = await repo.get_by_id(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    success = await repo.remove_permission(role_id, permission)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permission not found in role",
        )

    # Log audit
    await AuditService.log_action(
        session=session,
        resource_type="role",
        resource_id=str(role_id),
        action="remove_permission",
        changes={"permission": permission},
    )
    await session.commit()
