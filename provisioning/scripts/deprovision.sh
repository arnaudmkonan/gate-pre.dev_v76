#!/bin/bash
#
# GATE Platform - Deprovision Customer Instance
#
# This script removes a customer instance:
# 1. Stops all containers
# 2. Removes containers and volumes
# 3. Optionally backs up data
# 4. Removes the customer directory
#
# Usage: ./deprovision.sh <customer_id> [--no-backup]
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check arguments
if [ "$#" -lt 1 ]; then
    echo -e "${RED}Error: Missing customer_id${NC}"
    echo "Usage: $0 <customer_id> [--no-backup]"
    exit 1
fi

CUSTOMER_ID="$1"
NO_BACKUP="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTANCES_DIR="${SCRIPT_DIR}/../../instances"
CUSTOMER_DIR="${INSTANCES_DIR}/${CUSTOMER_ID}"
BACKUPS_DIR="${SCRIPT_DIR}/../../backups"

# Check if instance exists
if [ ! -d "${CUSTOMER_DIR}" ]; then
    echo -e "${RED}Error: Customer instance not found: ${CUSTOMER_ID}${NC}"
    echo "Available instances:"
    ls -1 "${INSTANCES_DIR}" 2>/dev/null || echo "  (none)"
    exit 1
fi

echo -e "${RED}========================================${NC}"
echo -e "${RED}  WARNING: Customer Deprovisioning${NC}"
echo -e "${RED}========================================${NC}"
echo ""
echo -e "Customer ID: ${YELLOW}${CUSTOMER_ID}${NC}"
echo ""
echo -e "${RED}This will PERMANENTLY DELETE:${NC}"
echo "  - All containers for this customer"
echo "  - All data volumes (database, files)"
echo "  - All configuration files"
echo ""

# Confirmation
read -p "Type the customer ID to confirm deletion: " CONFIRM
if [ "${CONFIRM}" != "${CUSTOMER_ID}" ]; then
    echo -e "${GREEN}Aborted. No changes made.${NC}"
    exit 0
fi

echo ""

# Backup database unless --no-backup
if [ "${NO_BACKUP}" != "--no-backup" ]; then
    echo -e "${GREEN}Creating database backup...${NC}"
    mkdir -p "${BACKUPS_DIR}"
    BACKUP_FILE="${BACKUPS_DIR}/${CUSTOMER_ID}_$(date +%Y%m%d_%H%M%S).sql"
    
    cd "${CUSTOMER_DIR}"
    if docker compose ps db --status running 2>/dev/null | grep -q "running"; then
        source .env
        docker compose exec -T db pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} > "${BACKUP_FILE}" 2>/dev/null || true
        if [ -s "${BACKUP_FILE}" ]; then
            echo -e "  Saved to: ${GREEN}${BACKUP_FILE}${NC}"
        else
            echo -e "  ${YELLOW}Warning: Backup may be empty (database not running?)${NC}"
        fi
    else
        echo -e "  ${YELLOW}Warning: Database not running, skipping backup${NC}"
    fi
    cd - > /dev/null
fi

# Stop and remove containers
echo -e "${GREEN}Stopping containers...${NC}"
cd "${CUSTOMER_DIR}"
docker compose down -v 2>/dev/null || true
cd - > /dev/null

# Remove customer directory
echo -e "${GREEN}Removing customer directory...${NC}"
rm -rf "${CUSTOMER_DIR}"

# Summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deprovisioning Complete${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Customer ${YELLOW}${CUSTOMER_ID}${NC} has been removed."
if [ -n "${BACKUP_FILE}" ] && [ -f "${BACKUP_FILE}" ]; then
    echo -e "Database backup saved to: ${GREEN}${BACKUP_FILE}${NC}"
fi
echo ""
