-- Initialize PostgreSQL with pgvector extension
-- This script runs on first database creation

-- Create pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create uuid extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create pg_trgm for text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialized with extensions: vector, uuid-ossp, pg_trgm';
END $$;
