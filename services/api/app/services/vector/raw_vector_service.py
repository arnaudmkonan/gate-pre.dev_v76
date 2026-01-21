import logging
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import RawVector, RawFile
from app.schemas.vector_store import RawVectorCreate, RawVectorResponse

logger = logging.getLogger(__name__)


class RawVectorService:
    """Service for storing and retrieving raw vectors with metadata."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def store(
        self,
        payload: RawVectorCreate,
    ) -> RawVectorResponse:
        """
        Store raw vector with provenance validation.

        Args:
            payload: RawVectorCreate payload

        Returns:
            Stored vector record

        Raises:
            ValueError: If provenance validation fails
            IntegrityError: If duplicate file_id (unique constraint violated)
        """
        # Validate provenance fields exist
        if not payload.provenance.get("processor_agent_id"):
            raise ValueError("Missing required provenance field: processor_agent_id")
        if not payload.provenance.get("extraction_version"):
            raise ValueError("Missing required provenance field: extraction_version")

        try:
            # Check if file_id exists
            stmt = select(RawFile).where(RawFile.id == payload.file_id)
            result = await self.session.execute(stmt)
            file_record = result.scalar_one_or_none()

            if not file_record:
                raise ValueError(f"File with id {payload.file_id} not found")

            # Create vector record
            vector_record = RawVector(
                file_id=payload.file_id,
                vector=payload.vector,
                doc_metadata=payload.metadata or {},
                provenance=payload.provenance,
            )

            self.session.add(vector_record)
            await self.session.commit()
            await self.session.refresh(vector_record)

            logger.info(f"Stored vector for file {payload.file_id}")
            return RawVectorResponse.model_validate(vector_record)

        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"Duplicate file_id: {payload.file_id}")
            raise ValueError(f"Vector already exists for file {payload.file_id}. Use upsert for idempotent updates.")
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to store vector: {e}")
            raise

    async def get_by_file_id(self, file_id: UUID) -> RawVectorResponse:
        """
        Retrieve vector by file_id (must be <200ms for 10k records).

        Args:
            file_id: File ID

        Returns:
            Vector record or None

        Raises:
            ValueError: If not found
        """
        try:
            stmt = select(RawVector).where(RawVector.file_id == file_id)
            result = await self.session.execute(stmt)
            vector = result.scalar_one_or_none()

            if not vector:
                raise ValueError(f"Vector not found for file {file_id}")

            logger.info(f"Retrieved vector for file {file_id}")
            return RawVectorResponse.model_validate(vector)

        except Exception as e:
            logger.error(f"Failed to retrieve vector: {e}")
            raise

    async def upsert(
        self,
        payload: RawVectorCreate,
    ) -> RawVectorResponse:
        """
        Idempotent upsert: update if exists, insert if not.

        Args:
            payload: RawVectorCreate payload

        Returns:
            Updated or created vector record
        """
        # Validate provenance
        if not payload.provenance.get("processor_agent_id"):
            raise ValueError("Missing required provenance field: processor_agent_id")
        if not payload.provenance.get("extraction_version"):
            raise ValueError("Missing required provenance field: extraction_version")

        try:
            # Check if file_id exists
            stmt = select(RawFile).where(RawFile.id == payload.file_id)
            result = await self.session.execute(stmt)
            file_record = result.scalar_one_or_none()

            if not file_record:
                raise ValueError(f"File with id {payload.file_id} not found")

            # Try to get existing vector
            stmt = select(RawVector).where(RawVector.file_id == payload.file_id)
            result = await self.session.execute(stmt)
            existing_vector = result.scalar_one_or_none()

            if existing_vector:
                # Update existing
                existing_vector.vector = payload.vector
                existing_vector.doc_metadata = payload.metadata or {}
                existing_vector.provenance = payload.provenance
                await self.session.commit()
                await self.session.refresh(existing_vector)
                logger.info(f"Upserted (updated) vector for file {payload.file_id}")
                return RawVectorResponse.model_validate(existing_vector)
            else:
                # Insert new
                vector_record = RawVector(
                    file_id=payload.file_id,
                    vector=payload.vector,
                    doc_metadata=payload.metadata or {},
                    provenance=payload.provenance,
                )
                self.session.add(vector_record)
                await self.session.commit()
                await self.session.refresh(vector_record)
                logger.info(f"Upserted (inserted) vector for file {payload.file_id}")
                return RawVectorResponse.model_validate(vector_record)

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to upsert vector: {e}")
            raise

    async def ensure_provenance(
        self,
        file_id: UUID,
    ) -> bool:
        """
        Validate that vector has required provenance metadata.

        Args:
            file_id: File ID

        Returns:
            True if provenance is valid
        """
        try:
            stmt = select(RawVector).where(RawVector.file_id == file_id)
            result = await self.session.execute(stmt)
            vector = result.scalar_one_or_none()

            if not vector:
                return False

            provenance = vector.provenance or {}
            has_processor_id = "processor_agent_id" in provenance
            has_extraction_version = "extraction_version" in provenance

            return has_processor_id and has_extraction_version

        except Exception as e:
            logger.error(f"Failed to check provenance: {e}")
            return False
