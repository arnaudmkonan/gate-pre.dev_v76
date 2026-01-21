import logging
import os
import sys
from pathlib import Path
from typing import Optional

import click
import httpx

logger = logging.getLogger(__name__)


class IngestionClient:
    """Client for interacting with the ingestion API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=30.0)

    def upload_file(self, file_path: str, uploader_id: Optional[str] = None) -> dict:
        """Upload a single file for ingestion."""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f)}
            params = {}
            if uploader_id:
                params["uploader_id"] = uploader_id

            response = self.client.post("/api/ingest/upload", files=files, params=params)
            response.raise_for_status()
            return response.json()

    def get_job_status(self, job_id: str) -> dict:
        """Get status of an ingestion job."""
        response = self.client.get(f"/api/ingest/jobs/{job_id}")
        response.raise_for_status()
        return response.json()

    def list_jobs(self, status: Optional[str] = None, uploader_id: Optional[str] = None) -> dict:
        """List ingestion jobs."""
        params = {}
        if status:
            params["status"] = status
        if uploader_id:
            params["uploader_id"] = uploader_id

        response = self.client.get("/api/ingest/jobs", params=params)
        response.raise_for_status()
        return response.json()

    def close(self):
        """Close the HTTP client."""
        self.client.close()


# Supported file types
SUPPORTED_TYPES = ["txt", "md", "pdf", "docx", "xlsx", "csv", "json"]


@click.group()
def ingest_cli():
    """Ingestion CLI for document processing."""
    pass


@ingest_cli.command()
@click.argument("file_path")
@click.option("--uploader-id", default=None, help="ID of the uploader")
@click.option("--api-url", default="http://localhost:8000", help="API base URL")
def enqueue(file_path: str, uploader_id: Optional[str], api_url: str):
    """Upload and enqueue a single file for ingestion."""
    try:
        file_path_obj = Path(file_path)

        # Validate file exists
        if not file_path_obj.exists():
            click.echo(f"❌ File not found: {file_path}", err=True)
            sys.exit(1)

        # Validate file type
        file_ext = file_path_obj.suffix[1:].lower()
        if file_ext not in SUPPORTED_TYPES:
            click.echo(
                f"❌ Unsupported file type: .{file_ext}. Supported: {', '.join(SUPPORTED_TYPES)}",
                err=True,
            )
            sys.exit(1)

        # Upload file
        click.echo(f"📤 Uploading {file_path_obj.name}...")
        client = IngestionClient(api_url)
        result = client.upload_file(file_path, uploader_id)
        client.close()

        click.echo(f"✅ File uploaded successfully!")
        click.echo(f"   Job ID: {result['job_id']}")
        click.echo(f"   File ID: {result['file_id']}")
        click.echo(f"   Storage Path: {result['storage_path']}")

    except FileNotFoundError as e:
        click.echo(f"❌ {str(e)}", err=True)
        sys.exit(1)
    except httpx.HTTPError as e:
        click.echo(f"❌ API error: {str(e)}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        sys.exit(1)


@ingest_cli.command()
@click.argument("directory")
@click.option("--uploader-id", default=None, help="ID of the uploader")
@click.option("--api-url", default="http://localhost:8000", help="API base URL")
def enqueue_bulk(directory: str, uploader_id: Optional[str], api_url: str):
    """Upload and enqueue multiple files from a directory."""
    try:
        dir_path = Path(directory)

        # Validate directory exists
        if not dir_path.is_dir():
            click.echo(f"❌ Directory not found: {directory}", err=True)
            sys.exit(1)

        # Find supported files
        files = []
        for file_path in dir_path.rglob("*"):
            if file_path.is_file():
                ext = file_path.suffix[1:].lower()
                if ext in SUPPORTED_TYPES:
                    files.append(file_path)

        if not files:
            click.echo(f"❌ No supported files found in {directory}", err=True)
            sys.exit(1)

        # Upload files
        click.echo(f"📤 Uploading {len(files)} files...")
        client = IngestionClient(api_url)

        succeeded = 0
        failed = 0

        for file_path in files:
            try:
                click.echo(f"  Uploading {file_path.name}...", nl=False)
                result = client.upload_file(str(file_path), uploader_id)
                click.echo(f" ✅ (Job: {result['job_id']})")
                succeeded += 1
            except Exception as e:
                click.echo(f" ❌ ({str(e)})")
                failed += 1

        client.close()

        click.echo(f"\n✅ Bulk upload completed: {succeeded} succeeded, {failed} failed")

    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        sys.exit(1)


@ingest_cli.command()
@click.argument("job_id")
@click.option("--api-url", default="http://localhost:8000", help="API base URL")
def status(job_id: str, api_url: str):
    """Get status of an ingestion job."""
    try:
        client = IngestionClient(api_url)
        job = client.get_job_status(job_id)
        client.close()

        click.echo(f"\n📋 Job Status: {job_id}")
        click.echo(f"   Filename: {job['filename']}")
        click.echo(f"   Status: {job['status']}")
        click.echo(f"   File Type: {job['file_type']}")
        click.echo(f"   Size: {job['size']} bytes")
        click.echo(f"   Created: {job['created_at']}")

        if job.get("error_message"):
            click.echo(f"   Error: {job['error_message']}")

    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        sys.exit(1)


@ingest_cli.command()
@click.option("--api-url", default="http://localhost:8000", help="API base URL")
def list_jobs(api_url: str):
    """List all ingestion jobs."""
    try:
        client = IngestionClient(api_url)
        result = client.list_jobs()
        client.close()

        jobs = result.get("items", [])

        if not jobs:
            click.echo("No jobs found")
            return

        click.echo(f"\n📋 Ingestion Jobs ({result.get('total', 0)} total)")
        click.echo("─" * 80)

        for job in jobs:
            click.echo(
                f"{job['filename']:<30} {job['status']:<12} "
                f"{job['file_type']:<10} {job['created_at']}"
            )

    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    ingest_cli()
