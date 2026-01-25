-- ================================================
-- Migration 035: Team Departments & Drive Folder Access
-- ================================================

-- Add department column to team_members
ALTER TABLE team_members ADD COLUMN IF NOT EXISTS department VARCHAR(50);

-- Add drive_folders column (array of allowed folder names)
ALTER TABLE team_members ADD COLUMN IF NOT EXISTS drive_folders JSONB DEFAULT '[]'::jsonb;

-- Create index for department lookups
CREATE INDEX IF NOT EXISTS idx_team_members_department ON team_members(department);

-- Create department configuration table
CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    drive_folders JSONB DEFAULT '[]'::jsonb,  -- Default folders for this department
    can_see_all BOOLEAN DEFAULT false,         -- Board members see everything
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert departments
INSERT INTO departments (code, name, drive_folders, can_see_all) VALUES
    ('setup', 'Setup Team', '["Legal", "Immigration", "Visa", "KITAS", "Setup"]', false),
    ('tax', 'Tax Department', '["Tax", "Pajak", "NPWP", "SPT", "Finance"]', false),
    ('marketing', 'Marketing', '["Marketing", "Content", "Social", "Blog"]', false),
    ('board', 'Board', '[]', true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    drive_folders = EXCLUDED.drive_folders,
    can_see_all = EXCLUDED.can_see_all;

-- Update existing team members with departments based on their roles/names
-- (You'll need to manually assign departments to each team member)

COMMENT ON COLUMN team_members.department IS 'Department code: setup, tax, marketing, board';
COMMENT ON COLUMN team_members.drive_folders IS 'Additional personal folders this member can access';
