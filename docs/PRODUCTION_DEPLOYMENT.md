# GATE Production Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start (5-Minute Deploy)](#quick-start)
3. [Cloud Provider Options](#cloud-providers)
4. [Environment Configuration](#environment-configuration)
5. [Database Setup](#database-setup)
6. [SSL/TLS Configuration](#ssl-configuration)
7. [Monitoring & Logging](#monitoring)
8. [Backup & Recovery](#backup-recovery)
9. [Scaling Guide](#scaling)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required
- Docker 24+ with Docker Compose V2
- Domain name (e.g., `gate.yourbrokerage.com`)
- SSL certificate (or use Let's Encrypt)
- PostgreSQL 15+ with pgvector extension
- Redis 7+

### Recommended
- 4 CPU cores, 8GB RAM minimum
- 100GB SSD storage
- Managed database service (AWS RDS, GCP Cloud SQL, etc.)

---

## Quick Start (5-Minute Deploy) {#quick-start}

### Option A: Single Server (Digital Ocean, Linode, etc.)

```bash
# 1. Clone the repository
git clone https://github.com/yourbrokerage/gate.git
cd gate

# 2. Copy production environment file
cp .env.example .env.production

# 3. Edit environment variables
nano .env.production
# Set: DATABASE_URL, REDIS_URL, SECRET_KEY, DOMAIN, etc.

# 4. Start production stack
docker compose -f docker-compose.prod.yml up -d

# 5. Run database migrations
docker compose exec api python -m alembic upgrade head

# 6. Create admin user
docker compose exec api python scripts/create_admin.py

# 7. Verify deployment
curl https://yourdomain.com/health
```

### Option B: Platform-as-a-Service (Railway, Render, Fly.io)

#### Railway (Recommended - Easiest)

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login and link
railway login
railway link

# 3. Set environment variables
railway variables set DATABASE_URL=postgresql://...
railway variables set REDIS_URL=redis://...
railway variables set SECRET_KEY=$(openssl rand -hex 32)
railway variables set ENVIRONMENT=production

# 4. Deploy
railway up
```

#### Render

1. Create new Web Service from GitHub repo
2. Set Docker build path: `services/api`
3. Add PostgreSQL and Redis addons
4. Configure environment variables
5. Deploy

#### Fly.io

```bash
# 1. Install flyctl
curl -L https://fly.io/install.sh | sh

# 2. Launch app
fly launch

# 3. Set secrets
fly secrets set SECRET_KEY=$(openssl rand -hex 32)
fly secrets set DATABASE_URL=postgresql://...

# 4. Deploy
fly deploy
```

---

## Cloud Provider Options {#cloud-providers}

### AWS (Full Production)

```
Architecture:
┌─────────────────────────────────────────────────────┐
│                   Route 53 (DNS)                     │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│              Application Load Balancer              │
│                 (SSL Termination)                    │
└─────────────────────────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
┌──────────────────┐      ┌──────────────────┐
│   ECS Fargate    │      │   ECS Fargate    │
│   (API Service)  │      │   (Worker)       │
└──────────────────┘      └──────────────────┘
            │                         │
            └────────────┬────────────┘
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
┌──────────────────┐      ┌──────────────────┐
│   RDS PostgreSQL │      │   ElastiCache    │
│   (with pgvector)│      │   (Redis)        │
└──────────────────┘      └──────────────────┘
            │
            ▼
┌──────────────────┐
│       S3         │
│   (Documents)    │
└──────────────────┘
```

#### Terraform Setup (AWS)

See: `/infrastructure/terraform/aws/` (included in repo)

```bash
cd infrastructure/terraform/aws
terraform init
terraform plan
terraform apply
```

### Google Cloud Platform

```bash
# Using Cloud Run
gcloud run deploy gate-api \
  --image gcr.io/your-project/gate-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --add-cloudsql-instances your-instance \
  --set-env-vars DATABASE_URL=...
```

### Azure

```bash
# Using Container Apps
az containerapp create \
  --name gate-api \
  --resource-group gate-rg \
  --environment gate-env \
  --image your-registry/gate-api \
  --target-port 8000 \
  --ingress external
```

---

## Environment Configuration {#environment-configuration}

### Required Environment Variables

```bash
# .env.production

# ===== Core =====
ENVIRONMENT=production
SECRET_KEY=your-256-bit-secret-key-here
DEBUG=false

# ===== Database =====
DATABASE_URL=postgresql://user:password@host:5432/gate_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# ===== Redis =====
REDIS_URL=redis://host:6379/0
CELERY_BROKER_URL=redis://host:6379/1

# ===== API =====
API_HOST=0.0.0.0
API_PORT=8000
WORKERS=4

# ===== Domain & CORS =====
DOMAIN=gate.yourbrokerage.com
ALLOWED_ORIGINS=https://gate.yourbrokerage.com
CORS_ORIGINS=["https://gate.yourbrokerage.com"]

# ===== File Storage =====
STORAGE_TYPE=s3  # or 'local', 'gcs', 'azure'
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_S3_BUCKET=gate-documents
AWS_REGION=us-east-1

# ===== Email (for notifications) =====
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
FROM_EMAIL=noreply@yourbrokerage.com

# ===== Stripe (for billing) =====
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_PROFESSIONAL=price_...
STRIPE_PRICE_ENTERPRISE=price_...

# ===== ACE Integration (CBP) =====
ACE_API_URL=https://ace.cbp.dhs.gov
ACE_CLIENT_ID=your-ace-client-id
ACE_CLIENT_SECRET=your-ace-secret

# ===== Security =====
JWT_EXPIRATION_HOURS=24
RATE_LIMIT_PER_MINUTE=60
```

### Generate Secrets

```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# Or using openssl
openssl rand -hex 32
```

---

## Database Setup {#database-setup}

### Production PostgreSQL with pgvector

```sql
-- Create database
CREATE DATABASE gate_db;

-- Enable extensions
\c gate_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- Create user
CREATE USER gate_user WITH PASSWORD 'secure-password';
GRANT ALL PRIVILEGES ON DATABASE gate_db TO gate_user;
```

### Run Migrations

```bash
# Using Docker
docker compose exec api alembic upgrade head

# Or directly
cd services/api
alembic upgrade head
```

### Seed Reference Data

```bash
docker compose exec api python scripts/seed_reference_data.py
```

This seeds:
- HTS codes
- Port codes
- Country codes
- ADD/CVD orders
- FTA agreements

---

## SSL/TLS Configuration {#ssl-configuration}

### Option 1: Let's Encrypt with Caddy (Recommended)

```yaml
# docker-compose.prod.yml
services:
  caddy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    depends_on:
      - api
```

```
# Caddyfile
gate.yourbrokerage.com {
    reverse_proxy api:8000
    
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
    }
}
```

### Option 2: Nginx with Certbot

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d gate.yourbrokerage.com
```

---

## Monitoring & Logging {#monitoring}

### Health Endpoints

```bash
# Basic health
curl https://gate.yourbrokerage.com/health
# Expected: {"status": "ok", "environment": "production"}

# Detailed health
curl https://gate.yourbrokerage.com/api/health/detailed
# Returns: database status, latency, component health

# Kubernetes probes
/api/health/live   # Liveness probe
/api/health/ready  # Readiness probe
```

### Logging Configuration

```python
# logging.json
{
  "version": 1,
  "formatters": {
    "json": {
      "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
      "format": "%(asctime)s %(levelname)s %(name)s %(message)s"
    }
  },
  "handlers": {
    "console": {
      "class": "logging.StreamHandler",
      "formatter": "json"
    }
  },
  "root": {
    "level": "INFO",
    "handlers": ["console"]
  }
}
```

### Recommended Monitoring Stack

1. **Prometheus + Grafana** - Metrics and dashboards
2. **Loki** - Log aggregation
3. **Sentry** - Error tracking

```bash
# Add Sentry
pip install sentry-sdk[fastapi]

# In main.py
import sentry_sdk
sentry_sdk.init(dsn="your-sentry-dsn")
```

---

## Backup & Recovery {#backup-recovery}

### Automated Daily Backups

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/backups

# PostgreSQL backup
pg_dump $DATABASE_URL | gzip > $BACKUP_DIR/gate_db_$DATE.sql.gz

# Upload to S3
aws s3 cp $BACKUP_DIR/gate_db_$DATE.sql.gz s3://gate-backups/

# Keep only last 30 days locally
find $BACKUP_DIR -mtime +30 -delete
```

### Cron Schedule

```bash
# crontab -e
0 2 * * * /opt/gate/backup.sh >> /var/log/gate-backup.log 2>&1
```

### Recovery

```bash
# Download backup
aws s3 cp s3://gate-backups/gate_db_20260127.sql.gz ./

# Restore
gunzip -c gate_db_20260127.sql.gz | psql $DATABASE_URL
```

---

## Scaling Guide {#scaling}

### Horizontal Scaling (Docker Swarm)

```yaml
# docker-compose.prod.yml
services:
  api:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

### Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gate-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: gate-api
  template:
    spec:
      containers:
      - name: api
        image: gate-api:latest
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /api/health/live
            port: 8000
        readinessProbe:
          httpGet:
            path: /api/health/ready
            port: 8000
```

---

## Troubleshooting {#troubleshooting}

### Common Issues

| Issue | Solution |
|-------|----------|
| Database connection refused | Check `DATABASE_URL`, ensure pg_hba.conf allows connections |
| Redis connection error | Verify `REDIS_URL`, check Redis service is running |
| 502 Bad Gateway | Check API container logs, increase timeout |
| Slow file uploads | Increase nginx `client_max_body_size` |
| CORS errors | Add frontend domain to `CORS_ORIGINS` |

### Debug Commands

```bash
# Check container logs
docker compose logs -f api

# Container resource usage
docker stats

# Database connections
docker compose exec postgres psql -U gate_user -c "SELECT * FROM pg_stat_activity;"

# Redis info
docker compose exec redis redis-cli INFO
```

### Health Check Script

```bash
#!/bin/bash
# health_check.sh

API_URL="https://gate.yourbrokerage.com"

# Check API
if curl -sf "$API_URL/health" > /dev/null; then
    echo "✅ API healthy"
else
    echo "❌ API unhealthy"
    exit 1
fi

# Check database (via detailed health)
DB_STATUS=$(curl -sf "$API_URL/api/health/detailed" | jq -r '.components.database.status')
if [ "$DB_STATUS" = "healthy" ]; then
    echo "✅ Database healthy"
else
    echo "❌ Database unhealthy"
    exit 1
fi

echo "All systems operational!"
```

---

## Deployment Checklist

- [ ] Environment variables configured
- [ ] Database created and migrated
- [ ] Reference data seeded
- [ ] SSL certificate installed
- [ ] Domain DNS configured
- [ ] Backups scheduled
- [ ] Monitoring enabled
- [ ] Admin user created
- [ ] Stripe webhooks configured
- [ ] ACE credentials configured
- [ ] Test email notifications
- [ ] Load test complete
- [ ] Go live!

---

## Quick Commands Reference

```bash
# Deploy update
git pull && docker compose pull && docker compose up -d

# View logs
docker compose logs -f api

# Restart services
docker compose restart

# Scale workers
docker compose up -d --scale worker=3

# Run migrations
docker compose exec api alembic upgrade head

# Create backup
docker compose exec postgres pg_dump -U gate_user gate_db > backup.sql

# Check status
docker compose ps
```

---

*Last Updated: 2026-01-27*
