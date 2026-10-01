-- ============================================================================
-- 009: Spaced-repetition scheduling for flashcards (SM-2)
-- ============================================================================
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS ease_factor DOUBLE PRECISION NOT NULL DEFAULT 2.5;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS repetitions INT NOT NULL DEFAULT 0;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS review_count INT NOT NULL DEFAULT 0;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS last_rating TEXT;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS due_date DATE;

CREATE INDEX IF NOT EXISTS idx_flashcards_workspace_due ON flashcards(workspace_id, due_date);
