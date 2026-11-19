"""Routes for file versioning and snapshot management."""

import logging
import mimetypes
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.document_metadata import DocumentMetadata
from app.models.ingest_job import IngestJob
from app.models.raw_file import RawFile
from app.models.storage_config import StorageConfig
from app.schemas.file_versions import FileVersionResponse, VersionListResponse
from app.services.local_storage_service import LocalStorageService
from app.services.snapshot_service import SnapshotService
from app.services.storage_service import StorageService
from app.core.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"], dependencies=[Depends(get_current_user)])


MIME_BY_EXT = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "json": "application/json",
    "xml": "application/xml",
    "html": "text/html; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/document/{document_id}/content")
async def get_document_raw_content(
    document_id: str,
    download: bool = Query(False, description="Force attachment download"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Stream the original uploaded file for a DocumentMetadata ID, IngestJob ID, or RawFile ID.
    Enforces tenant isolation for non-staff portal users and falls back cleanly for seeded/extracted docs.
    """
    from pathlib import Path
    from app.models.extraction_result import ExtractionResult
    from app.startup.client_access import is_broker_staff, portal_user_client_id

    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    storage_path: Optional[str] = None
    filename: str = f"document_{document_id[:8]}"
    file_type: str = ""
    mime_type: Optional[str] = None
    owner_client_id: Optional[str] = None
    owner_user_id: Optional[str] = None
    job: Optional[IngestJob] = None

    # 1. Try DocumentMetadata
    doc_res = await session.execute(
        select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
    )
    doc = doc_res.scalar_one_or_none()
    if doc:
        storage_path = doc.raw_storage_path
        filename = doc.filename or filename
        file_type = (doc.file_type or "").lower()
        mime_type = doc.mime_type
        owner_client_id = str(getattr(doc, "customer_id", "") or "") or None
        if doc.job_id:
            job_res = await session.execute(
                select(IngestJob).where(IngestJob.id == doc.job_id)
            )
            job = job_res.scalar_one_or_none()
            if job:
                storage_path = storage_path or job.storage_path
                owner_user_id = str(getattr(job, "user_id", "") or "") or None
                owner_client_id = owner_client_id or (str(getattr(job, "customer_id", "") or "") or None)

    # 2. Fallback: Try IngestJob directly
    if not storage_path and job is None:
        job_res = await session.execute(
            select(IngestJob).where(IngestJob.id == doc_uuid)
        )
        job = job_res.scalar_one_or_none()
        if job:
            storage_path = job.storage_path
            filename = job.filename or filename
            file_type = (job.file_type or "").lower()
            owner_user_id = str(getattr(job, "user_id", "") or "") or None
            owner_client_id = str(getattr(job, "customer_id", "") or "") or None

    # 3. Fallback: Try RawFile directly
    if not storage_path:
        raw_res = await session.execute(
            select(RawFile).where(RawFile.id == doc_uuid)
        )
        raw_file = raw_res.scalar_one_or_none()
        if raw_file:
            storage_path = raw_file.storage_path
            filename = raw_file.filename or filename
            file_type = (raw_file.file_type or "").lower()
            mime_type = raw_file.mime_type
            owner_client_id = owner_client_id or (str(getattr(raw_file, "customer_id", "") or "") or None)

    # Enforce tenant ownership for external importer portal accounts
    if not is_broker_staff(current_user):
        scoped_client = portal_user_client_id(current_user)
        caller_id = str(current_user.get("id") or "")
        allowed = (
            (owner_client_id and str(scoped_client) == owner_client_id)
            or (owner_user_id and caller_id == owner_user_id)
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this document",
            )

    # Fetch bytes from local storage, matching uploads, demo fixtures, or synthesized PDF/text preview
    file_bytes: Optional[bytes] = None
    local_storage = LocalStorageService()

    if storage_path:
        try:
            file_bytes = local_storage.get_file(storage_path)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"Error reading file {storage_path}: {e}")

    # Fallback A: Search /app/storage/uploads and bundled demo_documents for matching filename
    if file_bytes is None and filename:
        try:
            search_dirs = [
                local_storage.base_path / "uploads",
                Path("/app/data/demo_documents"),
                Path(__file__).resolve().parents[5] / "data" / "demo_documents",
            ]
            for sdir in search_dirs:
                if not sdir.exists():
                    continue
                for candidate in sdir.rglob("*"):
                    if candidate.is_file() and (
                        candidate.name == filename or candidate.name.endswith(f"_{filename}")
                    ):
                        file_bytes = candidate.read_bytes()
                        break
                if file_bytes is not None:
                    break
        except Exception as e:
            logger.warning(f"Uploads search fallback failed: {e}")

    # Fallback B: Cloud storage if configured
    if file_bytes is None and storage_path:
        cfg_res = await session.execute(
            select(StorageConfig).where(StorageConfig.is_active == True).limit(1)
        )
        storage_cfg = cfg_res.scalar_one_or_none()
        if storage_cfg:
            try:
                cloud_storage = StorageService(storage_cfg)
                file_bytes = cloud_storage.get_file(storage_path)
            except Exception as e:
                logger.error(f"Cloud storage fetch failed for {storage_path}: {e}")

    # Fallback C: Synthesize a clean PDF or text preview from extracted_text_snippet OR ExtractionResult fields
    ext = file_type or (filename.rsplit(".", 1)[-1].lower() if "." in filename else "")
    preview_text = (doc.extracted_text_snippet if doc else None) or ""
    if file_bytes is None and not preview_text:
        ext_rows_res = await session.execute(
            select(ExtractionResult).where(ExtractionResult.document_id == doc_uuid)
        )
        ext_rows = ext_rows_res.scalars().all()
        if ext_rows:
            preview_lines = [f"Extracted Trade Fields — {filename}", "=" * 56, ""]
            for r in ext_rows:
                conf_pct = f"{round((r.confidence or 0) * 100)}%"
                preview_lines.append(f"{r.field_name}: {r.final_value or r.field_value}  (confidence: {conf_pct})")
            preview_text = "\n".join(preview_lines)

    if file_bytes is None and preview_text:
        if ext == "pdf":
            import io
            from xml.sax.saxutils import escape
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

            buf = io.BytesIO()
            pdf_doc = SimpleDocTemplate(buf, pagesize=letter)
            styles = getSampleStyleSheet()
            mono_style = ParagraphStyle(
                "DocPreviewMono",
                parent=styles["Normal"],
                fontName="Courier",
                fontSize=9,
                leading=12,
            )
            story = [
                Paragraph(f"<b>Document:</b> {escape(filename)}", styles["Heading3"]),
                Spacer(1, 10),
            ]
            for line in preview_text.splitlines():
                safe_line = escape(line.strip())
                if safe_line:
                    story.append(Paragraph(safe_line, mono_style))
                else:
                    story.append(Spacer(1, 6))
            pdf_doc.build(story)
            file_bytes = buf.getvalue()
        else:
            file_bytes = preview_text.encode("utf-8")
            if not ext:
                ext = "txt"

    if file_bytes is None:
        raise HTTPException(
            status_code=404,
            detail=f"File content not found in storage for {filename}",
        )
    resolved_mime = (
        MIME_BY_EXT.get(ext)
        or mime_type
        or mimetypes.guess_type(filename)[0]
        or "application/octet-stream"
    )
    disposition = "attachment" if download else "inline"

    return Response(
        content=file_bytes,
        media_type=resolved_mime,
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/{file_id}/versions", response_model=VersionListResponse)
async def list_file_versions(
    file_id: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Get all versions of a file.

    Returns list of versions within 2 seconds.
    """
    try:
        versions = await SnapshotService.list_versions(session, file_id)

        return VersionListResponse(
            versions=versions,
            total_count=len(versions),
        )

    except Exception as e:
        logger.error(f"Error listing versions for file {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list versions")


@router.get("/{file_id}/versions/{version_id}")
async def get_version_metadata(
    file_id: str,
    version_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get metadata for a specific file version."""
    try:
        from sqlalchemy import select
        from app.models.file_version import FileVersion

        result = await session.execute(
            select(FileVersion).where(FileVersion.id == version_id)
        )
        version = result.scalar_one_or_none()

        if not version or str(version.upload_metadata_id) != file_id:
            raise HTTPException(status_code=404, detail="Version not found")

        return {
            "version_id": str(version.id),
            "version_number": version.version_number,
            "file_hash": version.file_hash,
            "is_deduplicated": version.is_deduplicated,
            "storage_path": version.storage_path,
            "created_at": version.created_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving version {version_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve version")


@router.get("/{file_id}/versions/{version_id}/download")
async def download_version(
    file_id: str,
    version_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Download a specific file version."""
    try:
        from sqlalchemy import select
        from app.models.file_version import FileVersion

        result = await session.execute(
            select(FileVersion).where(FileVersion.id == version_id)
        )
        version = result.scalar_one_or_none()

        if not version or str(version.upload_metadata_id) != file_id:
            raise HTTPException(status_code=404, detail="Version not found")

        # In a real implementation, you would:
        # 1. Fetch file from Supabase Storage using version.storage_path
        # 2. Return as StreamingResponse
        # For now, return metadata with signed URL instructions

        return {
            "version_id": str(version.id),
            "storage_path": version.storage_path,
            "file_hash": version.file_hash,
            "is_deduplicated": version.is_deduplicated,
            "message": "Use storage service to download file from storage_path",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading version {version_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to download version")
