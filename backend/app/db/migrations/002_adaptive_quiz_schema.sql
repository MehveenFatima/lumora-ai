-- LumoraAI Phase 1: Adaptive Quiz Engine Schema
-- PostgreSQL + pgvector Schema with Strict Workspace Isolation

-- 1. Quiz Sessions Table
CREATE TABLE IF NOT EXISTS quiz_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL DEFAULT 'default_user',
    status TEXT NOT NULL DEFAULT 'active', -- 'pending', 'active', 'completed', 'abandoned'
    target_question_count INT NOT NULL DEFAULT 5,
    current_question_index INT NOT NULL DEFAULT 0,
    score INT NOT NULL DEFAULT 0,
    correct_count INT NOT NULL DEFAULT 0,
    total_count INT NOT NULL DEFAULT 0,
    average_response_time_ms INT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Quiz Questions Table
CREATE TABLE IF NOT EXISTS quiz_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quiz_session_id UUID NOT NULL REFERENCES quiz_sessions(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    question_index INT NOT NULL,
    topic TEXT NOT NULL,
    concept TEXT NOT NULL,
    difficulty INT NOT NULL DEFAULT 2, -- 1 = Easy, 2 = Medium, 3 = Hard
    question_text TEXT NOT NULL,
    options JSONB NOT NULL, -- Array of {"key": "A", "text": "..."}
    correct_option TEXT NOT NULL, -- 'A', 'B', 'C', or 'D'
    explanation TEXT NOT NULL,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    page_number INT,
    source_excerpt TEXT,
    citation_metadata JSONB DEFAULT '{}'::jsonb,
    generation_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Quiz Attempts Table
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quiz_session_id UUID NOT NULL REFERENCES quiz_sessions(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL DEFAULT 'default_user',
    selected_option TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    response_time_ms INT NOT NULL DEFAULT 0,
    answered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for Fast Scoped Filtering & Analytics
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_workspace_id ON quiz_sessions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_user_id ON quiz_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_session_id ON quiz_questions(quiz_session_id);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_workspace_id ON quiz_questions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_session_id ON quiz_attempts(quiz_session_id);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_workspace_id ON quiz_attempts(workspace_id);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_question_id ON quiz_attempts(question_id);
