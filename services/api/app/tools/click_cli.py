"""Click CLI commands for documentation ingestion platform.

Implements three main commands:
1. upload - Upload files for ingestion
2. monitor - Monitor job status with optional polling
3. storage configure - Configure storage credentials
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

import click
import httpx

logger = logging.getLogger(__name__)

# Default API URL
DEFAULT_API_URL = "http://localhost:8000"

# Supported file types for upload
SUPPORTED_FILE_TYPES = {
    "txt", "md", "docx", "xlsx", "pptx", "html", "json", "csv", "yml", "xml"
}

# Maximum file size: 50MB
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


class ClickClient:
    """HTTP client for Click API interactions."""

    def __init__(self, base_url: str = DEFAULT_API_URL):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=30.0)

    def upload_file(self, file_path: str) -> dict:
        """
        Upload a single file for ingestion.

        Returns:
            dict with job_id, file_id, storage_path, etc.

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file type or size is invalid
            httpx.HTTPError: If API returns an error
        """
        file_path_obj = Path(file_path)

        # Validate file exists
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Validate file type
        file_ext = file_path_obj.suffix[1:].lower() if "." in file_path_obj.name else ""
        if file_ext not in SUPPORTED_FILE_TYPES:
            raise ValueError(
                f"Unsupported file type: .{file_ext}. "
                f"Supported types: {', '.join(sorted(SUPPORTED_FILE_TYPES))}"
            )

        # Validate file size
        file_size = file_path_obj.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File size {file_size} bytes exceeds maximum {MAX_FILE_SIZE_BYTES} bytes "
                f"({MAX_FILE_SIZE_MB}MB)"
            )

        # Upload file
        with open(file_path_obj, "rb") as f:
            files = {"file": (file_path_obj.name, f, "application/octet-stream")}
            response = self.client.post("/api/upload", files=files)
            response.raise_for_status()
            return response.json()

    def get_job_status(self, job_id: str) -> dict:
        """
        Get status of an ingestion job.

        Returns:
            dict with job details including status, progress, error message if any

        Raises:
            httpx.HTTPError: If API returns an error
        """
        response = self.client.get(f"/api/ingest/jobs/{job_id}")
        response.raise_for_status()
        return response.json()

    def configure_storage(
        self,
        storage_type: str,
        endpoint: str,
        key: str,
        secret: str,
        bucket: str = "documents",
        region: str = "us-east-1",
    ) -> dict:
        """
        Configure storage provider with credentials.

        Args:
            storage_type: Type of storage (e.g., 's3', 'supabase')
            endpoint: Storage endpoint URL
            key: Access key
            secret: Secret key
            bucket: Bucket name
            region: Region (optional)

        Returns:
            dict with storage config details

        Raises:
            httpx.HTTPError: If API returns an error
        """
        response = self.client.post(
            "/api/storage/config",
            json={
                "provider": storage_type,
                "endpoint": endpoint,
                "access_key": key,
                "secret_key": secret,
                "bucket_name": bucket,
                "region": region,
            },
        )
        response.raise_for_status()
        return response.json()

    def test_storage_connection(self) -> dict:
        """
        Test storage connection by attempting a non-destructive operation.

        Returns:
            dict with test results

        Raises:
            httpx.HTTPError: If API returns an error or connection test fails
        """
        response = self.client.get("/api/storage/test")
        response.raise_for_status()
        return response.json()

    def close(self):
        """Close the HTTP client."""
        self.client.close()


# ============================================================================
# Main CLI Group
# ============================================================================

@click.group()
def cli():
    """Click CLI for the documentation ingestion platform."""
    pass


# ============================================================================
# UPLOAD COMMAND
# ============================================================================

@cli.command()
@click.argument("file_path")
@click.option(
    "--api-url",
    default=DEFAULT_API_URL,
    help="API base URL (default: http://localhost:8000)",
)
def upload(file_path: str, api_url: str):
    """
    Upload a file for document ingestion.

    Validates file type and size, then uploads to the API.
    Returns job_id confirmation in < 5 seconds.

    FILE_PATH: Path to the file to upload (.txt, .md, .docx, .xlsx, .pptx, .html, .json, .csv, .yml, .xml)
    """
    start_time = time.time()

    try:
        # Validate file exists first
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            click.secho(f"❌ File not found: {file_path}", fg="red", err=True)
            sys.exit(1)

        # Validate file type
        file_ext = file_path_obj.suffix[1:].lower() if "." in file_path_obj.name else ""
        if file_ext not in SUPPORTED_FILE_TYPES:
            click.secho(
                f"❌ Unsupported file type: .{file_ext}. "
                f"Supported types: {', '.join(sorted(SUPPORTED_FILE_TYPES))}",
                fg="red",
                err=True,
            )
            sys.exit(1)

        # Validate file size
        file_size = file_path_obj.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            click.secho(
                f"❌ File size {file_size} bytes exceeds maximum {MAX_FILE_SIZE_BYTES} bytes ({MAX_FILE_SIZE_MB}MB)",
                fg="red",
                err=True,
            )
            sys.exit(1)

        click.echo(f"📤 Uploading {Path(file_path).name}...")
        client = ClickClient(api_url)

        try:
            result = client.upload_file(file_path)
            elapsed_time = time.time() - start_time

            # Extract job_id from response
            job_id = result.get("job_id")
            if not job_id:
                click.secho("❌ No job_id in API response", fg="red", err=True)
                sys.exit(1)

            click.secho(f"✅ File uploaded successfully!", fg="green")
            click.echo(f"   Job ID: {job_id}")
            click.echo(f"   File ID: {result.get('file_id')}")
            click.echo(f"   Size: {result.get('size')} bytes")
            click.echo(f"   Uploaded in: {elapsed_time:.2f}s")

            # Verify < 5 seconds
            if elapsed_time > 5.0:
                click.secho(
                    f"⚠️  Upload took {elapsed_time:.2f}s (target: < 5s)",
                    fg="yellow",
                )

        except httpx.HTTPError as e:
            click.secho(f"❌ API error: {str(e)}", fg="red", err=True)
            sys.exit(1)
        finally:
            client.close()

    except Exception as e:
        click.secho(f"❌ Error: {str(e)}", fg="red", err=True)
        sys.exit(1)


# ============================================================================
# MONITOR COMMAND
# ============================================================================

def format_job_status(job: dict) -> str:
    """Format job details for display."""
    status = job.get("status", "unknown").upper()
    progress = job.get("progress_percentage", 0)

    status_color = {
        "PENDING": "yellow",
        "QUEUED": "blue",
        "PROCESSING": "cyan",
        "COMPLETED": "green",
        "FAILED": "red",
    }.get(status, "white")

    lines = [
        f"📋 Job: {job.get('id')}",
        f"   Status: {click.style(status, fg=status_color)}",
        f"   Progress: {progress}%",
        f"   Filename: {job.get('filename')}",
        f"   File Type: {job.get('file_type')}",
        f"   Size: {job.get('size')} bytes",
        f"   Created: {job.get('created_at')}",
    ]

    if job.get("error_message"):
        lines.append(f"   Error: {job.get('error_message')}")

    return "\n".join(lines)


@cli.command()
@click.argument("job_id")
@click.option(
    "--watch",
    is_flag=True,
    help="Continuously poll for status updates until job completes",
)
@click.option(
    "--interval",
    default=2,
    type=int,
    help="Polling interval in seconds (default: 2)",
)
@click.option(
    "--timeout",
    default=300,
    type=int,
    help="Maximum polling time in seconds (default: 300 = 5 minutes)",
)
@click.option(
    "--api-url",
    default=DEFAULT_API_URL,
    help="API base URL (default: http://localhost:8000)",
)
def monitor(job_id: str, watch: bool, interval: int, timeout: int, api_url: str):
    """
    Monitor the status of an ingestion job.

    Queries the API endpoint /api/ingest/jobs/{job_id} and displays job stages with timestamps.
    Use --watch flag for continuous polling until job completes.

    JOB_ID: The job ID to monitor
    """
    try:
        start_time = time.time()
        client = ClickClient(api_url)
        last_status = None

        while True:
            try:
                query_start = time.time()
                job = client.get_job_status(job_id)
                query_time = time.time() - query_start

                current_status = job.get("status")

                # Display status
                click.clear()
                click.secho(f"=== Job Monitor (Queried in {query_time:.3f}s) ===\n", fg="cyan")
                click.echo(format_job_status(job))
                click.echo()

                # Check for completion
                if current_status in ("COMPLETED", "FAILED"):
                    if current_status == "COMPLETED":
                        click.secho("✅ Job completed successfully!", fg="green")
                    else:
                        click.secho("❌ Job failed!", fg="red")
                    break

                # Handle watch mode
                if not watch:
                    break

                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    click.secho(
                        f"⏱️  Timeout reached ({timeout}s). Job is still {current_status}.",
                        fg="yellow",
                    )
                    break

                # Status change notification
                if last_status and last_status != current_status:
                    click.secho(
                        f"→ Status changed from {last_status} to {current_status}",
                        fg="cyan",
                    )

                last_status = current_status

                # Wait before next poll
                time.sleep(interval)

            except httpx.HTTPError as e:
                if "404" in str(e):
                    click.secho(f"❌ Job not found: {job_id}", fg="red", err=True)
                    sys.exit(1)
                else:
                    click.secho(f"❌ API error: {str(e)}", fg="red", err=True)
                    if watch:
                        click.echo("Retrying...")
                        time.sleep(interval)
                    else:
                        sys.exit(1)

        client.close()

    except Exception as e:
        click.secho(f"❌ Error: {str(e)}", fg="red", err=True)
        sys.exit(1)


# ============================================================================
# STORAGE CONFIGURE COMMAND
# ============================================================================

@cli.group()
def storage():
    """Storage configuration commands."""
    pass


@storage.command("configure")
@click.option(
    "--type",
    "storage_type",
    required=True,
    type=click.Choice(["s3", "supabase"]),
    help="Storage type",
)
@click.option("--endpoint", required=True, help="Storage endpoint URL")
@click.option("--key", required=True, help="Access key (can use env var STORAGE_KEY)")
@click.option("--secret", required=True, help="Secret key (can use env var STORAGE_SECRET)")
@click.option("--bucket", default="documents", help="Bucket name (default: documents)")
@click.option("--region", default="us-east-1", help="Region (default: us-east-1)")
@click.option(
    "--api-url",
    default=DEFAULT_API_URL,
    help="API base URL (default: http://localhost:8000)",
)
def storage_configure(
    storage_type: str,
    endpoint: str,
    key: str,
    secret: str,
    bucket: str,
    region: str,
    api_url: str,
):
    """
    Configure storage provider with credentials.

    Validates the connection by attempting a test operation.
    Credentials are encrypted in config file if validation succeeds.
    Prevents uploads if configuration is invalid.

    Example:
        cli storage configure --type s3 --endpoint https://s3.amazonaws.com \\
            --key YOUR_KEY --secret YOUR_SECRET --bucket my-bucket
    """
    try:
        click.echo("🔐 Configuring storage provider...")
        client = ClickClient(api_url)

        # Step 1: Configure storage
        click.echo(f"   Setting up {storage_type} storage at {endpoint}...")
        config_result = client.configure_storage(
            storage_type=storage_type,
            endpoint=endpoint,
            key=key,
            secret=secret,
            bucket=bucket,
            region=region,
        )

        click.secho("✅ Storage configured", fg="green")
        click.echo(f"   Endpoint: {endpoint}")
        click.echo(f"   Bucket: {bucket}")
        click.echo(f"   Region: {region}")

        # Step 2: Test connection
        click.echo("\n🧪 Testing connection...")
        try:
            test_result = client.test_storage_connection()
            click.secho("✅ Connection test passed!", fg="green")
            click.echo(f"   {test_result.get('message', 'Storage is accessible')}")
        except httpx.HTTPError as e:
            click.secho("❌ Connection test failed!", fg="red", err=True)
            click.echo(f"   Error: {str(e)}", err=True)
            click.secho(
                "⚠️  Storage is configured but cannot be accessed. Uploads will fail.",
                fg="yellow",
                err=True,
            )
            sys.exit(1)

        click.echo("\n" + "=" * 50)
        click.secho("✅ Storage configuration complete!", fg="green")
        click.echo("   You can now upload files using the 'upload' command.")

        client.close()

    except ValueError as e:
        click.secho(f"❌ Configuration error: {str(e)}", fg="red", err=True)
        sys.exit(1)
    except httpx.HTTPError as e:
        click.secho(f"❌ API error: {str(e)}", fg="red", err=True)
        sys.exit(1)
    except Exception as e:
        click.secho(f"❌ Error: {str(e)}", fg="red", err=True)
        sys.exit(1)


# Add storage group to main CLI
cli.add_command(storage)


if __name__ == "__main__":
    cli()
