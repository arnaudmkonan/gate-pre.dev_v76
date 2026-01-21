# Quick Start: REST/SDK API

## Running the Platform

### Backend
```bash
cd services/api
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (already running on port 3000)
```bash
cd apps/web
npm install
npm run dev
```

### Redis (for Celery task queue)
```bash
docker run -d -p 6379:6379 redis:latest
```

### PostgreSQL (for database)
```bash
docker run -d -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  postgres:15
```

## Key URLs

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## API Quick Reference

### Upload a File
```bash
curl -X POST http://localhost:8000/api/upload \
  -H "Idempotency-Key: $(uuidgen)" \
  -F "file=@document.pdf" \
  -F "customer_id=cust_123" \
  -F "source=api" \
  -F "tags=important,2025"
```

**Response (202 Accepted):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_id": "550e8400-e29b-41d4-a716-446655440001",
  "filename": "document.pdf",
  "storage_path": "uploads/document.pdf",
  "status": "pending"
}
```

### Query Metadata
```bash
curl "http://localhost:8000/api/metadata?job_id=550e8400-e29b-41d4-a716-446655440000"
```

### Search by Customer
```bash
curl "http://localhost:8000/api/metadata?customer_id=cust_123&ingestion_status=completed&page_size=50"
```

## File Routes

### Backend Routes
- **Upload**: `app/api/routes/upload.py`
- **Callbacks**: `app/api/routes/storage_callbacks.py`
- **Metadata**: `app/api/routes/metadata.py`

### Database Models
- **RawFile**: `app/models/raw_file.py`
- **Metadata**: `app/models/document_metadata.py`
- **Idempotency**: `app/models/upload_idempotency.py`

### Services
- **Storage**: `app/services/storage_service.py`
- **Idempotency**: `app/services/idempotency_service.py`
- **Callbacks**: `app/services/storage_callback_service.py`
- **Metadata Queries**: `app/services/metadata_query_service.py`

### Frontend Components
- **Upload Form**: `apps/web/src/components/UploadForm.tsx`
- **Metadata Search**: `apps/web/src/pages/MetadataPage.tsx`

## Common Tasks

### Testing Upload Endpoint
```bash
# Create a test file
echo "Test document content" > test.txt

# Upload with all metadata
curl -X POST http://localhost:8000/api/upload \
  -H "Idempotency-Key: test-key-$(date +%s)" \
  -F "file=@test.txt" \
  -F "customer_id=test_customer" \
  -F "source=testing" \
  -F "tags=test,example"

# Check job status
curl "http://localhost:8000/api/ingest/jobs/{job_id}"
```

### Testing Idempotency
```bash
# First upload
RESPONSE=$(curl -s -X POST http://localhost:8000/api/upload \
  -H "Idempotency-Key: unique-key-123" \
  -F "file=@test.txt")

JOB_ID=$(echo $RESPONSE | jq -r '.job_id')

# Retry with same key
curl -X POST http://localhost:8000/api/upload \
  -H "Idempotency-Key: unique-key-123" \
  -F "file=@test.txt"

# Should return same job_id
```

### Testing Metadata Queries
```bash
# Query with no results
curl "http://localhost:8000/api/metadata?customer_id=nonexistent"

# Query by status
curl "http://localhost:8000/api/metadata?ingestion_status=completed&page_size=100"

# Get specific metadata
curl "http://localhost:8000/api/metadata/{metadata_id}"
```

## Database Queries

### List recent uploads
```sql
SELECT id, filename, file_type, file_size, status, created_at
FROM raw_files
ORDER BY created_at DESC
LIMIT 20;
```

### Find uploads by customer
```sql
SELECT id, filename, file_size, status
FROM raw_files
WHERE customer_id = 'cust_123'
ORDER BY created_at DESC;
```

### Check metadata availability
```sql
SELECT job_id, filename, ingestion_status, extraction_timestamp
FROM document_metadata
WHERE customer_id = 'cust_123'
ORDER BY created_at DESC;
```

### Check idempotency keys
```sql
SELECT idempotency_key, file_id, job_id, expires_at
FROM upload_idempotency_keys
WHERE expires_at > NOW()
ORDER BY expires_at DESC;
```

## Debugging

### Check API Logs
```bash
# Frontend dev server
npm run dev  # Logs to terminal

# Backend
python -m uvicorn app.main:app --reload  # Logs to terminal
```

### Check Database Connection
```bash
# PostgreSQL
psql -h localhost -U postgres -d doc_ingestion

# Redis
redis-cli ping  # Should return PONG
```

### View OpenAPI Schema
Open browser: http://localhost:8000/docs

### Database Migration Check
```bash
# List migrations
cd services/api
python -m alembic history

# Apply migrations
python -m alembic upgrade head

# Rollback
python -m alembic downgrade -1
```

## Environment Variables

### Backend (.env)
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/doc_ingestion
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxxx
SUPABASE_STORAGE_BUCKET=raw-files
STORAGE_CALLBACK_SECRET=dev-secret-change-in-production
MAX_UPLOAD_SIZE_MB=50
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
DEBUG=True
ENVIRONMENT=development
```

### Frontend (.env)
```
VITE_API_URL=http://localhost:8000
```

## Documentation

- **Upload API**: See `services/api/docs/UPLOAD_API.md`
- **Storage Callbacks**: See `services/api/docs/STORAGE_CALLBACKS.md`
- **Metadata API**: See `services/api/docs/METADATA_API.md`
- **Implementation Details**: See `REST_API_IMPLEMENTATION.md`

## Troubleshooting

### Upload Returns 415 Unsupported Media Type
- Check file extension is in supported list: txt, docx, xlsx, pptx, html, md, json, csv, yml, xml
- File extension must be lowercase

### Upload Returns 413 Payload Too Large
- File exceeds 50MB limit
- Change `MAX_UPLOAD_SIZE_MB` environment variable

### Metadata Returns 204 No Content
- Extraction is still in progress
- Wait a few seconds and retry
- Check extraction worker is running

### Storage Callback Fails Validation
- Verify `STORAGE_CALLBACK_SECRET` matches in environment
- Check raw request body matches signed payload
- Ensure no URL encoding or modifications

### Database Errors
- Check PostgreSQL is running: `psql -h localhost -U postgres`
- Verify connection string in `.env`
- Run migrations: `python -m alembic upgrade head`

## Performance Tips

1. **Indexes**: All main queries have indexes (job_id, customer_id, status, file_type)
2. **Pagination**: Always use pagination for large result sets (page_size=20-100)
3. **Caching**: Metadata is computed once during extraction, queried many times
4. **Async**: All endpoints are async - database operations don't block

## Next Steps

1. Configure Supabase Storage and webhook
2. Set up proper environment variables
3. Run integration tests
4. Deploy to Railway
5. Monitor with Sentry

See `REST_API_IMPLEMENTATION.md` for deployment checklist.
