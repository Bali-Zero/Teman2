-- ================================================
-- Migration 010: Fix team_members schema alignment
-- Purpose: Add missing columns and align with Python User model
-- Created: 2025-01-22
-- ================================================

BEGIN;

-- Add missing columns to team_members table if they don't exist
DO $$
BEGIN
    -- Add pin_hash column (for authentication)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_members' AND column_name = 'pin_hash'
    ) THEN
        ALTER TABLE team_members ADD COLUMN pin_hash VARCHAR(255);
        RAISE NOTICE 'Added pin_hash column to team_members table';
    END IF;

    -- Add department column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_members' AND column_name = 'department'
    ) THEN
        ALTER TABLE team_members ADD COLUMN department VARCHAR(100);
        RAISE NOTICE 'Added department column to team_members table';
    END IF;

    -- Add language column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_members' AND column_name = 'language'
    ) THEN
        ALTER TABLE team_members ADD COLUMN language VARCHAR(10) DEFAULT 'en';
        RAISE NOTICE 'Added language column to team_members table';
    END IF;

    -- Add personalized_response column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_members' AND column_name = 'personalized_response'
    ) THEN
        ALTER TABLE team_members ADD COLUMN personalized_response BOOLEAN DEFAULT false;
        RAISE NOTICE 'Added personalized_response column to team_members table';
    END IF;

    -- Add notes column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_members' AND column_name = 'notes'
    ) THEN
        ALTER TABLE team_members ADD COLUMN notes TEXT;
        RAISE NOTICE 'Added notes column to team_members table';
    END IF;

    -- Add last_login column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_members' AND column_name = 'last_login'
    ) THEN
        ALTER TABLE team_members ADD COLUMN last_login TIMESTAMP WITH TIME ZONE;
        RAISE NOTICE 'Added last_login column to team_members table';
    END IF;

    -- Add failed_attempts column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_members' AND column_name = 'failed_attempts'
    ) THEN
        ALTER TABLE team_members ADD COLUMN failed_attempts INTEGER DEFAULT 0;
        RAISE NOTICE 'Added failed_attempts column to team_members table';
    END IF;

    -- Add locked_until column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_members' AND column_name = 'locked_until'
    ) THEN
        ALTER TABLE team_members ADD COLUMN locked_until TIMESTAMP WITH TIME ZONE;
        RAISE NOTICE 'Added locked_until column to team_members table';
    END IF;

    -- Add 'name' column as alias/synonym for 'full_name' if it doesn't exist
    -- OR rename full_name to name if preferred
    -- For now, we'll keep both: full_name (DB) and map it to name (Python)
    -- The Python model handles the mapping via sa_column

    -- Ensure 'active' column exists (should already exist from migration 007)
    -- If not, add it
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_members' AND column_name = 'active'
    ) THEN
        ALTER TABLE team_members ADD COLUMN active BOOLEAN DEFAULT true;
        RAISE NOTICE 'Added active column to team_members table';
    END IF;

    -- Sync active and is_active if both exist (migration scenario)
    -- If is_active exists, copy values to active and drop is_active
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_members' AND column_name = 'is_active'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_members' AND column_name = 'active'
    ) THEN
        UPDATE team_members SET active = is_active WHERE active IS NULL;
        ALTER TABLE team_members DROP COLUMN IF EXISTS is_active;
        RAISE NOTICE 'Synced is_active to active and removed is_active column';
    END IF;

    -- Change id from SERIAL to VARCHAR(36) if needed (for UUID strings)
    -- Check current type
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_members'
        AND column_name = 'id'
        AND data_type = 'integer'
    ) THEN
        -- Keep SERIAL for now, but ensure we can handle string IDs
        -- The Python model accepts string IDs, so this should work
        RAISE NOTICE 'ID column is INTEGER (SERIAL). Python model accepts string IDs.';
    END IF;
END $$;

-- Create indexes for new columns
CREATE INDEX IF NOT EXISTS idx_team_members_department ON team_members(department);
CREATE INDEX IF NOT EXISTS idx_team_members_language ON team_members(language);
CREATE INDEX IF NOT EXISTS idx_team_members_pin_hash ON team_members(pin_hash) WHERE pin_hash IS NOT NULL;

-- Comments for documentation
COMMENT ON COLUMN team_members.full_name IS 'Full name of team member (mapped to Python model field "name")';
COMMENT ON COLUMN team_members.active IS 'Account active status (mapped to Python model field "is_active")';
COMMENT ON COLUMN team_members.pin_hash IS 'Bcrypt hash of user PIN/password';
COMMENT ON COLUMN team_members.department IS 'Department name';
COMMENT ON COLUMN team_members.language IS 'Preferred language code (e.g., en, id, it)';
COMMENT ON COLUMN team_members.personalized_response IS 'Enable personalized AI responses';
COMMENT ON COLUMN team_members.notes IS 'Character notes and personality traits for AI';
COMMENT ON COLUMN team_members.last_login IS 'Last successful login timestamp';
COMMENT ON COLUMN team_members.failed_attempts IS 'Number of failed login attempts';
COMMENT ON COLUMN team_members.locked_until IS 'Account lock expiry timestamp';

COMMIT;
