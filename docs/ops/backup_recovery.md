# Backup & Recovery Runbook

Complete guide for backup operations, recovery procedures, and disaster recovery scenarios.

## Overview

The backup system includes:
- Daily database backups to S3 (2 AM UTC)
- Daily storage backups to S3
- Hourly backup verification
- 30-day retention policy with PITR
- Automated cleanup of old backups

## Backup Schedule

| Task | Schedule | Retention | Location |
|------|----------|-----------|----------|
| Database Backup | Daily, 2 AM UTC | 30 days | S3 |
| Storage Backup | Daily, 2 AM UTC | 30 days | S3 |
| Backup Verify | Daily, 3 AM UTC | - | - |
| Backup Cleanup | Weekly | - | - |

## Manual Backup Operations

### Create Database Backup

```bash
cd services/api

# Run backup script
python tools/backup/pg_backup.py

# Or using Celery
celery -A app.core.celery_app call backup.database
```

### Create Storage Backup

```bash
python tools/backup/storage_backup.py

# Or using Celery
celery -A app.core.celery_app call backup.storage
```

### List Available Backups

```bash
# List database backups
aws s3 ls s3://doc-ingestion-backups/database/backups/ --recursive

# List storage backups
aws s3 ls s3://doc-ingestion-backups/storage/backups/ --recursive
```

## Recovery Procedures

### Database Recovery (Dry-Run)

Test restore without modifying production database:

```bash
python tools/backup/restore.py restore \
  --backup database/backups/backup-20240120-020000.sql.gz \
  --dry-run \
  --validate
```

### Database Recovery (Production)

```bash
# List available backups
python tools/backup/restore.py list

# Restore from specific backup
python tools/backup/restore.py restore \
  --backup database/backups/backup-20240120-020000.sql.gz \
  --validate
```

### Point-in-Time Recovery (PITR)

Available for last 7 days via Supabase:

```bash
# Via Supabase UI
# 1. Go to project dashboard
# 2. Click "Backups" in sidebar
# 3. Select desired backup timestamp
# 4. Click "Restore"

# Via Supabase CLI
supabase db pull --recovery-timestamp "2024-01-20T12:30:00Z"
```

## RTO and RPO Targets

**Recovery Time Objective (RTO)**: < 30 minutes
- Database restore: ~10 minutes
- Storage restore: ~15 minutes
- Verification: ~5 minutes

**Recovery Point Objective (RPO)**: < 1 hour
- Hourly verification checks
- Daily backups at 2 AM UTC
- Maximum data loss: 24 hours

## Disaster Recovery Scenarios

### Scenario 1: Accidental Data Deletion

**Cause**: User or application error deletes critical data

**Detection**:
- Monitoring alerts
- Application error logs
- User reports

**Recovery Steps**:

```bash
# 1. Assess scope
psql $DATABASE_URL -c "SELECT * FROM deleted_table LIMIT 1"

# 2. Create restore point
python tools/backup/restore.py list | head -5

# 3. Create backup of current state (if needed)
python tools/backup/pg_backup.py

# 4. Restore from backup before deletion
python tools/backup/restore.py restore \
  --backup database/backups/backup-20240119-020000.sql.gz \
  --dry-run

# 5. Verify data present
python tools/backup/restore.py restore \
  --backup database/backups/backup-20240119-020000.sql.gz \
  --validate

# 6. Execute recovery
python tools/backup/restore.py restore \
  --backup database/backups/backup-20240119-020000.sql.gz
```

### Scenario 2: Database Corruption

**Cause**: Hardware failure, query error, or software bug

**Detection**:
- Database connection failures
- Query errors
- Monitoring alerts

**Recovery Steps**:

```bash
# 1. Stop application to prevent further writes
# Disable traffic in Railway or load balancer

# 2. Check database status
psql $DATABASE_URL -c "SELECT 1"

# 3. Run VACUUM and ANALYZE on latest backup
# (in dry-run environment)

# 4. If corruption confirmed, restore
python tools/backup/restore.py restore \
  --backup database/backups/backup-latest.sql.gz

# 5. Run integrity checks
python tools/backup/restore.py restore \
  --backup database/backups/backup-latest.sql.gz \
  --dry-run \
  --validate

# 6. Resume application traffic
```

### Scenario 3: Storage Bucket Failure

**Cause**: S3 bucket issues, accidental deletion, or access errors

**Detection**:
- Upload/download failures
- 403/404 errors
- Monitoring alerts

**Recovery Steps**:

```bash
# 1. Check bucket status
aws s3api head-bucket --bucket doc-ingestion-raw

# 2. List available storage backups
aws s3 ls s3://doc-ingestion-backups/storage/backups/raw-files/

# 3. Download backup
aws s3 sync s3://doc-ingestion-backups/storage/backups/raw-files/backup-20240120/ \
  ./recovered-files/

# 4. Restore files to bucket
aws s3 sync ./recovered-files/ s3://doc-ingestion-raw --acl private

# 5. Verify restoration
aws s3 ls s3://doc-ingestion-raw --recursive
```

### Scenario 4: Complete System Failure

**Cause**: Total service outage, multiple component failures

**Detection**:
- Application unreachable
- Database unavailable
- All monitoring down

**Recovery Steps**:

```bash
# 1. Assess situation (likely 10-15 minutes)
# - Check all service statuses
# - Review error logs
# - Contact database provider

# 2. Full system recovery (30+ minutes)

# Create new infrastructure (if needed)
# OR restore from latest backup

# Database recovery
python tools/backup/restore.py restore \
  --backup database/backups/backup-latest.sql.gz

# Storage recovery
aws s3 sync s3://doc-ingestion-backups/storage/backups/ \
  s3://doc-ingestion-raw --exclude "*" --include "raw-files/*"

# Verify all systems
# - Database connectivity
# - Storage access
# - Application startup
# - Health checks

# Resume traffic
```

## Backup Encryption

All backups are encrypted at rest with AES-256.

### Manual Encryption

```bash
# Encrypt a file
python tools/backup/encrypt.py encrypt backup-file.sql.gz

# Decrypt a file
python tools/backup/encrypt.py decrypt backup-file.sql.gz.gpg

# Batch encrypt
python tools/backup/encrypt.py batch-encrypt /path/to/backups/

# Batch decrypt
python tools/backup/encrypt.py batch-decrypt /path/to/backups/
```

### Encryption Configuration

```python
# From environment
export ENCRYPTION_PASSPHRASE="strong-random-passphrase"

# Store in secure location
# - HashiCorp Vault
# - AWS Secrets Manager
# - Supabase Secrets
```

## Monitoring & Alerting

### Backup Success/Failure

Monitor Celery tasks:

```bash
celery -A app.core.celery_app events

# Or via database
SELECT * FROM celery_taskmeta
WHERE task_id LIKE 'backup.%'
ORDER BY date_done DESC
LIMIT 10;
```

### Backup Size Alerts

```sql
-- Check backup size trends
SELECT
  DATE(created_at) as date,
  COUNT(*) as count,
  SUM(size) / 1024 / 1024 as size_mb
FROM backup_metadata
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 7;
```

### Missing Backups

Check if recent backups exist:

```bash
# Should have backup within last 24 hours
aws s3 ls s3://doc-ingestion-backups/database/backups/ \
  --query 'Contents[0].{Key: Key, Modified: LastModified}' \
  --output table
```

## Retention Policy

### Database Backups

- Keep: Last 30 days
- Automation: Daily cleanup at 3 AM UTC
- Compliance: SOC 2 Type II

### Storage Backups

- Keep: Last 30 days
- Automation: Daily cleanup
- Compliance: SOC 2 Type II

### PITR

- Available: Last 7 days
- Provided by: Supabase PostgreSQL
- No action required

## Testing Recovery Procedures

### Monthly Recovery Test

Run monthly to ensure recovery procedures work:

```bash
# 1st of each month at 6 PM UTC

# Pick oldest available backup
BACKUP_KEY=$(aws s3 ls s3://doc-ingestion-backups/database/backups/ | head -1 | awk '{print $4}')

# Test restore in staging
python tools/backup/restore.py restore \
  --backup $BACKUP_KEY \
  --database-url $STAGING_DATABASE_URL \
  --validate

# Document results
echo "Recovery test $(date): Success" >> recovery-test.log
```

### Checklist

- [ ] List available backups
- [ ] Download specific backup
- [ ] Restore to test database
- [ ] Verify data integrity
- [ ] Test application connectivity
- [ ] Document findings
- [ ] Update procedures if needed

## Troubleshooting

### Backup fails with "permission denied"

```bash
# Check S3 credentials
aws s3 ls s3://doc-ingestion-backups/

# Verify IAM policy
aws iam get-user-policy --user-name backup-service --policy-name s3-backup
```

### Restore fails with "FATAL: remaining connection slots reserved"

```bash
# Kill idle connections
psql $DATABASE_URL -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
  AND pid <> pg_backend_pid();
"

# Retry restore
```

### Backup file is corrupted

```bash
# Verify integrity
tar -tzf backup-file.tar.gz > /dev/null

# If corrupted, restore from previous backup
python tools/backup/restore.py list
```

## Related Documentation

- [Supabase Production Configuration](./supabase-production.md)
- [Monitoring Guide](./monitoring.md)
- [CI/CD Secrets](../ci/SECRETS.md)
