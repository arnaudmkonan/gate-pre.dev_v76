#!/bin/bash
#
# GATE Platform — Instance Upgrade Script
#
# Upgrades a customer instance to a new platform version.
# Usage: ./upgrade.sh [version]
#
# If version is omitted, pulls 'latest'.
# Example: ./upgrade.sh v0.3.0
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="${1:-latest}"

# Load instance env
if [ ! -f "${SCRIPT_DIR}/.env" ]; then
    echo -e "${RED}Error: .env file not found. Are you in an instance directory?${NC}"
    exit 1
fi
source "${SCRIPT_DIR}/.env"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  GATE Platform — Instance Upgrade${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Instance:${NC}  ${CUSTOMER_ID} (${CUSTOMER_NAME})"
echo -e "${YELLOW}Version:${NC}   ${VERSION}"
echo ""

# Step 1: Pre-upgrade backup
echo -e "${GREEN}[1/6] Creating pre-upgrade backup...${NC}"
BACKUP_DIR="${SCRIPT_DIR}/backups"
mkdir -p "${BACKUP_DIR}"
BACKUP_FILE="${BACKUP_DIR}/pre-upgrade-$(date +%Y%m%d_%H%M%S).sql.gz"

docker compose exec -T db pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} | gzip > "${BACKUP_FILE}"
echo "  Backup saved: ${BACKUP_FILE}"

# Step 2: Pull new images
echo -e "${GREEN}[2/6] Pulling gate-platform images (${VERSION})...${NC}"
docker pull gate-platform/api:${VERSION} 2>/dev/null || echo "  Using local image"
docker pull gate-platform/web:${VERSION} 2>/dev/null || echo "  Using local image"

# Step 3: Stop worker and beat (graceful)
echo -e "${GREEN}[3/6] Stopping background workers (graceful)...${NC}"
docker compose stop worker beat 2>/dev/null || true
sleep 3

# Step 4: Run database migrations
echo -e "${GREEN}[4/6] Running database migrations...${NC}"
docker compose run --rm api alembic upgrade head
echo "  Migrations complete"

# Step 5: Restart all services
echo -e "${GREEN}[5/6] Restarting services...${NC}"
docker compose up -d

# Step 6: Verify health
echo -e "${GREEN}[6/6] Checking health...${NC}"
sleep 5  # Wait for services to start

for i in 1 2 3 4 5; do
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${EXTERNAL_API_PORT:-8000}/health 2>/dev/null || echo "000")
    if [ "$RESPONSE" == "200" ]; then
        echo -e "  ${GREEN}✅ API healthy${NC}"
        break
    fi
    echo "  Waiting for API... (attempt $i/5)"
    sleep 5
done

if [ "$RESPONSE" != "200" ]; then
    echo -e "  ${RED}⚠ API not responding. Check logs: docker compose logs api${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Upgrade complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  Backup:  ${BACKUP_FILE}"
echo -e "  Version: ${VERSION}"
echo -e "  Rollback: gunzip < ${BACKUP_FILE} | docker compose exec -T db psql -U ${POSTGRES_USER} ${POSTGRES_DB}"
