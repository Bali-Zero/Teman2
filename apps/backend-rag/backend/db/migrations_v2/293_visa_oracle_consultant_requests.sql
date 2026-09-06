-- ============================================================================
-- 293_visa_oracle_consultant_requests.sql
--
-- Integer bound late, at write time (scar W40 — a reservation in a doc
-- nobody re-checks decays). Measured fresh this turn:
--   git ls-tree -r --name-only origin/main -- apps/backend-rag/backend/db/migrations_v2/
--     -> highest present is 280 (280_research_os_objects_truncate_guard.sql)
--   gh pr list --state open --limit 200 --json number,files | grep migrations_v2
--     -> zero open PRs touching this directory
-- -> next available integer: 281. No collision at bind time.
--
-- Durable persistence for the frozen C3 contract
-- (docs/plans/2026-08-24-visa-oracle-live/contracts/FROZEN.md):
-- ConsultantAssignmentEvent, emitted by POST /api/visa-oracle/consultant-
-- assignment (backend/app/routers/visa_oracle_consultant.py). This table
-- IS "the CRM receiving a signal" — the load-bearing write; a downstream
-- Telegram alert is best-effort on top of it, never the durability source.
--
-- Law 2 (SYMBIOSIS.md), verbatim from the contract this table stores:
-- "This event carries no name, phone, email, passport, KTP, or free-text
-- from the applicant." The seven columns below are the seven frozen wire
-- fields and nothing else — there is no column this table could grow that
-- would let PII in without also breaking C1's own extra="forbid" contract
-- at the application layer first. Append-only: no legitimate UPDATE/DELETE
-- exists for a request log, enforced below (simpler than
-- 262_visa_evaluate_idempotency.sql's guard, which permits one specific
-- completion transition this table has no equivalent of).
--
-- ============================================================================

SET lock_timeout = '5s';
SET statement_timeout = '60s';

CREATE TABLE public.visa_oracle_consultant_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id       UUID NOT NULL,
    client_id           UUID,
    requested_at        TIMESTAMPTZ NOT NULL,
    origin_screen       TEXT NOT NULL CHECK (
        origin_screen IN ('wizard', 'verdict', 'checkout', 'portal')
    ),
    tier                TEXT NOT NULL CHECK (tier IN ('T1', 'T2', 'T3')),
    product_version_id  UUID,
    locale              TEXT NOT NULL CHECK (locale IN ('en', 'id')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()
);

COMMENT ON TABLE public.visa_oracle_consultant_requests IS
    'Durable, append-only log of the frozen C3 ConsultantAssignmentEvent. '
    'Exactly the seven wire fields — no PII column may ever be added here '
    'without also breaking the C3 Pydantic contract at the application '
    'layer (extra=forbid + closed-type fields) first.';

CREATE INDEX idx_visa_oracle_consultant_requests_evaluation_id
    ON public.visa_oracle_consultant_requests (evaluation_id);

CREATE INDEX idx_visa_oracle_consultant_requests_client_id
    ON public.visa_oracle_consultant_requests (client_id)
    WHERE client_id IS NOT NULL;

CREATE INDEX idx_visa_oracle_consultant_requests_created_at
    ON public.visa_oracle_consultant_requests (created_at);

CREATE OR REPLACE FUNCTION public.guard_visa_oracle_consultant_requests_append_only()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    RAISE EXCEPTION
        'visa_oracle_consultant_requests is append-only — % not permitted',
        TG_OP;
END;
$$;

CREATE TRIGGER trg_guard_visa_oracle_consultant_requests_append_only
BEFORE UPDATE OR DELETE ON public.visa_oracle_consultant_requests
FOR EACH ROW EXECUTE FUNCTION public.guard_visa_oracle_consultant_requests_append_only();

-- === ROLLBACK ===
SET lock_timeout = '5s';
SET statement_timeout = '60s';

DROP TRIGGER IF EXISTS trg_guard_visa_oracle_consultant_requests_append_only
    ON public.visa_oracle_consultant_requests;

DROP FUNCTION IF EXISTS public.guard_visa_oracle_consultant_requests_append_only();

DROP TABLE IF EXISTS public.visa_oracle_consultant_requests;
