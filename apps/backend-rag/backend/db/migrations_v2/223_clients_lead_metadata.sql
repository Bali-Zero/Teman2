-- 223_clients_lead_metadata.sql
--
-- The lead_intent_matcher cron (scripts/lead_intent_matcher.py) writes the
-- content-funnel attribution payload (lead_intent_id, source_app, context,
-- utm, matched_at) to clients.lead_metadata on every match. The matcher was
-- designed against this column (see also migration 118 first_touch_at) but
-- the column itself never got a migration — first real match would crash
-- with UndefinedColumnError (found 2026-06-11 while arming the cron).
--
-- Additive, idempotent, no backfill needed (NULL = no attribution yet).

ALTER TABLE clients ADD COLUMN IF NOT EXISTS lead_metadata JSONB;

COMMENT ON COLUMN clients.lead_metadata IS
    'Content-funnel attribution written by lead_intent_matcher on match: '
    '{lead_intent_id, source_app, context, utm, matched_at}. NULL until the '
    'client is matched to a lead_intents row.';

-- === ROLLBACK ===
ALTER TABLE clients DROP COLUMN IF EXISTS lead_metadata;
