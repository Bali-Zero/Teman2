"""
Migration 031: Client Portal Schema

Creates tables and columns for the Client Portal feature:
- Extends team_members for client authentication
- Client invitations for email-based onboarding
- Multi-company support (client_companies)
- Async messaging system (portal_messages)
- Client preferences

Created: 2025-12-30
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply the migration - create Client Portal schema."""

    logger.info("Applying migration 031: Client Portal Schema")

    # 1. Extend team_members for client authentication
    await conn.execute("""
        ALTER TABLE team_members
        ADD COLUMN IF NOT EXISTS linked_client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL;
    """)

    await conn.execute("""
        ALTER TABLE team_members
        ADD COLUMN IF NOT EXISTS portal_access BOOLEAN DEFAULT false;
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_team_members_linked_client
        ON team_members(linked_client_id)
        WHERE linked_client_id IS NOT NULL;
    """)

    # 2. Add client_visible flag to documents (if documents table exists)
    await conn.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents') THEN
                ALTER TABLE documents ADD COLUMN IF NOT EXISTS client_visible BOOLEAN DEFAULT true;
            END IF;
        END $$;
    """)

    # 3. Client invitations table (email invite flow)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS client_invitations (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            email VARCHAR(255) NOT NULL,
            token VARCHAR(255) UNIQUE NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            used_at TIMESTAMP WITH TIME ZONE,
            created_by VARCHAR(255),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_client_invitations_token
        ON client_invitations(token);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_client_invitations_client
        ON client_invitations(client_id);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_client_invitations_expires
        ON client_invitations(expires_at)
        WHERE used_at IS NULL;
    """)

    # 4. Multi-company support table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS client_companies (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            company_id INTEGER NOT NULL REFERENCES company_profiles(id) ON DELETE CASCADE,
            role VARCHAR(50) DEFAULT 'owner',
            is_primary BOOLEAN DEFAULT false,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT client_companies_unique UNIQUE(client_id, company_id)
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_client_companies_client
        ON client_companies(client_id);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_client_companies_company
        ON client_companies(company_id);
    """)

    # 5. Async messaging system
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS portal_messages (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            practice_id INTEGER REFERENCES practices(id) ON DELETE SET NULL,
            subject VARCHAR(255),
            direction VARCHAR(20) NOT NULL CHECK (direction IN ('client_to_team', 'team_to_client')),
            content TEXT NOT NULL,
            sent_by VARCHAR(255) NOT NULL,
            read_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_portal_messages_client
        ON portal_messages(client_id, created_at DESC);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_portal_messages_practice
        ON portal_messages(practice_id)
        WHERE practice_id IS NOT NULL;
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_portal_messages_unread
        ON portal_messages(client_id, direction)
        WHERE read_at IS NULL;
    """)

    # 6. Client preferences table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS client_preferences (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            email_notifications BOOLEAN DEFAULT true,
            whatsapp_notifications BOOLEAN DEFAULT true,
            language VARCHAR(10) DEFAULT 'en',
            timezone VARCHAR(50) DEFAULT 'Asia/Jakarta',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT client_preferences_client_unique UNIQUE(client_id)
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_client_preferences_client
        ON client_preferences(client_id);
    """)

    # 7. Create trigger for updated_at on client_preferences
    await conn.execute("""
        CREATE OR REPLACE FUNCTION update_client_preferences_timestamp()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    await conn.execute("""
        DROP TRIGGER IF EXISTS trigger_client_preferences_updated ON client_preferences;
        CREATE TRIGGER trigger_client_preferences_updated
        BEFORE UPDATE ON client_preferences
        FOR EACH ROW
        EXECUTE FUNCTION update_client_preferences_timestamp();
    """)

    logger.info("Migration 031 applied successfully: Client Portal Schema created")
    print("✅ Applied migration 031: Client Portal Schema")


async def rollback(conn: Any) -> None:
    """Rollback the migration - drop Client Portal tables and columns."""

    logger.info("Rolling back migration 031: Client Portal Schema")

    # Drop tables in reverse order
    await conn.execute("DROP TABLE IF EXISTS client_preferences CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS portal_messages CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS client_companies CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS client_invitations CASCADE;")

    # Drop trigger and function
    await conn.execute(
        "DROP TRIGGER IF EXISTS trigger_client_preferences_updated ON client_preferences;"
    )
    await conn.execute("DROP FUNCTION IF EXISTS update_client_preferences_timestamp();")

    # Remove columns from team_members
    await conn.execute("ALTER TABLE team_members DROP COLUMN IF EXISTS linked_client_id;")
    await conn.execute("ALTER TABLE team_members DROP COLUMN IF EXISTS portal_access;")

    # Remove column from documents (if exists)
    await conn.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents') THEN
                ALTER TABLE documents DROP COLUMN IF EXISTS client_visible;
            END IF;
        END $$;
    """)

    logger.info("Migration 031 rolled back successfully")
    print("⏪ Rolled back migration 031: Client Portal Schema")
