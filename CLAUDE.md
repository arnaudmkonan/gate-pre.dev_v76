# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent documentation ingestion platform with FastAPI backend and React frontend. Handles document upload, parsing, embedding generation via OpenAI, and semantic search using PostgreSQL + pgvector.

## Architecture

```
apps/web/          → React 18 + TypeScript + Vite frontend (port 3000)
services/api/      → FastAPI backend with Celery workers (port 8000)
infra/             → PostgreSQL, Redis, Supabase configuration
```

**Data Flow**: Upload → Storage (Supabase S3) → Celery Queue → Workers (parse, embed, extract) → PostgreSQL + pgvector → Search API

**Key Backend Directories**:
- `app/api/routes/` - API endpoints (40+ route files)
- `app/services/` - Business logic (60+ services)
- `app/workers/` - Celery async tasks (19 workers)
- `app/agents/` - LLM agent implementations
- `app/models/` - SQLAlchemy ORM models (55+ models)
- `app/core/` - Config, database, Celery setup

## Development Commands

### Start Local Environment
```bash
# Terminal 1: Start PostgreSQL + Redis
cd services/api && docker-compose up -d

# Terminal 2: Run migrations
cd services/api && alembic upgrade head

# Terminal 3: FastAPI server
cd services/api && uvicorn app.main:app --reload --port 8000

# Terminal 4: Celery worker
cd services/api && celery -A app.core.celery_app worker --loglevel=info

# Terminal 5: React frontend
cd apps/web && npm run dev
```

### Backend (services/api/)
```bash
# Tests
pytest app/tests/ -v --cov=app

# Single test file
pytest app/tests/test_storage.py -v

# Linting
ruff check app/

# Type checking
pyright app/
```

### Frontend (apps/web/)
```bash
# Development
npm run dev

# Build
npm run build

# Lint
npm run lint

# Type check
npm run type-check
```

### Database Migrations
```bash
cd services/api

# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

### CLI Tools
```bash
cd services/api

# Storage configuration
python -m app.tools.storage_cli configure
python -m app.tools.storage_cli test-connection
python -m app.tools.storage_cli show-config

# Queue management
python -m app.tools.queue_cli status
python -m app.tools.queue_cli list-jobs
python -m app.tools.queue_cli show-dlq
python -m app.tools.queue_cli retry <job_id>

# Vector store
python -m app.tools.vector_store_cli configure
python -m app.tools.vector_store_cli test-connection
```

## Key Technologies

- **Backend**: FastAPI, SQLAlchemy 2.0 (async), Celery + Redis, OpenAI API, pgvector
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Zustand, TanStack Query
- **Database**: PostgreSQL 16 with pgvector extension for embeddings
- **Storage**: Supabase Storage (S3-compatible)

## Environment Variables

Copy `services/api/.env.example` to `.env`. Key variables:
- `DATABASE_URL` - PostgreSQL async connection string
- `CELERY_BROKER_URL` - Redis broker URL
- `OPENAI_API_KEY` - For embeddings (text-embedding-3-small)
- `SUPABASE_*` - Storage credentials

## API Endpoints

- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Upload: POST `/api/storage/upload`
- Search: GET `/api/vector-store/search?query=...`
- Queue Status: GET `/api/queue/status`

## Testing Workflow

```bash
# Create test file
echo "Test content" > test.txt

# Upload
curl -X POST http://localhost:8000/api/storage/upload -F "file=@test.txt"

# Check job status
curl http://localhost:8000/api/queue/status

# Search
curl "http://localhost:8000/api/vector-store/search?query=test&limit=5"
```
