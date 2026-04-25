-- ============================================================
-- 118_clients_seo_attribution.sql
-- Adds SEO/CRO attribution columns to clients.
-- Date: 2026-04-21
--
-- Context
-- -------
-- backend/db/repositories/client_repository.py INSERTs into
-- clients.referrer_url / landing_page / first_touch_at (since commit
-- c0f5f70f6 "feat(seo-cell): Plan A Task 4+9"). A Python migration
-- at backend/migrations/migration_118_clients_referrer_url.py was
-- shipped alongside the code, but the Fly migration runner
-- (backend/db/migrate.py) ONLY scans backend/db/migrations_v2/*.sql,
-- so that Python file was dead. Production `clients` was missing the
-- three columns, and every POST /api/clients returned 503 with the
-- masked message "Database service temporarily unavailable"
-- (UndefinedColumnError mapped by app/utils/error_handlers.py).
--
-- Same scar as 117_llm_cost_events.sql — see that file's header.
--
-- Schema additions
-- ----------------
-- referrer_url    TEXT         — HTTP Referer header at first interaction
-- landing_page    TEXT         — first page on balizero.com domain visited
-- first_touch_at  TIMESTAMPTZ  — when the lead first interacted
--
-- Indexes use text_pattern_ops for LIKE '/visa/%' style queries from
-- the SEO attribution reports, partial (IS NOT NULL) so legacy rows
-- stay out of the index.
-- ============================================================

ALTER TABLE clients ADD COLUMN IF NOT EXISTS referrer_url   TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS landing_page   TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS first_touch_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_clients_referrer_url
    ON clients (referrer_url text_pattern_ops)
    WHERE referrer_url IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_clients_landing_page
    ON clients (landing_page text_pattern_ops)
    WHERE landing_page IS NOT NULL;

-- === ROLLBACK ===
-- Non-destructive data-wise; columns go away, indexes with them.
DROP INDEX IF EXISTS idx_clients_landing_page;
DROP INDEX IF EXISTS idx_clients_referrer_url;
ALTER TABLE clients DROP COLUMN IF EXISTS first_touch_at;
ALTER TABLE clients DROP COLUMN IF EXISTS landing_page;
ALTER TABLE clients DROP COLUMN IF EXISTS referrer_url;
