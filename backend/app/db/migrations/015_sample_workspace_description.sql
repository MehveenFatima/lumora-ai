-- Built-in workspaces read like normal ones: replace the earlier placeholder description.
UPDATE workspaces
   SET description = 'Exam revision for ' || name || ' from the course notes'
 WHERE is_sample AND description = 'Sample workspace with ready-made study material';
