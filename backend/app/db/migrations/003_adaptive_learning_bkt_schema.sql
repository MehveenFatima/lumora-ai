-- LumoraAI Phase 2: True Adaptive Learning Engine Schema
-- BKT Concept Mastery, Multi-Signal Knowledge Gaps & Question Fingerprints

-- 1. Learner Concept Mastery Table (BKT State)
CREATE TABLE IF NOT EXISTS learner_concept_mastery (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL DEFAULT 'default_user',
    topic TEXT NOT NULL,
    concept TEXT NOT NULL,
    p_mastery DOUBLE PRECISION NOT NULL DEFAULT 0.30, -- BKT P(K)
    attempts_count INT NOT NULL DEFAULT 0,
    correct_count INT NOT NULL DEFAULT 0,
    last_response_time_ms INT NOT NULL DEFAULT 0,
    last_practiced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_learner_concept UNIQUE (workspace_id, user_id, concept)
);

-- 2. Learner Knowledge Gaps Table
CREATE TABLE IF NOT EXISTS learner_knowledge_gaps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL DEFAULT 'default_user',
    topic TEXT NOT NULL,
    concept TEXT NOT NULL,
    gap_priority DOUBLE PRECISION NOT NULL DEFAULT 0.50, -- 0.0 to 1.0
    gap_status TEXT NOT NULL DEFAULT 'developing', -- 'strong', 'developing', 'needs_attention', 'critical_gap'
    contributing_signals JSONB DEFAULT '{}'::jsonb,
    recommended_action TEXT NOT NULL DEFAULT 'targeted_practice',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_learner_gap UNIQUE (workspace_id, user_id, concept)
);

-- 3. Quiz Question Fingerprints Table (Deduplication)
CREATE TABLE IF NOT EXISTS quiz_question_fingerprints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    quiz_session_id UUID NOT NULL REFERENCES quiz_sessions(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Alter Quiz Sessions for Multi-Batch Lifecycle
ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS adaptation_round INT NOT NULL DEFAULT 1;
ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS initial_diagnostic_completed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS current_adaptation_stage TEXT NOT NULL DEFAULT 'diagnostic';
ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS current_target_concepts JSONB DEFAULT '[]'::jsonb;

-- 5. Alter Quiz Questions for Fingerprints
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS fingerprint TEXT;

-- Indexes for Fast Scoped Filtering
CREATE INDEX IF NOT EXISTS idx_concept_mastery_lookup ON learner_concept_mastery(workspace_id, user_id, concept);
CREATE INDEX IF NOT EXISTS idx_knowledge_gaps_lookup ON learner_knowledge_gaps(workspace_id, user_id, gap_priority DESC);
CREATE INDEX IF NOT EXISTS idx_question_fingerprints_lookup ON quiz_question_fingerprints(workspace_id, fingerprint);
