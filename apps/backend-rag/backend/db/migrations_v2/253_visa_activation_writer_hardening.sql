-- Migration 253: Visa Oracle engine — activation writer hardening
-- (STEP-6a FIX-ROUND, roll-forward correction against an ALREADY-APPLIED
-- migration 251)
--
-- ============================================================================
-- WHY THIS IS A NEW MIGRATION, NOT AN EDIT TO 251
-- ============================================================================
--   Migration 251 (`251_visa_activation_writer.sql`) was merged to `main`
--   via PR #2840 at 2026-07-19T18:31:03Z and applied to production at
--   2026-07-19T18:39:19Z (8 minutes later) — BEFORE a dispatched FIX-ROUND
--   implementer could land the fixes a cross-family verify (Codex gpt-5.6-sol
--   xhigh + GLM) had already flagged, in fact across FOUR separate automated
--   tri-LLM review rounds on that PR, each returning a Codex RED verdict on
--   substantially the SAME findings below. The tri-LLM review bot is
--   review-only (Legge 5 — merge stays the operator's decision); it does not
--   block merge even on a persistent RED verdict, and PR #2840 merged anyway.
--
--   `migration_base.py` / `migration_manager.py` never re-run an
--   already-applied migration's SQL body once it is recorded in
--   `_schema_versions` — so 251's on-disk text must be treated as an
--   immutable historical record of what already executed against prod
--   (cicatrix family #9, "state-schema mutation drift" / W88 extended to
--   migration files themselves: the fix for something already-applied is a
--   roll-forward migration, never an in-place edit). This migration is that
--   roll-forward: every fix below targets the LIVE, POST-251 schema state,
--   confirmed via a live read-only query against prod immediately before
--   authoring this file (`schema_migrations` showed 251 applied;
--   `visa_rule_packs`/`visa_ruleset_activations` both had 0 rows;
--   `visa_activation_executor`/`visa_ledger_owner` do not exist as roles —
--   so the flawed grant below never actually fired and there is no
--   already-armed exposure to un-arm, only a defect to close before it CAN
--   arm).
--
-- ============================================================================
-- P1-3 — SCHEMA-QUALIFY THE FOUR TRIGGER-FUNCTION DECLARATIONS
-- ============================================================================
--   251 already hardened these four functions (SET search_path = pg_catalog,
--   pg_temp; every relation reference inside each body schema-qualified to
--   `public`) but declared each via a BARE, unqualified `CREATE OR REPLACE
--   FUNCTION reject_visa_...()` — the DDL statement itself resolves which
--   existing function it replaces via the ISSUING SESSION's search_path at
--   migration-apply time, not the function's own `SET search_path` clause
--   (that only governs execution). In every environment this has run in so
--   far that search_path included `public` first, so today's live functions
--   ARE `public.reject_visa_*` — this migration only makes that explicit and
--   removes the ambient-search_path dependency for any FUTURE re-declaration
--   (a differently-configured session/role issuing a later `CREATE OR
--   REPLACE` against an unqualified name is exactly the hijack surface P1-3
--   closes). Every line of body LOGIC below is byte-identical to what 251
--   already applied — this is a declaration-qualification-only change,
--   verified line-by-line against 251's applied text while porting.
-- ============================================================================
-- F9 — TRUNCATE GUARDS (both migration-250 tables)
-- ============================================================================
--   Migration 250's `reject_visa_immutable_mutation` trigger is a row-level
--   BEFORE UPDATE/DELETE trigger — Postgres never fires row-level triggers
--   for TRUNCATE (a statement-level operation with no per-row event), so
--   `TRUNCATE public.visa_rule_packs` / `TRUNCATE public.visa_ruleset_
--   activations` bypass the append-only guarantee entirely: the whole
--   ledger/signed-pack history could be wiped in one DDL statement, with the
--   BEFORE UPDATE/DELETE trigger never seeing it and raising nothing. Fix:
--   a SEPARATE `FOR EACH STATEMENT` trigger on the `TRUNCATE` event on each
--   table, reusing the same `reject_visa_immutable_mutation()` function
--   (its body already just raises unconditionally regardless of TG_OP/
--   TG_TABLE_NAME — correct for TRUNCATE too, no new function needed).
--   `visa_ruleset_activations` FK-references `visa_rule_packs`, so a
--   `TRUNCATE ... CASCADE` on the parent is the realistic attack/mistake
--   shape this guard must also stop — the statement-level BEFORE trigger
--   fires before cascade rows are touched, so it does.
-- ============================================================================
-- P2 — activated_by / activation_reason: OPAQUE TOKEN FORMAT, NOT FREE TEXT
-- ============================================================================
--   251's own function-level validation (`visa_activate_rule_pack`) treats
--   these two caller-supplied columns as free-text audit NARRATIVE (non-
--   blank, <=200 / <=1000 chars respectively) — but `visa_ruleset_
--   activations` is an APPEND-ONLY, un-redactable ledger (250's own
--   immutability trigger forbids UPDATE/DELETE of these columns once
--   inserted). Free text invites a caller to embed a client's real name,
--   phone number, or other PII directly into a column that can never be
--   redacted or deleted afterward without breaking the hash-chain/audit
--   trail — a structural UU PDP Art. 67-68 exposure (Legge/SYMBIOSIS Law 2).
--   This migration adds a CHECK constraint on both columns restricting them
--   to an OPAQUE TOKEN shape: `^[A-Za-z0-9._:-]{1,120}$` — alphanumeric plus
--   `. _ : -`, 1-120 chars, no spaces/quotes/free prose. This is STRICTER
--   than 251's ORIGINAL function-level bounds (200/1000 chars, prose-
--   shaped) — layered, not a contradiction: this migration ALSO re-declares
--   `visa_activate_rule_pack` itself (below, after the trigger functions)
--   so the function's OWN F6(a) validation enforces this SAME regex before
--   ever reaching the INSERT — a caller routed through the sanctioned
--   function path gets a clear, typed `RAISE EXCEPTION` (empirically
--   required: verified live via the test suite that a bare table CHECK
--   alone surfaces as a raw, low-level `asyncpg.CheckViolationError`
--   instead of a friendly function-level error). The table CHECK below
--   remains the hard structural boundary for any RAW-INSERT bypass of the
--   function (defense-in-depth — Postgres enforces both regardless of
--   which path an INSERT takes).
--   Both columns were confirmed to hold ZERO rows on prod via a live
--   read-only query immediately before this migration was authored — so an
--   immediate ADD CONSTRAINT could not have failed against existing data at
--   that instant. Even so (F4, cross-family fix-round), the ADD CONSTRAINT
--   below is TOCTOU-fragile as a single statement: it full-table-scans, and
--   a bad row inserted between that read-only check and deploy would abort
--   the ENTIRE migration transaction — including the P0-1 grant fix and the
--   F9 TRUNCATE guards above it. The constraint is therefore added `NOT
--   VALID` (no scan, enforced on all new writes immediately) followed by a
--   separate `VALIDATE CONSTRAINT` (checks existing rows) — if validation
--   ever fails, only that step needs a retry; the security-critical
--   statements earlier in the same migration are unaffected.
--   (`constraint-missing-not-valid` is excluded fleet-wide in
--   `.github/workflows/migration-lint.yml` regardless, so NOT VALID here is
--   a safety choice, not a lint-suppression one.)
-- ============================================================================
-- P0-1 / P1-4 — GRANT MODEL: EXECUTE-ONLY, SELF-HEALING, FAIL-CLOSED
-- ============================================================================
--   251's role-guarded DO block granted `SELECT, INSERT ON TABLE public.
--   visa_rule_packs` to `visa_activation_executor` in ADDITION to `EXECUTE
--   ON FUNCTION ... visa_activate_rule_pack` — table-level SELECT/INSERT on
--   `visa_rule_packs` would let that role INSERT a forged, unsigned pack
--   directly (migration 250's `reject_visa_pack_payload_mismatch` trigger
--   only checks that the payload's OWN embedded fields are internally
--   self-consistent — it never verifies the Ed25519 signature itself, which
--   is a service-layer check the writer function never re-does either); the
--   whole point of routing activation through a SECURITY DEFINER function is
--   that the runtime role should need NO direct table privilege at all.
--
--   This grant never fired against prod (`visa_activation_executor` does
--   not exist as of this writing) and, because `migration_base.py` never
--   re-runs an applied migration, IT NEVER WILL — 251's DO block is
--   permanently inert now regardless of when the operator eventually
--   provisions that role. That inertness is exactly why 251's own header
--   claim ("every grant here ... activates automatically, with zero further
--   code change, the moment that role exists") is FALSE (P1-4) — a grant
--   inside an already-applied migration's DO block can never activate after
--   the fact; only a migration that has NOT yet run (this one) can still
--   fire its DO block against the role once created.
--
--   This migration's own grant block below is therefore the FIRST one that
--   will actually execute once the executor role is provisioned — but it is
--   a BEST-EFFORT self-heal, not a guarantee that activates regardless of
--   ordering: it fires ONLY if `visa_activation_executor` already exists AT
--   THE MOMENT this migration applies. `migration_manager` runs each
--   migration exactly ONCE and never re-runs an applied migration's DO
--   block — so if the role is instead provisioned AFTER this migration has
--   already applied, this block has already executed (as the no-op RAISE
--   NOTICE branch below) and will NOT re-fire to pick up the newly-created
--   role. In that ordering the P0-1 dangerous-grant fix is NOT guaranteed by
--   this migration alone — it silently delegates to the operator
--   provisioning script, which is therefore the CANONICAL arm-site for that
--   case and MUST independently encode the same EXECUTE-only model (REVOKE
--   any SELECT/INSERT the role may hold on `visa_rule_packs`, GRANT only
--   EXECUTE on `visa_activate_rule_pack`). The read-only verify-and-warn
--   block immediately following this one (F1(b), cross-family fix-round)
--   exists precisely to make a mis-armed boundary from EITHER ordering
--   VISIBLE instead of silent. Behavior of this migration's own DO block:
--     (a) role absent -> RAISE NOTICE, no-op, same convention as 251;
--     (b) role present -> REVOKE the dangerous `SELECT, INSERT ON TABLE
--         public.visa_rule_packs` grant IF PRESENT (idempotent no-op if
--         absent — defensive cleanup in case a manual grant, or an operator
--         provisioning script authored before this fix landed, already put
--         it there; see PENDING-ARMS.md note on the delivered provisioning
--         script needing the same correction), then GRANT ONLY `EXECUTE ON
--         FUNCTION public.visa_activate_rule_pack(uuid, text, text)`.
--   Grant failure while the role IS present now RAISES EXCEPTION (was
--   `RAISE WARNING` in 251) — a half-armed boundary (role exists, function
--   EXECUTE grant silently failed, only the REVOKE succeeded) is worse than
--   a hard-failed migration; a WARNING here would ship a broken boundary
--   silently exactly as it already once did (P1-4's second half).
--
--   Function OWNERSHIP (P0-2 — SECURITY DEFINER runs as the function's
--   OWNER, `pg_proc.proowner`, independent of who owns the tables it
--   touches) is a superuser-only operation (`ALTER FUNCTION ... OWNER TO`)
--   this non-superuser migration role cannot perform — it remains the
--   operator provisioning script's job (`operator[secret]`, see
--   `.claude/skills/modus/PENDING-ARMS.md`), same as ownership transfer.
--   That provisioning script was delivered to Zero on 2026-07-19 BEFORE
--   this FIX-ROUND — it must be reviewed against these same findings before
--   use, since it may itself encode the flawed table-grant model this
--   migration corrects.
--
-- ============================================================================
-- Firebreak (unchanged from 251): SHADOW-only. No HTTP surface consults this
--   writer yet (STEP-6c). ENFORCE flip = Zero (Legge 5), and per 251's own
--   header, ENFORCE must not ship before the operator provisioning
--   (ownership transfer + role creation) has run.
-- ============================================================================
--
-- NOTE: `-- === ROLLBACK ===` marker is mandatory (migration_base.py:29) for
--   migrations > 111.

-- -- P1-3: re-declare the four migration-250/251 trigger functions,
-- schema-qualified. Bodies byte-identical to 251's applied text; only the
-- CREATE OR REPLACE target name gains an explicit `public.` prefix.

CREATE OR REPLACE FUNCTION public.reject_visa_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE OR REPLACE FUNCTION public.reject_visa_pack_payload_mismatch()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF NOT (NEW.payload ? 'rule_pack_id')
       OR NEW.id IS DISTINCT FROM (NEW.payload->>'rule_pack_id')::uuid THEN
        RAISE EXCEPTION 'visa_rule_packs.id % does not match signed payload rule_pack_id % (key must be present)',
            NEW.id, NEW.payload->>'rule_pack_id';
    END IF;
    IF NOT (NEW.payload ? 'environment')
       OR NEW.environment IS DISTINCT FROM NEW.payload->>'environment' THEN
        RAISE EXCEPTION 'visa_rule_packs.environment % does not match signed payload environment % (key must be present)',
            NEW.environment, NEW.payload->>'environment';
    END IF;
    IF NOT (NEW.payload ? 'sequence')
       OR jsonb_typeof(NEW.payload->'sequence') IS DISTINCT FROM 'number'
       OR NEW.sequence IS DISTINCT FROM (NEW.payload->>'sequence')::bigint THEN
        RAISE EXCEPTION 'visa_rule_packs.sequence % does not match signed payload sequence % (must be a present JSON number)',
            NEW.sequence, NEW.payload->>'sequence';
    END IF;
    IF NOT (NEW.payload ? 'previous_payload_sha256')
       OR encode(NEW.previous_payload_sha256, 'hex') IS DISTINCT FROM NEW.payload->>'previous_payload_sha256' THEN
        RAISE EXCEPTION 'visa_rule_packs.previous_payload_sha256 does not match signed payload (key must be present, may be null)';
    END IF;
    IF jsonb_typeof(NEW.payload->'valid_period') IS DISTINCT FROM 'object'
       OR NOT (NEW.payload->'valid_period' ? 'from')
       OR NOT (NEW.payload->'valid_period' ? 'to')
       OR NEW.legal_period IS DISTINCT FROM tstzrange(
              (NEW.payload->'valid_period'->>'from')::timestamptz,
              (NEW.payload->'valid_period'->>'to')::timestamptz,
              '[)') THEN
        RAISE EXCEPTION 'visa_rule_packs.legal_period % does not match signed payload valid_period % (from+to keys must be present)',
            NEW.legal_period, NEW.payload->'valid_period';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.reject_visa_activation_insert()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    pack RECORD;
    head RECORD;
BEGIN
    NEW.activated_by_principal := session_user;

    PERFORM pg_advisory_xact_lock(hashtext(NEW.environment || NEW.jurisdiction || NEW.decision_domain));

    SELECT environment, jurisdiction, decision_domain, legal_period, sequence, previous_payload_sha256
        INTO pack
        FROM public.visa_rule_packs
        WHERE id = NEW.rule_pack_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'visa activation references unknown rule_pack_id %', NEW.rule_pack_id;
    END IF;
    IF NEW.environment <> pack.environment
       OR NEW.jurisdiction <> pack.jurisdiction
       OR NEW.decision_domain <> pack.decision_domain
       OR NEW.legal_period IS DISTINCT FROM pack.legal_period THEN
        RAISE EXCEPTION 'visa activation scope/legal_period must equal the referenced pack (pack env=% jur=% domain=% legal=%)',
            pack.environment, pack.jurisdiction, pack.decision_domain, pack.legal_period;
    END IF;

    SELECT p.sequence AS seq, p.payload_sha256 AS hash
        INTO head
        FROM public.visa_ruleset_activations a
        JOIN public.visa_rule_packs p ON p.id = a.rule_pack_id
        WHERE a.environment = NEW.environment
          AND a.jurisdiction = NEW.jurisdiction
          AND a.decision_domain = NEW.decision_domain
          AND a.id <> NEW.id
        ORDER BY p.sequence DESC
        LIMIT 1;

    IF head IS NULL THEN
        IF pack.previous_payload_sha256 IS NOT NULL THEN
            RAISE EXCEPTION 'visa bootstrap activation must reference a pack with null previous_payload_sha256';
        END IF;
    ELSE
        IF pack.sequence <= head.seq THEN
            RAISE EXCEPTION 'visa activation rollback rejected: pack sequence % <= prior activated sequence %',
                pack.sequence, head.seq;
        END IF;
        IF pack.previous_payload_sha256 IS DISTINCT FROM head.hash THEN
            RAISE EXCEPTION 'visa activation hash chain broken: pack previous_payload_sha256 does not match the current head payload_sha256';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.reject_visa_activation_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'visa_ruleset_activations is append-only (DELETE rejected)';
    END IF;
    IF OLD.id IS DISTINCT FROM NEW.id
       OR OLD.rule_pack_id IS DISTINCT FROM NEW.rule_pack_id
       OR OLD.environment IS DISTINCT FROM NEW.environment
       OR OLD.jurisdiction IS DISTINCT FROM NEW.jurisdiction
       OR OLD.decision_domain IS DISTINCT FROM NEW.decision_domain
       OR OLD.legal_period IS DISTINCT FROM NEW.legal_period
       OR OLD.activated_by IS DISTINCT FROM NEW.activated_by
       OR OLD.activation_reason IS DISTINCT FROM NEW.activation_reason
       OR OLD.activated_by_principal IS DISTINCT FROM NEW.activated_by_principal
       OR OLD.created_at IS DISTINCT FROM NEW.created_at
       OR lower(OLD.system_period) IS DISTINCT FROM lower(NEW.system_period) THEN
        RAISE EXCEPTION 'visa_ruleset_activations: only closing an open system_period may be updated';
    END IF;
    IF upper(OLD.system_period) IS NOT NULL THEN
        RAISE EXCEPTION 'visa_ruleset_activations: system_period already closed, cannot re-close';
    END IF;
    IF upper(NEW.system_period) IS NULL THEN
        RAISE EXCEPTION 'visa_ruleset_activations: close must set a finite system_period upper bound';
    END IF;
    RETURN NEW;
END;
$$;

-- -- P2 (function-level refinement, discovered empirically while running
-- the visa_engine test suite against a throwaway DB immediately after
-- authoring the table CHECK constraints below): a bare table CHECK is
-- necessary but not sufficient on its own -- a caller routed through the
-- writer function that supplies a free-sentence/oversized/blank value
-- would previously get a raw, low-level asyncpg CheckViolationError
-- instead of the function's own friendly, typed RAISE EXCEPTION. Re-declare
-- visa_activate_rule_pack (CREATE OR REPLACE preserves its OID/ACL/grants
-- -- REVOKE ALL FROM PUBLIC and any future EXECUTE grant survive this
-- unchanged) with its F6(a) validation swapped from "non-blank and
-- <=200/<=1000 chars" (251's loose, prose-shaped bound) to the SAME opaque
-- token regex the table CHECK enforces -- the function now rejects with a
-- clear message BEFORE ever reaching the INSERT; the table CHECK remains
-- as defense-in-depth for any raw-INSERT bypass of this function. Every
-- OTHER line of logic (scope resolution, advisory lock, single clock read,
-- partial-overlap guard, close-then-insert) is byte-identical to 251's
-- applied body.
CREATE OR REPLACE FUNCTION public.visa_activate_rule_pack(
    p_rule_pack_id      uuid,
    p_activated_by      text,
    p_activation_reason text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_env      text;
    v_jur      text;
    v_domain   text;
    v_legal    tstzrange;
    v_now      timestamptz;
    v_new_id   uuid;
    v_orphan   int;
BEGIN
    -- P2: opaque-token-format validation (letters/digits/./_/:/- only,
    -- 1-120 chars) -- rejects blank, oversized, AND free-sentence shapes
    -- with one regex per column, before anything else runs.
    IF p_activated_by IS NULL OR NOT (p_activated_by ~ '^[A-Za-z0-9._:-]{1,120}$') THEN
        RAISE EXCEPTION 'visa_activate_rule_pack: activated_by must be an opaque token (letters/digits/./_/:/- only, 1-120 chars) -- not free text (got % chars)',
            char_length(p_activated_by);
    END IF;
    IF p_activation_reason IS NULL OR NOT (p_activation_reason ~ '^[A-Za-z0-9._:-]{1,120}$') THEN
        RAISE EXCEPTION 'visa_activate_rule_pack: activation_reason must be an opaque reason-code (letters/digits/./_/:/- only, 1-120 chars) -- not free text (got % chars)',
            char_length(p_activation_reason);
    END IF;

    -- 1. Resolve scope + legal_period FROM THE PACK (never from caller args --
    --    prevents scope spoofing).
    SELECT environment, jurisdiction, decision_domain, legal_period
        INTO v_env, v_jur, v_domain, v_legal
        FROM public.visa_rule_packs
        WHERE id = p_rule_pack_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'visa_activate_rule_pack: unknown rule_pack_id %', p_rule_pack_id;
    END IF;

    -- 2. SAME advisory lock key as the insert-guard trigger -- serialize
    --    against any concurrent activation (raw or via this function) for
    --    this triple.
    PERFORM pg_advisory_xact_lock(hashtext(v_env || v_jur || v_domain));

    -- 3. ONE clock read for the whole supersession (close + insert share
    --    this instant).
    v_now := clock_timestamp();

    -- 4. Partial-overlap guard (250's PR4/STEP-6 BOUNDARY note, round-4
    --    finding 1): a still-OPEN prior activation whose legal_period
    --    OVERLAPS the new pack's but is NOT fully contained by it would be
    --    orphaned by supersession -- reject. (F5: a legitimate narrowing
    --    correction is a separate, not-yet-built operation -- see 251's
    --    header.)
    SELECT count(*) INTO v_orphan
        FROM public.visa_ruleset_activations a
        WHERE a.environment = v_env AND a.jurisdiction = v_jur AND a.decision_domain = v_domain
          AND upper(a.system_period) IS NULL
          AND a.legal_period && v_legal
          AND NOT (v_legal @> a.legal_period);
    IF v_orphan > 0 THEN
        RAISE EXCEPTION 'visa_activate_rule_pack: partial legal-period overlap would orphan % prior activation(s); refusing (new legal=% must fully cover any overlapping open prior)',
            v_orphan, v_legal;
    END IF;

    -- 5. Close every still-open prior activation for the triple whose
    --    legal_period is covered by the new one, at v_now (goes through
    --    the mutation-guard trigger's close-open carve-out).
    UPDATE public.visa_ruleset_activations a
        SET system_period = tstzrange(lower(a.system_period), v_now, '[)')
        WHERE a.environment = v_env AND a.jurisdiction = v_jur AND a.decision_domain = v_domain
          AND upper(a.system_period) IS NULL
          AND v_legal @> a.legal_period;

    -- 6. Insert the new activation open at v_now (goes through the
    --    insert-guard trigger: scope/legal binding +
    --    bootstrap/sequence-monotonicity/hash-chain +
    --    activated_by_principal stamping).
    INSERT INTO public.visa_ruleset_activations
        (rule_pack_id, environment, jurisdiction, decision_domain, legal_period, system_period,
         activated_by, activation_reason)
        VALUES (p_rule_pack_id, v_env, v_jur, v_domain, v_legal,
                tstzrange(v_now, NULL, '[)'), p_activated_by, p_activation_reason)
        RETURNING id INTO v_new_id;

    RETURN v_new_id;
END;
$$;

-- -- F9: TRUNCATE guards. Row-level triggers never fire for TRUNCATE; these
-- are separate FOR EACH STATEMENT triggers on the TRUNCATE event, reusing
-- reject_visa_immutable_mutation() (its body raises unconditionally,
-- correct for TRUNCATE regardless of TG_OP/TG_TABLE_NAME).
CREATE TRIGGER visa_rule_packs_no_wipe
    BEFORE TRUNCATE ON public.visa_rule_packs
    FOR EACH STATEMENT
    EXECUTE FUNCTION public.reject_visa_immutable_mutation();

CREATE TRIGGER visa_ruleset_activations_no_wipe
    BEFORE TRUNCATE ON public.visa_ruleset_activations
    FOR EACH STATEMENT
    EXECUTE FUNCTION public.reject_visa_immutable_mutation();

-- -- P2/F4 (cross-family fix-round): opaque-token-format CHECK constraints,
-- added NOT VALID + separately VALIDATED (see header rationale above) so a
-- hypothetical bad row cannot abort the whole migration transaction.
ALTER TABLE public.visa_ruleset_activations
    ADD CONSTRAINT visa_ruleset_activations_activated_by_token_format
    CHECK (activated_by ~ '^[A-Za-z0-9._:-]{1,120}$') NOT VALID;
ALTER TABLE public.visa_ruleset_activations
    VALIDATE CONSTRAINT visa_ruleset_activations_activated_by_token_format;

ALTER TABLE public.visa_ruleset_activations
    ADD CONSTRAINT visa_ruleset_activations_activation_reason_token_format
    CHECK (activation_reason ~ '^[A-Za-z0-9._:-]{1,120}$') NOT VALID;
ALTER TABLE public.visa_ruleset_activations
    VALIDATE CONSTRAINT visa_ruleset_activations_activation_reason_token_format;

-- -- P0-1/P1-4: the FIRST grant block that can actually activate once the
-- operator provisions visa_activation_executor (251's own grant block is
-- permanently inert -- see header). Self-healing (revokes the dangerous
-- table grant if present from any other path) and fail-closed (RAISE
-- EXCEPTION, not WARNING, on a present-role grant failure).
DO $grant_block_253$
DECLARE
    executor_role constant text := 'visa_activation_executor';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = executor_role) THEN
        RAISE NOTICE 'visa_activation_writer hardening (253): role % absent -- skipping grants (operator provisioning not yet run)',
            executor_role;
        RETURN;
    END IF;

    -- Defensive cleanup: revoke the dangerous direct-table grant if any
    -- path (manual grant, or a provisioning script authored before this
    -- fix) already put it there. Idempotent no-op if never granted.
    EXECUTE format('REVOKE SELECT, INSERT ON TABLE public.visa_rule_packs FROM %I', executor_role);

    BEGIN
        EXECUTE format('GRANT EXECUTE ON FUNCTION public.visa_activate_rule_pack(uuid, text, text) TO %I', executor_role);
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE EXCEPTION 'visa_activation_writer hardening (253): manual grant required -- GRANT EXECUTE ON FUNCTION public.visa_activate_rule_pack(uuid, text, text) TO %; refusing to leave the boundary half-armed',
                executor_role;
    END;
END;
$grant_block_253$;

-- -- F1(b) (cross-family fix-round): READ-ONLY verify-and-warn. Makes a
-- mis-armed boundary VISIBLE instead of silent, regardless of WHICH path
-- armed (or failed to arm) the role -- this migration's own grant block
-- above, an operator provisioning script, or a manual grant. Never mutates
-- privileges itself (the grant block above is the only privilege-mutating
-- logic in this migration); guarded so an absent role/table/function never
-- aborts the migration -- it degrades to "nothing to verify yet".
DO $verify_boundary_253$
DECLARE
    executor_role constant text := 'visa_activation_executor';
    v_has_select_or_insert boolean := false;
    v_has_execute boolean := false;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = executor_role) THEN
        RETURN;
    END IF;

    IF to_regclass('public.visa_rule_packs') IS NOT NULL THEN
        BEGIN
            v_has_select_or_insert :=
                has_table_privilege(executor_role, 'public.visa_rule_packs', 'SELECT')
                OR has_table_privilege(executor_role, 'public.visa_rule_packs', 'INSERT');
        EXCEPTION
            WHEN undefined_table OR undefined_object THEN
                v_has_select_or_insert := false;
        END;
    END IF;

    IF v_has_select_or_insert THEN
        RAISE WARNING 'visa_activation_writer hardening (253): % still holds direct SELECT/INSERT on public.visa_rule_packs -- dangerous table grant present, boundary MIS-ARMED',
            executor_role;
    END IF;

    IF to_regprocedure('public.visa_activate_rule_pack(uuid, text, text)') IS NOT NULL THEN
        BEGIN
            v_has_execute :=
                has_function_privilege(executor_role, 'public.visa_activate_rule_pack(uuid, text, text)', 'EXECUTE');
        EXCEPTION
            WHEN undefined_function OR undefined_object THEN
                v_has_execute := false;
        END;
    END IF;

    IF NOT v_has_execute THEN
        RAISE WARNING 'visa_activation_writer hardening (253): % is missing EXECUTE on public.visa_activate_rule_pack(uuid, text, text) -- boundary MIS-ARMED (role can neither write directly nor via the sanctioned function)',
            executor_role;
    END IF;
END;
$verify_boundary_253$;

-- === ROLLBACK ===
DO $revoke_block_253$
DECLARE
    executor_role constant text := 'visa_activation_executor';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = executor_role) THEN
        RETURN;
    END IF;
    EXECUTE format('REVOKE EXECUTE ON FUNCTION public.visa_activate_rule_pack(uuid, text, text) FROM %I', executor_role);
END;
$revoke_block_253$;

ALTER TABLE IF EXISTS public.visa_ruleset_activations DROP CONSTRAINT IF EXISTS visa_ruleset_activations_activation_reason_token_format;
ALTER TABLE IF EXISTS public.visa_ruleset_activations DROP CONSTRAINT IF EXISTS visa_ruleset_activations_activated_by_token_format;

DROP TRIGGER IF EXISTS visa_ruleset_activations_no_wipe ON public.visa_ruleset_activations;
DROP TRIGGER IF EXISTS visa_rule_packs_no_wipe ON public.visa_rule_packs;

-- Restore visa_activate_rule_pack to its EXACT migration-251-applied body
-- (loose "non-blank and <=200/<=1000 chars" F6(a) validation, no opaque-
-- token regex) -- this is what "rollback of the P2 function-level
-- refinement" means: reverting to what 251 alone left live. CREATE OR
-- REPLACE (not DROP) because 251 itself is not being rolled back here --
-- only 253's own contribution is undone, leaving 251's function intact.
CREATE OR REPLACE FUNCTION public.visa_activate_rule_pack(
    p_rule_pack_id      uuid,
    p_activated_by      text,
    p_activation_reason text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_env      text;
    v_jur      text;
    v_domain   text;
    v_legal    tstzrange;
    v_now      timestamptz;
    v_new_id   uuid;
    v_orphan   int;
BEGIN
    IF btrim(p_activated_by) = '' OR char_length(p_activated_by) > 200 THEN
        RAISE EXCEPTION 'visa_activate_rule_pack: activated_by must be non-blank and <= 200 chars (got % chars)',
            char_length(p_activated_by);
    END IF;
    IF btrim(p_activation_reason) = '' OR char_length(p_activation_reason) > 1000 THEN
        RAISE EXCEPTION 'visa_activate_rule_pack: activation_reason must be non-blank and <= 1000 chars (got % chars)',
            char_length(p_activation_reason);
    END IF;

    SELECT environment, jurisdiction, decision_domain, legal_period
        INTO v_env, v_jur, v_domain, v_legal
        FROM public.visa_rule_packs
        WHERE id = p_rule_pack_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'visa_activate_rule_pack: unknown rule_pack_id %', p_rule_pack_id;
    END IF;

    PERFORM pg_advisory_xact_lock(hashtext(v_env || v_jur || v_domain));

    v_now := clock_timestamp();

    SELECT count(*) INTO v_orphan
        FROM public.visa_ruleset_activations a
        WHERE a.environment = v_env AND a.jurisdiction = v_jur AND a.decision_domain = v_domain
          AND upper(a.system_period) IS NULL
          AND a.legal_period && v_legal
          AND NOT (v_legal @> a.legal_period);
    IF v_orphan > 0 THEN
        RAISE EXCEPTION 'visa_activate_rule_pack: partial legal-period overlap would orphan % prior activation(s); refusing (new legal=% must fully cover any overlapping open prior)',
            v_orphan, v_legal;
    END IF;

    UPDATE public.visa_ruleset_activations a
        SET system_period = tstzrange(lower(a.system_period), v_now, '[)')
        WHERE a.environment = v_env AND a.jurisdiction = v_jur AND a.decision_domain = v_domain
          AND upper(a.system_period) IS NULL
          AND v_legal @> a.legal_period;

    INSERT INTO public.visa_ruleset_activations
        (rule_pack_id, environment, jurisdiction, decision_domain, legal_period, system_period,
         activated_by, activation_reason)
        VALUES (p_rule_pack_id, v_env, v_jur, v_domain, v_legal,
                tstzrange(v_now, NULL, '[)'), p_activated_by, p_activation_reason)
        RETURNING id INTO v_new_id;

    RETURN v_new_id;
END;
$$;

-- Restore the four trigger functions to their EXACT migration-251-applied
-- BODIES (logic byte-identical to 251). The declaration NAME, however,
-- stays schema-qualified (`public.`) even on rollback (F2, cross-family
-- fix-round) -- the same ambient-search_path hijack surface the forward
-- P1-3 fix closes applies equally to a rollback-issued CREATE OR REPLACE,
-- so rollback intentionally does NOT revert to 251's original bare/
-- unqualified declaration name.
CREATE OR REPLACE FUNCTION public.reject_visa_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE OR REPLACE FUNCTION public.reject_visa_pack_payload_mismatch()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF NOT (NEW.payload ? 'rule_pack_id')
       OR NEW.id IS DISTINCT FROM (NEW.payload->>'rule_pack_id')::uuid THEN
        RAISE EXCEPTION 'visa_rule_packs.id % does not match signed payload rule_pack_id % (key must be present)',
            NEW.id, NEW.payload->>'rule_pack_id';
    END IF;
    IF NOT (NEW.payload ? 'environment')
       OR NEW.environment IS DISTINCT FROM NEW.payload->>'environment' THEN
        RAISE EXCEPTION 'visa_rule_packs.environment % does not match signed payload environment % (key must be present)',
            NEW.environment, NEW.payload->>'environment';
    END IF;
    IF NOT (NEW.payload ? 'sequence')
       OR jsonb_typeof(NEW.payload->'sequence') IS DISTINCT FROM 'number'
       OR NEW.sequence IS DISTINCT FROM (NEW.payload->>'sequence')::bigint THEN
        RAISE EXCEPTION 'visa_rule_packs.sequence % does not match signed payload sequence % (must be a present JSON number)',
            NEW.sequence, NEW.payload->>'sequence';
    END IF;
    IF NOT (NEW.payload ? 'previous_payload_sha256')
       OR encode(NEW.previous_payload_sha256, 'hex') IS DISTINCT FROM NEW.payload->>'previous_payload_sha256' THEN
        RAISE EXCEPTION 'visa_rule_packs.previous_payload_sha256 does not match signed payload (key must be present, may be null)';
    END IF;
    IF jsonb_typeof(NEW.payload->'valid_period') IS DISTINCT FROM 'object'
       OR NOT (NEW.payload->'valid_period' ? 'from')
       OR NOT (NEW.payload->'valid_period' ? 'to')
       OR NEW.legal_period IS DISTINCT FROM tstzrange(
              (NEW.payload->'valid_period'->>'from')::timestamptz,
              (NEW.payload->'valid_period'->>'to')::timestamptz,
              '[)') THEN
        RAISE EXCEPTION 'visa_rule_packs.legal_period % does not match signed payload valid_period % (from+to keys must be present)',
            NEW.legal_period, NEW.payload->'valid_period';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.reject_visa_activation_insert()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    pack RECORD;
    head RECORD;
BEGIN
    NEW.activated_by_principal := session_user;

    PERFORM pg_advisory_xact_lock(hashtext(NEW.environment || NEW.jurisdiction || NEW.decision_domain));

    SELECT environment, jurisdiction, decision_domain, legal_period, sequence, previous_payload_sha256
        INTO pack
        FROM public.visa_rule_packs
        WHERE id = NEW.rule_pack_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'visa activation references unknown rule_pack_id %', NEW.rule_pack_id;
    END IF;
    IF NEW.environment <> pack.environment
       OR NEW.jurisdiction <> pack.jurisdiction
       OR NEW.decision_domain <> pack.decision_domain
       OR NEW.legal_period IS DISTINCT FROM pack.legal_period THEN
        RAISE EXCEPTION 'visa activation scope/legal_period must equal the referenced pack (pack env=% jur=% domain=% legal=%)',
            pack.environment, pack.jurisdiction, pack.decision_domain, pack.legal_period;
    END IF;

    SELECT p.sequence AS seq, p.payload_sha256 AS hash
        INTO head
        FROM public.visa_ruleset_activations a
        JOIN public.visa_rule_packs p ON p.id = a.rule_pack_id
        WHERE a.environment = NEW.environment
          AND a.jurisdiction = NEW.jurisdiction
          AND a.decision_domain = NEW.decision_domain
          AND a.id <> NEW.id
        ORDER BY p.sequence DESC
        LIMIT 1;

    IF head IS NULL THEN
        IF pack.previous_payload_sha256 IS NOT NULL THEN
            RAISE EXCEPTION 'visa bootstrap activation must reference a pack with null previous_payload_sha256';
        END IF;
    ELSE
        IF pack.sequence <= head.seq THEN
            RAISE EXCEPTION 'visa activation rollback rejected: pack sequence % <= prior activated sequence %',
                pack.sequence, head.seq;
        END IF;
        IF pack.previous_payload_sha256 IS DISTINCT FROM head.hash THEN
            RAISE EXCEPTION 'visa activation hash chain broken: pack previous_payload_sha256 does not match the current head payload_sha256';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.reject_visa_activation_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'visa_ruleset_activations is append-only (DELETE rejected)';
    END IF;
    IF OLD.id IS DISTINCT FROM NEW.id
       OR OLD.rule_pack_id IS DISTINCT FROM NEW.rule_pack_id
       OR OLD.environment IS DISTINCT FROM NEW.environment
       OR OLD.jurisdiction IS DISTINCT FROM NEW.jurisdiction
       OR OLD.decision_domain IS DISTINCT FROM NEW.decision_domain
       OR OLD.legal_period IS DISTINCT FROM NEW.legal_period
       OR OLD.activated_by IS DISTINCT FROM NEW.activated_by
       OR OLD.activation_reason IS DISTINCT FROM NEW.activation_reason
       OR OLD.activated_by_principal IS DISTINCT FROM NEW.activated_by_principal
       OR OLD.created_at IS DISTINCT FROM NEW.created_at
       OR lower(OLD.system_period) IS DISTINCT FROM lower(NEW.system_period) THEN
        RAISE EXCEPTION 'visa_ruleset_activations: only closing an open system_period may be updated';
    END IF;
    IF upper(OLD.system_period) IS NOT NULL THEN
        RAISE EXCEPTION 'visa_ruleset_activations: system_period already closed, cannot re-close';
    END IF;
    IF upper(NEW.system_period) IS NULL THEN
        RAISE EXCEPTION 'visa_ruleset_activations: close must set a finite system_period upper bound';
    END IF;
    RETURN NEW;
END;
$$;
