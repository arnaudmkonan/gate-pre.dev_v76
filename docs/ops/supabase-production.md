# Supabase Production Configuration

Complete guide for managing the Supabase production environment, including infrastructure, security, backups, and disaster recovery.

## Overview

The production Supabase setup includes:
- PostgreSQL database with pgvector extension
- Row-level security (RLS) for data isolation
- Authentication with JWT tokens
- Storage buckets with access control
- Automated backups with PITR support
- Monitoring and alerting

## Infrastructure Setup

### Terraform Deployment

Deploy production infrastructure using Terraform:

```bash
cd infra/supabase

# Initialize Terraform
terraform init -backend-config="bucket=doc-ingestion-terraform-state"

# Plan deployment
terraform plan -out=production.tfplan

# Apply infrastructure
terraform apply production.tfplan
```

### Environment Variables

Required environment variables for deployment:

```bash
export SUPABASE_ACCESS_TOKEN="your-access-token"
export TF_VAR_organization_id="your-org-id"
export TF_VAR_supabase_access_token="$SUPABASE_ACCESS_TOKEN"
export TF_VAR_jwt_secret="$(openssl rand -base64 32)"
```

### Database Connection

Get connection details from Terraform output:

```bash
# Get project details
terraform output project_id
terraform output project_url
terraform output database_host
terraform output database_port

# Connection string (async)
postgresql+asyncpg://user:password@host:port/db?ssl=require

# Connection string (sync)
postgresql://user:password@host:port/db?ssl=require
```

## Security Configuration

### RBAC Setup

Apply role-based access control:

```bash
# Connect to production database
psql postgresql://user:password@host:port/doc_ingestion?ssl=require

# Apply RBAC policies
\i infra/supabase/rbac.sql

# Apply storage policies
\i infra/supabase/storage_policies.sql
```

### User Roles

Production roles and their permissions:

| Role | Permissions | Use Case |
|------|-------------|----------|
| `admin_role` | Full database access | Administrators, DevOps |
| `service_role` | Full access for internal services | API backend service |
| `agent_role` | Read/write for processing | Extraction and normalization agents |
| `api_role` | Read-only access | Client-facing API |
| `readonly_role` | SELECT only | Reporting and analytics |

### Service Users

Pre-configured service users:

```sql
-- Admin user
Username: prod_admin
Grant: admin_role

-- API service
Username: api_service
Grant: service_role

-- Batch processor
Username: batch_processor
Grant: agent_role

-- Reporting
Username: reporting_user
Grant: readonly_role
```

Change default passwords:

```sql
ALTER USER prod_admin WITH PASSWORD 'strong-new-password';
ALTER USER api_service WITH PASSWORD 'strong-new-password';
ALTER USER batch_processor WITH PASSWORD 'strong-new-password';
ALTER USER reporting_user WITH PASSWORD 'strong-new-password';
```

### Row-Level Security (RLS)

RLS is enabled on all production tables:

```sql
-- View RLS policies
SELECT schemaname, tablename, policyname, permissive, roles, qual
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;
```

## Storage Configuration

### Buckets

Three storage buckets are provisioned:

1. **raw-files**: Original documents (100MB max, 30-day expiry)
2. **silver-data**: Normalized data (500MB max, 90-day retention)
3. **backups**: Database and storage backups (1GB max, 90-day retention)

### Access Control

Storage policies are RLS-based:

```sql
-- View storage policies
SELECT * FROM pg_policies WHERE schemaname = 'storage';

-- Test access
SELECT * FROM storage.objects WHERE bucket_id = 'raw-files';
```

### File Upload Configuration

```python
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Upload file
file_data = open("document.pdf", "rb").read()
response = supabase.storage.from_("raw-files").upload(
    "path/to/file.pdf",
    file_data,
    {
        "cacheControl": "3600",
        "upsert": False,
        "metadata": {
            "verified": False,
            "mime_type": "application/pdf"
        }
    }
)

# Get signed URL (5-min expiry)
url = supabase.storage.from_("raw-files").create_signed_url(
    "path/to/file.pdf",
    300
)
```

## Backup & Recovery

### Automated Backups

Backups run daily at 2 AM UTC:

```yaml
Schedule: Daily
Time: 02:00 UTC
Retention: 30 days
Incremental: Enabled
PITR: 7 days
```

### Manual Backup

```bash
# Create database backup
pg_dump \
  postgresql://user:password@host:5432/doc_ingestion \
  --format=custom \
  --compress=9 \
  > backup-$(date +%Y%m%d-%H%M%S).sql

# Backup storage buckets
s3cmd sync s3://doc-ingestion/raw-files/ ./backups/raw-files/
s3cmd sync s3://doc-ingestion/silver-data/ ./backups/silver-data/

# Compress and encrypt
tar czf backup-$(date +%Y%m%d).tar.gz backups/
gpg --encrypt --recipient backup@example.com backup-$(date +%Y%m%d).tar.gz
```

### Database Recovery

```bash
# List available backups in Supabase UI
# Go to: https://app.supabase.com/project/[PROJECT_ID]/database/backups

# Restore from backup (via UI)
# 1. Go to Backups section
# 2. Click "Restore" on desired backup
# 3. Confirm restoration

# Or restore via psql
pg_restore \
  -h host \
  -U user \
  -d doc_ingestion \
  -v \
  backup.sql
```

### Point-in-Time Recovery (PITR)

PITR available for last 7 days:

```bash
# Via Supabase CLI
supabase db pull \
  --project-ref <project-id> \
  --recovery-timestamp "2024-01-20T12:30:00Z"
```

## Monitoring

### Database Metrics

Monitor in Supabase dashboard:
- Connection count
- Disk usage
- Query performance
- Slow queries

### Slow Query Logs

```sql
-- Query slow log
SELECT
  query,
  mean_exec_time,
  calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Clear statistics
SELECT pg_stat_statements_reset();
```

### Storage Metrics

```sql
-- Get bucket statistics
SELECT * FROM get_bucket_stats('raw-files');
SELECT * FROM get_bucket_stats('silver-data');
SELECT * FROM get_bucket_stats('backups');

-- Check quota usage
SELECT org_id, bucket_id, quota_bytes, used_bytes
FROM storage_quotas
ORDER BY used_bytes DESC;
```

## Maintenance

### Database Maintenance

```sql
-- Analyze statistics
ANALYZE;

-- Vacuum and reindex
VACUUM FULL;
REINDEX DATABASE doc_ingestion;

-- Monitor long-running queries
SELECT pid, usename, state, query, query_start
FROM pg_stat_activity
WHERE query_start < now() - interval '10 minutes'
ORDER BY query_start DESC;
```

### Storage Cleanup

```sql
-- Clean expired objects (30+ days in raw-files)
SELECT cleanup_expired_objects();

-- Archive old objects (90+ days in silver-data)
UPDATE storage.objects
SET metadata = jsonb_set(metadata, '{archived}', 'true')
WHERE bucket_id = 'silver-data'
  AND created_at < now() - interval '90 days'
  AND metadata ->> 'archived' IS NULL;
```

## Disaster Recovery

### RTO and RPO Targets

- **RTO (Recovery Time Objective)**: < 30 minutes
- **RPO (Recovery Point Objective)**: < 1 hour (daily backups)

### Recovery Procedures

#### Database Failure

1. Check Supabase status dashboard
2. Review backup availability
3. Initiate PITR or backup restore
4. Verify data integrity
5. Update application connection strings

#### Storage Failure

1. Check bucket status in Supabase dashboard
2. Restore from backup (if available)
3. Verify file integrity with checksums
4. Resume upload/processing jobs

#### Application Failure

1. Check application logs in Railway
2. Scale up database connections if needed
3. Clear cache if applicable
4. Restart API services
5. Monitor for data consistency

### Failover Checklist

- [ ] Notify team of incident
- [ ] Check Supabase status
- [ ] Review recent backups
- [ ] Initiate recovery procedure
- [ ] Verify data integrity
- [ ] Update DNS/routing if needed
- [ ] Monitor metrics post-recovery
- [ ] Document incident and lessons learned

## Performance Optimization

### Query Optimization

```sql
-- Create indexes for frequently queried columns
CREATE INDEX idx_raw_uploads_user_id ON raw_uploads(user_id);
CREATE INDEX idx_silver_records_org_id ON silver_records(organization_id);
CREATE INDEX idx_vector_embeddings_org_id ON vector_embeddings(organization_id);

-- Use EXPLAIN to analyze queries
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM raw_uploads WHERE user_id = 'xxx';
```

### Connection Pooling

Use PgBouncer for connection pooling:

```ini
[databases]
doc_ingestion = host=db.example.com port=5432 dbname=doc_ingestion

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
```

## Troubleshooting

### Connection Issues

```bash
# Test connectivity
psql postgresql://user:password@host:5432/doc_ingestion -c "SELECT 1"

# Check SSL certificate
openssl s_client -connect host:5432 -starttls postgres

# Review firewall rules
# Ensure traffic from app servers is allowed
```

### Authentication Issues

```sql
-- Check user roles
SELECT usename, usesuper, usecreatedb FROM pg_user;

-- Reset user password
ALTER USER prod_admin WITH PASSWORD 'new-password';

-- Grant roles
GRANT admin_role TO prod_admin;
```

### Storage Issues

```sql
-- Check storage quota
SELECT * FROM storage_quotas WHERE org_id = 'xxx';

-- Reset quota
UPDATE storage_quotas
SET used_bytes = (
  SELECT COALESCE(SUM((metadata ->> 'size')::bigint), 0)
  FROM storage.objects
  WHERE bucket_id = storage_quotas.bucket_id
)
WHERE org_id = 'xxx';
```

### Performance Issues

```sql
-- Check active connections
SELECT pid, usename, state, wait_event
FROM pg_stat_activity
WHERE state != 'idle';

-- Kill long-running queries
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE pid <> pg_backend_pid()
  AND state = 'active'
  AND query_start < now() - interval '1 hour';
```

## Related Documentation

- [Registry Setup](../registry/README.md)
- [Backup Recovery Runbook](../ops/backup_recovery.md)
- [Monitoring Guide](../ops/monitoring.md)
- [Supabase Documentation](https://supabase.com/docs)
