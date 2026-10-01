-- ============================================================================
-- 008: User accounts and workspace ownership
-- ============================================================================
-- Every workspace belongs to one user. All learner data (documents, chunks,
-- quizzes, mastery, flashcards, study plans, activity) is scoped by workspace,
-- so ownership of the workspace is what isolates one user's data from another's.

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS owner_id TEXT REFERENCES users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_workspaces_owner_id ON workspaces(owner_id);

-- Workspaces created before this migration have no owner and are not visible to
-- anyone until claimed:  python -m backend.app.cli claim-workspaces --email you@example.com
