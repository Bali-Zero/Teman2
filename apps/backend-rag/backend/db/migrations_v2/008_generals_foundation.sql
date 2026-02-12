-- Migration 008: Generals Foundation
-- Purpose: Create base tables for The Generals Multi-Agent System
-- Author: Wakil (Deputy General)
-- Date: 2026-02-13

-- 1. Create generals_tasks table
CREATE TABLE IF NOT EXISTS generals_tasks (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL CHECK (task_type IN ('code', 'research', 'orchestration')),
    assigned_to VARCHAR(50) CHECK (assigned_to IN ('coding_general', 'intelligence_general', 'antigravity_general', 'marketing_general')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled')),
    priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    payload JSONB,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Create indexes for efficient polling
CREATE INDEX IF NOT EXISTS idx_generals_tasks_status_type ON generals_tasks(status, task_type);
CREATE INDEX IF NOT EXISTS idx_generals_tasks_assigned_to ON generals_tasks(assigned_to, status);
CREATE INDEX IF NOT EXISTS idx_generals_tasks_priority ON generals_tasks(priority DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_generals_tasks_created_at ON generals_tasks(created_at DESC);

-- 3. Create generals_memory table (shared key-value store)
CREATE TABLE IF NOT EXISTS generals_memory (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) NOT NULL UNIQUE,
    value JSONB NOT NULL,
    general_name VARCHAR(50),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Create indexes on generals_memory
CREATE INDEX IF NOT EXISTS idx_generals_memory_key ON generals_memory(key);
CREATE INDEX IF NOT EXISTS idx_generals_memory_expires ON generals_memory(expires_at) WHERE expires_at IS NOT NULL;

-- 5. Create generals_activity table (audit log)
CREATE TABLE IF NOT EXISTS generals_activity (
    id SERIAL PRIMARY KEY,
    general_name VARCHAR(50) NOT NULL,
    task_id INTEGER REFERENCES generals_tasks(id) ON DELETE SET NULL,
    activity_type VARCHAR(50) NOT NULL CHECK (activity_type IN (
        'task_polled', 'task_started', 'task_completed', 'task_failed',
        'memory_read', 'memory_written', 'lock_acquired', 'lock_released', 'error'
    )),
    message TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Create indexes on generals_activity
CREATE INDEX IF NOT EXISTS idx_generals_activity_general ON generals_activity(general_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_generals_activity_task ON generals_activity(task_id);
CREATE INDEX IF NOT EXISTS idx_generals_activity_type ON generals_activity(activity_type, created_at DESC);

-- 7. Create generals_locks table (for conflict resolution)
CREATE TABLE IF NOT EXISTS generals_locks (
    resource_key VARCHAR(255) PRIMARY KEY,
    owner_general VARCHAR(50) NOT NULL,
    acquired_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- 8. Create index on generals_locks
CREATE INDEX IF NOT EXISTS idx_generals_locks_expires ON generals_locks(expires_at);

-- 9. Create function for auto-updating updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

-- 10. Create triggers for auto-updating updated_at
DROP TRIGGER IF EXISTS update_generals_tasks_updated_at ON generals_tasks;
CREATE TRIGGER update_generals_tasks_updated_at
    BEFORE UPDATE ON generals_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_generals_memory_updated_at ON generals_memory;
CREATE TRIGGER update_generals_memory_updated_at
    BEFORE UPDATE ON generals_memory
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 11. Add helpful comments
COMMENT ON TABLE generals_tasks IS 'Task queue for The Generals Multi-Agent System';
COMMENT ON TABLE generals_memory IS 'Shared memory key-value store for inter-agent coordination';
COMMENT ON TABLE generals_activity IS 'Activity log for monitoring and debugging';
COMMENT ON TABLE generals_locks IS 'Resource locks for conflict resolution between generals';
COMMENT ON COLUMN generals_locks.resource_key IS 'Resource identifier (e.g., "file:backend/main.py", "deploy:production")';
COMMENT ON COLUMN generals_locks.owner_general IS 'General that currently holds the lock';
COMMENT ON COLUMN generals_locks.expires_at IS 'Lock expiration timestamp (TTL for auto-cleanup)';
