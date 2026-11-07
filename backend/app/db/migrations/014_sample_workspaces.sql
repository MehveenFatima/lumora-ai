-- 014: Sample workspaces
--
-- A sample workspace is created from built-in notes with a ready topic map, question bank and
-- flashcard deck, so a new user (or a demo) can try every feature straight away. Its study
-- material is not regenerated in the background.
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS is_sample BOOLEAN NOT NULL DEFAULT FALSE;
