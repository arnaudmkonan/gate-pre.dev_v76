# GATE Platform — Secrets Rotation Checklist

> ⚠️ **NEVER commit secrets to git.** `.env` is in `.gitignore` — keep it that way.
> 
> Last updated: 2026-03-12

---

## 🔴 CRITICAL — Rotate Before Production

| Secret | Location | Issue | Action |
|--------|----------|-------|--------|
| `OPENAI_API_KEY` | `.env` | Was exposed in plaintext in a previous session | **Rotate NOW** on OpenAI dashboard. Verify old key is revoked. |
| `SECRET_KEY` | `.env` | Defaults to `"change-me-in-production"` in `config.py` | Generate a new one (see below) before touching production. |

### Generate `SECRET_KEY`
```bash
python -c "import secrets; print(secrets.token_hex(32))"
# Then:
sed -i '' "s|SECRET_KEY=.*|SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')|" .env.production
```

---

## 🟡 Change Before Production (Not Critical in Dev)

| Secret | Location | Current Status | Action |
|--------|----------|----------------|--------|
| `POSTGRES_PASSWORD` | `docker-compose.yml` | `postgres` — fine for local dev | Change to `openssl rand -hex 16` in production |
| `FLOWER_BASIC_AUTH` | `docker-compose.yml` | `admin:admin` | Flower + pgweb are **excluded from prod compose** — but confirm firewall blocks ports 8081 and 5555 |

---

## Per-Instance Secrets (Provisioned Customer Instances)

Each customer instance in `instances/` needs unique values:

| Secret | Generate With |
|--------|---------------|
| `POSTGRES_PASSWORD` | `openssl rand -hex 16` |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `REDIS_PASSWORD` | `openssl rand -hex 16` (if password auth enabled) |

---

## Rotation Procedures

### 1. OpenAI API Key
```bash
# 1. Open https://platform.openai.com/api-keys → Create new key
# 2. Update your production env:
sed -i '' "s|OPENAI_API_KEY=.*|OPENAI_API_KEY=sk-NEW-KEY|" .env.production
# 3. Redeploy (Railway will pick up the new env):
railway up --service api --environment production
# 4. Confirm no 401 errors in logs within 60 seconds
# 5. REVOKE the old key at platform.openai.com
```

### 2. SECRET_KEY (invalidates all active sessions)
```bash
NEW_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
sed -i '' "s|SECRET_KEY=.*|SECRET_KEY=${NEW_KEY}|" .env.production
# Warn users before deploying — all sessions will be invalidated.
```

### 3. PostgreSQL Password (production only — destructive)
```bash
# Only do this on fresh deployments.
# If the DB already has data, you must ALTER USER manually:
NEW_PW=$(openssl rand -hex 16)
echo "New password: ${NEW_PW}"
# psql: ALTER USER gate_user WITH PASSWORD '<NEW_PW>';
# Then update DATABASE_URL in .env.production
```

---

## Secret Management for Production

| Platform | Recommended Approach |
|----------|---------------------|
| **Railway** | Built-in environment variables (encrypted at rest) |
| **GCP** | Google Secret Manager + env injection |
| **AWS** | AWS Secrets Manager or SSM Parameter Store |
| **HashiCorp Vault** | Best for enterprise / multi-tenant; roadmap item |

---

## Startup Guard

As of 2026-03-12, `config.py` enforces a startup validator that will cause the API to
**refuse to start** in production if:
- `SECRET_KEY` is the default placeholder
- `SMTP_HOST` is not configured (password reset would silently fail)
- `RATE_LIMIT_STORAGE` is `memory://` (unsafe for multi-worker)

This prevents accidental production deployments with insecure defaults.

---

## Verification

```bash
# Check no secrets in git history:
git log --all --full-history -- .env
# Should return NO results — if it does, rotate immediately.

# Check .gitignore covers secrets:
grep -n ".env" .gitignore

# Verify API key is loaded (never prints the value):
docker compose exec api python -c "
import os
key = os.getenv('OPENAI_API_KEY', '')
print(f'Key present: {bool(key)}')
print(f'Key prefix: {key[:8]}...' if key else 'NO KEY SET')
"
```

---

*Created: 2026-02-15 | Last updated: 2026-03-12*  
*❗ Keys rotated: NEVER — **rotate OPENAI_API_KEY and SECRET_KEY before production deploy***
