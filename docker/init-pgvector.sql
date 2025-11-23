-- Initialize pgvector extension for LightRAG
-- This script runs automatically on first container startup

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
DO $$
BEGIN
    RAISE NOTICE 'pgvector extension installed successfully';
    RAISE NOTICE 'PostgreSQL version: %', version();
END $$;
