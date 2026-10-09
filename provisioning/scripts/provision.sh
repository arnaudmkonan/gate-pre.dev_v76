#!/bin/bash
#
# GATE Platform - Customer Instance Provisioning Script
#
# This script provisions a new customer instance by:
# 1. Creating a new directory with customer-specific config
# 2. Generating unique secrets
# 3. Creating the customer's docker-compose.yml
# 4. Initializing the database
# 5. Creating the first admin user
#
# Usage: ./provision.sh <customer_id> <customer_name> <admin_email> <subdomain>
#
# Example: ./provision.sh acme-imports "Acme Imports LLC" admin@acme.com acme
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check arguments
if [ "$#" -lt 4 ]; then
    echo -e "${RED}Error: Missing arguments${NC}"
    echo "Usage: $0 <customer_id> <customer_name> <admin_email> <subdomain>"
    echo "Example: $0 acme-imports \"Acme Imports LLC\" admin@acme.com acme"
    exit 1
fi

CUSTOMER_ID="$1"
CUSTOMER_NAME="$2"
ADMIN_EMAIL="$3"
SUBDOMAIN="$4"
GATE_VERSION="${5:-latest}"  # Optional: pin image version

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/../templates"
INSTANCES_DIR="${SCRIPT_DIR}/../../instances"
CUSTOMER_DIR="${INSTANCES_DIR}/${CUSTOMER_ID}"

# Ports - we'll use a base port and offset by customer number
BASE_API_PORT=8100
BASE_WEB_PORT=3100
BASE_DB_PORT=5500
BASE_REDIS_PORT=6400
BASE_FLOWER_PORT=5600

# Get next available port offset by counting existing instances
INSTANCE_COUNT=$(find "${INSTANCES_DIR}" -maxdepth 1 -type d 2>/dev/null | wc -l)
PORT_OFFSET=$INSTANCE_COUNT

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  GATE Platform - Customer Provisioning${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Customer ID:${NC}    ${CUSTOMER_ID}"
echo -e "${YELLOW}Customer Name:${NC}  ${CUSTOMER_NAME}"
echo -e "${YELLOW}Admin Email:${NC}    ${ADMIN_EMAIL}"
echo -e "${YELLOW}Subdomain:${NC}      ${SUBDOMAIN}.gateplatform.com"
echo ""

# Check if customer already exists
if [ -d "${CUSTOMER_DIR}" ]; then
    echo -e "${RED}Error: Customer instance already exists at ${CUSTOMER_DIR}${NC}"
    exit 1
fi

# Create customer directory
echo -e "${GREEN}Creating customer directory...${NC}"
mkdir -p "${CUSTOMER_DIR}"

# Generate secrets
echo -e "${GREEN}Generating unique secrets...${NC}"
SECRET_KEY=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 16)
REDIS_PASSWORD=$(openssl rand -hex 16)
FIRST_USER_PASSWORD=$(openssl rand -base64 12)

# Calculate ports
API_PORT=$((BASE_API_PORT + PORT_OFFSET))
WEB_PORT=$((BASE_WEB_PORT + PORT_OFFSET))
DB_PORT=$((BASE_DB_PORT + PORT_OFFSET))
REDIS_PORT=$((BASE_REDIS_PORT + PORT_OFFSET))
FLOWER_PORT=$((BASE_FLOWER_PORT + PORT_OFFSET))

echo -e "${GREEN}Assigned ports:${NC}"
echo "  API:    ${API_PORT}"
echo "  Web:    ${WEB_PORT}"  
echo "  DB:     ${DB_PORT}"
echo "  Redis:  ${REDIS_PORT}"
echo "  Flower: ${FLOWER_PORT}"

# Create .env file
echo -e "${GREEN}Creating environment configuration...${NC}"
cat > "${CUSTOMER_DIR}/.env" << EOF
# GATE Platform - Customer Instance Configuration
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Customer: ${CUSTOMER_NAME}

# Instance Identification
CUSTOMER_ID=${CUSTOMER_ID}
CUSTOMER_NAME=${CUSTOMER_NAME}
SUBDOMAIN=${SUBDOMAIN}
INSTANCE_URL=https://${SUBDOMAIN}.gateplatform.com
GATE_VERSION=${GATE_VERSION}

# Database Configuration
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=gate_${CUSTOMER_ID//[-]/_}
POSTGRES_USER=gate_user
POSTGRES_PASSWORD=${DB_PASSWORD}
DATABASE_URL=postgresql://gate_user:${DB_PASSWORD}@db:5432/gate_${CUSTOMER_ID//[-]/_}

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

# Security
SECRET_KEY=${SECRET_KEY}
JWT_SECRET=${SECRET_KEY}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
ENVIRONMENT=production
DEBUG=false

# External Ports (for reverse proxy)
EXTERNAL_API_PORT=${API_PORT}
EXTERNAL_WEB_PORT=${WEB_PORT}
EXTERNAL_DB_PORT=${DB_PORT}
EXTERNAL_REDIS_PORT=${REDIS_PORT}
EXTERNAL_FLOWER_PORT=${FLOWER_PORT}

# Email Configuration (SMTP)
SMTP_HOST=\${SMTP_HOST:-}
SMTP_PORT=\${SMTP_PORT:-587}
SMTP_USER=\${SMTP_USER:-}
SMTP_PASSWORD=\${SMTP_PASSWORD:-}
SMTP_FROM_EMAIL=noreply@gateplatform.com
SMTP_FROM_NAME=GATE Platform

# First Admin User
FIRST_ADMIN_EMAIL=${ADMIN_EMAIL}
FIRST_ADMIN_PASSWORD=${FIRST_USER_PASSWORD}

# Storage Configuration
STORAGE_TYPE=local
STORAGE_LOCAL_PATH=/app/storage

# Celery Configuration
CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/1
CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/2

# Sentry (optional)
SENTRY_DSN=

# OpenAI Configuration
OPENAI_API_KEY=\${OPENAI_API_KEY:-}

# ACE Configuration
ACE_ENVIRONMENT=cert
ACE_CLIENT_CERTIFICATE_PATH=/app/certs/ace_client.pem
ACE_PRIVATE_KEY_PATH=/app/certs/ace_private.key
EOF

# Create docker-compose.yml
echo -e "${GREEN}Creating docker-compose configuration...${NC}"
cat > "${CUSTOMER_DIR}/docker-compose.yml" << 'EOF'
version: '3.8'

services:
  db:
    image: pgvector/pgvector:pg15
    container_name: gate_${CUSTOMER_ID}_db
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init-db.sql:ro
    ports:
      - "${EXTERNAL_DB_PORT}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: gate_${CUSTOMER_ID}_redis
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "${EXTERNAL_REDIS_PORT}:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  api:
    image: gate-platform/api:latest
    container_name: gate_${CUSTOMER_ID}_api
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - SECRET_KEY=${SECRET_KEY}
      - ENVIRONMENT=${ENVIRONMENT}
      - CUSTOMER_ID=${CUSTOMER_ID}
    volumes:
      - storage_data:/app/storage
      - ./certs:/app/certs:ro
    ports:
      - "${EXTERNAL_API_PORT}:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  worker:
    image: gate-platform/api:latest
    container_name: gate_${CUSTOMER_ID}_worker
    command: celery -A app.core.celery_app worker --loglevel=info
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
    volumes:
      - storage_data:/app/storage
    restart: unless-stopped

  beat:
    image: gate-platform/api:latest
    container_name: gate_${CUSTOMER_ID}_beat
    command: celery -A app.core.celery_app beat --loglevel=info
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
    restart: unless-stopped

  flower:
    image: mher/flower:0.9.7
    container_name: gate_${CUSTOMER_ID}_flower
    command: celery flower --broker=${CELERY_BROKER_URL}
    depends_on:
      - redis
    ports:
      - "${EXTERNAL_FLOWER_PORT}:5555"
    restart: unless-stopped

  frontend:
    image: gate-platform/web:latest
    container_name: gate_${CUSTOMER_ID}_web
    depends_on:
      - api
    environment:
      - VITE_API_URL=https://${SUBDOMAIN}.gateplatform.com/api
    ports:
      - "${EXTERNAL_WEB_PORT}:80"
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  storage_data:

networks:
  default:
    name: gate_${CUSTOMER_ID}_network
EOF

# Create init script
echo -e "${GREEN}Creating initialization script...${NC}"
cat > "${CUSTOMER_DIR}/init.sh" << 'INITEOF'
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
            select(ClientUser).where(ClientUser.email == "\${FIRST_ADMIN_EMAIL}")
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
            email="\${FIRST_ADMIN_EMAIL}",
            first_name="Admin",
            last_name="User",
            role=ClientUserRole.ADMIN.value,
            status=ClientUserStatus.ACTIVE.value,
            client_id=default_client.id,
        )
        admin.set_password("\${FIRST_ADMIN_PASSWORD}")
        
        session.add(admin)
        await session.commit()
        print(f"Created admin user: \${FIRST_ADMIN_EMAIL}")

asyncio.run(create_admin())
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
echo "IMPORTANT: Change this password after first login!"
echo ""
INITEOF
chmod +x "${CUSTOMER_DIR}/init.sh"

# Create start/stop scripts
echo -e "${GREEN}Creating management scripts...${NC}"
cat > "${CUSTOMER_DIR}/start.sh" << 'EOF'
#!/bin/bash
docker compose up -d
echo "Instance starting... Check status with: docker compose ps"
EOF
chmod +x "${CUSTOMER_DIR}/start.sh"

cat > "${CUSTOMER_DIR}/stop.sh" << 'EOF'
#!/bin/bash
docker compose down
echo "Instance stopped."
EOF
chmod +x "${CUSTOMER_DIR}/stop.sh"

cat > "${CUSTOMER_DIR}/logs.sh" << 'EOF'
#!/bin/bash
docker compose logs -f ${1:-api}
EOF
chmod +x "${CUSTOMER_DIR}/logs.sh"

# Create README
echo -e "${GREEN}Creating documentation...${NC}"
cat > "${CUSTOMER_DIR}/README.md" << EOF
# GATE Platform - ${CUSTOMER_NAME}

**Customer ID:** ${CUSTOMER_ID}
**Subdomain:** ${SUBDOMAIN}.gateplatform.com
**Created:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")

## Quick Start

1. Start the instance:
   \`\`\`bash
   ./start.sh
   \`\`\`

2. Initialize the database (first time only):
   \`\`\`bash
   ./init.sh
   \`\`\`

3. Access the platform:
   - Web UI: http://localhost:${WEB_PORT} (or https://${SUBDOMAIN}.gateplatform.com)
   - API: http://localhost:${API_PORT} (or https://${SUBDOMAIN}.gateplatform.com/api)

4. Stop the instance:
   \`\`\`bash
   ./stop.sh
   \`\`\`

## Initial Admin Credentials

- **Email:** ${ADMIN_EMAIL}
- **Password:** ${FIRST_USER_PASSWORD}

⚠️ **IMPORTANT:** Change this password after first login!

## Port Mappings

| Service | Container Port | External Port |
|---------|----------------|---------------|
| API     | 8000           | ${API_PORT}   |
| Web     | 80             | ${WEB_PORT}   |
| DB      | 5432           | ${DB_PORT}    |
| Redis   | 6379           | ${REDIS_PORT} |
| Flower  | 5555           | ${FLOWER_PORT}|

## Management Commands

\`\`\`bash
# View logs
./logs.sh          # API logs
./logs.sh worker   # Worker logs
./logs.sh db       # Database logs

# Access database
docker compose exec db psql -U gate_user -d gate_${CUSTOMER_ID//[-]/_}

# Run migrations
docker compose exec api alembic upgrade head

# Backup database
docker compose exec db pg_dump -U gate_user gate_${CUSTOMER_ID//[-]/_} > backup.sql
\`\`\`

## Directory Structure

\`\`\`
${CUSTOMER_ID}/
├── .env                 # Environment configuration (secrets)
├── docker-compose.yml   # Docker Compose configuration
├── init.sh              # Database initialization script
├── start.sh             # Start instance
├── stop.sh              # Stop instance
├── logs.sh              # View logs
├── certs/               # SSL and ACE certificates
└── README.md            # This file
\`\`\`
EOF

# Create init-db.sql for database extensions
cat > "${CUSTOMER_DIR}/init-db.sql" << 'SQLEOF'
-- Initialize database with required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
SQLEOF

# Create certificates directory
mkdir -p "${CUSTOMER_DIR}/certs"
touch "${CUSTOMER_DIR}/certs/.gitkeep"

# Copy operational scripts from templates
echo -e "${GREEN}Installing operational scripts...${NC}"
cp "${TEMPLATE_DIR}/upgrade.sh" "${CUSTOMER_DIR}/upgrade.sh"
cp "${TEMPLATE_DIR}/status.sh" "${CUSTOMER_DIR}/status.sh"
cp "${TEMPLATE_DIR}/backup.sh" "${CUSTOMER_DIR}/backup.sh"
chmod +x "${CUSTOMER_DIR}/upgrade.sh" "${CUSTOMER_DIR}/status.sh" "${CUSTOMER_DIR}/backup.sh"

# Create backups directory
mkdir -p "${CUSTOMER_DIR}/backups"

# Summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Provisioning Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Customer Directory:${NC} ${CUSTOMER_DIR}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Build Docker images (if not already done):"
echo "     docker build -t gate-platform/api:latest ./services/api"
echo "     docker build -t gate-platform/web:latest ./apps/web"
echo ""
echo "  2. Start the customer instance:"
echo "     cd ${CUSTOMER_DIR}"
echo "     ./start.sh"
echo ""
echo "  3. Initialize the database:"
echo "     ./init.sh"
echo ""
echo "  4. Configure DNS/reverse proxy for ${SUBDOMAIN}.gateplatform.com"
echo ""
echo -e "${BLUE}Admin Credentials:${NC}"
echo -e "  Email:    ${GREEN}${ADMIN_EMAIL}${NC}"
echo -e "  Password: ${GREEN}${FIRST_USER_PASSWORD}${NC}"
echo ""
echo -e "${RED}⚠️  Save the password! It will not be shown again.${NC}"
echo ""
