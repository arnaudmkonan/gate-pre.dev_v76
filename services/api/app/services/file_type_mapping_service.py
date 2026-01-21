"""Service for file type mapping operations."""

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_type_mapping import FileTypeMapping
from app.repositories.file_type_mapping_repo import FileTypeMappingRepository


class FileTypeMappingService:
    """Service for managing file type mappings."""

    @staticmethod
    async def create_mapping(
        session: AsyncSession,
        file_type: str,
        agent_name: str,
        is_default: bool = False,
        config: Optional[Dict[str, Any]] = None,
    ) -> FileTypeMapping:
        """Create a new file type mapping."""
        repo = FileTypeMappingRepository(session)
        return await repo.create(file_type, agent_name, is_default, config)

    @staticmethod
    async def get_mapping(session: AsyncSession, mapping_id: UUID) -> Optional[FileTypeMapping]:
        """Get mapping by ID."""
        repo = FileTypeMappingRepository(session)
        return await repo.get_by_id(mapping_id)

    @staticmethod
    async def get_mapping_for_file_type(session: AsyncSession, file_type: str) -> Optional[FileTypeMapping]:
        """Get mapping for a specific file type."""
        repo = FileTypeMappingRepository(session)
        return await repo.get_by_file_type(file_type)

    @staticmethod
    async def list_mappings(
        session: AsyncSession, page: int = 1, page_size: int = 50
    ) -> tuple[List[FileTypeMapping], int]:
        """List all file type mappings."""
        repo = FileTypeMappingRepository(session)
        return await repo.list_all(page, page_size)

    @staticmethod
    async def update_mapping(
        session: AsyncSession,
        mapping_id: UUID,
        agent_name: Optional[str] = None,
        is_default: Optional[bool] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[FileTypeMapping]:
        """Update a file type mapping."""
        repo = FileTypeMappingRepository(session)
        return await repo.update(mapping_id, agent_name, is_default, config)

    @staticmethod
    async def delete_mapping(session: AsyncSession, mapping_id: UUID) -> bool:
        """Delete a file type mapping."""
        repo = FileTypeMappingRepository(session)
        return await repo.delete(mapping_id)

    @staticmethod
    async def test_mapping(
        session: AsyncSession,
        mapping_id: UUID,
        test_file_type: Optional[str] = None,
        sample_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Test a file type mapping with optional file_type validation and sample data.

        This simulates routing a file to the mapped agent without actually processing it.
        It validates the mapping configuration and determines if a given file_type would be routed correctly.

        Args:
            session: Database session
            mapping_id: ID of the file type mapping to test
            test_file_type: Optional file type to test against the mapping (if provided, checks if it matches)
            sample_data: Optional sample data for validation (e.g., filename, file_size)

        Returns:
            Dict containing routing decision, configuration, and validation results
        """
        repo = FileTypeMappingRepository(session)
        mapping = await repo.get_by_id(mapping_id)

        if not mapping:
            return {
                "status": "failed",
                "message": f"Mapping not found: {mapping_id}",
            }

        # Validate the mapping configuration
        config_valid = mapping.config is not None and isinstance(mapping.config, dict)
        validation_errors = []

        if not mapping.agent_name or not mapping.agent_name.strip():
            validation_errors.append("Agent name is empty")

        if not mapping.file_type or not mapping.file_type.strip():
            validation_errors.append("File type is empty")

        # Check if test_file_type matches the mapping
        matched = True
        if test_file_type:
            matched = test_file_type.strip().lower() == mapping.file_type.strip().lower()
            if not matched:
                validation_errors.append(
                    f"File type '{test_file_type}' does not match mapping file type '{mapping.file_type}'"
                )

        # Simulate routing decision
        routing_decision = {
            "would_route": len(validation_errors) == 0 and matched,
            "matched_agent_name": mapping.agent_name if matched else None,
            "file_type_handled": mapping.file_type,
            "mapping_version": mapping.version,
        }

        # Add sample data validation if provided
        sample_validation = None
        if sample_data:
            sample_validation = {
                "provided_fields": list(sample_data.keys()),
                "sample_data_accepted": True,
            }

        # Get fallback agent if this file type doesn't match
        fallback_agent = None
        if not matched:
            default_mapping = await repo.get_by_file_type("default")
            if default_mapping:
                fallback_agent = default_mapping.agent_name

        return {
            "file_type": test_file_type or mapping.file_type,
            "agent_name": mapping.agent_name,
            "status": "success" if len(validation_errors) == 0 else "failed",
            "message": (
                f"File type '{test_file_type or mapping.file_type}' would be routed to {mapping.agent_name}"
                if len(validation_errors) == 0 and matched
                else f"Routing validation failed: {'; '.join(validation_errors)}"
            ),
            "routing_decision": routing_decision,
            "configuration": {
                "agent_config": mapping.config or {},
                "config_valid": config_valid,
                "fallback_agent": fallback_agent,
            },
            "validation_results": {
                "errors": validation_errors,
                "error_count": len(validation_errors),
            },
            "sample_validation": sample_validation,
            "processed_items": 0,
        }

    @staticmethod
    async def export_mappings(session: AsyncSession) -> List[FileTypeMapping]:
        """Export all file type mappings."""
        repo = FileTypeMappingRepository(session)
        mappings, _ = await repo.list_all(page=1, page_size=1000)
        return mappings

    @staticmethod
    async def import_mappings(
        session: AsyncSession,
        mappings: List[Dict[str, Any]],
        overwrite_existing: bool = False,
    ) -> Dict[str, Any]:
        """Import file type mappings from list."""
        repo = FileTypeMappingRepository(session)
        imported = 0
        skipped = 0
        errors = []

        for mapping_data in mappings:
            try:
                existing = await repo.get_by_file_type(mapping_data["file_type"])

                if existing and not overwrite_existing:
                    skipped += 1
                    continue

                if existing and overwrite_existing:
                    await repo.delete(existing.id)

                await repo.create(
                    file_type=mapping_data["file_type"],
                    agent_name=mapping_data["agent_name"],
                    is_default=mapping_data.get("is_default", False),
                    config=mapping_data.get("config"),
                )
                imported += 1
            except Exception as e:
                errors.append(f"Error importing {mapping_data.get('file_type')}: {str(e)}")

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
        }
