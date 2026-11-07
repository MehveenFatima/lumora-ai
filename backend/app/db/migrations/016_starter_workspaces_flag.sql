-- Every account gets the Operating Systems, DBMS and Computer Networks workspaces once.
ALTER TABLE users ADD COLUMN IF NOT EXISTS starter_workspaces_added BOOLEAN NOT NULL DEFAULT FALSE;

-- Same description as a workspace created from the dashboard
UPDATE workspaces SET description = 'Custom learning workspace grounded in your uploaded documents.'
 WHERE is_sample AND description LIKE 'Exam revision for %';
