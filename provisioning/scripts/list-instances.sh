#!/bin/bash
#
# GATE Platform - List Customer Instances
#
# Lists all provisioned customer instances and their status
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTANCES_DIR="${SCRIPT_DIR}/../../instances"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  GATE Platform - Customer Instances${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ ! -d "${INSTANCES_DIR}" ]; then
    echo -e "${YELLOW}No instances directory found.${NC}"
    echo "Run provision.sh to create your first customer instance."
    exit 0
fi

# Count instances
INSTANCE_COUNT=$(find "${INSTANCES_DIR}" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')

if [ "${INSTANCE_COUNT}" -eq 0 ]; then
    echo -e "${YELLOW}No customer instances found.${NC}"
    echo "Run provision.sh to create your first customer instance."
    exit 0
fi

echo -e "Found ${GREEN}${INSTANCE_COUNT}${NC} customer instance(s):"
echo ""
printf "%-20s %-25s %-10s %-8s %-15s\n" "CUSTOMER ID" "SUBDOMAIN" "STATUS" "API" "DB"
printf "%-20s %-25s %-10s %-8s %-15s\n" "--------------------" "-------------------------" "----------" "--------" "---------------"

for instance_dir in "${INSTANCES_DIR}"/*/; do
    if [ -d "${instance_dir}" ]; then
        customer_id=$(basename "${instance_dir}")
        
        # Read env vars safely (grep instead of source to avoid spaces issue)
        if [ -f "${instance_dir}/.env" ]; then
            subdomain=$(grep "^SUBDOMAIN=" "${instance_dir}/.env" | cut -d'=' -f2)
            api_port=$(grep "^EXTERNAL_API_PORT=" "${instance_dir}/.env" | cut -d'=' -f2)
            db_port=$(grep "^EXTERNAL_DB_PORT=" "${instance_dir}/.env" | cut -d'=' -f2)
            subdomain="${subdomain:-unknown}.gateplatform.com"
            api_port="${api_port:-N/A}"
            db_port="${db_port:-N/A}"
        else
            subdomain="unknown"
            api_port="N/A"
            db_port="N/A"
        fi
        
        # Check if running
        if [ -f "${instance_dir}/docker-compose.yml" ]; then
            cd "${instance_dir}"
            running_count=$(docker compose ps --status running 2>/dev/null | grep -c "running" 2>/dev/null || true)
            running_count=${running_count:-0}
            running_count=$(echo "$running_count" | tr -d '[:space:]')
            if [ -n "${running_count}" ] && [ "${running_count}" -gt 0 ] 2>/dev/null; then
                status="${GREEN}Running${NC}"
            else
                status="${YELLOW}Stopped${NC}"
            fi
            cd - > /dev/null
        else
            status="${RED}No Config${NC}"
        fi
        
        printf "%-20s %-25s ${status}%-10s %-8s %-15s\n" "${customer_id}" "${subdomain}" "" "${api_port}" "${db_port}"
    fi
done

echo ""
echo -e "${BLUE}Commands:${NC}"
echo "  Start:  cd instances/<customer_id> && ./start.sh"
echo "  Stop:   cd instances/<customer_id> && ./stop.sh"
echo "  Logs:   cd instances/<customer_id> && ./logs.sh"
echo ""
