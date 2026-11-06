-- 012: Day-by-day study plan, daily email reminders and resumable uploads
--
-- study_plans keeps today's frozen task list (snapshot) and every completed task with its date,
-- so today's and this week's minutes are worked out from real dates and reset by themselves.
ALTER TABLE study_plans ADD COLUMN IF NOT EXISTS completions JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE study_plans ADD COLUMN IF NOT EXISTS snapshot JSONB;
ALTER TABLE study_plans ADD COLUMN IF NOT EXISTS snapshot_date DATE;
ALTER TABLE study_plans ADD COLUMN IF NOT EXISTS snapshot_at TIMESTAMPTZ;
ALTER TABLE study_plans ADD COLUMN IF NOT EXISTS previous_snapshot JSONB;

-- Users: local time zone (for "today" and reminder times) and the daily reminder email setting
ALTER TABLE users ADD COLUMN IF NOT EXISTS tz_offset_minutes INT NOT NULL DEFAULT 330;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_reminders BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_reminder_date DATE;

-- Documents: how many times processing was resumed after a restart
ALTER TABLE documents ADD COLUMN IF NOT EXISTS resume_count INT NOT NULL DEFAULT 0;
