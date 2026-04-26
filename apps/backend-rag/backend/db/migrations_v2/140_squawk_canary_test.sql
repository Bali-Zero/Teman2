-- Migration 140: SQUAWK CANARY TEST — DO NOT MERGE.
--
-- This migration is a deliberate live test of the Squawk migration-lint
-- workflow shipped in PR #306 (commit 935e61a75). It contains two patterns
-- that Squawk should flag with `fail-on-violations=true`:
--
--   1. ALTER TABLE ADD COLUMN ... NOT NULL without DEFAULT — known Squawk
--      rule "adding-required-field" / data-dependency violation. Would lock
--      the `clients` table during application on a populated row set.
--   2. CREATE INDEX without CONCURRENTLY on an existing table — Squawk
--      rule "non-concurrent-index". Acquires an ACCESS EXCLUSIVE lock that
--      blocks reads + writes on `clients` for the duration of the build.
--
-- Expected behaviour: Squawk's GitHub Action posts a PR comment listing
-- both violations, and the `Migration Lint (Squawk) / Lint` check turns
-- red within ~90s of the push. The PR will be CLOSED without merging
-- once the canary test is confirmed.

ALTER TABLE clients ADD COLUMN squawk_canary_field TEXT NOT NULL;

CREATE INDEX idx_clients_squawk_canary ON clients (squawk_canary_field);

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_clients_squawk_canary;
ALTER TABLE clients DROP COLUMN IF EXISTS squawk_canary_field;
