#!/bin/bash
#
# GATE Platform — Instance Status Report
#
# Shows current health, resource usage, and key metrics.
# Usage: ./status.sh
#

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Load instance env
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "${SCRIPT_DIR}/.env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi
source "${SCRIPT_DIR}/.env"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  GATE Platform — Instance Status${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Instance:${NC}  ${CUSTOMER_ID}"
echo -e "${YELLOW}Customer:${NC}  ${CUSTOMER_NAME}"
echo -e "${YELLOW}URL:${NC}       ${INSTANCE_URL}"
echo ""

# Service status
echo -e "${BLUE}--- Service Status ---${NC}"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  Docker Compose not available"
echo ""

# API health
echo -e "${BLUE}--- API Health ---${NC}"
API_URL="http://localhost:${EXTERNAL_API_PORT:-8000}"
HEALTH=$(curl -s "${API_URL}/health" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo -e "  Liveness:  ${GREEN}${HEALTH}${NC}"
else
    echo -e "  Liveness:  ${RED}UNREACHABLE${NC}"
fi

READY=$(curl -s "${API_URL}/api/health/ready" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo -e "  Readiness: ${GREEN}${READY}${NC}"
else
    echo -e "  Readiness: ${RED}UNREACHABLE${NC}"
fi
echo ""

# Database size
echo -e "${BLUE}--- Database ---${NC}"
DB_SIZE=$(docker compose exec -T db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -t -c "SELECT pg_size_pretty(pg_database_size('${POSTGRES_DB}'));" 2>/dev/null || echo "unavailable")
TABLE_COUNT=$(docker compose exec -T db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -t -c "SELECT count(*) FROM pg_tables WHERE schemaname = 'public';" 2>/dev/null || echo "unavailable")
echo "  Database size:  ${DB_SIZE}"
echo "  Table count:    ${TABLE_COUNT}"
echo ""

# Last backup
echo -e "${BLUE}--- Backups ---${NC}"
BACKUP_DIR="${SCRIPT_DIR}/backups"
if [ -d "${BACKUP_DIR}" ]; then
    LATEST_BACKUP=$(ls -t "${BACKUP_DIR}"/*.sql.gz 2>/dev/null | head -1)
    if [ -n "${LATEST_BACKUP}" ]; then
        BACKUP_SIZE=$(du -h "${LATEST_BACKUP}" | cut -f1)
        BACKUP_DATE=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "${LATEST_BACKUP}" 2>/dev/null || stat -c "%y" "${LATEST_BACKUP}" 2>/dev/null | cut -d. -f1)
        echo "  Latest:  ${LATEST_BACKUP}"
        echo "  Size:    ${BACKUP_SIZE}"
        echo "  Date:    ${BACKUP_DATE}"
    else
        echo -e "  ${YELLOW}No backups found${NC}"
    fi
    BACKUP_COUNT=$(ls "${BACKUP_DIR}"/*.sql.gz 2>/dev/null | wc -l)
    echo "  Total:   ${BACKUP_COUNT} backup(s)"
else
    echo -e "  ${YELLOW}No backup directory${NC}"
fi
echo ""

# Resource usage
echo -e "${BLUE}--- Resource Usage ---${NC}"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" 2>/dev/null || echo "  Stats unavailable"
echo ""

echo -e "${BLUE}========================================${NC}"
