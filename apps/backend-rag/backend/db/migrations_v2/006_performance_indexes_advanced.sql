-- Migration 006: Advanced Performance Indexes
-- Created: 2026-02-09
-- Purpose: Optimize query performance for high-traffic tables
-- Reference: ADVANCED_OPTIMIZATIONS_ONBOARDING.md Phase 3

-- ====================
-- CONVERSATIONS - Compound indexes for common query patterns
-- ====================

-- Compound index for "get user's recent conversations" (most common query)
-- Speeds up: WHERE user_id = ? ORDER BY created_at DESC LIMIT N
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_user_created
ON conversations(user_id, created_at DESC);

-- Index for channel-based filtering (WhatsApp, Telegram, Web)
-- Speeds up: WHERE channel = ? AND created_at > ?
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_channel_created
ON conversations(channel, created_at DESC)
WHERE channel IS NOT NULL;

-- ====================
-- DOCUMENTS - Compound indexes for filtered lookups
-- ====================

-- Compound index for "get client's active documents by type"
-- Speeds up: WHERE client_id = ? AND status = ? ORDER BY created_at DESC
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_client_status_created
ON documents(client_id, status, created_at DESC);

-- Compound index for expiring documents check
-- Speeds up: WHERE expiry_date BETWEEN ? AND ? AND status = 'active'
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_expiry_active
ON documents(expiry_date, status)
WHERE status = 'active';

-- ====================
-- PRACTICES - Compound indexes for dashboard queries
-- ====================

-- Compound index for "get client's practices by status"
-- Speeds up: WHERE client_id = ? AND status = ? ORDER BY created_at DESC
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_practices_client_status_created
ON practices(client_id, status, created_at DESC);

-- Compound index for renewal tracking dashboard
-- Speeds up: WHERE next_renewal_date BETWEEN ? AND ? AND status IN ('active', 'expiring')
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_practices_renewal_active
ON practices(next_renewal_date, status)
WHERE status IN ('active', 'expiring_soon', 'pending_renewal');

-- ====================
-- CLIENTS - Additional compound indexes
-- ====================

-- Compound index for "search clients by status + creation date"
-- Speeds up: WHERE status = ? ORDER BY created_at DESC (dashboard listing)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_status_created
ON clients(status, created_at DESC);

-- Compound index for assigned_to + status (team member workload view)
-- Speeds up: WHERE assigned_to = ? AND status = ?
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_assigned_status
ON clients(assigned_to, status);

-- Full-text search index on client name (for search functionality)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_fullname_search
ON clients USING gin(to_tsvector('simple', full_name));

-- ====================
-- COLLECTIVE MEMORIES - Query optimization
-- ====================

-- Compound index for recent memories by category
-- Speeds up: WHERE category = ? ORDER BY created_at DESC LIMIT N
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_collective_memories_cat_created
ON collective_memories(category, created_at DESC);

-- ====================
-- QUERY ANALYTICS - Dashboard query optimization
-- ====================

-- Index for daily volume aggregation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_query_analytics_created
ON query_analytics(created_at DESC);

-- Index for collection hit rate analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_query_analytics_collections
ON query_analytics USING gin(collections_queried);

-- Index for failed queries (low chunk count = potential issues)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_query_analytics_failed
ON query_analytics(chunks_retrieved_count, created_at DESC)
WHERE chunks_retrieved_count = 0;

-- ====================
-- TEAM TIMESHEET - Reporting optimization
-- ====================

-- Compound index for team member time reports
-- Speeds up: WHERE user_id = ? AND date BETWEEN ? AND ?
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_timesheet_user_date
ON team_timesheet(user_id, date DESC);

-- ====================
-- UPDATE STATISTICS
-- ====================

ANALYZE conversations;
ANALYZE documents;
ANALYZE practices;
ANALYZE clients;
ANALYZE collective_memories;
ANALYZE team_timesheet;
