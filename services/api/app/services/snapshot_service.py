"""Snapshot service for creating immutable file snapshots with deduplication."""

import hashlib
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_snapshot import FileSnapshot
from app.models.file_version import FileVersion

logger = logging.getLogger(__name__)


class SnapshotService:
    """Creates and manages immutable file snapshots with content-addressed storage."""

    @staticmethod
    def compute_sha256(file_bytes: bytes) -> str:
        """Compute SHA-256 hash of file content."""
        sha256_hash = hashlib.sha256()
        sha256_hash.update(file_bytes)
        return sha256_hash.hexdigest()

    @staticmethod
    async def create_snapshot(
        session: AsyncSession,
        file_id: str,
        file_bytes: bytes,
        filename: str,
        created_by: Optional[str] = None,
    ) -> Dict:
        """
        Create an immutable snapshot of uploaded file.

        Args:
            session: Database session
            file_id: ID of the upload metadata
            file_bytes: Raw file content
            filename: Original filename
            created_by: User ID of uploader

        Returns:
            Dict with snapshot_id, content_hash, storage_path, version_number
        """
        # Compute content hash
        content_hash = SnapshotService.compute_sha256(file_bytes)

        # Check for deduplication
        is_deduplicated = False
        existing_snapshot = await session.execute(
            select(FileSnapshot).where(FileSnapshot.content_hash == content_hash)
        )
        existing = existing_snapshot.scalar_one_or_none()

        if existing:
            is_deduplicated = True
            logger.info(f"Snapshot detected as deduplicated with hash {content_hash}")

        # Get next version number for this file
        version_result = await session.execute(
            select(FileSnapshot).where(FileSnapshot.file_id == file_id).order_by(FileSnapshot.version_number.desc())
        )
        last_version = version_result.scalar_one_or_none()
        version_number = (last_version.version_number + 1) if last_version else 1

        # Create snapshot path (content-addressed)
        storage_path = f"snapshots/{content_hash}/{filename}"

        # Create snapshot record
        snapshot = FileSnapshot(
            file_id=file_id,
            version_number=version_number,
            content_hash=content_hash,
            snapshot_path=storage_path,
            storage_size=len(file_bytes),
            created_by=created_by,
            dedup_info={"filename": filename, "is_deduplicated": is_deduplicated},
        )

        session.add(snapshot)
        await session.flush()

        logger.info(f"Snapshot created: {snapshot.id}, hash: {content_hash}, deduplicated: {is_deduplicated}")

        return {
            "snapshot_id": str(snapshot.id),
            "content_hash": content_hash,
            "storage_path": storage_path,
            "version_number": version_number,
            "is_deduplicated": is_deduplicated,
            "storage_size": len(file_bytes),
        }

    @staticmethod
    async def get_version(
        session: AsyncSession,
        file_id: str,
        version_number: int,
    ) -> Optional[Dict]:
        """
        Retrieve a specific file version.

        Args:
            session: Database session
            file_id: ID of the upload metadata
            version_number: Version number to retrieve

        Returns:
            Dict with version details or None if not found
        """
        result = await session.execute(
            select(FileVersion).where(
                (FileVersion.upload_metadata_id == file_id)
                & (FileVersion.version_number == version_number)
            )
        )
        version = result.scalar_one_or_none()

        if not version:
            return None

        # Get associated snapshot
        snapshot_result = await session.execute(
            select(FileSnapshot).where(FileSnapshot.id == version.snapshot_id)
        )
        snapshot = snapshot_result.scalar_one_or_none()

        if not snapshot:
            return None

        return {
            "version_id": str(version.id),
            "version_number": version.version_number,
            "file_hash": version.file_hash,
            "is_deduplicated": version.is_deduplicated,
            "storage_path": version.storage_path,
            "created_at": version.created_at,
            "snapshot_id": str(snapshot.id),
            "content_hash": snapshot.content_hash,
            "storage_size": snapshot.storage_size,
        }

    @staticmethod
    async def list_versions(
        session: AsyncSession,
        file_id: str,
    ) -> list:
        """
        List all versions of a file.

        Args:
            session: Database session
            file_id: ID of the upload metadata

        Returns:
            List of version details
        """
        result = await session.execute(
            select(FileVersion)
            .where(FileVersion.upload_metadata_id == file_id)
            .order_by(FileVersion.version_number.desc())
        )
        versions = result.scalars().all()

        response = []
        for version in versions:
            # Get associated snapshot
            snapshot_result = await session.execute(
                select(FileSnapshot).where(FileSnapshot.id == version.snapshot_id)
            )
            snapshot = snapshot_result.scalar_one_or_none()

            if snapshot:
                response.append({
                    "version_id": str(version.id),
                    "version_number": version.version_number,
                    "file_hash": version.file_hash,
                    "is_deduplicated": version.is_deduplicated,
                    "storage_path": version.storage_path,
                    "created_at": version.created_at,
                    "snapshot_id": str(snapshot.id),
                    "content_hash": snapshot.content_hash,
                    "storage_size": snapshot.storage_size,
                })

        return response
