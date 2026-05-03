"""Widen clients.gender from varchar(1) to varchar(20).

The original column was too narrow for human-readable values like
'male', 'female', 'other' — only single-char codes (M/F/O) fit.
Frontend forms and passport OCR send full words. Also normalizes
any existing single-char values to their full form.
"""

UPGRADE_SQL = """
-- Widen column (already applied live, this makes it reproducible)
ALTER TABLE clients ALTER COLUMN gender TYPE varchar(20);

-- Normalize existing single-char values
UPDATE clients SET gender = 'male' WHERE gender = 'M';
UPDATE clients SET gender = 'female' WHERE gender = 'F';
UPDATE clients SET gender = 'other' WHERE gender = 'O';
"""

DOWNGRADE_SQL = """
-- Revert to single-char
UPDATE clients SET gender = 'M' WHERE gender = 'male';
UPDATE clients SET gender = 'F' WHERE gender = 'female';
UPDATE clients SET gender = 'O' WHERE gender = 'other';
ALTER TABLE clients ALTER COLUMN gender TYPE varchar(1);
"""
