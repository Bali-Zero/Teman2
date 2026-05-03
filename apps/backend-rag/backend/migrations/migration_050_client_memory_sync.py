"""
Migration 050: Client-Memory Sync Trigger

Purpose:
- Auto-sync CRM clients table → user_stats table (memory system)
- Enables frontend to read client context without querying CRM directly
- Maintains link between CRM client_id and memory user_id (email)

Trigger on: INSERT/UPDATE on clients table
Action: UPSERT into user_stats with CRM metadata in preferences JSONB

Author: Claude Sonnet 4.5
Date: 2026-01-18
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply the migration - create client-memory sync trigger."""

    logger.info("Applying migration 050: Client-Memory Sync Trigger")

    # 1. Create trigger function
    await conn.execute("""
        CREATE OR REPLACE FUNCTION sync_client_to_memory()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Upsert into user_stats using email as user_id
            -- Store CRM metadata in preferences JSONB for frontend access
            INSERT INTO user_stats (
                user_id,
                preferences,
                updated_at,
                last_activity
            ) VALUES (
                COALESCE(NEW.email, NEW.id::text),  -- Use email or fallback to client_id
                jsonb_build_object(
                    'crm_client_id', NEW.id,
                    'assigned_to', NEW.assigned_to,
                    'status', NEW.status,
                    'client_type', NEW.client_type,
                    'full_name', NEW.full_name,
                    'phone', NEW.phone,
                    'nationality', NEW.nationality,
                    'tags', NEW.tags,
                    'last_sync_at', NOW()
                ),
                NOW(),
                NOW()
            )
            ON CONFLICT (user_id) DO UPDATE SET
                preferences = user_stats.preferences || jsonb_build_object(
                    'crm_client_id', EXCLUDED.preferences->>'crm_client_id',
                    'assigned_to', EXCLUDED.preferences->>'assigned_to',
                    'status', EXCLUDED.preferences->>'status',
                    'client_type', EXCLUDED.preferences->>'client_type',
                    'full_name', EXCLUDED.preferences->>'full_name',
                    'phone', EXCLUDED.preferences->>'phone',
                    'nationality', EXCLUDED.preferences->>'nationality',
                    'tags', EXCLUDED.preferences->'tags',
                    'last_sync_at', to_jsonb(NOW())
                ),
                updated_at = NOW(),
                last_activity = NOW();

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    logger.info("✅ Created sync_client_to_memory() function")

    # 2. Create trigger on clients table
    await conn.execute("""
        DROP TRIGGER IF EXISTS client_to_memory_sync ON clients;

        CREATE TRIGGER client_to_memory_sync
        AFTER INSERT OR UPDATE ON clients
        FOR EACH ROW
        EXECUTE FUNCTION sync_client_to_memory();
    """)

    logger.info("✅ Created client_to_memory_sync trigger on clients table")

    # 3. Add helpful comment
    await conn.execute("""
        COMMENT ON FUNCTION sync_client_to_memory() IS
        'Auto-syncs CRM clients to user_stats for unified memory access.
        Frontend reads from user_stats.preferences.crm_* instead of querying CRM directly.';
    """)

    logger.info("Migration 050 applied successfully: Client-Memory Sync Trigger created")
    print("✅ Applied migration 050: Client-Memory Sync Trigger")


async def rollback(conn: Any) -> None:
    """Rollback the migration - drop trigger and function."""

    logger.info("Rolling back migration 050: Client-Memory Sync Trigger")

    # Drop trigger first
    await conn.execute("DROP TRIGGER IF EXISTS client_to_memory_sync ON clients;")

    # Then drop function
    await conn.execute("DROP FUNCTION IF EXISTS sync_client_to_memory();")

    logger.info("Migration 050 rolled back successfully")
    print("⏪ Rolled back migration 050: Client-Memory Sync Trigger")
