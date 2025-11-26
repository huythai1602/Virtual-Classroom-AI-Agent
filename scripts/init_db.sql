-- PostgreSQL + pgvector Database Schema
-- Run this after creating the database and enabling pgvector extension

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Lessons table: stores lesson metadata and full transcripts
CREATE TABLE IF NOT EXISTS lessons (
    id SERIAL PRIMARY KEY,
    lesson_id VARCHAR(50) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    subject VARCHAR(50) NOT NULL,
    grade INTEGER NOT NULL,
    transcript TEXT NOT NULL,
    summary TEXT,
    total_chunks INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

-- Chunks table: stores text chunks with vector embeddings
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    lesson_id VARCHAR(50) NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT fk_lesson 
        FOREIGN KEY (lesson_id) 
        REFERENCES lessons(lesson_id) 
        ON DELETE CASCADE,
    UNIQUE(lesson_id, chunk_index)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_lessons_lesson_id ON lessons(lesson_id);
CREATE INDEX IF NOT EXISTS idx_lessons_subject_grade ON lessons(subject, grade);
CREATE INDEX IF NOT EXISTS idx_lessons_status ON lessons(status);
CREATE INDEX IF NOT EXISTS idx_chunks_lesson_id ON chunks(lesson_id);

-- IVFFlat index for vector similarity search
-- lists = 100 is suitable for ~10,000 chunks
-- For 100,000+ chunks, increase to lists = 1000
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- Verify setup
SELECT 'pgvector extension enabled' AS status 
WHERE EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector');

SELECT 'Tables created successfully' AS status 
WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'lessons')
  AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chunks');
