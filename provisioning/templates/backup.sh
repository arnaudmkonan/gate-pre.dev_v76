#!/bin/bash
#
# GATE Platform — Instance Backup Script
#
# Creates a compressed database backup.
# Usage: ./backup.sh [--quiet]
#
# Schedule via cron:
#   0 2 * * * /path/to/instances/customer-id/backup.sh --quiet
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUIET="${1:-}"

# Load instance env
source "${SCRIPT_DIR}/.env"

BACKUP_DIR="${SCRIPT_DIR}/backups"
mkdir -p "${BACKUP_DIR}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/gate_${CUSTOMER_ID}_${TIMESTAMP}.sql.gz"

# Create backup
docker compose exec -T db pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} | gzip > "${BACKUP_FILE}"

# Verify
if [ -s "${BACKUP_FILE}" ]; then
    SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    [ "$QUIET" != "--quiet" ] && echo "✅ Backup created: ${BACKUP_FILE} (${SIZE})"
else
    echo "❌ Backup failed: ${BACKUP_FILE} is empty" >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# Rotate — keep last 30 backups
BACKUP_COUNT=$(ls -1 "${BACKUP_DIR}"/gate_*.sql.gz 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt 30 ]; then
    ls -1t "${BACKUP_DIR}"/gate_*.sql.gz | tail -n +31 | xargs rm -f
    [ "$QUIET" != "--quiet" ] && echo "  Rotated: kept 30 of ${BACKUP_COUNT} backups"
fi
