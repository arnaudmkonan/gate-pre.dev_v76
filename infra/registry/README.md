# Private Container Registry Setup

This document describes the setup and management of the private container registry for Docker image storage and distribution.

## Registry Infrastructure

### Deployment on Railway

The private container registry is deployed on Railway using the official Docker Registry image.

**Project Details:**
- Platform: Railway
- Service: Docker Registry v2
- Storage: S3-compatible (Railway volumes or external S3)
- Access: Private network + authentication

### Registry URL

```
REGISTRY_URL=registry.railway.app/doc-ingestion
```

## Authentication

### Docker Login

```bash
# Login to registry
docker login registry.railway.app -u <username> -p <password>

# Verify login
docker images registry.railway.app/*
```

### Bearer Token Authentication

Requests can use bearer token authentication:

```bash
# Create authorization header
Authorization: Bearer <token>

# Example with curl
curl -H "Authorization: Bearer $TOKEN" \
  https://registry.railway.app/v2/_catalog
```

## Image Management

### Pushing Images

```bash
# Build and tag image
docker build -t registry.railway.app/doc-ingestion/api:v1.0.0 .

# Push to registry
docker push registry.railway.app/doc-ingestion/api:v1.0.0

# Push multiple tags
docker tag myapp:latest registry.railway.app/doc-ingestion/api:latest
docker push registry.railway.app/doc-ingestion/api:latest
```

### Image Tagging Strategy

Use semantic versioning with git SHA for reproducibility:

```
<registry>/<image>:<version>-<git-sha>
<registry>/<image>:<semver>
<registry>/<image>:latest
<registry>/<image>:commit-<short-sha>
```

Examples:
```
registry.railway.app/doc-ingestion/api:1.2.3-a1b2c3d
registry.railway.app/doc-ingestion/api:v1.2.3
registry.railway.app/doc-ingestion/api:latest
registry.railway.app/doc-ingestion/api:commit-a1b2c3d
```

### Pulling Images

```bash
# Pull specific version
docker pull registry.railway.app/doc-ingestion/api:1.2.3-a1b2c3d

# Pull latest
docker pull registry.railway.app/doc-ingestion/api:latest
```

## Access Control & RBAC

### Registry Users

Create service accounts for different roles:

```bash
# Admin user (CI/CD pipeline)
Username: ci-bot
Password: <strong-random-password>
Permissions: push, pull, admin
TTL: No expiration

# Reader user (staging deployments)
Username: staging-reader
Password: <strong-random-password>
Permissions: pull only
TTL: 90 days

# Reader user (production deployments)
Username: prod-reader
Password: <strong-random-password>
Permissions: pull only
TTL: 90 days
```

### Token-Based Access

Generate time-limited tokens for deployments:

```bash
# Create deployment token
./infra/registry/rbac.sh create-token \
  --service prod-reader \
  --ttl 7d \
  --permissions pull

# Output: token_string
# Use in deployment: docker login -u <token> -p <token>
```

## Token Rotation

### Quarterly Token Rotation

```bash
#!/bin/bash
# Rotate all deployment tokens

# Generate new staging token
NEW_STAGING_TOKEN=$(./infra/registry/rbac.sh create-token \
  --service staging-reader \
  --ttl 90d \
  --permissions pull)

# Update Railway environment
railway link <project-id>
railway env set REGISTRY_PASSWORD="$NEW_STAGING_TOKEN"

# Verify new token works
echo "$NEW_STAGING_TOKEN" | docker login -u staging-reader --password-stdin registry.railway.app

# Revoke old token
./infra/registry/rbac.sh revoke-token <old-token-id>
```

## Security Policies

### Network Access

- Private network access only
- IP whitelisting for CI/CD runners
- VPN requirement for manual access

### Credentials Management

- All credentials stored in secure vaults
- No credentials in version control
- Credentials rotated every 90 days
- Audit logs for all access

### Image Scanning

- Scan images for vulnerabilities before push
- Block push if critical vulnerabilities detected
- Automated scanning on pull requests

```bash
# Scan image before push
trivy image registry.railway.app/doc-ingestion/api:latest

# Only push if no critical vulnerabilities
trivy image --exit-code 0 --severity HIGH,CRITICAL registry.railway.app/doc-ingestion/api:latest
```

## Retention Policies

### Image Retention

```
Keep last 10 versions of each image
Keep latest tag indefinitely
Delete untagged images after 30 days
```

### Cleanup Script

```bash
#!/bin/bash
# Cleanup old images

# List repositories
curl -s -H "Authorization: Bearer $REGISTRY_TOKEN" \
  https://registry.railway.app/v2/_catalog | jq '.repositories[]'

# Delete old tags
curl -X DELETE -H "Authorization: Bearer $REGISTRY_TOKEN" \
  https://registry.railway.app/v2/doc-ingestion/api/manifests/sha256:<digest>
```

## Monitoring & Logging

### Registry Metrics

- Image push/pull volume
- Authentication success/failure rates
- Storage usage
- API response times

### Audit Logging

```bash
# Enable audit logging in Docker Registry config
{
  "log": {
    "level": "info",
    "formatter": "json",
    "fields": {
      "service": "registry",
      "environment": "production"
    }
  }
}
```

### Alerts

Configure alerts for:
- Unauthorized access attempts
- Disk usage > 80%
- High error rate (>1%)
- Slow response times (>2s)

## Disaster Recovery

### Backup Strategy

```bash
# Backup registry data
docker exec registry-container \
  tar czf - /var/lib/registry | \
  aws s3 cp - s3://backup-bucket/registry-backup-$(date +%Y%m%d).tar.gz

# Restore from backup
aws s3 cp s3://backup-bucket/registry-backup-latest.tar.gz - | \
  docker exec -i registry-container tar xzf -
```

### Recovery Time Objective (RTO)

- RTO: 1 hour (rebuild from S3 or Railway backups)
- RPO: 24 hours (daily backup snapshots)

## Troubleshooting

### Push/Pull Failures

```bash
# Check registry connectivity
curl https://registry.railway.app/v2/

# Verify authentication
docker login -u <username> -p <password> registry.railway.app

# Check image layers
docker history registry.railway.app/doc-ingestion/api:latest
```

### Authentication Errors

```bash
# Verify credentials
cat ~/.docker/config.json

# Re-authenticate
docker login -u <username> -p <password> registry.railway.app --password-stdin

# Clear old credentials
rm ~/.docker/config.json
```

### Storage Issues

```bash
# Check registry storage usage
docker exec registry-container du -sh /var/lib/registry

# List repositories and sizes
curl -s -H "Authorization: Bearer $TOKEN" \
  https://registry.railway.app/v2/_catalog
```

## Related Documents

- [RBAC Configuration](./rbac.sh)
- [Rollback Procedure](../../deploy/rollback.sh)
- [CI/CD Pipeline Documentation](../../docs/ci/SECRETS.md)
- [Railway Documentation](https://docs.railway.app/)
