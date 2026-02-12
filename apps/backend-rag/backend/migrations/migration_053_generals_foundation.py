"""
Migration 053: Generals Foundation

Purpose:
- Create base tables for The Generals Multi-Agent System
- Add resource locking mechanism for conflict resolution
- Support code, research, and orchestration task types
- Enable shared memory and activity logging

Tables Created:
1. generals_tasks - Task queue with priority and status tracking
2. generals_memory - Shared key-value store with expiration
3. generals_activity - Activity log for monitoring and debugging
4. generals_locks - Resource locking for conflict resolution

Use Cases:
1. Autonomous task execution by specialized generals
2. Inter-agent coordination via shared memory
3. Conflict resolution via resource locks
4. System monitoring and debugging via activity logs

Author: Wakil (Deputy General)
Date: 2026-02-12
"""

import logging
from typing import Any
import asyncpg
from backend.db.migration_base import BaseMigration

logger = logging.getLogger(__name__)


class Migration053(BaseMigration):
    """Generals Foundation Migration"""

    def __init__(self):
        super().__init__(
            migration_number=53,
            description="Create Generals Foundation tables (tasks, memory, activity, locks)",
        )

    async def up(self, conn: asyncpg.Connection) -> None:
        """Apply the migration - create Generals Foundation tables."""
        await _apply_migration(conn)

    async def down(self, conn: asyncpg.Connection) -> None:
        """Rollback the migration - drop all Generals Foundation tables."""
        await _rollback_migration(conn)

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify all Generals tables were created"""
        tables = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN (
                'generals_tasks', 'generals_memory',
                'generals_activity', 'generals_locks'
            )
        """
        )
        return len(tables) == 4


async def _apply_migration(conn: Any) -> None:
    """Apply the migration - create Generals Foundation tables."""

    logger.info("Applying migration 053: Generals Foundation")

    # 1. Create generals_tasks table
    await conn.execute("""
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
    """)
    logger.info("✅ Created generals_tasks table")

    # 2. Create indexes for efficient polling
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_generals_tasks_status_type
        ON generals_tasks(status, task_type);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_generals_tasks_assigned_to
        ON generals_tasks(assigned_to, status);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_generals_tasks_priority
        ON generals_tasks(priority DESC, created_at ASC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_generals_tasks_created_at
        ON generals_tasks(created_at DESC);
    """)
    logger.info("✅ Created indexes on generals_tasks")

    # 3. Create generals_memory table (shared key-value store)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS generals_memory (
            id SERIAL PRIMARY KEY,
            key VARCHAR(255) NOT NULL UNIQUE,
            value JSONB NOT NULL,
            general_name VARCHAR(50),
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    logger.info("✅ Created generals_memory table")

    # 4. Create indexes on generals_memory
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_generals_memory_key
        ON generals_memory(key);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_generals_memory_expires
        ON generals_memory(expires_at) WHERE expires_at IS NOT NULL;
    """)
    logger.info("✅ Created indexes on generals_memory")

    # 5. Create generals_activity table (audit log)
    await conn.execute("""
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
    """)
    logger.info("✅ Created generals_activity table")

    # 6. Create indexes on generals_activity
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_generals_activity_general
        ON generals_activity(general_name, created_at DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_generals_activity_task
        ON generals_activity(task_id);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_generals_activity_type
        ON generals_activity(activity_type, created_at DESC);
    """)
    logger.info("✅ Created indexes on generals_activity")

    # 7. Create generals_locks table (NEW - for conflict resolution)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS generals_locks (
            resource_key VARCHAR(255) PRIMARY KEY,
            owner_general VARCHAR(50) NOT NULL,
            acquired_at TIMESTAMPTZ DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL
        );
    """)
    logger.info("✅ Created generals_locks table")

    # 8. Create index on generals_locks
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_generals_locks_expires
        ON generals_locks(expires_at);
    """)
    logger.info("✅ Created index on generals_locks")

    # 9. Create function for auto-updating updated_at
    await conn.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE 'plpgsql';
    """)
    logger.info("✅ Created update_updated_at_column function")

    # 10. Create triggers for auto-updating updated_at
    await conn.execute("""
        DROP TRIGGER IF EXISTS update_generals_tasks_updated_at ON generals_tasks;
        CREATE TRIGGER update_generals_tasks_updated_at
            BEFORE UPDATE ON generals_tasks
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    await conn.execute("""
        DROP TRIGGER IF EXISTS update_generals_memory_updated_at ON generals_memory;
        CREATE TRIGGER update_generals_memory_updated_at
            BEFORE UPDATE ON generals_memory
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    logger.info("✅ Created triggers for auto-updating updated_at")

    # 11. Add helpful comments
    await conn.execute("""
        COMMENT ON TABLE generals_tasks IS
        'Task queue for The Generals Multi-Agent System';
    """)
    await conn.execute("""
        COMMENT ON TABLE generals_memory IS
        'Shared memory key-value store for inter-agent coordination';
    """)
    await conn.execute("""
        COMMENT ON TABLE generals_activity IS
        'Activity log for monitoring and debugging';
    """)
    await conn.execute("""
        COMMENT ON TABLE generals_locks IS
        'Resource locks for conflict resolution between generals';
    """)
    await conn.execute("""
        COMMENT ON COLUMN generals_locks.resource_key IS
        'Resource identifier (e.g., "file:backend/main.py", "deploy:production")';
    """)
    await conn.execute("""
        COMMENT ON COLUMN generals_locks.owner_general IS
        'General that currently holds the lock';
    """)
    await conn.execute("""
        COMMENT ON COLUMN generals_locks.expires_at IS
        'Lock expiration timestamp (TTL for auto-cleanup)';
    """)

    logger.info("Migration 053 applied successfully: Generals Foundation created")
    print("✅ Applied migration 053: Generals Foundation (tasks, memory, activity, locks)")


async def _rollback_migration(conn: Any) -> None:
    """Rollback the migration - drop all Generals Foundation tables."""

    logger.info("Rolling back migration 053: Generals Foundation")

    # Drop triggers first
    await conn.execute("DROP TRIGGER IF EXISTS update_generals_tasks_updated_at ON generals_tasks;")
    await conn.execute("DROP TRIGGER IF EXISTS update_generals_memory_updated_at ON generals_memory;")

    # Drop function
    await conn.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    # Drop tables in reverse order (respecting foreign keys)
    await conn.execute("DROP TABLE IF EXISTS generals_activity;")
    await conn.execute("DROP TABLE IF EXISTS generals_locks;")
    await conn.execute("DROP TABLE IF EXISTS generals_memory;")
    await conn.execute("DROP TABLE IF EXISTS generals_tasks;")

    logger.info("Migration 053 rolled back successfully")
    print("⏪ Rolled back migration 053: Generals Foundation")


async def main():
    """Run migration standalone"""
    migration = Migration053()
    success = await migration.apply()
    return success
