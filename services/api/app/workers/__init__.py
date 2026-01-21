# Import all worker modules to ensure Celery task registration
from app.workers import (
    dispatch,
    ingest_worker,
    retry_worker,
    batch_runner,
    metadata_enqueue,
    process_ingest_batch,
    ingest_file_processor,
    metadata_processor,
    vectorize_worker,
    job_processor,
)

__all__ = [
    "dispatch",
    "ingest_worker",
    "retry_worker",
    "batch_runner",
    "metadata_enqueue",
    "process_ingest_batch",
    "ingest_file_processor",
    "metadata_processor",
    "vectorize_worker",
    "job_processor",
]
