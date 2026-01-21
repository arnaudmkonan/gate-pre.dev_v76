"""Ingestion SDK client for interacting with the ingestion API."""

import logging
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class IngestionClient:
    """Client for uploading and managing document ingestion jobs."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        verify: bool = True,
    ):
        """
        Initialize the ingestion client.

        Args:
            base_url: Base URL of the ingestion API
            timeout: Request timeout in seconds
            verify: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify = verify
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            verify=verify,
        )

    def upload_file(
        self,
        file_path: str,
        uploader_id: Optional[str] = None,
    ) -> dict:
        """
        Upload a file for ingestion.

        Args:
            file_path: Path to the file to upload
            uploader_id: Optional ID of the uploader

        Returns:
            Response with file_id, job_id, storage_path, etc.

        Raises:
            FileNotFoundError: If file doesn't exist
            httpx.HTTPError: If API request fails
        """
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path_obj, "rb") as f:
            files = {"file": (file_path_obj.name, f)}
            params = {}

            if uploader_id:
                params["uploader_id"] = uploader_id

            response = self.client.post(
                "/api/ingest/upload",
                files=files,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    def batch_upload(
        self,
        file_paths: list[str],
        uploader_id: Optional[str] = None,
    ) -> dict:
        """
        Upload multiple files for ingestion.

        Args:
            file_paths: List of file paths to upload
            uploader_id: Optional ID of the uploader

        Returns:
            Dict with succeeded count, failed count, and results

        Raises:
            httpx.HTTPError: If API requests fail
        """
        results = {
            "succeeded": 0,
            "failed": 0,
            "jobs": [],
            "errors": [],
        }

        for file_path in file_paths:
            try:
                job = self.upload_file(file_path, uploader_id)
                results["jobs"].append(job)
                results["succeeded"] += 1
            except Exception as e:
                results["errors"].append({
                    "file": file_path,
                    "error": str(e),
                })
                results["failed"] += 1

        return results

    def get_job_status(self, job_id: str) -> dict:
        """
        Get status of an ingestion job.

        Args:
            job_id: UUID of the job

        Returns:
            Job details including status, filename, metadata, etc.

        Raises:
            httpx.HTTPError: If API request fails
        """
        response = self.client.get(f"/api/ingest/jobs/{job_id}")
        response.raise_for_status()
        return response.json()

    def list_jobs(
        self,
        status: Optional[str] = None,
        uploader_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        List ingestion jobs with optional filtering.

        Args:
            status: Filter by status (pending, processing, completed, failed)
            uploader_id: Filter by uploader ID
            page: Page number for pagination
            page_size: Number of jobs per page

        Returns:
            Paginated list of jobs

        Raises:
            httpx.HTTPError: If API request fails
        """
        params = {
            "page": page,
            "page_size": page_size,
        }

        if status:
            params["status"] = status
        if uploader_id:
            params["uploader_id"] = uploader_id

        response = self.client.get("/api/ingest/jobs", params=params)
        response.raise_for_status()
        return response.json()

    def get_queue_status(self) -> dict:
        """
        Get queue status summary.

        Returns:
            Status with counts for pending, processing, completed, failed

        Raises:
            httpx.HTTPError: If API request fails
        """
        response = self.client.get("/api/ingest/status")
        response.raise_for_status()
        return response.json()

    def get_job_metadata(self, job_id: str) -> dict:
        """
        Get extracted metadata for a job.

        Args:
            job_id: UUID of the job

        Returns:
            Extracted metadata (title, page_count, language, etc.)

        Raises:
            httpx.HTTPError: If API request fails
        """
        response = self.client.get(f"/api/ingest/jobs/{job_id}/metadata")
        response.raise_for_status()
        return response.json()

    def close(self):
        """Close the HTTP client and cleanup resources."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
