# Queue (Redis/Celery) Configuration Guide

## Overview

The Queue system uses Redis as a message broker and Celery for distributed task processing. Jobs are enqueued on file upload, processed by worker processes, and tracked with full audit logging.

## Architecture

- **Broker**: Redis (pub/sub, persistence)
- **Task Queue**: Celery with async task execution
- **Worker Processes**: Configurable concurrency
- **Retry Policy**: Exponential backoff with jitter
- **Dead Letter Queue**: Failed jobs after max retries
- **Job Audit Logging**: Full job lifecycle tracking

## Setup

### Redis Installation

**Docker**:
```bash
docker run -d --name doc_ingestion_redis \
  -p 6379:6379 \
  redis:7-alpine
```

**Local Install** (macOS):
```bash
brew install redis
redis-server
```

### Celery Worker

Start worker in separate terminal:
```bash
celery -A app.core.celery_app worker --loglevel=info
```

For multiple workers:
```bash
celery -A app.core.celery_app worker --concurrency=4 --loglevel=info
```

### Configuration

**Admin UI**: Navigate to `/admin/queue-config`

**CLI**:
```bash
python -m app.tools.queue_cli configure \
  --redis-host localhost \
  --redis-port 6379 \
  --concurrency 4 \
  --timeout 3600 \
  --max-retries 3
```

**Test Connection**:
```bash
python -m app.tools.queue_cli status
```

## Job Lifecycle

```
PENDING → RUNNING → COMPLETED
              ↓
            FAILED → RETRIED → RUNNING ... (up to max_retries)
              ↓
        DEAD_LETTER_QUEUE (manual review)
```

## API Endpoints

### Get Queue Status
**GET** `/api/queue/status`

**Response** (200):
```json
{
  "pending": 5,
  "running": 2,
  "failed": 1
}
```

### List Jobs
**GET** `/api/queue/jobs?page=1&page_size=20&status=running`

**Response** (200):
```json
{
  "total": 42,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "job_id": "abc123xyz",
      "upload_metadata_id": "...",
      "job_type": "extraction",
      "status": "running",
      "retry_count": 0,
      "attempts": 1,
      "started_at": "2024-01-09T21:05:00Z",
      "completed_at": null,
      "created_at": "2024-01-09T21:00:00Z"
    }
  ]
}
```

### Get Dead Letter Queue
**GET** `/api/queue/dlq?limit=50`

**Response** (200):
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "job_id": "abc123xyz",
    "error_message": "Connection timeout",
    "final_exception": "TimeoutError",
    "created_at": "2024-01-09T21:00:00Z",
    "marked_resolved_at": null
  }
]
```

### Retry Job
**POST** `/api/queue/jobs/{job_id}/retry`

**Response** (200):
```json
{
  "status": "retry_queued",
  "job_id": "abc123xyz"
}
```

### Queue Config Management
**POST** `/api/queue/config`
**GET** `/api/queue/config`

## Retry Policy

### Exponential Backoff

Retry delays increase exponentially:
- Retry 1: 2^1 = 2 seconds + jitter
- Retry 2: 2^2 = 4 seconds + jitter
- Retry 3: 2^3 = 8 seconds + jitter
- Max: capped at 3600 seconds (1 hour)

### Transient Exceptions

Retried automatically:
- `ConnectionError`: Network issues
- `TimeoutError`: Slow responses
- `OSError`: File/system errors

### Permanent Exceptions

Not retried, move to DLQ immediately:
- `ValueError`: Invalid input
- `FileNotFoundError`: Missing required files
- Custom business logic exceptions

## CLI Commands

```bash
# Show queue status
python -m app.tools.queue_cli status

# List recent jobs
python -m app.tools.queue_cli list-jobs --page 1 --status running

# View dead letter queue
python -m app.tools.queue_cli show-dlq --limit 20

# Retry specific job
python -m app.tools.queue_cli retry --job-id abc123xyz
```

## Monitoring

### Redis Memory
```bash
redis-cli INFO memory
```

### Active Jobs
```bash
python -m app.tools.queue_cli status
```

### Worker Health
Check logs in separate worker terminal for:
- Task execution times
- Retry attempts
- Failed jobs

## Production Configuration

### Recommended Settings
```python
{
  "redis_host": "your-redis-host",
  "redis_port": 6379,
  "redis_password": "strong-password",
  "worker_concurrency": 8,        # Match CPU cores
  "task_timeout": 1800,            # 30 minutes
  "max_retries": 5,                # More aggressive retry
  "retry_backoff": true            # Exponential backoff
}
```

### Redis Persistence
Enable AOF (append-only file) for durability:
```bash
redis-cli CONFIG SET appendonly yes
```

### Worker Scaling
Deploy multiple worker instances:
```bash
# Scale to N workers
for i in {1..4}; do
  celery -A app.core.celery_app worker --loglevel=info &
done
```

## Dead Letter Queue Management

### Automatic Handling
Failed jobs after max_retries automatically move to DLQ

### Manual Review
Access via `/api/queue/dlq` endpoint:
- Review error message and traceback
- Determine if issue is fixed
- Use retry endpoint to requeue

### Cleanup
Mark resolved jobs in DLQ (future enhancement):
```python
# POST /api/queue/dlq/{dlq_id}/resolve
```

## Troubleshooting

### Redis Connection Error
Check Redis is running:
```bash
redis-cli ping
# Should return: PONG
```

### Jobs Not Processing
1. Verify worker is running: `celery -A app.core.celery_app worker --loglevel=info`
2. Check Redis broker URL in config
3. View worker logs for errors

### High Retry Rate
Check job implementation for transient issues:
- Network stability
- Resource availability
- Database connection pooling

### Memory Leak
Monitor Redis memory:
```bash
redis-cli INFO memory | grep used_memory_human
```

Consider reducing result retention in config:
```python
{
  "result_expires": 3600  # Expire results after 1 hour
}
```

## Performance Tuning

### Concurrency
```python
# CPU-intensive tasks
worker_concurrency = CPU_CORES

# I/O-intensive tasks
worker_concurrency = CPU_CORES * 2-4
```

### Prefetch
Reduce prefetch multiplier for long-running tasks:
```python
worker_prefetch_multiplier = 1  # Default: 4
```

### Task Compression
Enable for large payloads:
```python
task_compression = "gzip"
```
