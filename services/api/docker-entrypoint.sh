#!/bin/bash
set -euo pipefail

echo "Bootstrapping database schema and running migrations..."
python - <<'PY'
from sqlalchemy import create_engine, inspect
from app.core.config import settings
from app.models.base import Base
import app.models  # noqa: F401 — register all ORM tables

sync_url = settings.database_url_sync or settings.database_url.replace("+asyncpg", "+psycopg2")
if sync_url.startswith("postgresql://"):
    sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(sync_url)
inspector = inspect(engine)
existing = set(inspector.get_table_names())

# On a brand-new empty Postgres database, bootstrap base ORM tables first if Alembic has never run
if "alembic_version" not in existing and "entries" not in existing:
    print("Greenfield database detected — creating baseline ORM schema...")
    for table in Base.metadata.sorted_tables:
        with engine.begin() as conn:
            table.create(conn, checkfirst=True)
    engine.dispose()
    import subprocess
    subprocess.run(["alembic", "stamp", "head"], check=True)
else:
    engine.dispose()
PY

alembic upgrade head

exec "$@"
