#!/bin/bash
#
# Initialize the customer database and create first admin user
#

set -e

# Get environment variables directly using grep (safer than sourcing)
POSTGRES_USER=$(grep "^POSTGRES_USER=" .env | cut -d'=' -f2 | tr -d '\r')
FIRST_ADMIN_EMAIL=$(grep "^FIRST_ADMIN_EMAIL=" .env | cut -d'=' -f2 | tr -d '\r')
FIRST_ADMIN_PASSWORD=$(grep "^FIRST_ADMIN_PASSWORD=" .env | cut -d'=' -f2 | tr -d '\r')

# Use defaults if not found
POSTGRES_USER=${POSTGRES_USER:-gate_user}

echo "Waiting for database to be ready..."
until docker compose exec -T db pg_isready -U ${POSTGRES_USER} 2>/dev/null; do
    echo "  Database not ready, waiting..."
    sleep 2
done

echo "Database is ready!"

echo "Creating database tables..."
docker compose exec -T api python << 'PYTHON'
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from app.models.base import Base
from app.core.config import settings

# Import all models to register them
from app.models import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use sync connection
sync_url = settings.database_url
if "+asyncpg" in sync_url:
    sync_url = sync_url.replace("+asyncpg", "+psycopg2")
if "postgresql://" in sync_url and "+psycopg2" not in sync_url:
    sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")

engine = create_engine(sync_url, echo=False)

# Create tables one by one to handle errors per table
with engine.connect() as conn:
    for table in Base.metadata.sorted_tables:
        try:
            # Use autobegin and commit each table separately
            table.create(conn, checkfirst=True)
            conn.commit()
            print(f"  Created table: {table.name}")
        except ProgrammingError as e:
            if "already exists" in str(e).lower():
                print(f"  Table {table.name} or its indexes already exist (OK)")
                conn.rollback()
            else:
                print(f"  Error creating {table.name}: {e}")
                conn.rollback()
        except Exception as e:
            print(f"  Error creating {table.name}: {e}")
            conn.rollback()

# Verify
with engine.connect() as conn:
    result = conn.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"))
    count = result.scalar()
    print(f"\nTotal tables created: {count}")

engine.dispose()
print("Table creation complete!")
PYTHON

echo ""
echo "Creating first admin user (with default client)..."
docker compose exec -T api python << PYTHON
import asyncio
import uuid
from sqlalchemy import select
from app.models.client_portal import ClientUser, ClientUserRole, ClientUserStatus
from app.models.client import Client, ClientStatus
from app.core.database import AsyncSessionLocal

async def create_admin():
    async with AsyncSessionLocal() as session:
        # Check if admin user already exists
        result = await session.execute(
            select(ClientUser).where(ClientUser.email == "${FIRST_ADMIN_EMAIL}")
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"Admin user {existing.email} already exists")
            return
        
        # First, create a default client (or find existing)
        result = await session.execute(
            select(Client).where(Client.name == "Default Broker Account")
        )
        default_client = result.scalar_one_or_none()
        
        if not default_client:
            default_client = Client(
                name="Default Broker Account",
                status=ClientStatus.ACTIVE.value,
            )
            session.add(default_client)
            await session.flush()  # Get the ID
            print(f"Created default client: Default Broker Account")
        
        # Create admin user
        admin = ClientUser(
            email="${FIRST_ADMIN_EMAIL}",
            first_name="Admin",
            last_name="User",
            role=ClientUserRole.ADMIN.value,
            status=ClientUserStatus.ACTIVE.value,
            client_id=default_client.id,
        )
        admin.set_password("${FIRST_ADMIN_PASSWORD}")
        
        session.add(admin)
        await session.commit()
        print(f"Created admin user: ${FIRST_ADMIN_EMAIL}")

asyncio.run(create_admin())
PYTHON

echo ""
echo "Seeding extraction templates..."
docker compose exec -T api python << 'PYTHON'
import asyncio
from app.core.database import AsyncSessionLocal
from app.services.template_loader_service import TemplateLoaderService, DOCUMENT_TYPES

async def seed_templates():
    async with AsyncSessionLocal() as session:
        print(f"Loading {len(DOCUMENT_TYPES)} document templates...")
        
        for doc_type in DOCUMENT_TYPES:
            try:
                template = await TemplateLoaderService.seed_template(session, doc_type)
                if template:
                    print(f"  ✓ {template.name} ({len(template.field_definitions) if template.field_definitions else 0} fields)")
            except Exception as e:
                print(f"  ✗ {doc_type}: {e}")
        
        print("\nTemplate seeding complete!")

asyncio.run(seed_templates())
PYTHON

echo ""
echo "========================================="
echo "  Customer instance initialized!"
echo "========================================="
echo ""
echo "Admin Login Credentials:"
echo "  Email:    ${FIRST_ADMIN_EMAIL}"
echo "  Password: ${FIRST_ADMIN_PASSWORD}"
echo ""
echo "Extraction Templates: ${#DOCUMENT_TYPES[@]} loaded"
echo ""
echo "IMPORTANT: Change this password after first login!"
echo ""
