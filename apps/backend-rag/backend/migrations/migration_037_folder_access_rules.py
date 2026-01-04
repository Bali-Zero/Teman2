#!/usr/bin/env python3
"""
Migration 037: Folder Access Rules

Creates the folder_access_rules table for granular Google Drive folder visibility.
This replaces the simple can_see_all logic with per-context permission rules.

Usage:
    python -m backend.migrations.migration_037_folder_access_rules
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncpg

MIGRATION_SQL = """
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
    -- NULL = root level
    -- 'BALI ZERO' = inside BALI ZERO folder
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
"""


SEED_SQL = """
-- Clear existing rules (for re-run safety)
DELETE FROM folder_access_rules;

-- =============================================================================
-- LEVEL 1: Drive Root (context_folder = NULL)
-- Everyone sees BALI ZERO only
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
-- =============================================================================

-- Ruslana (Board): additional personal folder visibility
INSERT INTO folder_access_rules (user_email, allowed_folders, context_folder, priority, description) VALUES
('ruslana@balizero.com', ARRAY['Ruslana'], 'BALI ZERO', 20, 'Ruslana: personal folder at BALI ZERO level');

-- Anton (Board): hospitality projects
INSERT INTO folder_access_rules (user_email, allowed_folders, context_folder, priority, description) VALUES
('anton@balizero.com', ARRAY['Anton', 'Anton - Hospitality'], 'BALI ZERO', 20, 'Anton: personal folders at BALI ZERO level');
"""


async def run_migration():
    """Run the migration."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    print("Connecting to database...")
    conn = await asyncpg.connect(database_url)

    try:
        # Check if table already exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'folder_access_rules'
            )
        """)

        if exists:
            print("Table folder_access_rules already exists")
            count = await conn.fetchval("SELECT COUNT(*) FROM folder_access_rules")
            print(f"Current rule count: {count}")

            if count == 0:
                print("Table is empty, seeding data...")
                await conn.execute(SEED_SQL)
                count = await conn.fetchval("SELECT COUNT(*) FROM folder_access_rules")
                print(f"Seeded {count} rules")
            else:
                print("Skipping seed (table has data). To re-seed, run:")
                print("  DELETE FROM folder_access_rules; then re-run this script")
        else:
            print("Creating folder_access_rules table...")
            await conn.execute(MIGRATION_SQL)
            print("Table created successfully")

            print("Seeding initial access rules...")
            await conn.execute(SEED_SQL)
            count = await conn.fetchval("SELECT COUNT(*) FROM folder_access_rules")
            print(f"Seeded {count} rules")

        # Show summary
        print("\n=== Migration 037 Complete ===")
        rules = await conn.fetch("""
            SELECT context_folder, COUNT(*) as count
            FROM folder_access_rules
            GROUP BY context_folder
            ORDER BY context_folder NULLS FIRST
        """)
        for rule in rules:
            ctx = rule["context_folder"] or "ROOT"
            print(f"  {ctx}: {rule['count']} rules")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
