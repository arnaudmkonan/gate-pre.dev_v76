"""API routes for file type mapping management."""

from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.rbac import admin_required
from app.models.file_type_mapping import FileTypeMapping
from app.repositories.file_type_mapping_repo import FileTypeMappingRepository
from app.schemas.file_type_mapping import (
    FileTypeMappingCreate,
    FileTypeMappingUpdate,
    FileTypeMappingResponse,
    FileTypeMappingListResponse,
    FileTypeMappingTestRequest,
    FileTypeMappingTestResponse,
    FileTypeMappingExportResponse,
    FileTypeMappingImportRequest,
)
from app.services.file_type_mapping_service import FileTypeMappingService
from app.services.audit_service import AuditService

router = APIRouter(
    prefix="/api/admin/file-type-mappings",
    tags=["Admin - File Type Mappings"],
)


async def get_mapping_repo(session: AsyncSession = Depends(get_db)) -> FileTypeMappingRepository:
    """Get file type mapping repository."""
    return FileTypeMappingRepository(session)


@router.get("/", response_model=FileTypeMappingListResponse)
async def list_mappings(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """List all file type mappings."""
    mappings, total = await FileTypeMappingService.list_mappings(
        session, page=page, page_size=page_size
    )

    return FileTypeMappingListResponse(
        mappings=[
            FileTypeMappingResponse(
                id=m.id,
                file_type=m.file_type,
                agent_name=m.agent_name,
                is_default=m.is_default,
                version=m.version,
                config=m.config,
                created_at=m.created_at.isoformat(),
                updated_at=m.updated_at.isoformat(),
            )
            for m in mappings
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=FileTypeMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_mapping(
    mapping_data: FileTypeMappingCreate,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """Create a new file type mapping."""
    repo = FileTypeMappingRepository(session)

    # Check if file type already exists
    existing = await repo.get_by_file_type(mapping_data.file_type)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mapping for file type '{mapping_data.file_type}' already exists",
        )

    mapping = await repo.create(
        file_type=mapping_data.file_type,
        agent_name=mapping_data.agent_name,
        is_default=mapping_data.is_default,
        config=mapping_data.config,
    )

    # Log audit
    await AuditService.log_action(
        session=session,
        resource_type="file_type_mapping",
        resource_id=str(mapping.id),
        action="create",
        changes={
            "file_type": mapping.file_type,
            "agent_name": mapping.agent_name,
            "is_default": mapping.is_default,
        },
    )
    await session.commit()

    return FileTypeMappingResponse(
        id=mapping.id,
        file_type=mapping.file_type,
        agent_name=mapping.agent_name,
        is_default=mapping.is_default,
        version=mapping.version,
        config=mapping.config,
        created_at=mapping.created_at.isoformat(),
        updated_at=mapping.updated_at.isoformat(),
    )


@router.get("/export", response_model=FileTypeMappingExportResponse)
async def export_mappings(
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """Export all file type mappings as JSON."""
    mappings = await FileTypeMappingService.export_mappings(session)

    return FileTypeMappingExportResponse(
        mappings=[
            FileTypeMappingResponse(
                id=m.id,
                file_type=m.file_type,
                agent_name=m.agent_name,
                is_default=m.is_default,
                version=m.version,
                config=m.config,
                created_at=m.created_at.isoformat(),
                updated_at=m.updated_at.isoformat(),
            )
            for m in mappings
        ],
        export_timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/import", status_code=status.HTTP_200_OK)
async def import_mappings(
    import_request: FileTypeMappingImportRequest,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """Import file type mappings from JSON."""
    result = await FileTypeMappingService.import_mappings(
        session,
        [m.dict() for m in import_request.mappings],
        overwrite_existing=import_request.overwrite_existing,
    )

    await session.commit()

    return {
        "status": "success",
        "imported": result["imported"],
        "skipped": result["skipped"],
        "errors": result["errors"],
    }


@router.get("/{mapping_id}", response_model=FileTypeMappingResponse)
async def get_mapping(
    mapping_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """Get a file type mapping by ID."""
    repo = FileTypeMappingRepository(session)
    mapping = await repo.get_by_id(mapping_id)

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File type mapping not found",
        )

    return FileTypeMappingResponse(
        id=mapping.id,
        file_type=mapping.file_type,
        agent_name=mapping.agent_name,
        is_default=mapping.is_default,
        version=mapping.version,
        config=mapping.config,
        created_at=mapping.created_at.isoformat(),
        updated_at=mapping.updated_at.isoformat(),
    )


@router.put("/{mapping_id}", response_model=FileTypeMappingResponse)
async def update_mapping(
    mapping_id: UUID,
    mapping_data: FileTypeMappingUpdate,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """Update a file type mapping."""
    repo = FileTypeMappingRepository(session)
    mapping = await repo.get_by_id(mapping_id)

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File type mapping not found",
        )

    updated = await repo.update(
        mapping_id,
        agent_name=mapping_data.agent_name,
        is_default=mapping_data.is_default,
        config=mapping_data.config,
    )

    # Log audit
    changes = {}
    if mapping_data.agent_name is not None:
        changes["agent_name"] = mapping_data.agent_name
    if mapping_data.is_default is not None:
        changes["is_default"] = mapping_data.is_default
    if mapping_data.config is not None:
        changes["config"] = mapping_data.config

    if changes:
        await AuditService.log_action(
            session=session,
            resource_type="file_type_mapping",
            resource_id=str(mapping_id),
            action="update",
            changes=changes,
        )
        await session.commit()

    return FileTypeMappingResponse(
        id=updated.id,
        file_type=updated.file_type,
        agent_name=updated.agent_name,
        is_default=updated.is_default,
        version=updated.version,
        config=updated.config,
        created_at=updated.created_at.isoformat(),
        updated_at=updated.updated_at.isoformat(),
    )


@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mapping(
    mapping_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """Delete a file type mapping."""
    repo = FileTypeMappingRepository(session)
    mapping = await repo.get_by_id(mapping_id)

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File type mapping not found",
        )

    await repo.delete(mapping_id)

    # Log audit
    await AuditService.log_action(
        session=session,
        resource_type="file_type_mapping",
        resource_id=str(mapping_id),
        action="delete",
        changes={"file_type": mapping.file_type},
    )
    await session.commit()


@router.post("/{mapping_id}/test-run", response_model=FileTypeMappingTestResponse)
async def test_mapping(
    mapping_id: UUID,
    test_request: FileTypeMappingTestRequest = Body(default=None, embed=False),
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """
    Test a file type mapping without actually processing a file.

    This endpoint simulates routing a file to the mapped agent and validates
    the mapping configuration. It returns routing decisions and validation results.

    Args:
        mapping_id: ID of the file type mapping to test
        test_request: Optional request with file_type and sample_data for validation

    Returns:
        FileTypeMappingTestResponse with routing decision and validation results
    """
    repo = FileTypeMappingRepository(session)
    mapping = await repo.get_by_id(mapping_id)

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File type mapping not found",
        )

    # Get file_type to test from request or use mapping's file_type
    test_file_type = None
    if test_request and test_request.file_type:
        test_file_type = test_request.file_type.strip().lower()

    result = await FileTypeMappingService.test_mapping(
        session,
        mapping_id,
        test_file_type=test_file_type,
        sample_data=test_request.sample_data if test_request else None,
    )

    return FileTypeMappingTestResponse(
        file_type=result["file_type"],
        agent_name=result["agent_name"],
        status=result["status"],
        message=result["message"],
        routing_decision=result.get("routing_decision"),
        configuration=result.get("configuration"),
        validation_results=result.get("validation_results"),
        sample_validation=result.get("sample_validation"),
        processed_items=result.get("processed_items"),
    )
