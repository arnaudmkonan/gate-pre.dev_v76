# Vector Store Configuration Guide

## Overview

The Vector Store system provides semantic search capabilities by converting document content into embeddings and storing them in a vector database. Supports Supabase pgvector (PostgreSQL) and Pinecone.

## Architecture

- **Backend**: Supabase (pgvector) or Pinecone
- **Embedding Model**: OpenAI text-embedding-3-small (default)
- **Dimension**: 1536 (auto-set based on model)
- **Indexing**: IVFFLAT or HNSW for ANN search
- **Namespace**: Project-based isolation support

## Setup

### Supabase pgvector Setup

1. Enable pgvector extension in Supabase:
   ```sql
   CREATE EXTENSION vector;
   ```

2. Migration creates embeddings table automatically (run: `alembic upgrade head`)

3. Get Supabase endpoint and API key from Settings → API

### Configuration

**Admin UI**: Navigate to `/admin/vector-store-config`

**CLI**:
```bash
python -m app.tools.vector_store_cli configure \
  --backend supabase \
  --url https://your-project.supabase.co \
  --api-key YOUR_API_KEY \
  --embedding-model text-embedding-3-small \
  --namespace my-documents
```

**Test Connection**:
```bash
python -m app.tools.vector_store_cli test-connection
```

## API Endpoints

### Create Vector Store Config
**POST** `/api/vector-store/config`

**Request**:
```json
{
  "backend": "supabase",
  "url": "https://your-project.supabase.co",
  "api_key": "YOUR_API_KEY",
  "embedding_model": "text-embedding-3-small",
  "embedding_dimension": 1536,
  "namespace_collection_name": "my-documents"
}
```

### Get Vector Store Config
**GET** `/api/vector-store/config`

**Response** (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "backend": "supabase",
  "url": "https://your-project.supabase.co",
  "embedding_model": "text-embedding-3-small",
  "embedding_dimension": 1536,
  "namespace_collection_name": "my-documents",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Search Embeddings
**POST** `/api/vector-store/search?query=...&limit=10`

**Request**:
```bash
curl "http://localhost:8000/api/vector-store/search?query=authentication&limit=10"
```

**Response** (200):
```json
{
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "content_chunk": "User authentication is handled via JWT tokens...",
      "metadata_source_file_id": "file_123",
      "metadata_timestamp": "2024-01-09T21:00:00Z",
      "metadata_embedding_model": "text-embedding-3-small",
      "similarity_score": 0.92
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "content_chunk": "Multi-factor authentication provides additional security...",
      "metadata_source_file_id": "file_456",
      "metadata_timestamp": "2024-01-09T21:05:00Z",
      "metadata_embedding_model": "text-embedding-3-small",
      "similarity_score": 0.87
    }
  ],
  "query_time_ms": 245
}
```

### Get Embeddings for Document
**GET** `/api/vector-store/embeddings?upload_id=...&limit=50`

**Response** (200):
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "content_chunk": "First 2000 chars of content...",
    "metadata_source_file_id": "file_123",
    "metadata_timestamp": "2024-01-09T21:00:00Z",
    "metadata_embedding_model": "text-embedding-3-small",
    "similarity_score": null
  }
]
```

## Embedding Pipeline

### Process Flow

1. **Upload File**
   ```
   POST /api/storage/upload → UploadMetadata created
   ```

2. **Enqueue Job**
   ```
   Celery task: enqueue_for_processing(upload_id, metadata)
   JobLog status: PENDING
   ```

3. **Extract Content** (Future: dedicated extraction agents)
   ```
   Worker processes file, extracts text chunks
   ```

4. **Generate Embeddings**
   ```
   Call OpenAI embedding API for each chunk
   Store vector + metadata in embeddings table
   ```

5. **Searchable**
   ```
   Within 60 seconds of upload, vectors are indexed
   ANN search immediately available
   ```

### Metadata Provenance

Each embedding stores:
- `source_file_id`: Original file ID (links to upload_metadata)
- `timestamp`: When embedding was generated
- `embedding_model`: Which model was used (text-embedding-3-small)
- `content_chunk`: First 2000 chars of content (for context)

## Similarity Search

### Cosine Similarity
Default metric: cosine distance (1 - dot product)

```python
# Query embedding matches similar documents
query_vector = generate_embedding("authentication")
results = search_similar(query_vector, limit=10)
# Returns: [doc1(0.92), doc2(0.87), ...]
```

### Score Interpretation
- `1.0`: Perfect match
- `0.8-0.9`: Highly relevant
- `0.6-0.8`: Somewhat relevant
- `<0.6`: Low relevance

## Indexing Strategy

### IVFFLAT (Default)
- Fast approximate search
- Lower memory usage
- Good for 1-10M vectors
- Configure in migration

### HNSW (Alternative)
- Faster for smaller datasets
- Higher memory overhead
- Better for frequent updates

## Validation

### Dimension Checking
Validates embedding dimensions match config:
```python
if len(embedding) != expected_dimension:
    raise ValueError("Dimension mismatch")
```

### Content Validation
- Chunks up to 2000 characters
- Skips empty/whitespace-only chunks
- Handles multiple languages

## Namespace/Collection Management

Isolate embeddings by project:

```python
# Create embeddings in namespace
config.namespace_collection_name = "project_123"

# Search within namespace
search_similar(query, namespace="project_123")
```

Useful for:
- Multi-tenant applications
- Project-specific search
- Compliance data isolation

## CLI Commands

```bash
# Configure vector store
python -m app.tools.vector_store_cli configure \
  --backend supabase \
  --url https://your-project.supabase.co \
  --api-key YOUR_KEY

# Test connection
python -m app.tools.vector_store_cli test-connection

# Show config
python -m app.tools.vector_store_cli show-config
```

## Production Configuration

### OpenAI API
```bash
export OPENAI_API_KEY="sk-..."
```

### Recommended Settings
```python
{
  "backend": "supabase",
  "embedding_model": "text-embedding-3-small",
  "embedding_dimension": 1536,
  "namespace_collection_name": "production"
}
```

### Rate Limiting
OpenAI has rate limits:
- Requests per minute: 3,500 (tier dependent)
- Tokens per minute: 90,000

Monitor and implement backoff if needed.

### Cost Management
text-embedding-3-small: $0.02 per 1M tokens

Estimate:
- 100K documents × 100 tokens avg = 10M tokens
- Cost: ~$0.20

## Performance Tuning

### Index Optimization
For large datasets (>1M vectors):
```sql
-- Use HNSW for better performance
CREATE INDEX embeddings_vector_hnsw
  ON embeddings USING hnsw (vector vector_cosine_ops);
```

### Query Optimization
- Limit results: default 10, reasonable max 100
- Use namespaces to partition data
- Cache frequent queries (future: Redis)

## Troubleshooting

### "No active vector store config"
Configure vector store:
```bash
python -m app.tools.vector_store_cli configure ...
```

### Slow searches
Check index exists:
```sql
SELECT * FROM pg_stat_user_indexes
WHERE relname = 'embeddings';
```

If missing, recreate via migration.

### Dimension mismatch error
Ensure embedding model matches dimension:
- text-embedding-3-small: 1536 ✓
- text-embedding-3-large: 3072
- other models: verify docs

### Missing embeddings
1. Verify upload was processed (check job_log)
2. Check for extraction errors (review error_message)
3. Verify vector store connection

## Monitoring

### Vector Count by Document
```sql
SELECT upload_metadata_id, COUNT(*)
FROM embeddings
GROUP BY upload_metadata_id;
```

### Index Health
```sql
SELECT * FROM pg_stat_user_indexes
WHERE schemaname = 'public';
```

### Search Performance
Monitor `query_time_ms` in SearchResponse

## Future Enhancements

- [ ] Batch embedding generation for performance
- [ ] Semantic caching with Redis
- [ ] Support for hybrid search (vector + keyword)
- [ ] Custom embedding models
- [ ] Re-ranking with cross-encoders
