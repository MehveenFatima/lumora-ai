-- 011: Topic map per document, and quality metadata for the question bank and flashcards
--
-- workspace_concepts holds the concepts the AI identified in each document (with a short summary,
-- the key facts a learner must know and the pages they come from). Quiz questions and flashcards
-- are generated per concept from it, so they cover the real subject matter of the notes.

CREATE TABLE IF NOT EXISTS workspace_concepts (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    document_id TEXT,
    document_name TEXT,
    topic TEXT NOT NULL,
    concept TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    key_points JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_pages JSONB NOT NULL DEFAULT '[]'::jsonb,
    position INT NOT NULL DEFAULT 0,
    method TEXT NOT NULL DEFAULT 'ai',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workspace_concepts_workspace ON workspace_concepts(workspace_id);
CREATE INDEX IF NOT EXISTS idx_workspace_concepts_document ON workspace_concepts(document_id);
ALTER TABLE workspace_concepts ENABLE ROW LEVEL SECURITY;

-- Question bank: link to the concept, keep an embedding for meaning-based duplicate checks,
-- and make fingerprints unique per workspace instead of across all workspaces
ALTER TABLE workspace_question_bank ADD COLUMN IF NOT EXISTS concept_id TEXT;
ALTER TABLE workspace_question_bank ADD COLUMN IF NOT EXISTS embedding JSONB;
ALTER TABLE workspace_question_bank ADD COLUMN IF NOT EXISTS generator TEXT;
ALTER TABLE workspace_question_bank DROP CONSTRAINT IF EXISTS workspace_question_bank_fingerprint_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_question_bank_workspace_fingerprint
    ON workspace_question_bank(workspace_id, fingerprint);
CREATE INDEX IF NOT EXISTS idx_question_bank_concept ON workspace_question_bank(concept_id);
-- Questions from the earlier template generator are retired; the bank is rebuilt per concept
DELETE FROM workspace_question_bank WHERE generator IS NULL;

-- Flashcards: which document and concept a card comes from, which generator made it,
-- and an embedding for meaning-based duplicate checks
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS document_id TEXT;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS concept_id TEXT;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS generator TEXT;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS embedding JSONB;
CREATE INDEX IF NOT EXISTS idx_flashcards_document ON flashcards(document_id);
