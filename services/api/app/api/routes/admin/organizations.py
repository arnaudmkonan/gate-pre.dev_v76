from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.organization import Organization
from app.repositories.organization_repo import OrganizationRepository
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationListResponse,
)
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/admin/organizations", tags=["Admin - Organizations"])


async def get_org_repo(session: AsyncSession = Depends(get_db)) -> OrganizationRepository:
    """Get organization repository."""
    return OrganizationRepository(session)


@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_data: OrganizationCreate,
    repo: OrganizationRepository = Depends(get_org_repo),
    session: AsyncSession = Depends(get_db),
):
    """Create a new organization."""
    # Check if organization name already exists
    existing = await repo.get_by_name(org_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization with name '{org_data.name}' already exists",
        )

    org = await repo.create(name=org_data.name, description=org_data.description)

    # Log audit
    await AuditService.log_action(
        session=session,
        resource_type="organization",
        resource_id=str(org.id),
        action="create",
        changes={"name": org.name, "description": org.description},
    )
    await session.commit()

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        description=org.description,
        is_active=org.is_active,
        created_at=org.created_at.isoformat(),
        updated_at=org.updated_at.isoformat(),
    )


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID,
    repo: OrganizationRepository = Depends(get_org_repo),
):
    """Get organization by ID."""
    org = await repo.get_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        description=org.description,
        is_active=org.is_active,
        created_at=org.created_at.isoformat(),
        updated_at=org.updated_at.isoformat(),
    )


@router.get("/", response_model=OrganizationListResponse)
async def list_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    repo: OrganizationRepository = Depends(get_org_repo),
):
    """List organizations with pagination."""
    orgs, total = await repo.list_all(page=page, page_size=page_size)

    return OrganizationListResponse(
        organizations=[
            OrganizationResponse(
                id=org.id,
                name=org.name,
                description=org.description,
                is_active=org.is_active,
                created_at=org.created_at.isoformat(),
                updated_at=org.updated_at.isoformat(),
            )
            for org in orgs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: UUID,
    org_data: OrganizationUpdate,
    repo: OrganizationRepository = Depends(get_org_repo),
    session: AsyncSession = Depends(get_db),
):
    """Update organization."""
    org = await repo.get_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check if new name conflicts with existing organization
    if org_data.name and org_data.name != org.name:
        existing = await repo.get_by_name(org_data.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organization with name '{org_data.name}' already exists",
            )

    update_data = org_data.dict(exclude_unset=True)
    org = await repo.update(org_id, **update_data)

    # Log audit
    await AuditService.log_action(
        session=session,
        resource_type="organization",
        resource_id=str(org_id),
        action="update",
        changes=update_data,
    )
    await session.commit()

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        description=org.description,
        is_active=org.is_active,
        created_at=org.created_at.isoformat(),
        updated_at=org.updated_at.isoformat(),
    )


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: UUID,
    repo: OrganizationRepository = Depends(get_org_repo),
    session: AsyncSession = Depends(get_db),
):
    """Delete organization (soft delete)."""
    org = await repo.get_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    await repo.delete(org_id)

    # Log audit
    await AuditService.log_action(
        session=session,
        resource_type="organization",
        resource_id=str(org_id),
        action="delete",
        changes={"is_active": False},
    )
    await session.commit()


@router.post("/{org_id}/users", status_code=status.HTTP_201_CREATED)
async def add_user_to_organization(
    org_id: UUID,
    user_id: str,
    role_id: UUID,
    repo: OrganizationRepository = Depends(get_org_repo),
    session: AsyncSession = Depends(get_db),
):
    """Add user to organization."""
    org = await repo.get_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    success = await repo.add_user(org_id, user_id, role_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add user to organization",
        )

    # Log audit
    await AuditService.log_action(
        session=session,
        resource_type="organization",
        resource_id=str(org_id),
        action="add_user",
        changes={"user_id": user_id, "role_id": str(role_id)},
    )
    await session.commit()

    return {"status": "success", "message": f"User {user_id} added to organization {org_id}"}


@router.delete("/{org_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_organization(
    org_id: UUID,
    user_id: str,
    repo: OrganizationRepository = Depends(get_org_repo),
    session: AsyncSession = Depends(get_db),
):
    """Remove user from organization."""
    org = await repo.get_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    success = await repo.remove_user(org_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found in organization",
        )

    # Log audit
    await AuditService.log_action(
        session=session,
        resource_type="organization",
        resource_id=str(org_id),
        action="remove_user",
        changes={"user_id": user_id},
    )
    await session.commit()
