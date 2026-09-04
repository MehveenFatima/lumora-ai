-- LumoraAI Phase: Question Quality, Question Type & Anti-Leakage Schema
-- Adds question_type and quality_score to quiz_questions

ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS question_type TEXT NOT NULL DEFAULT 'conceptual';
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS quality_score DOUBLE PRECISION NOT NULL DEFAULT 1.0;

-- Index for analytics and filtering by question type
CREATE INDEX IF NOT EXISTS idx_quiz_questions_type ON quiz_questions(question_type);
