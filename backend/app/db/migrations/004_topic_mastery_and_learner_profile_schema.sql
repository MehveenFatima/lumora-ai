-- LumoraAI Phase 3: Topic Mastery Engine & Learner Knowledge Profile Schema
-- Concept-to-Topic Aggregation, Evidence Confidence, Trends & Mastery Snapshots

-- 1. Extend Learner Concept Mastery Table (Phase 2 -> Phase 3)
ALTER TABLE learner_concept_mastery ADD COLUMN IF NOT EXISTS bkt_version TEXT NOT NULL DEFAULT '1.0';
ALTER TABLE learner_concept_mastery ADD COLUMN IF NOT EXISTS incorrect_count INT NOT NULL DEFAULT 0;
ALTER TABLE learner_concept_mastery ADD COLUMN IF NOT EXISTS recent_accuracy DOUBLE PRECISION NOT NULL DEFAULT 0.0;
ALTER TABLE learner_concept_mastery ADD COLUMN IF NOT EXISTS average_response_time_ms INT NOT NULL DEFAULT 0;
ALTER TABLE learner_concept_mastery ADD COLUMN IF NOT EXISTS repeated_error_count INT NOT NULL DEFAULT 0;
ALTER TABLE learner_concept_mastery ADD COLUMN IF NOT EXISTS first_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE learner_concept_mastery ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE learner_concept_mastery ADD COLUMN IF NOT EXISTS mastery_status TEXT NOT NULL DEFAULT 'developing';
ALTER TABLE learner_concept_mastery ADD COLUMN IF NOT EXISTS confidence_level TEXT NOT NULL DEFAULT 'low';
ALTER TABLE learner_concept_mastery ADD COLUMN IF NOT EXISTS trend TEXT NOT NULL DEFAULT 'insufficient_data';

-- 2. Create Learner Topic Mastery Table
CREATE TABLE IF NOT EXISTS learner_topic_mastery (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL DEFAULT 'default_user',
    topic TEXT NOT NULL,
    mastery_probability DOUBLE PRECISION NOT NULL DEFAULT 0.30, -- Aggregated BKT probability
    confidence_level TEXT NOT NULL DEFAULT 'low', -- 'low', 'moderate', 'high'
    mastery_status TEXT NOT NULL DEFAULT 'developing', -- 'strong', 'developing', 'needs_review', 'critical_gap', 'low_evidence'
    trend TEXT NOT NULL DEFAULT 'insufficient_data', -- 'improving', 'declining', 'stable', 'insufficient_data'
    concept_count INT NOT NULL DEFAULT 0,
    assessed_concept_count INT NOT NULL DEFAULT 0,
    coverage_ratio DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    attempt_count INT NOT NULL DEFAULT 0,
    correct_count INT NOT NULL DEFAULT 0,
    recent_accuracy DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    average_response_time_ms INT NOT NULL DEFAULT 0,
    gap_priority DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    last_assessed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_learner_topic UNIQUE (workspace_id, user_id, topic)
);

-- 3. Create Learner Mastery Snapshots Table (Historical Trends & Analytics)
CREATE TABLE IF NOT EXISTS learner_mastery_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL DEFAULT 'default_user',
    entity_type TEXT NOT NULL, -- 'concept', 'topic', 'workspace'
    entity_id TEXT NOT NULL,   -- concept name, topic name, or workspace id
    mastery_probability DOUBLE PRECISION NOT NULL,
    confidence_level TEXT NOT NULL,
    gap_priority DOUBLE PRECISION DEFAULT 0.0,
    attempt_count INT NOT NULL DEFAULT 0,
    snapshot_event TEXT NOT NULL DEFAULT 'attempt', -- 'attempt', 'round_complete', 'session_complete'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for Scoped Fast Filtering
CREATE INDEX IF NOT EXISTS idx_topic_mastery_lookup ON learner_topic_mastery(workspace_id, user_id, topic);
CREATE INDEX IF NOT EXISTS idx_mastery_snapshots_lookup ON learner_mastery_snapshots(workspace_id, user_id, entity_type, entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_concept_mastery_workspace ON learner_concept_mastery(workspace_id, user_id);
