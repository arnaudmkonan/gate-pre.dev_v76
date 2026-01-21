"""
Ingestion SDK for document processing.

Usage:
    from sdk import IngestionClient

    client = IngestionClient(base_url="http://localhost:8000")
    job = client.upload_file("document.pdf")
    print(f"Job ID: {job['job_id']}")

    status = client.get_job_status(str(job['job_id']))
    print(f"Status: {status['status']}")

    client.close()
"""

from sdk.client import IngestionClient

__version__ = "0.1.0"
__all__ = ["IngestionClient"]
