-- Optional Postgres + pgvector memory store for production deployments.
-- The template defaults to a FAISS-backed memory store under data/rag/memory/.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memory_entries (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id     TEXT NOT NULL,
    content       TEXT NOT NULL,
    memory_type   TEXT NOT NULL,
    importance    REAL NOT NULL DEFAULT 0.5,
    embedding     vector(1536),
    source_ids    JSONB DEFAULT '[]',
    created_at    TIMESTAMPTZ DEFAULT now(),
    superseded_by UUID REFERENCES memory_entries(id)
);

CREATE INDEX IF NOT EXISTS idx_memory_thread ON memory_entries(thread_id);
