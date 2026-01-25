-- Migration 037: Folder Access Rules
-- Granular permission system for Google Drive folder visibility

CREATE TABLE IF NOT EXISTS folder_access_rules (
    id SERIAL PRIMARY KEY,

    -- Who this rule applies to (priority: user > department > role)
    user_email VARCHAR(255),           -- Specific user email
    department_code VARCHAR(50),       -- Department code (setup, tax, marketing, etc.)
    role VARCHAR(50),                  -- Role name (board, team, admin)

    -- What folders are visible (array of folder name patterns, case-insensitive)
    allowed_folders TEXT[] NOT NULL,

    -- Context: where does this rule apply
    -- NULL = root level (inside BALI ZERO)
    -- 'Setup' = inside Setup folder
    -- 'Tax' = inside Tax folder
    context_folder VARCHAR(255),

    -- Rule metadata
    priority INT DEFAULT 0,            -- Higher priority wins on conflicts
    active BOOLEAN DEFAULT true,
    description TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_folder_access_user ON folder_access_rules(user_email) WHERE user_email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_folder_access_dept ON folder_access_rules(department_code) WHERE department_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_folder_access_role ON folder_access_rules(role) WHERE role IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_folder_access_context ON folder_access_rules(context_folder);

-- Comments
COMMENT ON TABLE folder_access_rules IS 'Granular folder visibility rules for Google Drive access';
COMMENT ON COLUMN folder_access_rules.allowed_folders IS 'Array of folder names user can see (case-insensitive match)';
COMMENT ON COLUMN folder_access_rules.context_folder IS 'NULL=root level, or folder name for nested visibility rules';

-- =====================================================
-- SEED DATA: Initial access rules
-- =====================================================
-- Folder structure:
--   Drive Root → BALI ZERO → [Setup, Tax, Marketing, BOARD, _Shared]
--   BALI ZERO/Setup → [Anton, Rina, Dea, _Shared, ...]
--   BALI ZERO/Tax → [Kadek, Dewa Ayu, Faysha, Angel, Dea, _Shared, ...]

-- =============================================================================
-- LEVEL 1: Drive Root (context_folder = NULL)
-- Everyone sees BALI ZERO only (frontend already filters to show just this)
-- =============================================================================
INSERT INTO folder_access_rules (role, allowed_folders, context_folder, priority, description) VALUES
('*', ARRAY['BALI ZERO'], NULL, 1, 'Everyone: BALI ZERO at root');

-- =============================================================================
-- LEVEL 2: Inside BALI ZERO (context_folder = 'BALI ZERO')
-- This is where departments are shown
-- =============================================================================

-- Board members: see all departments
INSERT INTO folder_access_rules (role, allowed_folders, context_folder, priority, description) VALUES
('board', ARRAY['Setup', 'Tax', 'BOARD', '_Shared', 'Shared', 'Templates', 'INSTRUCTIONS', 'Common'], 'BALI ZERO', 10, 'Board: all departments inside BALI ZERO');

-- Setup department: only their department + shared
INSERT INTO folder_access_rules (department_code, allowed_folders, context_folder, priority, description) VALUES
('setup', ARRAY['Setup', '_Shared', 'Shared', 'Templates', 'INSTRUCTIONS', 'Common'], 'BALI ZERO', 5, 'Setup: their dept inside BALI ZERO');

-- Tax department: only their department + shared
INSERT INTO folder_access_rules (department_code, allowed_folders, context_folder, priority, description) VALUES
('tax', ARRAY['Tax', '_Shared', 'Shared', 'Templates', 'INSTRUCTIONS', 'Common'], 'BALI ZERO', 5, 'Tax: their dept inside BALI ZERO');

-- Marketing department: only their department + shared
INSERT INTO folder_access_rules (department_code, allowed_folders, context_folder, priority, description) VALUES
('marketing', ARRAY['Marketing', '_Shared', 'Shared', 'Templates', 'Common'], 'BALI ZERO', 5, 'Marketing: their dept inside BALI ZERO');

-- Default: shared folders only inside BALI ZERO
INSERT INTO folder_access_rules (role, allowed_folders, context_folder, priority, description) VALUES
('*', ARRAY['_Shared', 'Shared', 'Templates', 'INSTRUCTIONS', 'Common'], 'BALI ZERO', 1, 'Default: shared inside BALI ZERO');

-- =============================================================================
-- LEVEL 3: Inside Setup folder (context_folder = 'Setup')
-- =============================================================================

-- Board members: specific team members only (NOT all)
INSERT INTO folder_access_rules (role, allowed_folders, context_folder, priority, description) VALUES
('board', ARRAY['Anton', 'Rina', 'Dea', '_Shared', 'Shared', 'Templates', 'Common'], 'Setup', 10, 'Board: Anton, Rina, Dea inside Setup');

-- Setup department: shared folders + own folder (added dynamically via full_name)
INSERT INTO folder_access_rules (department_code, allowed_folders, context_folder, priority, description) VALUES
('setup', ARRAY['_Shared', 'Shared', 'Templates', 'Common'], 'Setup', 5, 'Setup: shared folders inside Setup');

-- =============================================================================
-- LEVEL 3: Inside Tax folder (context_folder = 'Tax')
-- =============================================================================

-- Board members: specific team members only
INSERT INTO folder_access_rules (role, allowed_folders, context_folder, priority, description) VALUES
('board', ARRAY['Kadek', 'Dewa Ayu', 'Faysha', 'Angel', 'Dea', '_Shared', 'Shared', 'Templates', 'Common'], 'Tax', 10, 'Board: visible members inside Tax');

-- Tax department: shared folders + own folder (added dynamically via full_name)
INSERT INTO folder_access_rules (department_code, allowed_folders, context_folder, priority, description) VALUES
('tax', ARRAY['_Shared', 'Shared', 'Templates', 'Common'], 'Tax', 5, 'Tax: shared folders inside Tax');

-- =============================================================================
-- LEVEL 3: Inside Marketing folder (context_folder = 'Marketing')
-- =============================================================================

-- Marketing department: shared folders + own folder
INSERT INTO folder_access_rules (department_code, allowed_folders, context_folder, priority, description) VALUES
('marketing', ARRAY['_Shared', 'Shared', 'Templates', 'Common'], 'Marketing', 5, 'Marketing: shared folders inside Marketing');

-- =============================================================================
-- LEVEL 3: Inside BOARD folder (context_folder = 'BOARD')
-- =============================================================================

-- Board members: see everything inside BOARD
INSERT INTO folder_access_rules (role, allowed_folders, context_folder, priority, description) VALUES
('board', ARRAY['_Shared', 'Shared', 'Templates', 'Common', 'Minutes', 'Reports', 'Strategic'], 'BOARD', 10, 'Board: full access inside BOARD');

-- =============================================================================
-- USER-SPECIFIC OVERRIDES
-- Personal folders are added automatically via full_name in get_user_allowed_folders()
-- These are for special cases only
-- =============================================================================

-- Ruslana (Board): additional personal folder visibility
INSERT INTO folder_access_rules (user_email, allowed_folders, context_folder, priority, description) VALUES
('ruslana@balizero.com', ARRAY['Ruslana'], 'BALI ZERO', 20, 'Ruslana: personal folder at BALI ZERO level');

-- Anton (Board): hospitality projects
INSERT INTO folder_access_rules (user_email, allowed_folders, context_folder, priority, description) VALUES
('anton@balizero.com', ARRAY['Anton', 'Anton - Hospitality'], 'BALI ZERO', 20, 'Anton: personal folders at BALI ZERO level');
