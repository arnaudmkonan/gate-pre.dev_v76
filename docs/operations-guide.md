# GATE Platform — SaaS Operations Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Instance Provisioning](#instance-provisioning)
3. [Instance Management](#instance-management)
4. [Monitoring & Alerting](#monitoring--alerting)
5. [Backup & Recovery](#backup--recovery)
6. [Upgrades](#upgrades)
7. [Troubleshooting](#troubleshooting)
8. [Security](#security)

---

## Architecture Overview

Each GATE customer runs an isolated Docker Compose stack:

```
┌─────────────────────────────────────────┐
│  Customer Instance (e.g. acme-widgets)  │
│                                         │
│  ┌─────┐  ┌──────┐  ┌────────┐         │
│  │ API │  │Worker│  │  Beat  │         │
│  │:8000│  │      │  │(cron)  │         │
│  └──┬──┘  └──┬───┘  └───┬────┘         │
│     │        │           │              │
│  ┌──┴────────┴───────────┴──┐           │
│  │      PostgreSQL :5432    │           │
│  └──────────────────────────┘           │
│  ┌──────────────────────────┐           │
│  │       Redis :6379        │           │
│  └──────────────────────────┘           │
│  ┌──────────────────────────┐           │
│  │     Web (React) :3000    │           │
│  └──────────────────────────┘           │
└─────────────────────────────────────────┘
```

**Data isolation:** Each instance has its own PostgreSQL database. No shared tenancy at the DB level.

**Networking:** Ports are automatically calculated from customer index to avoid conflicts when running multiple instances on the same host.

---

## Instance Provisioning

### Quick Start

```bash
# From project root
make provision ID=acme-widgets NAME="Acme Widgets Inc" EMAIL=admin@acme.com SUB=acme

# Or directly
./provisioning/scripts/provision.sh acme-widgets "Acme Widgets Inc" admin@acme.com acme 1.0.0
```

### What Provisioning Creates

```
provisioning/instances/acme-widgets/
├── .env                    # All configuration (secrets auto-generated)
├── docker-compose.yml      # Service definitions
├── upgrade.sh              # Instance upgrade script
├── status.sh               # Health & status check
├── backup.sh               # Database backup with rotation
├── backups/                # Backup storage directory
└── certs/                  # TLS certificates
```

### Configuration

Key environment variables in `.env`:

| Variable | Description |
|----------|-------------|
| `CUSTOMER_ID` | Unique customer identifier |
| `GATE_VERSION` | Pinned Docker image version |
| `POSTGRES_PASSWORD` | Auto-generated database password |
| `JWT_SECRET` | Auto-generated JWT signing secret |
| `EXTERNAL_API_PORT` | Host port for API (auto-calculated) |
| `EXTERNAL_WEB_PORT` | Host port for web UI (auto-calculated) |
| `SMTP_HOST` | Outbound email server (optional) |
| `SENTRY_DSN` | Error tracking (optional) |

### Starting an Instance

```bash
cd provisioning/instances/acme-widgets
docker compose up -d

# Verify
docker compose ps
./status.sh
```

---

## Instance Management

### Status Check

```bash
cd provisioning/instances/acme-widgets
./status.sh
```

Output includes:
- Service health (all containers)
- API liveness and readiness
- Database size and table count
- Last backup info
- Resource usage (CPU, memory, disk)

### Restarting Services

```bash
# Full restart
docker compose restart

# Single service
docker compose restart api

# Full rebuild
docker compose up -d --build
```

### Database Access

```bash
# Interactive psql
docker compose exec db psql -U postgres -d doc_ingestion

# Run a query
docker compose exec db psql -U postgres -d doc_ingestion -c "SELECT count(*) FROM entries"
```

### Logs

```bash
# All services
docker compose logs -f

# API only (last 100 lines)
docker compose logs -f --tail=100 api

# Worker only
docker compose logs -f worker
```

---

## Monitoring & Alerting

### Health Endpoints

| Endpoint | Purpose | Used By |
|----------|---------|---------|
| `GET /health` | Liveness probe | Docker healthcheck, load balancer |
| `GET /api/health/ready` | Readiness probe | Kubernetes, deployment |
| `GET /api/health/info` | Operator dashboard | Monitoring UI |
| `GET /api/health/cache` | Redis stats | Performance monitoring |

### Recommended Monitoring

1. **Uptime:** Poll `/health` every 30s
2. **Database:** Poll `/api/health/ready` every 60s
3. **Celery:** Check Flower at `:5555` for worker status
4. **Disk:** Monitor backup directory size
5. **Logs:** Watch for ERROR level messages

### Alerting Rules

| Condition | Severity | Action |
|-----------|----------|--------|
| `/health` returns non-200 | Critical | Restart API container |
| `/api/health/ready` returns 503 | Critical | Check database |
| Webhook failure_count > 5 | Warning | Check endpoint URL |
| Backup older than 25 hours | Warning | Check backup cron |
| Disk usage > 80% | Warning | Rotate backups, check logs |

---

## Backup & Recovery

### Automated Backups

Each instance includes `backup.sh` designed for cron:

```bash
# Add to crontab (daily at 2 AM)
0 2 * * * /path/to/instances/acme-widgets/backup.sh
```

Backups are:
- Compressed with gzip
- Named: `gate_<customer>_<timestamp>.sql.gz`
- Rotated: keeps last 30 backups

### Manual Backup

```bash
cd provisioning/instances/acme-widgets
./backup.sh
```

### Recovery

```bash
# Stop services
docker compose stop api worker beat

# Restore from backup
gunzip -c backups/gate_acme_20260207_020000.sql.gz | \
  docker compose exec -T db psql -U postgres -d doc_ingestion

# Restart
docker compose start api worker beat
```

### Point-in-Time Recovery

For WAL-based PITR, configure PostgreSQL archiving in `docker-compose.yml`:
```yaml
environment:
  - POSTGRES_INITDB_ARGS=--wal-level=archive
```

---

## Upgrades

### Standard Upgrade

```bash
cd provisioning/instances/acme-widgets
./upgrade.sh 1.1.0
```

The upgrade script:
1. ✅ Creates pre-upgrade database backup
2. ✅ Pulls new Docker images (version-pinned)
3. ✅ Stops services gracefully
4. ✅ Runs Alembic database migrations
5. ✅ Restarts all services
6. ✅ Verifies health endpoint responds

### Rollback

If the upgrade fails:
```bash
# Stop
docker compose down

# Restore database
gunzip -c backups/pre_upgrade_*.sql.gz | \
  docker compose exec -T db psql -U postgres -d doc_ingestion

# Revert to old version
export GATE_VERSION=1.0.0
docker compose up -d
```

### Building New Versions

```bash
# Build tagged images
make build-all VERSION=1.1.0

# Push to registry
make push VERSION=1.1.0
```

---

## Troubleshooting

### Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| API returns 401 on all requests | JWT_SECRET changed | Restart API, users re-login |
| Worker not processing | Redis connection | Check `docker compose logs worker` |
| Database connection refused | PostgreSQL crashed | `docker compose restart db` |
| Migrations fail | Schema conflict | Check `alembic history` for branches |
| Webhook disabled | 10 consecutive failures | Re-enable in Platform Settings UI |
| High memory usage | Redis cache unbounded | Restart Redis or flush DB 3 |

### Diagnostic Commands

```bash
# Check all service health
docker compose ps

# API connectivity
curl http://localhost:8000/health

# Database connectivity
curl http://localhost:8000/api/health/ready

# Celery worker status
curl http://localhost:5555/api/workers

# Redis connectivity
docker compose exec redis redis-cli ping

# Migration status
docker compose exec api alembic current
```

---

## Security

### Secrets Management

- All secrets are auto-generated during provisioning using `openssl rand`
- Secrets are stored in `.env` files (not committed to version control)
- API keys are SHA-256 hashed before storage
- Webhook signing secrets use `secrets.token_hex(24)`

### Authentication

- Session tokens expire after inactivity
- API keys support scoped permissions
- Rate limiting protects against brute force
- All `/api/*` routes require authentication (except exempted health/auth routes)

### Network Security

- Enable TLS using `provisioning/scripts/setup-ssl.sh`
- Use reverse proxy (nginx/Caddy) in production
- Restrict database port to internal network

### Audit Trail

- All write operations can be tracked via `AuditService.log_action()`
- Audit logs retained for 180 days (configurable)
- Daily cleanup task runs via Celery beat
- Export available at `GET /api/audit` and `POST /api/audit/export`
