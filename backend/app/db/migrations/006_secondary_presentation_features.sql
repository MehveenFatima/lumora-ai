-- Migration 006: Secondary Presentation Features (Flashcards, Study Plans, Activity Events)

CREATE TABLE IF NOT EXISTS flashcards (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    concept TEXT NOT NULL,
    source_document TEXT,
    source_page INT DEFAULT 1,
    interval_days INT DEFAULT 1,
    last_reviewed DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flashcards_workspace_id ON flashcards(workspace_id);

CREATE TABLE IF NOT EXISTS study_plans (
    workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    daily_target_minutes INT DEFAULT 45,
    today_completed_minutes INT DEFAULT 0,
    weekly_target_minutes INT DEFAULT 225,
    week_completed_minutes INT DEFAULT 0,
    tasks JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS activity_events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_events_workspace_id ON activity_events(workspace_id);
