# Documentation Ingestion Platform

A multi-agent documentation ingestion system using OpenAI SDK with web UI, CLI, and REST API.

## 🎯 Features

- **Multi-format Ingestion**: Support for txt, docx, xlsx, pptx, html, md, json, csv, yml, xml
- **Object Storage**: Supabase Storage or S3-compatible endpoints with signed URLs
- **Job Queue**: Redis/Celery for async processing with retry policies
- **Vector Search**: Semantic search using OpenAI embeddings + pgvector
- **Admin UI**: Non-technical user interface for configuration
- **CLI Tools**: Command-line utilities for all operations
- **REST API**: Full-featured API for integration

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Web App (React + Vite)                 │
│         Admin Panel for Storage/Queue/Vector Config          │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────┐
│                 FastAPI Backend (Python)                    │
│  • Storage Routes          • Queue Routes                    │
│  • Vector Store Routes     • Job Management                  │
└────────────────┬───────────────────────────────┬────────────┘
                 │                               │
    ┌────────────┴─────────┐        ┌───────────┴──────────┐
    │                      │        │                      │
┌───▼──────────────────┐  │  ┌─────▼────────────────────┐ │
│  Supabase Storage    │  │  │  PostgreSQL + pgvector  │ │
│  (Raw Files)         │  │  │  (Embeddings, Metadata) │ │
└──────────────────────┘  │  └────────────────────────┘ │
                          │                              │
                    ┌─────┴──────────┐                   │
                    │  Redis Broker  │                   │
                    │  (Job Queue)   │                   │
                    └────────────────┘                   │
```

## ⚙️ Tech Stack

**Backend**:
- FastAPI (async REST API)
- SQLAlchemy 2.0+ (async ORM)
- Celery + Redis (job queue)
- PostgreSQL + pgvector (data + embeddings)
- Supabase Storage (S3-compatible)
- OpenAI API (embeddings)
- Pydantic (validation)

**Frontend**:
- React 18 + Vite
- TypeScript
- Tailwind CSS
- Lucide icons

**Infrastructure**:
- Docker/Docker Compose
- PostgreSQL 16
- Redis 7
- Supabase managed services

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Supabase account (for Storage)
- OpenAI API key

### 1. Clone and Setup

```bash
# Clone repository
git clone <repo>
cd doc-ingestion-platform

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install backend dependencies
cd services/api
pip install -e .[dev]

# Copy and configure environment
cp .env.example .env
# Edit .env with your Supabase and OpenAI credentials
```

### 2. Start Services

```bash
# Terminal 1: Start PostgreSQL and Redis
cd services/api
docker-compose up -d

# Terminal 2: Run database migrations
alembic upgrade head

# Terminal 3: Start FastAPI backend
uvicorn app.main:app --reload --port 8000

# Terminal 4: Start Celery worker
celery -A app.core.celery_app worker --loglevel=info

# Terminal 5: Start React frontend
cd apps/web
npm install
npm run dev
```

### 3. Access the Platform

- **Web UI**: http://localhost:3000
- **Admin Panel**: http://localhost:3000/admin/storage-config
- **API Docs**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/health

## 📋 Configuration

### Storage Setup

1. **Via Admin UI**:
   - Navigate to http://localhost:3000/admin/storage-config
   - Enter Supabase Storage credentials
   - Click "Test Connection"

2. **Via CLI**:
   ```bash
   python -m app.tools.storage_cli configure \
     --provider supabase \
     --endpoint https://your-project.supabase.co/storage/v1/s3 \
     --bucket raw-files \
     --access-key YOUR_KEY \
     --secret-key YOUR_SECRET
   ```

### Queue Setup

1. **Via Admin UI**:
   - Navigate to http://localhost:3000/admin/queue-config
   - Enter Redis host/port
   - Configure worker settings

2. **Via CLI**:
   ```bash
   python -m app.tools.queue_cli configure \
     --redis-host localhost \
     --redis-port 6379 \
     --concurrency 4
   ```

### Vector Store Setup

1. **Via Admin UI**:
   - Navigate to http://localhost:3000/admin/vector-store-config
   - Select backend (Supabase)
   - Enter API credentials

2. **Via CLI**:
   ```bash
   python -m app.tools.vector_store_cli configure \
     --backend supabase \
     --url https://your-project.supabase.co \
     --api-key YOUR_API_KEY
   ```

## 📚 API Examples

### Upload File
```bash
curl -X POST http://localhost:8000/api/storage/upload \
  -F "file=@document.pdf"
```

Response:
```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "signed_url": "https://...",
  "expires_at": "2024-01-09T22:00:00Z",
  "job_id": "abc123xyz"
}
```

### Search Documents
```bash
curl "http://localhost:8000/api/vector-store/search?query=authentication&limit=10"
```

Response:
```json
{
  "results": [
    {
      "content_chunk": "User authentication...",
      "similarity_score": 0.92
    }
  ],
  "query_time_ms": 245
}
```

### Get Queue Status
```bash
curl http://localhost:8000/api/queue/status
```

Response:
```json
{
  "pending": 5,
  "running": 2,
  "failed": 1
}
```

## 📖 Documentation

- [Storage Configuration](./services/api/docs/Storage.md)
- [Queue (Celery/Redis)](./services/api/docs/Queue.md)
- [Vector Store Configuration](./services/api/docs/VectorStore.md)

## 🧪 Testing

### Run Tests
```bash
cd services/api
pytest tests/ -v

# With coverage
pytest tests/ --cov=app
```

### Test Upload Workflow
```bash
# 1. Create test file
echo "Test content" > test.txt

# 2. Upload
curl -X POST http://localhost:8000/api/storage/upload \
  -F "file=@test.txt"

# 3. Check job status
curl http://localhost:8000/api/queue/status

# 4. Search embeddings
curl "http://localhost:8000/api/vector-store/search?query=test"
```

## 🔧 CLI Commands

```bash
# Storage
python -m app.tools.storage_cli configure      # Configure storage
python -m app.tools.storage_cli test-connection # Test connection
python -m app.tools.storage_cli show-config    # Show current config

# Queue
python -m app.tools.queue_cli configure        # Configure queue
python -m app.tools.queue_cli status           # Show queue status
python -m app.tools.queue_cli list-jobs        # List jobs
python -m app.tools.queue_cli show-dlq         # Show dead letter queue
python -m app.tools.queue_cli retry            # Retry failed job

# Vector Store
python -m app.tools.vector_store_cli configure     # Configure
python -m app.tools.vector_store_cli test-connection # Test
python -m app.tools.vector_store_cli show-config   # Show config

# Health
python -m app.cli health                       # Check API health
```

## 📁 Project Structure

```
.
├── services/
│   └── api/
│       ├── app/
│       │   ├── api/routes/         # API endpoints
│       │   ├── core/               # Configuration, database, celery
│       │   ├── models/             # SQLAlchemy models
│       │   ├── schemas/            # Pydantic schemas
│       │   ├── services/           # Business logic
│       │   ├── tools/              # CLI commands
│       │   ├── workers/            # Celery tasks
│       │   ├── main.py             # FastAPI app
│       │   └── cli.py              # CLI entry point
│       ├── alembic/                # Database migrations
│       ├── docs/                   # Documentation
│       ├── tests/                  # Test suite
│       ├── docker-compose.yml      # Local services
│       └── pyproject.toml          # Dependencies
├── apps/
│   └── web/
│       ├── src/
│       │   ├── components/         # React components
│       │   ├── pages/              # Page components
│       │   ├── hooks/              # Custom hooks
│       │   └── App.tsx             # Main app
│       ├── index.html
│       └── package.json
├── infra/
│   ├── postgres/                   # PostgreSQL setup
│   ├── redis/                      # Redis config
│   └── supabase/                   # Supabase setup
└── README.md
```

## 🔒 Security

### Credentials Management
- Store secrets in `.env` (never commit)
- Use environment variables in production
- Encrypt sensitive fields at application level

### API Security
- CORS enabled for frontend
- Input validation via Pydantic
- File type and size validation
- Signed URLs for storage access

### Database
- SQL injection protection via SQLAlchemy ORM
- Row-level security (RLS) via Supabase
- Connection pooling and prepared statements

## 📊 Monitoring

### Logging
```bash
# View API logs
tail -f /tmp/api.log

# View worker logs
celery -A app.core.celery_app worker --loglevel=debug
```

### Redis Monitoring
```bash
redis-cli INFO stats
redis-cli KEYS "*"
redis-cli MONITOR
```

### Database
```sql
-- Connection count
SELECT count(*) FROM pg_stat_activity;

-- Query performance
SELECT query, mean_time FROM pg_stat_statements;

-- Vector index health
SELECT * FROM pg_stat_user_indexes WHERE relname LIKE 'embeddings%';
```

## 🐛 Troubleshooting

### Service Startup Issues

**Database connection fails**:
```bash
# Check PostgreSQL is running
docker-compose ps

# Check connection
psql -U postgres -d doc_ingestion -c "SELECT 1"
```

**Redis connection fails**:
```bash
# Check Redis is running
docker-compose ps

# Test connection
redis-cli ping
```

**Worker doesn't process jobs**:
```bash
# Verify worker is running
celery -A app.core.celery_app worker --loglevel=debug

# Check broker URL
python -c "from app.core.config import settings; print(settings.celery_broker_url)"
```

### Common Errors

**"No active storage config"**:
```bash
python -m app.tools.storage_cli configure ...
```

**"Dimension mismatch in embeddings"**:
- Check OpenAI embedding model in config
- Ensure database pgvector dimension matches (1536 for text-embedding-3-small)

**"Job stuck in RUNNING state"**:
```bash
# Check worker logs
# If worker crashed, restart:
celery -A app.core.celery_app worker --loglevel=info
```

## 🤝 Contributing

1. Create feature branch: `git checkout -b feature/amazing-feature`
2. Make changes and test: `pytest tests/`
3. Run type check: `mypy app/`
4. Commit: `git commit -m 'Add amazing feature'`
5. Push: `git push origin feature/amazing-feature`
6. Open PR

## 📝 License

MIT License - see LICENSE file for details

## 🎓 Learning Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [Celery Guide](https://docs.celeryproject.io/)
- [Supabase Documentation](https://supabase.com/docs)
- [pgvector Documentation](https://github.com/pgvector/pgvector)

## 📞 Support

- Open an issue for bugs
- Discussions for questions
- Documentation for guides

---

**Version**: 0.1.0 | **Status**: Milestone 1 - Infrastructure & Setup ✅
