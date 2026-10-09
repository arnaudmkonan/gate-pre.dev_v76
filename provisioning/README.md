# GATE Platform - Provisioning System

This directory contains scripts and templates for provisioning new customer instances of the GATE Platform.

## Architecture

The GATE Platform uses a **Single-Tenant** deployment model where each customer gets their own isolated infrastructure:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Your Control Plane                          │
│  - Customer provisioning (this system)                          │
│  - Billing (Stripe)                                             │
│  - Instance monitoring                                          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Broker A    │ │  Broker B    │ │  Broker C    │
│  Instance    │ │  Instance    │ │  Instance    │
│              │ │              │ │              │
│ • API        │ │ • API        │ │ • API        │
│ • Frontend   │ │ • Frontend   │ │ • Frontend   │
│ • Workers    │ │ • Workers    │ │ • Workers    │
│ • Database   │ │ • Database   │ │ • Database   │
│ • Redis      │ │ • Redis      │ │ • Redis      │
│              │ │              │ │              │
│ broker-a.    │ │ broker-b.    │ │ broker-c.    │
│ gateplatform │ │ gateplatform │ │ gateplatform │
│ .com         │ │ .com         │ │ .com         │
└──────────────┘ └──────────────┘ └──────────────┘
```

## Quick Start

### 1. Prerequisites

- Docker and Docker Compose installed
- Built Docker images for GATE Platform:
  ```bash
  # From project root
  docker build -t gate-platform/api:latest ./services/api
  docker build -t gate-platform/web:latest ./apps/web
  ```

### 2. Provision a New Customer

```bash
./scripts/provision.sh <customer_id> "<customer_name>" <admin_email> <subdomain>

# Example:
./scripts/provision.sh acme-imports "Acme Imports LLC" admin@acme.com acme
```

This creates:
- `instances/acme-imports/` directory
- Unique database and Redis credentials
- Docker Compose configuration
- Management scripts (start, stop, logs)
- First admin user credentials

### 3. Start the Instance

```bash
cd instances/acme-imports
./start.sh
./init.sh  # First time only - runs migrations and creates admin user
```

### 4. Access the Platform

- **Local:** http://localhost:{PORT}
- **Production:** https://acme.gateplatform.com (after DNS setup)

## Scripts

| Script | Description |
|--------|-------------|
| `provision.sh` | Create a new customer instance |
| `deprovision.sh` | Remove a customer instance (with backup option) |
| `list-instances.sh` | List all customer instances and their status |

## Directory Structure

```
provisioning/
├── README.md           # This file
├── scripts/
│   ├── provision.sh    # Create new customer
│   ├── deprovision.sh  # Remove customer
│   └── list-instances.sh
├── templates/          # Template files (future use)
└── terraform/          # Cloud infrastructure (AWS/GCP)

instances/              # Created customer instances
├── <customer_id>/
│   ├── .env           # Environment configuration
│   ├── docker-compose.yml
│   ├── start.sh
│   ├── stop.sh
│   ├── init.sh
│   ├── logs.sh
│   └── certs/
└── ...
```

## Port Allocation

Each instance gets unique ports to avoid conflicts:

| Service | Base Port | Example (Instance 1) |
|---------|-----------|---------------------|
| API     | 8100      | 8101                |
| Web     | 3100      | 3101                |
| DB      | 5500      | 5501                |
| Redis   | 6400      | 6401                |
| Flower  | 5600      | 5601                |

## Production Deployment

For production, you'll need:

### 1. Reverse Proxy (Nginx/Traefik)

Configure wildcard subdomains to route to the correct instance:

```nginx
server {
    listen 443 ssl;
    server_name *.gateplatform.com;
    
    # Route based on subdomain
    location / {
        proxy_pass http://localhost:$PORT;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 2. DNS Configuration

- Add wildcard A record: `*.gateplatform.com → your-server-ip`
- Or use Cloudflare with wildcard proxying

### 3. SSL Certificates

- Use Let's Encrypt with wildcard certificate
- Or Cloudflare Universal SSL

## Cloud Deployment (AWS)

For AWS deployment, see the `terraform/` directory (coming soon):

```bash
cd terraform/aws
terraform init
terraform apply -var="customer_id=acme-imports" -var="subdomain=acme"
```

## Billing Integration

Each instance tracks:
- `CUSTOMER_ID` for Stripe customer mapping
- Usage metrics for subscription enforcement
- Entry counts per billing period

See `services/api/app/models/production_ready.py` for subscription tiers.

## Backup & Recovery

### Manual Backup

```bash
cd instances/<customer_id>
docker compose exec db pg_dump -U gate_user <db_name> > backup.sql
```

### Restore

```bash
docker compose exec -T db psql -U gate_user <db_name> < backup.sql
```

### Automated Backups

Set up a cron job:
```bash
0 2 * * * /path/to/provisioning/scripts/backup-all.sh
```

## Security Considerations

1. **Secret Management:** Each instance gets unique secrets (SecretKey, DB password, Redis password)
2. **Network Isolation:** Each instance runs in its own Docker network
3. **Database Isolation:** Each instance has its own PostgreSQL database
4. **Access Control:** Admin users are created per-instance with unique credentials

## Monitoring

For production, set up:
- Health checks (already configured in docker-compose)
- Prometheus/Grafana for metrics
- Centralized logging (ELK/CloudWatch)
- Uptime monitoring (Pingdom/UptimeRobot)

## Support

For issues with provisioning:
1. Check container logs: `./logs.sh api`
2. Verify environment: `cat .env`
3. Test database connectivity: `docker compose exec db pg_isready`
