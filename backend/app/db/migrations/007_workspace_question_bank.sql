-- Migration 007: Workspace Question Bank Schema
CREATE TABLE IF NOT EXISTS workspace_question_bank (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    concept TEXT NOT NULL,
    difficulty INT NOT NULL DEFAULT 2,
    question_text TEXT NOT NULL,
    options JSONB NOT NULL,
    correct_option TEXT NOT NULL,
    explanation TEXT NOT NULL,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    source_chunk_id TEXT,
    page_number INT,
    source_excerpt TEXT,
    citation_metadata JSONB DEFAULT '{}'::jsonb,
    generation_metadata JSONB DEFAULT '{}'::jsonb,
    fingerprint TEXT UNIQUE,
    question_type TEXT NOT NULL DEFAULT 'conceptual',
    quality_score DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_question_bank_workspace_id ON workspace_question_bank(workspace_id);
CREATE INDEX IF NOT EXISTS idx_question_bank_fingerprint ON workspace_question_bank(fingerprint);
