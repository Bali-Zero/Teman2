-- Migration: 130_drop_legacy_generals
-- Created: 2026-03-24
-- Description: Drop legacy "The Generals" tables from Gen 1

DROP TABLE IF EXISTS generals_activity CASCADE;
DROP TABLE IF EXISTS generals_memory CASCADE;
DROP TABLE IF EXISTS generals_tasks CASCADE;

-- Remove the update_updated_at_column triggers if they are no longer used by other tables
-- but usually they are shared, so we only drop the specific triggers for these tables if they were unique.
DROP TRIGGER IF EXISTS update_generals_tasks_updated_at ON generals_tasks;
DROP TRIGGER IF EXISTS update_generals_memory_updated_at ON generals_memory;
