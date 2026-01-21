# Ingest Queue - Usage Guide

## Quick Start

### 1. Web UI Upload
1. Navigate to `http://localhost:3000/ingest`
2. Drag & drop a file or click to select
3. Click "Upload" button
4. Job ID appears in success message
5. Job appears in queue list within 5 seconds

### 2. CLI Upload
```bash
# Single file
python -m app.tools.ingest_cli enqueue /path/to/document.pdf

# Directory (all supported files)
python -m app.tools.ingest_cli enqueue-bulk /path/to/folder

# Check job status
python -m app.tools.ingest_cli status <job-id>

# List all jobs
python -m app.tools.ingest_cli list-jobs
```

### 3. SDK Upload
```python
from sdk import IngestionClient

client = IngestionClient("http://localhost:8000")

# Upload single file
job = client.upload_file("document.pdf")
print(f"Job ID: {job['job_id']}")

# Upload multiple files
results = client.batch_upload(["file1.pdf", "file2.md"])
print(f"Success: {results['succeeded']}, Failed: {results['failed']}")

# Get job status
status = client.get_job_status(job['job_id'])
print(f"Status: {status['status']}")

# List jobs
jobs = client.list_jobs(status="completed", page=1)
print(f"Total completed: {jobs['total']}")

client.close()
```

---

## Admin Pages

### 📥 Ingest Queue (`/ingest`)
- **Upload Section**: Drag-and-drop file upload
- **Queue Status**: Live counters (pending, processing, completed, failed)
- **Job List**:
  - Paginated table of all jobs
  - Filter by status
  - Shows filename, size, type, creation time
  - Auto-refreshes every 5 seconds

**Actions:**
- Upload new files
- Monitor queue health
- Check job progress

### 🚨 Dead Letter Queue (`/admin/dlq`)
- **Failed Jobs List**: All unrecoverable failures
- **Error Details**: Expandable rows with full error information
- **Retry History**: Track all attempts
- **Manual Notes**: Add notes to items

**Actions:**
- **Reprocess**: Re-enqueue failed job (pending_review items only)
- **Delete**: Remove item from DLQ
- **Add Notes**: Document triage decisions

### ⏰ Batch Schedules (`/admin/batch-schedules`)
- **Schedule List**: Table of all configured schedules
- **Create Form**: Add new schedules with:
  - Schedule name
  - Cron expression (e.g., "0 18 * * *" for 6 PM daily)
  - Max concurrency (1-100)
  - Batch size (1-500)
  - Optional description

**Actions:**
- **Create**: New schedule
- **Toggle**: Active/inactive
- **Delete**: Remove schedule

---

## API Examples

### Upload File
```bash
curl -X POST http://localhost:8000/api/ingest/upload \
  -F "file=@document.pdf" \
  -F "uploader_id=user123"

# Response:
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "storage_path": "uploads/document.pdf",
  "file_type": "pdf",
  "message": "File uploaded and job queued successfully"
}
```

### Get Job Status
```bash
curl http://localhost:8000/api/ingest/jobs/550e8400-e29b-41d4-a716-446655440000

# Response:
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "file_type": "pdf",
  "size": 1024000,
  "status": "pending",
  "storage_path": "uploads/document.pdf",
  "extracted_metadata": null,
  "error_message": null,
  "attempts": 0,
  "max_attempts": 3,
  "priority": "normal",
  "created_at": "2026-01-11T12:00:00Z",
  "updated_at": "2026-01-11T12:00:00Z"
}
```

### List Jobs
```bash
curl "http://localhost:8000/api/ingest/jobs?status=pending&page=1&page_size=20"

# Response:
{
  "total": 42,
  "page": 1,
  "page_size": 20,
  "items": [...]
}
```

### Get Queue Status
```bash
curl http://localhost:8000/api/ingest/status

# Response:
{
  "pending": 5,
  "processing": 2,
  "completed": 127,
  "failed": 1
}
```

### Create Batch Schedule
```bash
curl -X POST http://localhost:8000/api/batch/schedules \
  -H "Content-Type: application/json" \
  -d '{
    "schedule_name": "evening_batch",
    "cron_expression": "0 18 * * *",
    "max_concurrency": 5,
    "batch_size": 20,
    "description": "Daily evening batch at 6 PM"
  }'

# Response:
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "schedule_name": "evening_batch",
  "cron_expression": "0 18 * * *",
  "max_concurrency": 5,
  "batch_size": 20,
  "is_active": true,
  "last_run_at": null,
  "next_run_at": "2026-01-11T18:00:00Z",
  "description": "Daily evening batch at 6 PM",
  "created_at": "2026-01-11T12:00:00Z",
  "updated_at": "2026-01-11T12:00:00Z"
}
```

### List DLQ Items
```bash
curl "http://localhost:8000/api/ingest/dlq?status=pending_review&limit=50"

# Response: Array of DLQ items
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "original_filename": "corrupted.pdf",
    "error_message": "Corrupted PDF file",
    "retry_history": [...],
    "failure_count": 3,
    "manual_notes": null,
    "status": "pending_review",
    "created_at": "2026-01-11T12:00:00Z",
    "updated_at": "2026-01-11T12:00:00Z"
  }
]
```

### Reprocess DLQ Item
```bash
curl -X POST http://localhost:8000/api/ingest/dlq/550e8400-e29b-41d4-a716-446655440000/reprocess

# Response:
{
  "status": "reprocessed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Job has been re-queued for processing"
}
```

---

## Error Handling

### Common Status Codes

**200 OK** - Successful request
**201 Created** - Job created successfully
**204 No Content** - Successful delete
**400 Bad Request** - Invalid file type or parameters
**404 Not Found** - Job/schedule/DLQ item not found
**413 Payload Too Large** - File exceeds size limit
**500 Internal Server Error** - Server error (check logs)

### Common Errors

**"Unsupported file type: .doc"**
→ Only .docx is supported, not .doc

**"File size exceeds maximum"**
→ Increase MAX_UPLOAD_SIZE_MB in .env

**"Job not found"**
→ Check job ID exists with `GET /api/ingest/jobs`

**"Invalid cron expression"**
→ Use valid format: `minute hour day month day_of_week`
→ Example: `0 18 * * *` = 6 PM every day

---

## Monitoring

### Queue Health

```bash
# Check queue status
curl http://localhost:8000/api/ingest/status

# Expected response shows pending jobs are being processed
{
  "pending": 2,       # Low = healthy
  "processing": 1,    # Should see activity
  "completed": 50,    # Growing = healthy
  "failed": 0         # Ideally none
}
```

### DLQ Monitoring

```bash
# Check DLQ items
curl http://localhost:8000/api/ingest/dlq?status=pending_review

# If DLQ grows quickly, investigate:
# 1. Check error_message for patterns
# 2. Review job logs
# 3. Reprocess if transient error
# 4. Add notes for permanent failures
```

### Batch Performance

```bash
# Check next scheduled batch
curl http://localhost:8000/api/batch/schedules

# Look for:
# - is_active: true
# - next_run_at: in the future
# - last_run_at: recently updated
```

---

## Cron Expression Syntax

Format: `minute hour day month day_of_week`

### Common Examples

| Expression | Meaning |
|-----------|---------|
| `0 * * * *` | Every hour |
| `0 0 * * *` | Every day at midnight |
| `0 6 * * *` | Every day at 6 AM |
| `0 18 * * *` | Every day at 6 PM |
| `0 0 * * 0` | Every Sunday at midnight |
| `0 9 1 * *` | First of every month at 9 AM |
| `*/15 * * * *` | Every 15 minutes |
| `0 9-17 * * 1-5` | Every hour 9 AM-5 PM, Monday-Friday |

**Tools:**
- Online cron expression validator: https://crontab.guru/
- Verify before creating schedule in UI

---

## Troubleshooting

### "Jobs not appearing in queue"
1. Check file type is supported
2. Verify file size < MAX_UPLOAD_SIZE_MB
3. Check network request succeeded (check browser DevTools)
4. Wait 5 seconds for list to refresh
5. Check server logs for errors

### "Retry worker not running"
1. Verify Celery worker is running: `celery -A app.workers worker`
2. Verify Redis is running: `redis-cli ping`
3. Check logs for exceptions

### "Batch scheduler not triggering"
1. Verify Celery Beat is running: `celery -A app.core.celery_app beat`
2. Check schedule is_active = true
3. Verify cron expression is valid
4. Check next_run_at timestamp

### "DLQ item won't reprocess"
1. Verify status = "pending_review" (archived can't reprocess)
2. Check API response for errors
3. Verify job_id FK still exists
4. Check job max_attempts not exceeded

### "High memory usage"
1. Reduce batch_size (smaller batches = less concurrent jobs)
2. Reduce page_size when listing jobs
3. Archive old completed jobs

---

## Performance Tips

### For Large Uploads
- Use CLI bulk upload: `enqueue-bulk` with multiple jobs
- Set higher max_concurrency in batch schedules
- Monitor DLQ for failures

### For Many Jobs
- Increase batch_size in schedules (100+)
- Use multiple batch schedules at different times
- Monitor job completion rates

### For Slow Processing
- Check if jobs are failing (showing in DLQ)
- Increase max_concurrency if resource-bound
- Check CPU/memory availability on server

---

## Integration Examples

### Scheduled Daily Ingestion
```bash
# Create 8 AM batch
curl -X POST http://localhost:8000/api/batch/schedules \
  -H "Content-Type: application/json" \
  -d '{
    "schedule_name": "daily_morning",
    "cron_expression": "0 8 * * *",
    "max_concurrency": 10,
    "batch_size": 50
  }'

# Upload files in between - they'll be auto-batched at 8 AM
```

### Monitor via Webhook (Future)
```python
# After implementing webhooks
client.register_webhook("https://yourserver.com/webhook", events=["job_completed"])

# Webhook will POST when jobs complete
```

### Python Automation
```python
import time
from sdk import IngestionClient

client = IngestionClient()

# Upload files
jobs = client.batch_upload(["file1.pdf", "file2.md"])

# Wait for completion
for job_id in jobs['jobs']:
    while True:
        status = client.get_job_status(job_id['job_id'])
        if status['status'] in ['completed', 'failed']:
            print(f"{job_id['filename']}: {status['status']}")
            break
        time.sleep(5)

client.close()
```

---

## Next Steps

1. **Test the flow**: Upload → Monitor → View results
2. **Set up schedules**: Create batch schedules for your use case
3. **Monitor DLQ**: Check for failed jobs regularly
4. **Tune parameters**: Adjust concurrency and batch size based on performance
5. **Integrate**: Use CLI or SDK in your workflows

---

**Questions?** Check the logs or error messages in the DLQ admin panel.
