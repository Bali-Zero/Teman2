#!/usr/bin/env python3
"""
Migration 041: Team Activity Logging System
Date: 2026-01-05
Purpose: Comprehensive logging system for team activities, conversations, and API calls

Tables:
- activity_logs: General activity tracking (login, CRM actions, etc.)
- team_interactions: Team communications (chat, WhatsApp, email, calls)
- api_audit_trail: Complete API request/response audit trail
"""

import asyncio

import asyncpg


async def run_migration():
    """Create comprehensive logging tables for team activity tracking"""

    from backend.app.core.config import settings

    if not settings.database_url:
        print("❌ ERROR: DATABASE_URL not found")
        return False

    try:
        print("🔌 Connecting to PostgreSQL...")
        conn = await asyncpg.connect(settings.database_url)
        print("✅ Connected")

        # =============================================================================
        # Table 1: activity_logs - General activity tracking
        # =============================================================================
        print("\n📊 Creating activity_logs table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                action_type VARCHAR(100) NOT NULL,  -- login, logout, message_sent, crm_create, etc.
                resource_type VARCHAR(100),          -- conversation, client, practice, document, etc.
                resource_id VARCHAR(255),            -- ID of the resource affected
                description TEXT,                    -- Human-readable description
                details JSONB DEFAULT '{}',          -- Full details (payload, changes, etc.)
                ip_address VARCHAR(50),
                user_agent TEXT,
                session_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW(),

                -- Indexes for fast querying
                INDEX idx_activity_logs_user_email (user_email),
                INDEX idx_activity_logs_action_type (action_type),
                INDEX idx_activity_logs_resource_type (resource_type),
                INDEX idx_activity_logs_created_at (created_at DESC),
                INDEX idx_activity_logs_session_id (session_id)
            );

            -- Composite indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_activity_logs_user_date
                ON activity_logs(user_email, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_activity_logs_resource
                ON activity_logs(resource_type, resource_id);

            -- GIN index for JSONB details field
            CREATE INDEX IF NOT EXISTS idx_activity_logs_details_gin
                ON activity_logs USING GIN (details);
        """)
        print("✅ activity_logs table created")

        # =============================================================================
        # Table 2: team_interactions - Communication tracking
        # =============================================================================
        print("\n📊 Creating team_interactions table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS team_interactions (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,       -- Team member who sent/received
                interaction_type VARCHAR(50) NOT NULL,  -- chat, whatsapp, email, call, meeting
                direction VARCHAR(20) NOT NULL,         -- inbound, outbound
                client_email VARCHAR(255),              -- Client involved (if any)
                client_name VARCHAR(255),
                subject TEXT,                           -- Email subject, call topic, etc.
                message_content TEXT,                   -- Full message/transcript
                message_preview VARCHAR(500),           -- First 500 chars for quick view
                attachments JSONB DEFAULT '[]',         -- List of attachments
                metadata JSONB DEFAULT '{}',            -- Extra data (duration, status, etc.)
                conversation_id INTEGER,                -- Link to conversations table
                practice_id INTEGER,                    -- Link to practices table
                response_time_seconds INTEGER,          -- Time to respond (for analytics)
                created_at TIMESTAMP DEFAULT NOW(),

                -- Foreign keys
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
                FOREIGN KEY (practice_id) REFERENCES practices(id) ON DELETE SET NULL,

                -- Indexes
                INDEX idx_team_interactions_user_email (user_email),
                INDEX idx_team_interactions_type (interaction_type),
                INDEX idx_team_interactions_direction (direction),
                INDEX idx_team_interactions_client_email (client_email),
                INDEX idx_team_interactions_created_at (created_at DESC)
            );

            -- Composite indexes for analytics
            CREATE INDEX IF NOT EXISTS idx_team_interactions_user_date
                ON team_interactions(user_email, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_team_interactions_client_date
                ON team_interactions(client_email, created_at DESC);

            -- Full-text search on message_content
            CREATE INDEX IF NOT EXISTS idx_team_interactions_content_fts
                ON team_interactions USING GIN (to_tsvector('english', message_content));
        """)
        print("✅ team_interactions table created")

        # =============================================================================
        # Table 3: api_audit_trail - Complete API audit
        # =============================================================================
        print("\n📊 Creating api_audit_trail table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_audit_trail (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255),                -- Authenticated user (if any)
                method VARCHAR(10) NOT NULL,            -- GET, POST, PUT, DELETE, PATCH
                endpoint VARCHAR(500) NOT NULL,         -- Full API path
                query_params JSONB DEFAULT '{}',        -- URL query parameters
                request_body JSONB,                     -- Request payload (sanitized)
                response_status INTEGER,                -- HTTP status code
                response_body JSONB,                    -- Response payload (sanitized, optional)
                response_time_ms INTEGER,               -- Response time in milliseconds
                error_message TEXT,                     -- Error details (if any)
                ip_address VARCHAR(50),
                user_agent TEXT,
                correlation_id VARCHAR(100),            -- For request tracing
                session_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW(),

                -- Indexes for performance
                INDEX idx_api_audit_user_email (user_email),
                INDEX idx_api_audit_method (method),
                INDEX idx_api_audit_endpoint (endpoint),
                INDEX idx_api_audit_status (response_status),
                INDEX idx_api_audit_created_at (created_at DESC),
                INDEX idx_api_audit_correlation_id (correlation_id)
            );

            -- Composite indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_api_audit_user_date
                ON api_audit_trail(user_email, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_api_audit_endpoint_date
                ON api_audit_trail(endpoint, created_at DESC);

            -- GIN indexes for JSONB fields
            CREATE INDEX IF NOT EXISTS idx_api_audit_request_body_gin
                ON api_audit_trail USING GIN (request_body);
            CREATE INDEX IF NOT EXISTS idx_api_audit_query_params_gin
                ON api_audit_trail USING GIN (query_params);
        """)
        print("✅ api_audit_trail table created")

        # =============================================================================
        # Table 4: session_tracking - User session tracking
        # =============================================================================
        print("\n📊 Creating session_tracking table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS session_tracking (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) UNIQUE NOT NULL,
                user_email VARCHAR(255) NOT NULL,
                ip_address VARCHAR(50),
                user_agent TEXT,
                device_type VARCHAR(50),            -- desktop, mobile, tablet
                browser VARCHAR(100),
                os VARCHAR(100),
                login_at TIMESTAMP DEFAULT NOW(),
                logout_at TIMESTAMP,
                last_activity_at TIMESTAMP DEFAULT NOW(),
                duration_seconds INTEGER,           -- Session duration
                actions_count INTEGER DEFAULT 0,    -- Number of actions in session
                is_active BOOLEAN DEFAULT TRUE,

                -- Indexes
                INDEX idx_session_tracking_session_id (session_id),
                INDEX idx_session_tracking_user_email (user_email),
                INDEX idx_session_tracking_is_active (is_active),
                INDEX idx_session_tracking_login_at (login_at DESC)
            );
        """)
        print("✅ session_tracking table created")

        # =============================================================================
        # Create views for common queries
        # =============================================================================
        print("\n📊 Creating helper views...")

        # View 1: Today's team activity summary
        await conn.execute("""
            CREATE OR REPLACE VIEW v_today_team_activity AS
            SELECT
                user_email,
                COUNT(*) as total_actions,
                COUNT(DISTINCT action_type) as unique_action_types,
                MIN(created_at) as first_action,
                MAX(created_at) as last_action
            FROM activity_logs
            WHERE DATE(created_at) = CURRENT_DATE
            GROUP BY user_email
            ORDER BY total_actions DESC;
        """)
        print("✅ View: v_today_team_activity")

        # View 2: Team interactions summary
        await conn.execute("""
            CREATE OR REPLACE VIEW v_team_interactions_summary AS
            SELECT
                user_email,
                interaction_type,
                direction,
                COUNT(*) as count,
                DATE(created_at) as date
            FROM team_interactions
            WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY user_email, interaction_type, direction, DATE(created_at)
            ORDER BY date DESC, count DESC;
        """)
        print("✅ View: v_team_interactions_summary")

        # View 3: API usage by endpoint
        await conn.execute("""
            CREATE OR REPLACE VIEW v_api_usage_by_endpoint AS
            SELECT
                endpoint,
                method,
                COUNT(*) as request_count,
                AVG(response_time_ms) as avg_response_time_ms,
                COUNT(CASE WHEN response_status >= 400 THEN 1 END) as error_count,
                DATE(created_at) as date
            FROM api_audit_trail
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY endpoint, method, DATE(created_at)
            ORDER BY date DESC, request_count DESC;
        """)
        print("✅ View: v_api_usage_by_endpoint")

        print("\n🎉 Migration 041 completed successfully!")
        print("\n📋 Created tables:")
        print("   • activity_logs (general activity tracking)")
        print("   • team_interactions (communications)")
        print("   • api_audit_trail (API calls)")
        print("   • session_tracking (user sessions)")
        print("\n📊 Created views:")
        print("   • v_today_team_activity")
        print("   • v_team_interactions_summary")
        print("   • v_api_usage_by_endpoint")

        await conn.close()
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys

    result = asyncio.run(run_migration())
    sys.exit(0 if result else 1)
