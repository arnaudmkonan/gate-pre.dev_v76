"""Access control helpers for ingestion jobs."""

from fastapi import HTTPException, status

from app.models.client_portal import ClientUserRole
from app.models.ingest_job import IngestJob


def is_ingest_admin(user: dict) -> bool:
    return user.get("role") == ClientUserRole.ADMIN.value


def uploader_scope_for_list(user: dict) -> str | None:
    """None = no filter (admin); otherwise restrict to this user id."""
    if is_ingest_admin(user):
        return None
    return user.get("id")


def assert_can_access_job(job: IngestJob, user: dict) -> None:
    if is_ingest_admin(user):
        return
    owner = job.uploader_id
    if owner is None:
        return
    if owner != user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this ingestion job",
        )
