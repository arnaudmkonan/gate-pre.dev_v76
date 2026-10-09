# GATE Platform - Demo Customs Broker LLC

**Customer ID:** demo-broker
**Subdomain:** demo.gateplatform.com
**Created:** 2026-02-02T20:14:35Z

## Quick Start

1. Start the instance:
   ```bash
   ./start.sh
   ```

2. Initialize the database (first time only):
   ```bash
   ./init.sh
   ```

3. Access the platform:
   - Web UI: http://localhost:3101 (or https://demo.gateplatform.com)
   - API: http://localhost:8101 (or https://demo.gateplatform.com/api)

4. Stop the instance:
   ```bash
   ./stop.sh
   ```

## Initial Admin Credentials

- **Email:** admin@demo-broker.com
- **Password:** f+2ZerzNIb22TpnH

⚠️ **IMPORTANT:** Change this password after first login!

## Port Mappings

| Service | Container Port | External Port |
|---------|----------------|---------------|
| API     | 8000           | 8101   |
| Web     | 80             | 3101   |
| DB      | 5432           | 5501    |
| Redis   | 6379           | 6401 |
| Flower  | 5555           | 5601|

## Management Commands

```bash
# View logs
./logs.sh          # API logs
./logs.sh worker   # Worker logs
./logs.sh db       # Database logs

# Access database
docker compose exec db psql -U gate_user -d gate_demo_broker

# Run migrations
docker compose exec api alembic upgrade head

# Backup database
docker compose exec db pg_dump -U gate_user gate_demo_broker > backup.sql
```

## Directory Structure

```
demo-broker/
├── .env                 # Environment configuration (secrets)
├── docker-compose.yml   # Docker Compose configuration
├── init.sh              # Database initialization script
├── start.sh             # Start instance
├── stop.sh              # Stop instance
├── logs.sh              # View logs
├── certs/               # SSL and ACE certificates
└── README.md            # This file
```
