-- LumoraAI Database Initial Schema
-- PostgreSQL + pgvector Schema with strict Workspace Isolation

-- Enable the pgvector extension for dense embedding storage and similarity search
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Workspaces Table
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    goal TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'intermediate',
    target_date DATE,
    daily_target_minutes INT DEFAULT 45,
    description TEXT,
    overall_mastery INT DEFAULT 0,
    mastery_delta INT DEFAULT 0,
    status TEXT DEFAULT 'active',
    icon_name TEXT DEFAULT 'FolderKanban',
    document_count INT DEFAULT 0,
    topics_count INT DEFAULT 0,
    flashcards_due_count INT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Documents Table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL, -- 'pdf', 'docx', 'pptx', 'txt'
    file_size BIGINT NOT NULL,
    storage_path TEXT,
    page_count INT DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'uploading', -- 'uploading', 'processing', 'extracting', 'indexing', 'ready', 'failed'
    chunk_count INT DEFAULT 0,
    error_message TEXT,
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Document Chunks Table with 768-dimensional pgvector Embedding
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    page_number INT DEFAULT 1,
    heading TEXT,
    text TEXT NOT NULL,
    token_count INT,
    embedding vector(768) NOT NULL, -- 768-dim Google Gemini embeddings (L2 normalized)
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Tutor Conversations Table
CREATE TABLE IF NOT EXISTS tutor_conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    title TEXT DEFAULT 'Tutor Conversation',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Tutor Messages Table
CREATE TABLE IF NOT EXISTS tutor_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES tutor_conversations(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    role TEXT NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    citations JSONB DEFAULT '[]'::jsonb,
    retrieval_metadata JSONB DEFAULT '{}'::jsonb,
    feedback TEXT, -- 'like', 'dislike'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for Fast Scoped Filtering & Vector Similarity Search
CREATE INDEX IF NOT EXISTS idx_documents_workspace_id ON documents(workspace_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_workspace_id ON document_chunks(workspace_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_tutor_conversations_workspace_id ON tutor_conversations(workspace_id);
CREATE INDEX IF NOT EXISTS idx_tutor_messages_conversation_id ON tutor_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_tutor_messages_workspace_id ON tutor_messages(workspace_id);

-- Cosine Distance Vector Index (HNSW) for fast nearest neighbor search within workspace
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw 
ON document_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Seed Baseline Workspaces
INSERT INTO workspaces (id, name, goal, description, overall_mastery, mastery_delta, status, document_count)
VALUES 
    ('dsa', 'Data Structures & Algorithms', 'Placement Prep 2026', 'Master fundamental and advanced algorithmic problem solving.', 74, 5, 'on_track', 3),
    ('os', 'Operating Systems', 'Semester 5 Core Prep', 'Concurrency, virtual memory management, and file systems.', 64, 3, 'on_track', 2),
    ('ml', 'Machine Learning & AI', 'Certification Track', 'Statistical modeling, deep learning architectures, and transformers.', 57, 7, 'active', 2),
    ('aws', 'AWS Solutions Architect', 'SAA-C03 Certification', 'Cloud architecture, high availability, VPC, and IAM policies.', 48, 4, 'active', 1)
ON CONFLICT (id) DO NOTHING;
