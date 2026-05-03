-- Performance Optimization Indexes
-- Created: 2026-02-07
-- Purpose: Add indexes for frequently queried columns

-- Articles table indexes
-- For news feed queries (ORDER BY created_at DESC)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_created_at 
    ON articles(created_at DESC);

-- For filtering by status
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_status 
    ON articles(status) 
    WHERE status IN ('published', 'draft', 'archived');

-- For source-based filtering and aggregation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_source_created 
    ON articles(source, created_at DESC);

-- For status + created_at combined queries (common in admin)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_status_created 
    ON articles(status, created_at DESC) 
    WHERE status = 'published';

-- Clients table indexes
-- For client list alphabetical ordering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_name 
    ON clients(name);

-- For status-based filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_status 
    ON clients(status);

-- Documents table indexes
-- For recent documents query
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_created 
    ON documents(created_at DESC);
