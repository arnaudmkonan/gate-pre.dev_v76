# GATE Quick Start Guide

## Get Up and Running in 5 Minutes

### Prerequisites

- Docker & Docker Compose installed
- Git installed

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourbrokerage/gate.git
cd gate
```

### Step 2: Start the Application

```bash
# Start all services
docker compose up -d

# Wait for services to be healthy (about 30 seconds)
docker compose ps
```

### Step 3: Access the Application

- **Web App**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Database Admin**: http://localhost:8081 (pgweb)
- **Task Monitor**: http://localhost:5555 (flower)

### Step 4: Create Your First Entry

1. Open http://localhost:3000
2. Click **Customs Entries** in the sidebar
3. Click **+ New Entry**
4. Fill in:
   - Port of Entry: `4601` (Los Angeles)
   - Entry Type: `Consumption`
   - Importer: `12-3456789`
5. Add a line item:
   - HTS Code: `8471.30.0100`
   - Country: `CN`
   - Value: `10000`
6. Click **Save**

### Step 5: Calculate Duties

1. Click **Duty Calculator** in the sidebar
2. Enter:
   - HTS Code: `8471.30.0100`
   - Value: `$10,000`
   - Country: `China`
3. View the duty breakdown:
   - Base Duty: $0 (free)
   - Section 301: $2,500 (25%)
   - Total: $2,500

### Step 6: Add a Client

1. Click **Clients** in sidebar
2. Click **+ Add Client**
3. Enter company info
4. Save

---

## Common Commands

```bash
# View logs
docker compose logs -f api

# Restart services
docker compose restart

# Stop all services
docker compose down

# Update to latest
git pull && docker compose up -d --build
```

---

## Next Steps

- 📖 Read the [User Manual](USER_MANUAL.md)
- 🔧 Check out [API Reference](API_REFERENCE.md)
- 🚀 Deploy to production: [Deployment Guide](PRODUCTION_DEPLOYMENT.md)

---

## Need Help?

- **Docs**: `/help` in the app
- **Support**: support@yourbrokerage.com
