"""Pytest configuration and fixtures for API tests."""

import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text, MetaData
from app.core.config import settings
from app.models.base import Base


# Clear SQLAlchemy reflection cache to ensure we see the latest schema
def _clear_sqlalchemy_cache():
    """Clear the SQLAlchemy table metadata cache."""
    # This ensures that when we create new sessions, they'll use the current database schema
    if hasattr(Base, 'metadata'):
        Base.metadata.clear()
    # Also clear any table-specific caches
    MetaData().clear()


@pytest.fixture(scope="session", autouse=True)
def clear_sqlalchemy_cache():
    """Clear SQLAlchemy cache at the start of all tests."""
    _clear_sqlalchemy_cache()
    yield


@pytest_asyncio.fixture(scope="function")
async def engine():
    """Create test database engine using the existing database."""
    # Use the same database as the application
    # Ensure we're using asyncpg for async operations
    db_url = settings.database_url
    if "postgresql://" in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    elif "postgresql+psycopg2://" in db_url:
        db_url = db_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")

    engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
        pool_size=1,
        max_overflow=0,
    )

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine):
    """Create a new database session for each test."""
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
        # Cleanup: delete test data from silver_records table
        try:
            await session.execute(text("DELETE FROM silver_records WHERE document_id LIKE 'doc_%'"))
            await session.commit()
        except:
            await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def session(engine):
    """Create a new database session for each test (alias for db_session)."""
    # Use default settings for a clean session
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Pre-test cleanup - ensure clean state before test runs
    tables_to_truncate = [
        "upload_events", "quarantine", "raw_vectors",
        "document_metadata", "silver_metadata", "raw_metadata",
        "dlq_entries", "batches"
    ]
    for table in tables_to_truncate:
        async with async_session() as pre_cleanup:
            try:
                await pre_cleanup.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                await pre_cleanup.commit()
            except:
                pass  # Table might not exist

    async with async_session() as session:
        yield session

    # Post-test cleanup with a separate connection to ensure clean state
    tables_to_truncate = [
        "upload_events", "quarantine", "raw_vectors",
        "document_metadata", "silver_metadata", "raw_metadata",
        "dlq_entries", "batches"
    ]
    for table in tables_to_truncate:
        async with async_session() as post_cleanup:
            try:
                await post_cleanup.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                await post_cleanup.commit()
            except:
                pass  # Table might not exist
