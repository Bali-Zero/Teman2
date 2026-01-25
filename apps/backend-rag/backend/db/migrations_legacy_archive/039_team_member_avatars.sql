-- ================================================
-- Migration 039: Add avatar column to team_members
-- Purpose: Store team member profile photo URLs
-- Created: 2026-01-04
-- ================================================

BEGIN;

-- Add avatar column to team_members table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_members' AND column_name = 'avatar'
    ) THEN
        ALTER TABLE team_members ADD COLUMN avatar VARCHAR(255);
        RAISE NOTICE 'Added avatar column to team_members table';
    END IF;
END $$;

-- Set default avatars for existing team members with photos
UPDATE team_members SET avatar = '/images/team/adit.png' WHERE email = 'adit@balizero.com' AND avatar IS NULL;
UPDATE team_members SET avatar = '/images/team/krisna.png' WHERE email = 'krisna@balizero.com' AND avatar IS NULL;
UPDATE team_members SET avatar = '/images/team/ari.png' WHERE email = 'ari.firda@balizero.com' AND avatar IS NULL;
UPDATE team_members SET avatar = '/images/team/dea.png' WHERE email = 'dea@balizero.com' AND avatar IS NULL;
UPDATE team_members SET avatar = '/images/team/sahira.png' WHERE email = 'sahira@balizero.com' AND avatar IS NULL;

-- Comment for documentation
COMMENT ON COLUMN team_members.avatar IS 'URL path to team member profile photo';

COMMIT;
