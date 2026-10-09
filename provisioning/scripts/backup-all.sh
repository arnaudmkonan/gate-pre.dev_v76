#!/bin/bash
#
# GATE Platform - Backup All Customer Instances
#
# Creates database backups for all running customer instances
# Intended to be run as a cron job
#
# Usage: ./backup-all.sh [--keep-days 7]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTANCES_DIR="${SCRIPT_DIR}/../../instances"
BACKUPS_DIR="${SCRIPT_DIR}/../../backups"
KEEP_DAYS="${2:-7}"

# Create backup directory
mkdir -p "${BACKUPS_DIR}"

DATE=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${BACKUPS_DIR}/backup_${DATE}.log"

log() {
    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") $1" | tee -a "${LOG_FILE}"
}

log "Starting backup of all customer instances"

# Check if instances directory exists
if [ ! -d "${INSTANCES_DIR}" ]; then
    log "No instances directory found. Nothing to backup."
    exit 0
fi

# Backup each instance
BACKUP_COUNT=0
FAIL_COUNT=0

for instance_dir in "${INSTANCES_DIR}"/*/; do
    if [ -d "${instance_dir}" ]; then
        customer_id=$(basename "${instance_dir}")
        
        if [ ! -f "${instance_dir}/.env" ] || [ ! -f "${instance_dir}/docker-compose.yml" ]; then
            log "Skipping ${customer_id}: missing configuration files"
            continue
        fi
        
        source "${instance_dir}/.env"
        
        log "Backing up ${customer_id}..."
        
        cd "${instance_dir}"
        
        # Check if database is running
        if docker compose ps db --status running 2>/dev/null | grep -q "running"; then
            BACKUP_FILE="${BACKUPS_DIR}/${customer_id}_${DATE}.sql"
            
            if docker compose exec -T db pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} > "${BACKUP_FILE}" 2>/dev/null; then
                # Compress the backup
                gzip "${BACKUP_FILE}"
                SIZE=$(ls -lh "${BACKUP_FILE}.gz" | awk '{print $5}')
                log "  ✓ ${customer_id}: ${BACKUP_FILE}.gz (${SIZE})"
                BACKUP_COUNT=$((BACKUP_COUNT + 1))
            else
                log "  ✗ ${customer_id}: backup failed"
                FAIL_COUNT=$((FAIL_COUNT + 1))
                rm -f "${BACKUP_FILE}"
            fi
        else
            log "  - ${customer_id}: database not running, skipping"
        fi
        
        cd - > /dev/null
    fi
done

# Cleanup old backups
log "Cleaning up backups older than ${KEEP_DAYS} days..."
find "${BACKUPS_DIR}" -name "*.sql.gz" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true
find "${BACKUPS_DIR}" -name "*.log" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true

# Summary
log "========================================="
log "Backup Summary"
log "  Successful: ${BACKUP_COUNT}"
log "  Failed: ${FAIL_COUNT}"
log "  Log: ${LOG_FILE}"
log "========================================="

exit ${FAIL_COUNT}
