# CI/CD Secrets Management

This document describes the secrets and environment variables required for the CI/CD pipeline.

## GitHub Actions Secrets

Configure the following secrets in your GitHub repository settings (Settings > Secrets and variables > Actions):

### Container Registry Secrets

```bash
REGISTRY_URL              # Container registry URL (e.g., registry.example.com)
REGISTRY_USERNAME         # Registry username for authentication
REGISTRY_PASSWORD         # Registry password or access token
```

### Railway Deployment Secrets

```bash
RAILWAY_TOKEN             # Railway API token for CLI operations
RAILWAY_API_KEY           # Railway API key for deployments
RAILWAY_BACKEND_PROJECT_ID   # Railway project ID for backend service
RAILWAY_FRONTEND_PROJECT_ID  # Railway project ID for frontend service
```

### Sentry Error Tracking Secrets

```bash
SENTRY_AUTH_TOKEN         # Sentry authentication token for release management
SENTRY_DSN_BACKEND        # Sentry DSN for backend error tracking
SENTRY_DSN_FRONTEND       # Sentry DSN for frontend error tracking
```

### Supabase Production Secrets

```bash
SUPABASE_URL              # Supabase project URL
SUPABASE_SERVICE_ROLE_KEY # Service role key for admin operations
SUPABASE_ANON_KEY         # Anonymous key for client operations
```

### AWS S3 Backup Secrets

```bash
S3_BACKUP_BUCKET          # S3 bucket for backups
S3_ACCESS_KEY             # AWS access key ID
S3_SECRET_KEY             # AWS secret access key
```

### Notification Secrets

```bash
SLACK_WEBHOOK_URL         # Slack webhook for deployment notifications
PAGERDUTY_KEY             # PagerDuty integration key for critical alerts
```

## Setting Secrets in GitHub

### Via GitHub UI

1. Go to your repository
2. Settings > Secrets and variables > Actions
3. Click "New repository secret"
4. Enter secret name and value
5. Click "Add secret"

### Via GitHub CLI

```bash
# List existing secrets
gh secret list

# Create a new secret
gh secret set REGISTRY_URL --body "registry.example.com"

# Delete a secret
gh secret delete REGISTRY_URL
```

## Environment Variables in Workflows

Environment variables are configured in workflow files (.github/workflows/*.yml):

### Backend Environment Variables

```yaml
env:
  SENTRY_DSN: ${{ secrets.SENTRY_DSN_BACKEND }}
  SENTRY_ENV: production
  SENTRY_TRACES_SAMPLE_RATE: "0.1"
  DATABASE_URL: ${{ secrets.DATABASE_URL }}
  SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

### Frontend Environment Variables

```yaml
env:
  VITE_SENTRY_DSN: ${{ secrets.SENTRY_DSN_FRONTEND }}
  VITE_ENV: production
  VITE_API_URL: https://api.example.com
  VITE_SENTRY_TRACES_SAMPLE_RATE: "0.1"
```

## Secret Rotation

### Railway Token Rotation

1. Generate new token in Railway console
2. Update `RAILWAY_TOKEN` secret in GitHub
3. Test deployment with new token
4. Revoke old token in Railway

### Sentry Token Rotation

1. Generate new auth token in Sentry settings
2. Update `SENTRY_AUTH_TOKEN` secret in GitHub
3. Verify releases can be created
4. Revoke old token in Sentry

### AWS S3 Credentials Rotation

1. Create new access key in AWS IAM
2. Update `S3_ACCESS_KEY` and `S3_SECRET_KEY` in GitHub
3. Test backup operations
4. Deactivate old access key in AWS

## Secret Redaction in Logs

Secrets are automatically redacted in GitHub Actions logs:
- Secrets containing "password", "token", "key", "secret" are masked
- Check workflow logs to verify no secrets are printed
- Use `::add-mask::` to manually mask values in logs

```yaml
- name: Mask sensitive output
  run: echo "::add-mask::${{ secrets.SENSITIVE_VALUE }}"
```

## Security Best Practices

1. **Principle of Least Privilege**: Create service accounts with minimal required permissions
2. **Regular Rotation**: Rotate credentials every 90 days
3. **Access Audit**: Regularly review who has access to secrets
4. **Encryption**: All secrets are encrypted at rest in GitHub
5. **No Hardcoding**: Never commit secrets to version control
6. **Audit Logs**: Enable audit logs for secret access
7. **Expiration**: Set expiration dates for temporary credentials

## Troubleshooting

### Secret Not Found Error

```bash
# Verify secret exists
gh secret list

# Create missing secret
gh secret set SECRET_NAME --body "secret_value"
```

### Secrets Not Accessible in Workflow

- Ensure secret is defined in repository settings (not organization)
- Check workflow has permissions to access secrets
- Verify branch protection rules don't block workflow

### Token Expiration

- Railway: Check expiration in Railway console
- Sentry: Check token validity in Sentry settings
- AWS: Check access key status in IAM console

## References

- [GitHub Actions Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Railway Documentation](https://docs.railway.app/)
- [Sentry Documentation](https://docs.sentry.io/)
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
