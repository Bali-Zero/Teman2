-- ============================================================================
-- 304_garuda_documents.sql
-- GARUDA VOA — document-upload lane (product step 5) persistence.
--
-- NUMBERING NOTE: the mandate that produced this file named it
-- `302_garuda_documents.sql`. By the time this branch was built, `302` and
-- `303` were already real, merged, production-applied migrations
-- (`302_practice_types_voa_price_790.sql`, `303_practice_types_voa_price_750.sql`
-- — PR #5428). Renumbered to the next free slot (304) rather than colliding;
-- flagged in the shipping PR body, not silently renamed.
--
-- WHAT THIS DOES. Backs `backend/services/garuda_documents/ports.py`'s
-- `DocumentStorePort` (`get_existing`/`commit`) with real, retention-covered
-- Postgres storage (`backend/services/garuda_documents/postgres_store.py`),
-- replacing the lane's own `InMemoryDocumentStore` test double the same way
-- migration 284 replaced `garuda_orders`' in-memory seam. Two tables:
--   1. garuda_documents             -- one row per idempotency key: outcome
--                                       structure + retention binding.
--   2. garuda_document_review_fields -- child rows: field NAME +
--                                       confirmation_required flag only.
--
-- THE PII BOUNDARY DECISION (postgres_store.py module docstring carries the
-- full argument; summarized here because it shapes the schema). A
-- `ReadyOutcome.review_fields` entry (`models.ReviewField`) carries the
-- actual OCR'd passport field VALUE (full name, passport number,
-- nationality, expiry date) -- that value IS the personal data this whole
-- lane's redaction.py module exists to keep off any wire this pipeline does
-- not strictly need. `garuda_document_review_fields` therefore has NO value
-- column at all: it persists only `field_path` and `confirmation_required`
-- -- enough to rehydrate a `LowConfidenceOutcome.uncertain_fields` entry
-- faithfully (`UncertainReviewField` itself carries no value either) but
-- NOT enough to rehydrate a `ReadyOutcome.review_fields` entry's `value`.
-- That is a genuine, unresolved architecture question the mandate that
-- built this file asked to be flagged rather than papered over with an
-- invented encryption scheme -- see postgres_store.py's
-- `ReadyOutcomeValueNotPersisted` for the shape of the gap and the
-- candidates for resolving it. It affects ONLY the idempotent-replay path
-- of an already-READY document; a first-time submission is unaffected
-- (the caller already holds the real values in memory and never round-trips
-- them through this store).
--
-- RETENTION: a fifth scope on the SAME Zero-approved authority migration
-- 281/285 already widened (`visa_decision_retention_policies`,
-- ARCHITECTURE.md D2 "one authority, not two") -- `GARUDA_DOCUMENT`, not a
-- table-specific policy. `garuda_document_review_fields` is NOT added to
-- `guard_visa_decision_retention_policy_mutation()`'s strand-protection
-- EXISTS clauses: migration 284 (`garuda_orders`/`garuda_order_idempotency`)
-- set the precedent that not every new GARUDA_* table family joins that
-- guard -- 285/286 added themselves because their rows are durable
-- customer-decision records with a real retrospective-audit need; this
-- table is closer in nature to an idempotency/outcome cache (like
-- `garuda_order_idempotency`, also not in that guard) than to a decision
-- record, and it carries no PII value to investigate in the first place.
--
-- THE OWNERSHIP TRANSFER (migration 301's outage, not repeated here).
-- Migration 285 shipped `bind_garuda_magic_link_token_retention_policy` as
-- SECURITY DEFINER owned by `backend_rag_v2` -- which buys nothing, because
-- the app role cannot take the `FOR SHARE` lock on
-- `visa_decision_retention_policies` either, and the function runs with the
-- OWNER's privileges, not the caller's. That silently 500'd every real
-- INSERT for weeks until migration 301 transferred ownership to
-- `visa_ledger_owner` (owner of `visa_decision_retention_policies`) in a
-- follow-up migration. This file does the CREATE and the transfer in ONE
-- migration so the same defect cannot recur here by omission -- see the
-- `DO $garuda_304_owner_transfer$` block below, replicated from 301's shape
-- verbatim except for the function signature and block tag. 301's own
-- honest caveat carries over unchanged: the postcondition assertion is
-- reached on only ONE of three paths (role absent / function absent both
-- NOTICE-and-RETURN before it); nothing in this repository currently probes
-- for the other two.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- (0) Widen the one retention authority with a fifth scope
-- ----------------------------------------------------------------------------

DO $garuda_304_widen_scope_check$
DECLARE
    scope_check_name text;
BEGIN
    -- Same find-by-shape discipline 285/281 use: the inline
    -- `policy_scope ... CHECK (policy_scope IN (...))` constraint renders
    -- back as `CHECK ((policy_scope = ANY (ARRAY[...])))`, distinct from
    -- `visa_decision_retention_policies_scope_anchor` (which renders as
    -- `CHECK ((policy_scope <> 'GARUDA_CHECK'::text) OR ...)`). Never a
    -- hardcoded constraint name.
    SELECT conname INTO scope_check_name
      FROM pg_constraint
     WHERE conrelid = 'public.visa_decision_retention_policies'::regclass
       AND contype = 'c'
       AND pg_get_constraintdef(oid) LIKE 'CHECK ((policy_scope = ANY (ARRAY[%';
    IF scope_check_name IS NULL THEN
        RAISE EXCEPTION 'garuda 304: could not locate the policy_scope enum CHECK to widen';
    END IF;
    EXECUTE format(
        'ALTER TABLE public.visa_decision_retention_policies DROP CONSTRAINT %I',
        scope_check_name
    );
END;
$garuda_304_widen_scope_check$;

ALTER TABLE public.visa_decision_retention_policies
    ADD CONSTRAINT visa_decision_retention_policies_policy_scope_check
        CHECK (policy_scope IN ('VISA_DECISION', 'GARUDA_CHECK', 'GARUDA_ORDER', 'GARUDA_MAGIC_LINK', 'GARUDA_DOCUMENT'));

-- ----------------------------------------------------------------------------
-- (1) garuda_documents -- one row per idempotency key
--
-- Retention basis: same tier as `garuda_order_idempotency` (an
-- operational-lifetime idempotency/outcome cache), not the
-- durable-decision tier `garuda_voa_checks`/`garuda_magic_link_tokens` sit
-- in -- but STILL policy-gated through the shared authority (never a bare
-- fixed TTL default) so Zero signs off on the duration like every other
-- GARUDA_* scope, and so a future change of mind about this table's
-- retention tier does not require a schema change.
-- ----------------------------------------------------------------------------

CREATE TABLE public.garuda_documents (
    key_sha256              BYTEA PRIMARY KEY CHECK (octet_length(key_sha256) = 32),
    canonical_payload_sha256 BYTEA NOT NULL CHECK (octet_length(canonical_payload_sha256) = 32),
    -- uuid4().hex from service.py's DefaultClock.new_document_id() -- 32
    -- lowercase hex characters, no dashes.
    document_id              TEXT NOT NULL UNIQUE CHECK (document_id ~ '^[0-9a-f]{32}$'),
    environment               TEXT NOT NULL CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),
    -- Mirrors `models.ProcessingState` plus one storage-layer-only member,
    -- UNREADABLE, for `models.UnreadableOutcome` -- that dataclass is
    -- deliberately domain-internal (module docstring: the frozen contract
    -- has no schema for the 422 UNREADABLE_DOCUMENT success-shaped body) and
    -- carries no `processing_state` field of its own to reuse.
    processing_state          TEXT NOT NULL CHECK (
        processing_state IN ('PROCESSING', 'LOW_CONFIDENCE', 'READY_FOR_REVIEW', 'UNREADABLE')
    ),
    retention_policy_id       UUID NOT NULL REFERENCES public.visa_decision_retention_policies (id),
    retention_until           TIMESTAMPTZ NOT NULL,
    -- NOW() (== transaction_timestamp()), NOT statement_timestamp(): the
    -- retention-binding trigger below checks `NEW.created_at IS DISTINCT
    -- FROM transaction_timestamp()` (285's exact convention) -- this INSERT
    -- is not the transaction's first statement (the fail-closed policy
    -- pre-check in postgres_store.py runs first, in the same transaction),
    -- so `statement_timestamp()` here would differ from
    -- `transaction_timestamp()` by the gap between the two statements and
    -- the trigger would reject every real row.
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (retention_until > created_at)
);

COMMENT ON TABLE public.garuda_documents IS
    'GARUDA VOA document-upload intake (product step 5). One row per Idempotency-Key. Never stores raw document bytes or extracted passport field VALUES -- see postgres_store.py / garuda_document_review_fields for the PII-boundary rationale.';
COMMENT ON COLUMN public.garuda_documents.key_sha256 IS
    'sha256 of the Idempotency-Key header value. Raw key is never persisted.';
COMMENT ON COLUMN public.garuda_documents.canonical_payload_sha256 IS
    'sha256 of (document_kind || raw upload bytes) -- service.py::_payload_hash. Raw bytes are never persisted anywhere.';

CREATE INDEX idx_garuda_documents_retention_purge
    ON public.garuda_documents (retention_until);

-- Fail-closed retention binding -- identical shape to
-- `active_garuda_magic_link_policy_available` (285) / `active_garuda_
-- check_policy_available` (garuda_flow/retention.py), scoped to
-- GARUDA_DOCUMENT / CREATED_AT anchor (this table has no evaluation
-- timestamp distinct from row creation).
CREATE FUNCTION public.active_garuda_document_policy_available(
    p_environment TEXT,
    p_created_at TIMESTAMPTZ
) RETURNS BOOLEAN
LANGUAGE sql
STABLE
SET search_path = pg_catalog, public
AS $func$
    SELECT count(*) = 1
    FROM public.visa_decision_retention_policies
    WHERE environment = p_environment
      AND policy_scope = 'GARUDA_DOCUMENT'
      AND effective_period @> p_created_at;
$func$;

COMMENT ON FUNCTION public.active_garuda_document_policy_available IS
    'Pre-INSERT read for PostgresDocumentStore.commit(): one Zero-approved GARUDA_DOCUMENT policy must cover this clock, or the upload fails closed (PERSISTENCE_POLICY_UNAVAILABLE) before any row is attempted.';

CREATE FUNCTION public.bind_garuda_document_retention_policy()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $func$
DECLARE
    policy RECORD;
    expected_until TIMESTAMPTZ;
BEGIN
    IF NEW.created_at IS DISTINCT FROM transaction_timestamp() THEN
        RAISE EXCEPTION 'garuda document created_at must use the database transaction clock';
    END IF;

    BEGIN
        SELECT id, retention_interval, retention_anchor
          INTO STRICT policy
          FROM public.visa_decision_retention_policies
         WHERE environment = NEW.environment
           AND policy_scope = 'GARUDA_DOCUMENT'
           AND effective_period @> NEW.created_at
         FOR SHARE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE EXCEPTION 'garuda document has no active Zero-approved retention policy';
        WHEN TOO_MANY_ROWS THEN
            RAISE EXCEPTION 'garuda document retention policy authority is ambiguous';
    END;

    IF policy.retention_anchor <> 'CREATED_AT' THEN
        RAISE EXCEPTION 'unsupported retention anchor for GARUDA_DOCUMENT scope';
    END IF;
    expected_until := NEW.created_at + policy.retention_interval;
    IF expected_until <= clock_timestamp() THEN
        RAISE EXCEPTION 'garuda document retention deadline has already elapsed';
    END IF;

    IF NEW.retention_policy_id IS NOT NULL
       AND NEW.retention_policy_id IS DISTINCT FROM policy.id THEN
        RAISE EXCEPTION 'garuda document retention policy does not match active policy';
    END IF;
    IF NEW.retention_until IS NOT NULL
       AND NEW.retention_until IS DISTINCT FROM expected_until THEN
        RAISE EXCEPTION 'garuda document retention deadline does not match active policy';
    END IF;

    NEW.retention_policy_id := policy.id;
    NEW.retention_until := expected_until;
    RETURN NEW;
END;
$func$;

REVOKE ALL ON FUNCTION public.bind_garuda_document_retention_policy() FROM PUBLIC;

CREATE TRIGGER garuda_documents_retention_binding
BEFORE INSERT ON public.garuda_documents
FOR EACH ROW EXECUTE FUNCTION public.bind_garuda_document_retention_policy();

-- ----------------------------------------------------------------------------
-- (2) THE OWNERSHIP TRANSFER -- replicated from migration 301's shape
-- verbatim (see the module header above for why this is done inline rather
-- than deferred to a follow-up migration the way 285/301 were split).
-- ----------------------------------------------------------------------------

DO $garuda_304_owner_transfer$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    signature constant text := 'public.bind_garuda_document_retention_policy()';
    fn oid;
    current_owner text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ledger_owner) THEN
        RAISE NOTICE 'garuda documents (304): role % absent -- skipping ownership transfer, same convention as 251/253/268/281/301',
            ledger_owner;
        RETURN;
    END IF;

    fn := to_regprocedure(signature);
    IF fn IS NULL THEN
        RAISE NOTICE 'garuda documents (304): % not present -- nothing to transfer', signature;
        RETURN;
    END IF;

    SELECT pg_get_userbyid(proowner) INTO current_owner FROM pg_proc WHERE oid = fn;

    IF current_owner IS DISTINCT FROM ledger_owner THEN
        BEGIN
            EXECUTE format('ALTER FUNCTION %s OWNER TO %I', signature, ledger_owner);
        EXCEPTION
            WHEN insufficient_privilege THEN
                RAISE NOTICE 'garuda documents (304): ALTER denied (current owner %) -- this session is neither superuser nor a member of %',
                    current_owner, ledger_owner;
        END;
        SELECT pg_get_userbyid(proowner) INTO current_owner FROM pg_proc WHERE oid = fn;
    END IF;

    IF current_owner IS DISTINCT FROM ledger_owner THEN
        RAISE EXCEPTION
            'garuda documents (304): % is still owned by % -- the SECURITY DEFINER trigger cannot take its FOR SHARE lock on visa_decision_retention_policies, so document intake would answer 500 on write. Refusing to record this migration as applied while that is true: run the ALTER on a superuser connection, then re-apply.',
            signature, current_owner;
    END IF;
END;
$garuda_304_owner_transfer$;

-- Rows are immutable once inserted (no mutable field like magic-link's
-- `used_at`); deletion is only permitted once retention has actually
-- elapsed. Same "close/consume, never silently mutate" discipline as
-- `guard_garuda_magic_link_token_mutation` (285).
CREATE FUNCTION public.guard_garuda_document_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $func$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF clock_timestamp() < OLD.retention_until THEN
            RAISE EXCEPTION 'unexpired garuda_documents rows are immutable';
        END IF;
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'garuda_documents rows are immutable once inserted';
END;
$func$;

CREATE TRIGGER trg_guard_garuda_document_mutation
BEFORE UPDATE OR DELETE ON public.garuda_documents
FOR EACH ROW EXECUTE FUNCTION public.guard_garuda_document_mutation();

-- ----------------------------------------------------------------------------
-- (3) garuda_document_review_fields -- structure-only child rows
--
-- Deliberately has NO mutation guard of its own and NO independent
-- retention binding: it lives and dies with its parent row via `ON DELETE
-- CASCADE` (a guard trigger here would have to special-case a cascade
-- delete to avoid fighting the parent's own erasure path). Application
-- code only ever INSERTs these rows once, alongside the parent, inside the
-- same transaction (postgres_store.py::commit).
-- ----------------------------------------------------------------------------

CREATE TABLE public.garuda_document_review_fields (
    document_id           TEXT NOT NULL REFERENCES public.garuda_documents (document_id) ON DELETE CASCADE,
    field_path             TEXT NOT NULL CHECK (
        field_path IN ('full_name', 'passport_number', 'nationality', 'passport_expiry_date')
    ),
    confirmation_required   BOOLEAN NOT NULL,
    PRIMARY KEY (document_id, field_path)
);

COMMENT ON TABLE public.garuda_document_review_fields IS
    'Structure-only rehydration data for ReadyOutcome.review_fields / LowConfidenceOutcome.uncertain_fields -- field NAME + confirmation_required flag only. The extracted VALUE (passport field content) is deliberately never persisted here -- see postgres_store.py module docstring for the PII-boundary rationale and its one open gap (idempotent replay of a READY_FOR_REVIEW outcome cannot return the original values).';

-- === ROLLBACK ===

DROP TRIGGER IF EXISTS trg_guard_garuda_document_mutation ON public.garuda_documents;
DROP FUNCTION IF EXISTS public.guard_garuda_document_mutation();
DROP TABLE IF EXISTS public.garuda_document_review_fields;
DROP TRIGGER IF EXISTS garuda_documents_retention_binding ON public.garuda_documents;
DROP FUNCTION IF EXISTS public.bind_garuda_document_retention_policy();
DROP FUNCTION IF EXISTS public.active_garuda_document_policy_available(TEXT, TIMESTAMPTZ);
DROP TABLE IF EXISTS public.garuda_documents;

-- Narrowing the policy_scope CHECK back to pre-304's list is only safe if
-- no row has ever used 'GARUDA_DOCUMENT' -- visa_decision_retention_policies
-- is append-only (264's guard trigger blocks UPDATE/DELETE/TRUNCATE
-- unconditionally), so a 'GARUDA_DOCUMENT'-scoped row, once inserted, can
-- never be removed to make room for a narrower constraint. Same reasoning,
-- and the same bug class, as 285's rollback (PR #4902 follow-up: an
-- unconditional DROP/ADD CONSTRAINT pair there always failed with
-- CheckViolationError once a widened value had ever been used) -- narrow
-- when safe, otherwise leave the CHECK WIDENED rather than fail the whole
-- rollback.
DO $garuda_304_narrow_policy_scope$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.visa_decision_retention_policies
         WHERE policy_scope = 'GARUDA_DOCUMENT'
    ) THEN
        RAISE NOTICE 'garuda 304 rollback: visa_decision_retention_policies has row(s) with policy_scope = ''GARUDA_DOCUMENT'' -- the append-only guard makes them impossible to remove, so the policy_scope CHECK is left WIDENED (304''s state) rather than narrowed back to pre-304''s list. This is a one-way widening, same as any append-only enum on this table.';
    ELSE
        ALTER TABLE public.visa_decision_retention_policies
            DROP CONSTRAINT IF EXISTS visa_decision_retention_policies_policy_scope_check;
        ALTER TABLE public.visa_decision_retention_policies
            ADD CONSTRAINT visa_decision_retention_policies_policy_scope_check
                CHECK (policy_scope IN ('VISA_DECISION', 'GARUDA_CHECK', 'GARUDA_ORDER', 'GARUDA_MAGIC_LINK'));
    END IF;
END;
$garuda_304_narrow_policy_scope$;
