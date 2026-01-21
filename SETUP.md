# Complete Setup Guide

Follow these steps to get the Documentation Ingestion Platform running locally.

## Prerequisites

- **Python**: 3.11 or higher
- **Node.js**: 18 or higher
- **Docker**: Latest version with Docker Compose
- **Git**: For cloning the repository
- **Supabase Account**: Free tier available at https://supabase.com
- **OpenAI Account**: API key from https://platform.openai.com

## Step 1: Environment Setup

### 1.1 Create Environment Files

Backend (.env):
```bash
cd services/api
cp .env.example .env
```

Edit `.env` with your credentials:
```bash
# Database (use default for local development)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/doc_ingestion
DATABASE_URL_SYNC=postgresql://postgres:postgres@localhost:5432/doc_ingestion

# Supabase Storage
SUPABASE_STORAGE_ENDPOINT=https://your-project.supabase.co/storage/v1/s3
SUPABASE_STORAGE_BUCKET=raw-files
SUPABASE_STORAGE_REGION=us-east-1
# Get these from Supabase Settings → API → S3
SUPABASE_STORAGE_ACCESS_KEY=your_key_here
SUPABASE_STORAGE_SECRET_KEY=your_secret_here

# Redis (use defaults for local)
REDIS_HOST=localhost
REDIS_PORT=6379
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Vector Store
OPENAI_API_KEY=sk-your-key-here
VECTOR_STORE_BACKEND=supabase
VECTOR_STORE_URL=https://your-project.supabase.co

# API
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=False
SECRET_KEY=change-me-in-production
```

## Step 2: Backend Setup

### 2.1 Install Backend Dependencies

```bash
cd services/api

# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2.2 Start Services (Terminal 1)

```bash
cd services/api
docker-compose up -d

# Verify services are running
docker-compose ps
# Should see: postgres and redis with "Up" status
```

### 2.3 Run Database Migrations (Terminal 2)

```bash
cd services/api
source venv/bin/activate

# Create database tables
alembic upgrade head

# Verify (should not error)
python -c "from app.core.database import AsyncSessionLocal; print('✓ Database connected')"
```

### 2.4 Start FastAPI Backend (Terminal 3)

```bash
cd services/api
source venv/bin/activate

# Start development server
uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Test it:
```bash
curl http://localhost:8000/health
# Should return: {"status":"ok","environment":"development"}
```

### 2.5 Start Celery Worker (Terminal 4)

```bash
cd services/api
source venv/bin/activate

# Start worker
celery -A app.core.celery_app worker --loglevel=info
```

You should see:
```
celery@hostname ready.
Connected to redis://localhost:6379/0
```

## Step 3: Frontend Setup

### 3.1 Install Frontend Dependencies (Terminal 5)

```bash
cd apps/web
npm install
```

### 3.2 Start Development Server

```bash
npm run dev
```

You should see:
```
VITE v5.0.5  ready in 234 ms
➜  Local:   http://localhost:3000/
```

## Step 4: Initial Configuration

### 4.1 Storage Configuration

Option A: Via Admin UI
1. Open http://localhost:3000/admin/storage-config
2. Fill in Supabase Storage credentials
3. Click "Test Connection"
4. Click "Save Configuration"

Option B: Via CLI
```bash
python -m app.tools.storage_cli configure \
  --provider supabase \
  --endpoint https://your-project.supabase.co/storage/v1/s3 \
  --bucket raw-files \
  --region us-east-1 \
  --access-key <your-access-key> \
  --secret-key <your-secret-key>
```

Verify:
```bash
python -m app.tools.storage_cli show-config
```

### 4.2 Queue Configuration

Option A: Via Admin UI
1. Open http://localhost:3000/admin/queue-config
2. Enter Redis localhost:6379
3. Keep defaults for other fields
4. Click "Save Configuration"

Option B: Via CLI
```bash
python -m app.tools.queue_cli configure \
  --redis-host localhost \
  --redis-port 6379 \
  --concurrency 4
```

Verify:
```bash
python -m app.tools.queue_cli status
# Should show: Pending: 0, Running: 0, Failed: 0
```

### 4.3 Vector Store Configuration

Option A: Via Admin UI
1. Open http://localhost:3000/admin/vector-store-config
2. Select backend: "Supabase (pgvector)"
3. Enter your Supabase URL and API key
4. Keep other defaults
5. Click "Save Configuration"

Option B: Via CLI
```bash
python -m app.tools.vector_store_cli configure \
  --backend supabase \
  --url https://your-project.supabase.co \
  --api-key <your-api-key>
```

Verify:
```bash
python -m app.tools.vector_store_cli show-config
```

## Step 5: Verify Everything Works

### 5.1 Check All Services

```bash
# API Health
curl http://localhost:8000/health

# Queue Status
curl http://localhost:8000/api/queue/status

# Storage Config
curl http://localhost:8000/api/storage/config

# Vector Store Config
curl http://localhost:8000/api/vector-store/config
```

All should return 200 with valid JSON.

### 5.2 Test Upload Workflow

```bash
# Create test file
echo "Test document for ingestion" > test_document.txt

# Upload file
curl -X POST http://localhost:8000/api/storage/upload \
  -F "file=@test_document.txt"

# Response should include:
# - file_id
# - signed_url
# - job_id

# Check queue status
curl http://localhost:8000/api/queue/status
# Should show: pending: 1 (or running: 1)

# Wait for job to complete
sleep 5

# Check status again
curl http://localhost:8000/api/queue/status
```

### 5.3 Test Search

```bash
curl "http://localhost:8000/api/vector-store/search?query=test&limit=5"

# Should return embeddings with similarity scores
```

## Step 6: Access the Platform

- **Admin Panel**: http://localhost:3000
  - Storage Config: http://localhost:3000/admin/storage-config
  - Queue Config: http://localhost:3000/admin/queue-config
  - Queue Metrics: http://localhost:3000/admin/queue-metrics
  - Vector Store Config: http://localhost:3000/admin/vector-store-config

- **API Documentation**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/health

## Troubleshooting

### Database Connection Error

```bash
# Check if PostgreSQL is running
docker-compose ps

# If not, start it
docker-compose up -d postgres

# Check connection
psql -U postgres -d doc_ingestion -c "SELECT 1"
```

### Redis Connection Error

```bash
# Check if Redis is running
docker-compose ps

# If not, start it
docker-compose up -d redis

# Test connection
redis-cli ping
# Should return: PONG
```

### Worker Not Processing Jobs

```bash
# 1. Verify worker is running (check Terminal 4)
# 2. Check queue status
python -m app.tools.queue_cli status

# 3. Restart worker if needed
# Kill current worker (Ctrl+C in Terminal 4)
# Restart: celery -A app.core.celery_app worker --loglevel=info
```

### Frontend Not Showing

```bash
# Check if Vite is running (should see in Terminal 5)
# If not, restart:
cd apps/web
npm run dev
```

### Storage Upload Fails

```bash
# Verify storage is configured
python -m app.tools.storage_cli show-config

# Test connection
python -m app.tools.storage_cli test-connection

# Check Supabase credentials in .env
```

## Next Steps

1. ✅ All services running locally
2. ✅ Admin UI accessible
3. ✅ Basic upload/search working

Now you can:
- Develop new features
- Run tests
- Deploy to production

See [README.md](./README.md) for more information and [docs/](./services/api/docs/) for detailed documentation.

## Stopping Everything

To stop all services:

```bash
# Terminal with docker-compose
docker-compose down

# Activate venv and exit Python processes
# Ctrl+C in other terminals

# Full cleanup (removes volumes)
docker-compose down -v
```

## Production Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) (to be created) for:
- Environment configuration
- Database setup on managed PostgreSQL
- Redis on managed service
- Docker image building
- CI/CD pipeline setup
- Monitoring and logging
