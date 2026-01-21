"""Repository for file type mapping operations."""

from typing import List, Tuple, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_type_mapping import FileTypeMapping


class FileTypeMappingRepository:
    """Repository for managing file type mappings."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        file_type: str,
        agent_name: str,
        is_default: bool = False,
        config: Optional[dict] = None,
    ) -> FileTypeMapping:
        """Create a new file type mapping."""
        mapping = FileTypeMapping(
            file_type=file_type.lower(),
            agent_name=agent_name,
            is_default=is_default,
            config=config,
            version=1,
        )
        self.session.add(mapping)
        await self.session.flush()
        return mapping

    async def get_by_id(self, mapping_id: UUID) -> Optional[FileTypeMapping]:
        """Get mapping by ID."""
        result = await self.session.execute(select(FileTypeMapping).where(FileTypeMapping.id == mapping_id))
        return result.scalars().first()

    async def get_by_file_type(self, file_type: str) -> Optional[FileTypeMapping]:
        """Get mapping by file type."""
        result = await self.session.execute(
            select(FileTypeMapping).where(FileTypeMapping.file_type == file_type.lower())
        )
        return result.scalars().first()

    async def list_all(
        self, page: int = 1, page_size: int = 50
    ) -> Tuple[List[FileTypeMapping], int]:
        """List all file type mappings with pagination."""
        # Get total count
        count_result = await self.session.execute(select(FileTypeMapping))
        total = len(count_result.scalars().all())

        # Get paginated results
        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(FileTypeMapping).offset(offset).limit(page_size)
        )
        mappings = result.scalars().all()
        return mappings, total

    async def update(
        self,
        mapping_id: UUID,
        agent_name: Optional[str] = None,
        is_default: Optional[bool] = None,
        config: Optional[dict] = None,
    ) -> Optional[FileTypeMapping]:
        """Update a file type mapping."""
        mapping = await self.get_by_id(mapping_id)
        if not mapping:
            return None

        if agent_name is not None:
            mapping.agent_name = agent_name
        if is_default is not None:
            mapping.is_default = is_default
        if config is not None:
            mapping.config = config

        # Increment version
        mapping.version += 1

        await self.session.flush()
        return mapping

    async def delete(self, mapping_id: UUID) -> bool:
        """Delete a file type mapping."""
        mapping = await self.get_by_id(mapping_id)
        if not mapping:
            return False

        await self.session.delete(mapping)
        await self.session.flush()
        return True

    async def get_default_for_file_type(self, file_type: str) -> Optional[FileTypeMapping]:
        """Get the default mapping for a file type."""
        result = await self.session.execute(
            select(FileTypeMapping).where(
                and_(
                    FileTypeMapping.file_type == file_type.lower(),
                    FileTypeMapping.is_default == True,
                )
            )
        )
        return result.scalars().first()

    async def search_by_agent(self, agent_name: str) -> List[FileTypeMapping]:
        """Search mappings by agent name."""
        result = await self.session.execute(
            select(FileTypeMapping).where(FileTypeMapping.agent_name.contains(agent_name))
        )
        return result.scalars().all()
