-- Migration 043: Unified Identities View (Virtual Identity Layer)
-- Purpose: Combine team_members and clients into a single view for Admin/Auth purposes
-- Created: 2026-01-19

CREATE OR REPLACE VIEW unified_identities_view AS
SELECT 
    id::text AS uuid,
    name AS display_name,
    email,
    role,
    avatar,
    'team_members' AS source_table,
    created_at,
    active AS is_active
FROM team_members

UNION ALL

SELECT 
    uuid::text AS uuid,
    full_name AS display_name,
    email,
    'client' AS role,
    NULL AS avatar,
    'clients' AS source_table,
    created_at,
    CASE WHEN status = 'active' THEN true ELSE false END AS is_active
FROM clients
WHERE uuid IS NOT NULL;  -- Ensure we only pick clients with generated UUIDs

COMMENT ON VIEW unified_identities_view IS 'Virtual Identity Layer merging Staff (team_members) and Customers (clients) for admin observability.';
