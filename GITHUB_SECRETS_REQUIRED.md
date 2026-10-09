# GitHub Secrets & Environments — Setup Checklist

> Add these in **GitHub → Repository → Settings → Secrets and variables → Actions**

## Required Repository Secrets

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `RAILWAY_TOKEN` | Railway API authentication token | Railway Dashboard → Account → Tokens |
| `RAILWAY_BACKEND_PROJECT_ID` | Railway project ID for the API backend | Railway Dashboard → Project Settings |
| `RAILWAY_FRONTEND_PROJECT_ID` | Railway project ID for the frontend | Railway Dashboard → Project Settings |
| `REGISTRY_URL` | Docker container registry URL | Your registry (Railway, GHCR, ECR, etc.) |
| `REGISTRY_USERNAME` | Registry login username | Your registry credentials |
| `REGISTRY_PASSWORD` | Registry login password/token | Your registry credentials |
| `SENTRY_AUTH_TOKEN` | Sentry release tracking token | Sentry → Account Settings → Auth Tokens |
| `SENTRY_ORG` | Sentry organisation slug | Your Sentry org name |
| `SENTRY_DSN_FRONTEND` | Sentry DSN for the React frontend | Sentry → Project → Client Keys |

## Environment-Specific Secrets

Create two **GitHub Environments** (`staging`, `production`) with these secrets:

### Staging Environment
| Secret Name | Description |
|-------------|-------------|
| `STAGING_DOMAIN` | Your staging domain (e.g. `staging.gate.yourbrokerage.com`) |

### Production Environment
| Secret Name | Description |
|-------------|-------------|
| `PRODUCTION_DOMAIN` | Your production domain (e.g. `gate.yourbrokerage.com`) |

> **Tip:** Set the `production` environment to require a **manual approval** from a reviewer before deployment proceeds. Configure this under GitHub → Environments → production → Protection rules.

## GitHub Environment Setup (Recommended)

```
Repository Settings
└── Environments
    ├── staging
    │   ├── Secrets: STAGING_DOMAIN
    │   └── (no protection rules — auto-deploys)
    └── production
        ├── Secrets: PRODUCTION_DOMAIN
        ├── Required reviewers: [your handle]
        └── Deployment branches: main (only)
```

## Verify All Secrets Are Set

Run this to list configured secrets (values are never shown):
```bash
gh secret list
gh secret list --env staging
gh secret list --env production
```

## Notes
- The `RAILWAY_TOKEN` should be a **service token**, not your personal token.
- Rotate `SENTRY_AUTH_TOKEN` every 90 days.
- Never commit `.env.production` — it is in `.gitignore`.
