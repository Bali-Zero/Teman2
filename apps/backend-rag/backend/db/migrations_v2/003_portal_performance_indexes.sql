-- Migration 003: Add Performance Indexes for Tax & Visa Portal Endpoints
-- Created: 2026-02-02
-- Purpose: Optimize query performance for tax_obligations and visa_records

-- ====================
-- TAX OBLIGATIONS INDEXES
-- ====================

-- Index for client_id + status filtering (used in get_client_taxes)
-- Speeds up: WHERE client_id = ? AND status NOT IN ('paid', 'filed')
CREATE INDEX IF NOT EXISTS idx_tax_client_status 
ON tax_obligations(client_id, status);

-- Index for due_date range queries (used in deadline_checker)
-- Speeds up: WHERE due_date = ? AND status IN ('upcoming', 'pending')
CREATE INDEX IF NOT EXISTS idx_tax_due_date_status 
ON tax_obligations(due_date, status) 
WHERE status IN ('upcoming', 'pending');

-- Partial index for active obligations only (smaller, faster)
CREATE INDEX IF NOT EXISTS idx_tax_active_obligations 
ON tax_obligations(client_id, due_date) 
WHERE status NOT IN ('paid', 'filed');

-- Index for summary aggregations (used in get_tax_summary)
-- Speeds up: GROUP BY client_id with WHERE status filters
CREATE INDEX IF NOT EXISTS idx_tax_summary 
ON tax_obligations(client_id, status, amount_due, due_date);

-- ====================
-- VISA RECORDS INDEXES
-- ====================

-- Index for client_id + status filtering (used in get_active_visa)
-- Speeds up: WHERE client_id = ? AND status IN ('active', 'expiring_soon')
CREATE INDEX IF NOT EXISTS idx_visa_client_status 
ON visa_records(client_id, status);

-- Index for expiry_date range queries (used in deadline_checker)
-- Speeds up: WHERE expiry_date <= ? AND status = 'active'
CREATE INDEX IF NOT EXISTS idx_visa_expiry_date_status 
ON visa_records(expiry_date, status) 
WHERE status IN ('active', 'expiring_soon');

-- Index for active visas only (smaller, faster)
CREATE INDEX IF NOT EXISTS idx_visa_active 
ON visa_records(client_id, expiry_date DESC) 
WHERE status IN ('active', 'expiring_soon');

-- Index for visa history queries (used in get_visa_history)
-- Speeds up: WHERE client_id = ? ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_visa_history 
ON visa_records(client_id, created_at DESC);

-- ====================
-- TIMELINE EVENTS INDEXES
-- ====================

-- Index for client-visible events (used in Portal dashboard)
-- Speeds up: WHERE client_id = ? AND client_visible = true ORDER BY event_date DESC
CREATE INDEX IF NOT EXISTS idx_timeline_client_visible 
ON timeline_events(client_id, client_visible, event_date DESC);

-- Index for reminder duplicate checks (used in deadline_checker)
-- Speeds up: WHERE client_id = ? AND event_type = 'reminder' AND title LIKE ? AND DATE(event_date) = ?
CREATE INDEX IF NOT EXISTS idx_timeline_reminder_check 
ON timeline_events(client_id, event_type, event_date) 
WHERE event_type = 'reminder';

-- ====================
-- ANALYZE TABLES
-- ====================

-- Update query planner statistics
ANALYZE tax_obligations;
ANALYZE visa_records;
ANALYZE timeline_events;

-- ====================
-- VERIFICATION QUERIES
-- ====================

-- Run these to verify indexes are being used:

-- 1. Tax obligations query (should use idx_tax_client_status)
-- EXPLAIN ANALYZE
-- SELECT * FROM tax_obligations 
-- WHERE client_id = 123 AND status NOT IN ('paid', 'filed')
-- ORDER BY due_date ASC;

-- 2. Visa active query (should use idx_visa_active)
-- EXPLAIN ANALYZE
-- SELECT * FROM visa_records 
-- WHERE client_id = 123 AND status IN ('active', 'expiring_soon')
-- ORDER BY expiry_date DESC LIMIT 1;

-- 3. Deadline checker tax query (should use idx_tax_due_date_status)
-- EXPLAIN ANALYZE
-- SELECT * FROM tax_obligations 
-- WHERE due_date = '2026-03-02' AND status IN ('upcoming', 'pending');

-- 4. Timeline events query (should use idx_timeline_client_visible)
-- EXPLAIN ANALYZE
-- SELECT * FROM timeline_events 
-- WHERE client_id = 123 AND client_visible = true 
-- ORDER BY event_date DESC LIMIT 20;
