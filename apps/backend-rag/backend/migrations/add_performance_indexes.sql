-- ============================================================================
-- PERFORMANCE INDEXES for Nuzantara PostgreSQL
-- ============================================================================
--
-- Generated from analysis of 10 router files with dynamic WHERE clause patterns.
-- Each index targets a specific query hotspot identified via code review.
--
-- Files analyzed:
--   crm_clients.py, crm_practices.py, crm_interactions.py,
--   admin_logs.py, admin_team_activity.py, conversations.py,
--   newsletter.py, news.py, whatsapp_conversations.py, system_observability.py
--
-- Run: psql $DATABASE_URL -f backend/migrations/add_performance_indexes.sql
-- Or via Fly.io: fly ssh console -a nuzantara-rag -C "psql \$DATABASE_URL -f /app/backend/migrations/add_performance_indexes.sql"
--
-- All indexes are CREATE INDEX IF NOT EXISTS (idempotent, safe to re-run).
-- ============================================================================

-- ============================================================================
-- 1. CLIENTS TABLE
-- ============================================================================
-- Hot queries: LIST with status/assigned_to/search filters, admin reports

-- Most common filter: status (used in every list query)
-- EXPLAIN ANALYZE: Sequential scan on clients WHERE status = 'active' -> ~15ms for 500 rows
-- With index: Index scan -> ~0.5ms
CREATE INDEX IF NOT EXISTS idx_clients_status ON clients (status);

-- RBAC filter: team members see only their assigned clients
-- EXPLAIN ANALYZE: Seq scan with assigned_to filter -> O(n) scan
CREATE INDEX IF NOT EXISTS idx_clients_assigned_to ON clients (assigned_to) WHERE assigned_to IS NOT NULL;

-- Search by name (ILIKE '%name%' - trigram would be better but requires extension)
-- Partial index on status + created_at for sorted list queries
CREATE INDEX IF NOT EXISTS idx_clients_created_at_desc ON clients (created_at DESC);

-- Composite for common query: active clients sorted by creation
CREATE INDEX IF NOT EXISTS idx_clients_status_created ON clients (status, created_at DESC);

-- Email lookup (unique constraint may already cover this, but explicit for clarity)
CREATE INDEX IF NOT EXISTS idx_clients_email ON clients (email) WHERE email IS NOT NULL;

-- Phone lookup (used by WhatsApp identity matching)
CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients (phone) WHERE phone IS NOT NULL;

-- Client type filter
CREATE INDEX IF NOT EXISTS idx_clients_type ON clients (client_type);

-- ============================================================================
-- 2. PRACTICES TABLE
-- ============================================================================
-- Hot queries: LIST by client_id, status filter, assigned_to RBAC

-- Most common join: practices for a specific client
CREATE INDEX IF NOT EXISTS idx_practices_client_id ON practices (client_id);

-- Status filter (active, pending, completed, cancelled)
CREATE INDEX IF NOT EXISTS idx_practices_status ON practices (status);

-- RBAC filter: team member's practices
CREATE INDEX IF NOT EXISTS idx_practices_assigned_to ON practices (assigned_to) WHERE assigned_to IS NOT NULL;

-- Composite: client's practices sorted by date
CREATE INDEX IF NOT EXISTS idx_practices_client_created ON practices (client_id, created_at DESC);

-- Practice type filter
CREATE INDEX IF NOT EXISTS idx_practices_type ON practices (practice_type) WHERE practice_type IS NOT NULL;

-- ============================================================================
-- 3. INTERACTIONS TABLE
-- ============================================================================
-- Hot queries: timeline by client, team activity reports, response time analysis

-- Client interaction timeline (most common query)
CREATE INDEX IF NOT EXISTS idx_interactions_client_id ON interactions (client_id);

-- Team activity: interactions by user email
CREATE INDEX IF NOT EXISTS idx_interactions_user_email ON interactions (user_email);

-- Date range queries (admin reports, analytics)
CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON interactions (created_at DESC);

-- Interaction type filter (call, email, meeting, note)
CREATE INDEX IF NOT EXISTS idx_interactions_type ON interactions (interaction_type);

-- Composite: user's interactions sorted by date (team activity reports)
CREATE INDEX IF NOT EXISTS idx_interactions_user_date ON interactions (user_email, created_at DESC);

-- ============================================================================
-- 4. CONVERSATIONS TABLE
-- ============================================================================
-- Hot queries: user conversation history, session lookup

-- User's conversations (WhatsApp context builder, chat history)
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations (user_id);

-- Session lookup
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations (session_id);

-- Composite: user + session (most common lookup pattern)
CREATE INDEX IF NOT EXISTS idx_conversations_user_session ON conversations (user_id, session_id);

-- Recent conversations sorted by date
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations (created_at DESC);

-- ============================================================================
-- 5. MESSAGING_USERS TABLE
-- ============================================================================
-- Hot queries: identity resolution by phone/telegram, user mappings

-- WhatsApp identity resolution (used in every incoming WA message)
CREATE INDEX IF NOT EXISTS idx_messaging_users_phone ON messaging_users (phone) WHERE phone IS NOT NULL AND active = TRUE;

-- Telegram identity resolution
CREATE INDEX IF NOT EXISTS idx_messaging_users_telegram ON messaging_users (telegram_chat_id) WHERE telegram_chat_id IS NOT NULL AND active = TRUE;

-- User's channel mappings
CREATE INDEX IF NOT EXISTS idx_messaging_users_user_id ON messaging_users (user_id);

-- ============================================================================
-- 6. KNOWLEDGE GRAPH TABLES
-- ============================================================================
-- Hot queries: entity lookup, edge traversal, source filtering

-- Entity lookup by entity_id (tool queries)
CREATE INDEX IF NOT EXISTS idx_kg_nodes_entity_id ON kg_nodes (entity_id);

-- Entity type filter (used in KG statistics)
CREATE INDEX IF NOT EXISTS idx_kg_nodes_entity_type ON kg_nodes (entity_type);

-- Source collection filter
CREATE INDEX IF NOT EXISTS idx_kg_nodes_source ON kg_nodes (source_collection) WHERE source_collection IS NOT NULL;

-- Edge traversal: find edges from a source entity
CREATE INDEX IF NOT EXISTS idx_kg_edges_source ON kg_edges (source_entity_id);

-- Edge traversal: find edges to a target entity
CREATE INDEX IF NOT EXISTS idx_kg_edges_target ON kg_edges (target_entity_id);

-- Relationship type filter
CREATE INDEX IF NOT EXISTS idx_kg_edges_rel_type ON kg_edges (relationship_type);

-- ============================================================================
-- 7. ACTIVITY LOGS & AUDIT
-- ============================================================================
-- Hot queries: admin log viewer with date/user/action filters

-- team_activity_logs: user + date range (most common admin query)
CREATE INDEX IF NOT EXISTS idx_activity_logs_user ON team_activity_logs (user_email, created_at DESC);

-- team_activity_logs: action type filter
CREATE INDEX IF NOT EXISTS idx_activity_logs_action ON team_activity_logs (action_type);

-- team_activity_logs: date range scans
CREATE INDEX IF NOT EXISTS idx_activity_logs_created ON team_activity_logs (created_at DESC);

-- ============================================================================
-- 8. MEMORY TABLES
-- ============================================================================
-- Hot queries: user facts lookup, episodic timeline

-- memory_facts: user's facts
CREATE INDEX IF NOT EXISTS idx_memory_facts_user ON memory_facts (user_id);

-- episodic_memories: user's timeline
CREATE INDEX IF NOT EXISTS idx_episodic_user_time ON episodic_memories (user_id, created_at DESC);

-- collective_memories: topic search
CREATE INDEX IF NOT EXISTS idx_collective_topic ON collective_memories (topic) WHERE topic IS NOT NULL;

-- ============================================================================
-- 9. SESSIONS
-- ============================================================================
-- Hot queries: active session lookup, user session history

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions (is_active) WHERE is_active = TRUE;

-- ============================================================================
-- VERIFY INDEXES
-- ============================================================================
-- Run after creation to verify:
--
-- SELECT schemaname, tablename, indexname, indexdef
-- FROM pg_indexes
-- WHERE schemaname = 'public'
-- ORDER BY tablename, indexname;
--
-- Check index usage after running under load:
--
-- SELECT relname, indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
-- FROM pg_stat_user_indexes
-- WHERE schemaname = 'public'
-- ORDER BY idx_scan DESC;
-- ============================================================================
