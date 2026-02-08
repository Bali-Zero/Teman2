-- The Generals Multi-Agent System Database Schema
-- Database: nuzantara_local

-- Task queue for generals
CREATE TABLE IF NOT EXISTS generals_tasks (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL CHECK (task_type IN ('code', 'research')),
    assigned_to VARCHAR(50) CHECK (assigned_to IN ('coding_general', 'intelligence_general')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled')),
    priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    payload JSONB, -- Task-specific data
    result JSONB, -- Execution result
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    assigned_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for efficient polling
CREATE INDEX IF NOT EXISTS idx_generals_tasks_status_type ON generals_tasks(status, task_type);
CREATE INDEX IF NOT EXISTS idx_generals_tasks_assigned_to ON generals_tasks(assigned_to, status);
CREATE INDEX IF NOT EXISTS idx_generals_tasks_priority ON generals_tasks(priority DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_generals_tasks_created_at ON generals_tasks(created_at DESC);

-- Shared memory between generals
CREATE TABLE IF NOT EXISTS generals_memory (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) NOT NULL UNIQUE,
    value JSONB NOT NULL,
    general_name VARCHAR(50), -- Which general created/updated this
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generals_memory_key ON generals_memory(key);
CREATE INDEX IF NOT EXISTS idx_generals_memory_expires ON generals_memory(expires_at) WHERE expires_at IS NOT NULL;

-- Activity log for monitoring and debugging
CREATE TABLE IF NOT EXISTS generals_activity (
    id SERIAL PRIMARY KEY,
    general_name VARCHAR(50) NOT NULL,
    task_id INTEGER REFERENCES generals_tasks(id) ON DELETE SET NULL,
    activity_type VARCHAR(50) NOT NULL CHECK (activity_type IN ('task_polled', 'task_started', 'task_completed', 'task_failed', 'memory_read', 'memory_written', 'error')),
    message TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generals_activity_general ON generals_activity(general_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_generals_activity_task ON generals_activity(task_id);
CREATE INDEX IF NOT EXISTS idx_generals_activity_type ON generals_activity(activity_type, created_at DESC);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for auto-updating updated_at
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
