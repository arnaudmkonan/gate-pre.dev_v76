import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.sentry_init import init_sentry
from app.api.routes import (
    queue, storage, vector_store, files, audit, queue_jobs, dlq,
    batch_schedule, upload, storage_callbacks, metadata, orchestration, silver_records, routing,
    extractions, normalization,    validation, vectorize, scheduler, internal_metadata, ingest_jobs, retry,
    monitoring, alerts, metrics, dlq_management, agents, export, review, templates, feedback, batch, duplicates,
    data_fabric, trade_compliance, reference_data, entry_reconciliation, ace_import, compliance_scorecard, shipments,
    compliance_integration
)
from app.api.routes import retry_policy
from app.api.routes.admin import override, queues, errors, organizations, roles, dashboard, file_type_mapping, retry_dlq
from app.core.config import settings
from app.core.database import engine
from app.models.base import Base

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Sentry error tracking
init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup
    logger.info("Starting application...")
    try:
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down application...")
    await engine.dispose()


# Create FastAPI app
app = FastAPI(
    title="Documentation Ingestion Platform",
    description="Multi-agent documentation ingestion API with LLM-powered analysis",
    version="0.2.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(storage.router)
app.include_router(queue.router)
app.include_router(vector_store.router)
app.include_router(files.router)
app.include_router(audit.router)
app.include_router(queue_jobs.router)
app.include_router(ingest_jobs.router)
app.include_router(retry.router)
app.include_router(dlq.router)
app.include_router(batch_schedule.router)
app.include_router(upload.router)
app.include_router(storage_callbacks.router)
app.include_router(silver_records.router)
app.include_router(metadata.router)
app.include_router(internal_metadata.router)
app.include_router(orchestration.router)
app.include_router(routing.router)
app.include_router(extractions.router)
app.include_router(normalization.router)
app.include_router(override.router)
app.include_router(queues.router)
app.include_router(errors.router)
app.include_router(organizations.router)
app.include_router(roles.router)
app.include_router(dashboard.router)
app.include_router(file_type_mapping.router)
app.include_router(retry_dlq.router)
app.include_router(validation.router)
app.include_router(vectorize.router)
app.include_router(scheduler.router)
app.include_router(monitoring.router)
app.include_router(alerts.router)
app.include_router(metrics.router)
app.include_router(dlq_management.router)
app.include_router(retry_policy.router)
app.include_router(agents.router)
app.include_router(export.router)
app.include_router(review.router)
app.include_router(templates.router)
app.include_router(feedback.router)
app.include_router(batch.router)
app.include_router(duplicates.router)
app.include_router(data_fabric.router)
app.include_router(trade_compliance.router)
app.include_router(reference_data.router)
app.include_router(entry_reconciliation.router)
app.include_router(ace_import.router)
app.include_router(compliance_scorecard.router)
app.include_router(shipments.router)
app.include_router(compliance_integration.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Documentation Ingestion Platform",
        "version": "0.1.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
