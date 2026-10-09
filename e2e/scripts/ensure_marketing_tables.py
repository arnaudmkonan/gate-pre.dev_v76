"""Create leads + landing analytics tables if migrations are behind."""
from sqlalchemy import create_engine, inspect

from app.api.routes.landing_analytics import LandingPageEvent
from app.api.routes.leads import Lead
from app.core.config import settings

sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
if sync_url.startswith("postgresql://") and "+psycopg2" not in sync_url:
    sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")

engine = create_engine(sync_url)
insp = inspect(engine)
existing = set(insp.get_table_names())
for table in (Lead.__table__, LandingPageEvent.__table__):
    if table.name not in existing:
        table.create(engine, checkfirst=True)
        print(f"created table: {table.name}")
    else:
        print(f"exists: {table.name}")

engine.dispose()
