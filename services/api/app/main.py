import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.auth import AuthenticationMiddleware
from app.middleware.api_version import ApiVersionMiddleware, CURRENT_API_VERSION, SUPPORTED_VERSIONS

from app.sentry_init import init_sentry
from app.core.exceptions import GateError
from app.api.routes import (
    queue, storage, vector_store, files, audit, queue_jobs, dlq,
    batch_schedule, upload, storage_callbacks, metadata, orchestration, silver_records, routing,
    extractions, normalization, validation, vectorize, scheduler, internal_metadata, ingest_jobs, retry,
    monitoring, alerts, metrics, dlq_management, agents, export, review, templates, feedback, batch, duplicates,
    data_fabric, trade_compliance, reference_data, entry_reconciliation, ace_import, compliance_scorecard, shipments,
    compliance_integration, entries, duty_calculator, clients, ace_settings, isf, broker_management, client_templates,
    client_preferences, client_reports, client_billing, client_portal, client_dashboard, document_requests,
    entry_lifecycle, analytics, production_ready, email, cargowise_export, leads, landing_analytics, embeddings,
    shipment_assembly, entry_prep, ace_transmit, webhooks, api_keys, notifications
)

from app.api.routes import retry_policy
from app.api.routes.admin import override, queues, errors, organizations, roles, dashboard, file_type_mapping, retry_dlq
from app.core.config import settings
from app.core.database import engine
from app.models.base import Base
from sqlalchemy import text

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
        # Check database connectivity
        # Table creation is handled by init.sh script to work around index conflicts
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            
            # Check if tables exist
            result = await conn.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'entries')")
            )
            if result.scalar():
                logger.info("Database tables are ready")
            else:
                logger.warning("Database tables not found - run init.sh to create them")
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        logger.warning("Application starting without database verification")

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

# Add Rate Limiting middleware (before CORS so it can reject early)
app.add_middleware(RateLimitMiddleware)

# Add Authentication middleware
app.add_middleware(AuthenticationMiddleware)

# Add API Versioning middleware (URL rewriting /api/v1/* → /api/*)
app.add_middleware(ApiVersionMiddleware)

# Add CORS middleware with environment-based origins
# In development: allows all origins
# In production: uses CORS_ORIGINS env variable
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Tier",
        "X-API-Version",
        "Deprecation",
        "Sunset",
    ],
)

# =============================================================================
# GLOBAL EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(GateError)
async def gate_error_handler(request: Request, exc: GateError):
    """Handle all domain-specific GATE exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError as 400 Bad Request."""
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "BAD_REQUEST",
                "message": str(exc),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — log and return 500."""
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred" if settings.environment != "development" else str(exc),
            }
        },
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
app.include_router(entries.router)
app.include_router(entry_prep.router)
app.include_router(duty_calculator.router)
app.include_router(clients.router)
app.include_router(ace_settings.router)
app.include_router(ace_transmit.router)
app.include_router(isf.router)
app.include_router(broker_management.router)
app.include_router(client_templates.router)
app.include_router(client_preferences.router)
app.include_router(client_reports.router)
app.include_router(client_billing.router)
app.include_router(client_portal.router)
app.include_router(client_dashboard.router)
app.include_router(document_requests.router)
app.include_router(entry_lifecycle.router)
app.include_router(analytics.router)
app.include_router(production_ready.router)
app.include_router(email.router)
app.include_router(cargowise_export.router)
app.include_router(leads.router)
app.include_router(landing_analytics.router)
app.include_router(embeddings.router)
app.include_router(shipment_assembly.router)
app.include_router(webhooks.router)
app.include_router(api_keys.router)
app.include_router(notifications.router)


@app.get("/health")
async def health_check():
    """Lightweight liveness probe — no external deps checked."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/api/health/ready")
async def readiness_check():
    """
    Deep readiness probe — checks database, Redis, and reports status.

    Used by load balancers and orchestrators to determine if the
    instance is ready to serve traffic.
    """
    import time as _time
    checks = {}
    overall = "ready"

    # Database check
    try:
        async with engine.begin() as conn:
            start = _time.monotonic()
            await conn.execute(text("SELECT 1"))
            latency_ms = round((_time.monotonic() - start) * 1000, 1)
            checks["database"] = {"status": "ok", "latency_ms": latency_ms}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}
        overall = "not_ready"

    # Redis check
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(
            f"redis://{settings.redis_host}:{settings.redis_port}",
            password=settings.redis_password or None,
            decode_responses=True,
        )
        start = _time.monotonic()
        await r.ping()
        latency_ms = round((_time.monotonic() - start) * 1000, 1)
        checks["redis"] = {"status": "ok", "latency_ms": latency_ms}
        await r.aclose()
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}
        overall = "not_ready"

    status_code = 200 if overall == "ready" else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "environment": settings.environment,
            "checks": checks,
        },
    )


@app.get("/api/health/info")
async def health_info():
    """
    Operational info — version, table count, uptime.

    Not for automated probes. For human operators and dashboards.
    """
    import sys
    info = {
        "name": "GATE Platform API",
        "version": "0.2.0",
        "environment": settings.environment,
        "python_version": sys.version.split()[0],
    }

    # Table count
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
            )
            info["table_count"] = result.scalar()
    except Exception:
        info["table_count"] = "unavailable"

    return info


@app.get("/api/health/cache")
async def cache_health():
    """Cache statistics endpoint."""
    from app.core.cache import get_cache_stats
    return get_cache_stats()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "GATE Platform",
        "version": "0.2.0",
        "api_version": CURRENT_API_VERSION,
        "docs": "/docs",
    }


@app.get("/api/versions")
async def api_versions():
    """List supported API versions."""
    return {
        "current": CURRENT_API_VERSION,
        "supported": SUPPORTED_VERSIONS,
        "deprecation_policy": "Unversioned /api/* URLs will be sunset on 2026-12-31. Use /api/v1/* instead.",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
