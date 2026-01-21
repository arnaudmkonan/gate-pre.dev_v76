import logging
from typing import AsyncGenerator
from contextlib import contextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine

from app.core.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# ASYNC DATABASE (for FastAPI / async endpoints)
# =============================================================================

# Use async-compatible database URL
db_url = settings.database_url or "postgresql+asyncpg://postgres:postgres@localhost:5432/doc_ingestion"

# Ensure we're using asyncpg, not psycopg2
if "+asyncpg://" not in db_url:
    db_url = db_url.replace("+psycopg://", "+asyncpg://").replace("+psycopg2://", "+asyncpg://").replace("postgresql://", "postgresql+asyncpg://")

# Create async engine with asyncpg
engine = create_async_engine(
    db_url,
    echo=settings.debug,
    future=True,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=0,
    connect_args={"server_settings": {"jit": "off"}},
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session dependency for FastAPI."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


# =============================================================================
# SYNC DATABASE (for Celery workers)
# =============================================================================

# Use sync database URL for Celery
sync_db_url = settings.database_url_sync or "postgresql+psycopg2://postgres:postgres@localhost:5432/doc_ingestion"

# Ensure we're using psycopg2
if "+psycopg2://" not in sync_db_url:
    sync_db_url = sync_db_url.replace("+asyncpg://", "+psycopg2://").replace("+psycopg://", "+psycopg2://")
    if "postgresql://" in sync_db_url and "+psycopg2://" not in sync_db_url:
        sync_db_url = sync_db_url.replace("postgresql://", "postgresql+psycopg2://")

# Create sync engine for Celery workers
sync_engine = create_engine(
    sync_db_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Create sync session factory
SyncSessionLocal = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@contextmanager
def get_sync_db():
    """Get sync database session for Celery workers."""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Sync database session error: {e}")
        raise
    finally:
        session.close()

