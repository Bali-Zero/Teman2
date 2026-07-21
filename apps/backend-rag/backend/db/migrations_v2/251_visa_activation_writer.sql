-- Migration 251: Visa Oracle engine — activation WRITER
-- (STEP-6a: `visa_activate_rule_pack()` SECURITY DEFINER + boundary scaffold)
--
-- Purpose:
--   Migration 250 shipped the bitemporal READ substrate (visa_rule_packs +
--   visa_ruleset_activations) plus the caller-independent structural triggers
--   (reject_visa_immutable_mutation / reject_visa_pack_payload_mismatch /
--   reject_visa_activation_insert / reject_visa_activation_mutation) — but NO
--   activation writer: a raw-SQL INSERT/UPDATE into visa_ruleset_activations
--   can still backdate system_period or slip a partial legal-period overlap,
--   because close-then-insert atomicity + a single shared clock cannot be
--   guaranteed by a Python method plus BEFORE-triggers alone (250's own
--   "PR4/STEP-6 BOUNDARY" note, round-4 finding 1).
--
--   This migration closes that gap: a function performs the WHOLE
--   supersession — partial-overlap reject, close every covered still-open
--   prior, insert the new activation — in ONE transaction, under ONE
--   `clock_timestamp()` read, under the SAME advisory lock key
--   `reject_visa_activation_insert` already takes.
--
-- Source: research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
--   concretization.md section 5, STEP-6a design doc
--   (tasks/step6a_design.md, 2026-07-19), as AMENDED by a cross-family
--   design red-team (Codex sol xhigh, same day) — FIX-FIRST verdict, 7
--   findings (F1-F7) below. The design doc's function body is implemented
--   verbatim in intent; every deviation from it is one of these findings.
--
-- ============================================================================
-- F1+F2 (P0) — ROLE MODEL IS AN OPTION-1 SCAFFOLD, NOT YET A BOUNDARY
-- ============================================================================
--   The design doc's original GRANT model targeted `backend_rag_v2`: REVOKE
--   INSERT/UPDATE/DELETE on visa_ruleset_activations FROM it, GRANT only
--   EXECUTE on the function. The red-team found this INERT in production
--   TODAY: `backend_rag_v2` is BOTH the table OWNER and the serving role in
--   prod (the migration runner itself runs as that role) — a REVOKE from a
--   role against objects it OWNS is a no-op (owners always retain implicit
--   DML rights, REVOKE cannot touch them), so the "boundary" would silently
--   not exist, and worse, could be read as a security guarantee that isn't
--   there (a false sense of closure is worse than a documented gap).
--
--   The REAL boundary requires an ownership move FIRST: two NOLOGIN roles
--   (`visa_ledger_owner` — becomes the new table owner; `visa_activation_
--   executor` — the role the FastAPI runtime authenticates as for this one
--   surface) provisioned and the tables' ownership transferred to
--   `visa_ledger_owner` BEFORE any REVOKE-from-serving-role has teeth. That
--   ownership move is a superuser operation — it cannot run inside a
--   migration executed BY the serving role itself (a role cannot revoke its
--   own owner-implicit privileges, nor reassign ownership away from itself
--   without already being superuser). Per Zero's decision (2026-07-19), the
--   provisioning script for this move has ALREADY been delivered to him
--   directly (operator[superuser-SQL] — see the PENDING-ARMS.md line this PR
--   also adds) — it is explicitly OUT OF SCOPE for this migration, which a
--   non-superuser runtime role applies.
--
--   Consequently, THIS migration:
--     (a) does NOT grant `backend_rag_v2` anything new, and does NOT attempt
--         any REVOKE against it — that REVOKE only has teeth once ownership
--         has moved off it, which is the operator script's job, not this
--         file's;
--     (b) grants ONLY to `visa_activation_executor` (role-guarded — the role
--         does not exist yet in ANY environment, including a fresh CI clone,
--         until the operator provisioning runs — so every grant here is a
--         no-op today and activates automatically, with zero further code
--         change, the moment that role exists);
--     (c) REVOKEs EXECUTE on the function from PUBLIC (Postgres grants
--         EXECUTE to PUBLIC by default at CREATE FUNCTION time — this alone
--         is NOT deferred, it costs nothing and closes an unrelated,
--         unconditional exposure regardless of the role-provisioning state).
--
--   >>> BOUNDARY ARMS VIA OPERATOR ROLE-SQL (ENFORCE-prereq): until the
--   >>> operator provisioning runs (visa_ledger_owner + visa_activation_
--   >>> executor created, table ownership moved, REVOKE issued against the
--   >>> now-non-owning backend_rag_v2), this writer is FUNCTIONALLY CORRECT
--   >>> (the supersession logic is complete and correct) but is NOT YET a
--   >>> security boundary — backend_rag_v2 can still, today, write
--   >>> visa_ruleset_activations directly, bypassing this function, exactly
--   >>> as it always could since migration 250. ENFORCE (STEP-6c wiring a
--   >>> real HTTP surface to this writer) must not ship before that
--   >>> provisioning has run — this is a hard prerequisite, not a nice-to-
--   >>> have.
--
-- ============================================================================
-- F3 (P0) — search_path MUST NOT LEAK INTO NESTED TRIGGERS
-- ============================================================================
--   The writer function runs with `SET search_path = pg_catalog, pg_temp`
--   (privilege-escalation hardening — an attacker-writable schema earlier in
--   a hijacked search_path can never shadow a builtin). The function's own
--   write statements FIRE migration 250's BEFORE triggers (the insert-guard
--   and the mutation-guard) as NESTED calls within that same execution — and
--   those trigger functions, as written in 250, declare NO `SET search_path`
--   of their own and reference the two visa tables UNQUALIFIED. A function
--   with no explicit `SET search_path` inherits whatever search_path is
--   ACTIVE at the moment it is invoked — which, nested inside this SECURITY
--   DEFINER function, is `pg_catalog, pg_temp`, NOT the caller's session
--   search_path. `public` is deliberately excluded from that path, so every
--   unqualified table reference inside those trigger bodies would fail to
--   resolve at all ("relation ... does not exist") the moment they run
--   nested inside this function — silently breaking every activation ever
--   issued through the writer.
--
--   Fix: all four migration-250 trigger functions are `CREATE OR REPLACE`d
--   here with (a) their own `SET search_path = pg_catalog, pg_temp` (so they
--   behave identically regardless of caller context — the same hardening
--   this function gets, and closes the same class of search-path-hijack
--   risk for triggers fired by a RAW insert/update too, not only nested
--   ones) and (b) every relation reference schema-qualified to the public
--   schema (required BECAUSE `public` is no longer in scope). Every OTHER
--   line of logic is byte-identical to 250 — this is a hardening-only
--   rewrite, verified line-by-line against 250 while porting — WITH ONE
--   DELIBERATE, DOCUMENTED EXTENSION per trigger (F6 below: the insert
--   trigger stamps `activated_by_principal`; the mutation trigger's own
--   immutability OR-chain is extended to cover that new column).
--
-- ============================================================================
-- F4 (P1) — SCHEMA-QUALIFY EVERYTHING
-- ============================================================================
--   The writer function, and every GRANT/REVOKE/DROP below, are all by
--   fully-qualified name + full signature, and the repository call is
--   `SELECT public.visa_activate_rule_pack($1, $2, $3)` (repository.py).
--   Belt-and-suspenders against the exact class of ambiguity F3 above
--   depends on not existing.
--
-- ============================================================================
-- F6 (P1) — AUDIT FORGERY: activated_by/activation_reason are caller-free-
--   text; nothing stops a caller from claiming to be someone they are not
-- ============================================================================
--   (a) The writer function validates its two free-text arguments up front:
--       activated_by must be non-blank (btrim(...) <> '') and <= 200 chars;
--       activation_reason non-blank and <= 1000 chars; else RAISE. These
--       stay human-readable audit NARRATIVE — not an identity guarantee (see
--       (b)).
--   (b) The actual, UNFORGEABLE identity is a NEW column on the ledger:
--       activated_by_principal text NOT NULL (ADD COLUMN below — safe as a
--       bare NOT NULL with no DEFAULT because migration 250 is NOT yet
--       deployed to prod and lands in the SAME release as this one; every
--       test DB rebuilds the table from scratch, so it is always empty at
--       ALTER time — there is no pre-existing row this ALTER could ever
--       violate). The replaced insert-guard trigger sets this column to
--       session_user UNCONDITIONALLY, first thing, before anything else —
--       this OVERWRITES any value the INSERT statement (raw or via this
--       function) may or may not have supplied, so the column can never be
--       spoofed at insert time. A matching non-blank CHECK constraint is
--       added on the column too — defense-in-depth; session_user is never
--       blank in practice, but the invariant is now structural, not just
--       assumed.
--
--   IMPLEMENTER-ADDED CLOSURE (documented, not in the red-team's literal F6
--   text, but required by F6's own stated goal): if the stamped column were
--   left out of the mutation-guard trigger's immutability OR-chain, a
--   subsequent raw UPDATE could silently overwrite activated_by_principal
--   post-insert (the exact "enumerated OR-chain misses a new column" shape
--   250's own round-2 finding 5 fixed for the primary key column — cicatrix
--   family #3, guard-under-match) — defeating the entire point of an
--   "unforgeable" audit stamp. The mutation-guard's OR-chain below therefore
--   ALSO enumerates the new column, alongside the F3 search_path/
--   qualification hardening every trigger gets.
--
-- ============================================================================
-- F5 (P1) — DEFERRED: no replace_activation_set in this migration
-- ============================================================================
--   The partial-legal-overlap REJECT is deliberately conservative: a
--   legitimate future-narrowing correction (re-issuing a pack whose
--   legal_period narrows an existing open activation rather than fully
--   covering it) is a DIFFERENT operation from supersession and needs its
--   own atomic "replace one activation's legal_period in place" writer — NOT
--   a silent close-or-orphan decision inside this function. That writer
--   (`replace_activation_set` or equivalent) is an ENFORCE-prereq FOLLOW-UP,
--   not built here; the conservative partial-overlap reject stands as this
--   migration's behavior until it exists.
--
-- ============================================================================
-- F7 (P1) — no fetchval_safe on BaseRepository
-- ============================================================================
--   repository.py's activate_rule_pack uses fetchrow_safe (SELECT
--   public.visa_activate_rule_pack($1,$2,$3) AS activation_id, ...),
--   None-checked, and returns the UUID from the row — BaseRepository only
--   exposes fetchrow_safe/fetch_safe/execute_safe (verified against
--   backend/db/base_repository.py, no fetchval_safe exists).
--
-- ============================================================================
-- Firebreak (unchanged): SHADOW-only. This is the WRITE primitive; no HTTP
--   surface consults it yet (STEP-6c). No key-ceremony change — the
--   function activates already-signed packs, the crypto gate
--   (bundle.verify_rule_pack + validate_activation) stays service-layer,
--   BEFORE this function is ever called. ENFORCE flip = Zero (Legge 5).
-- ============================================================================
--
-- NOTE (mirrors 250's own): migration_base.py wraps the forward SQL in a
--   single transaction; the `-- === ROLLBACK ===` marker is mandatory
--   (migration_base.py:29) for migrations > 111.

-- -- F6(b): the unforgeable audit-identity column.
-- Bare NOT NULL, no DEFAULT -- safe ONLY because this table is guaranteed
-- empty at this point (migration 250 ships in the same release as this one;
-- every test DB is rebuilt from scratch per-test). Do NOT copy this pattern
-- against a table that might already hold rows.
--
-- Squawk suppression notes (verified empirically against squawk-cli 2.60.0,
-- 2026-07-19 -- two real gotchas, neither previously hit in this repo):
--   1) the ignore-comment separator is a SPACE, not a colon -- several
--      OTHER migrations here (147/145/151) use the colon form, which is
--      silently a no-op (an "unknown name" unused-ignore warning fires
--      instead of suppressing) on this squawk-cli version; those files
--      still lint clean only because their specific rules are ALSO
--      excluded at the workflow level (migration-lint.yml), so the dead
--      inline comments never mattered in practice.
--   2) the comment must sit directly above the SUB-CLAUSE line the finding
--      itself is anchored to (here, the `ADD COLUMN ...` line), NOT above
--      the statement-start line (`ALTER TABLE ...`) -- placing it one line
--      too high leaves the finding unsuppressed with zero warning at all.
ALTER TABLE public.visa_ruleset_activations
    -- squawk-ignore adding-required-field
    ADD COLUMN activated_by_principal text NOT NULL;

ALTER TABLE public.visa_ruleset_activations
    ADD CONSTRAINT visa_ruleset_activations_principal_nonblank
    CHECK (btrim(activated_by_principal) <> '');

-- -- F3: harden migration 250's four trigger functions.
-- Same names/signatures as 250 (CREATE OR REPLACE keeps every existing
-- CREATE TRIGGER pointer valid -- no trigger needs re-declaring). Every line
-- of LOGIC is byte-identical to 250 except: (1) SET search_path added to
-- each; (2) every relation reference schema-qualified; (3) the insert-guard
-- additionally stamps activated_by_principal (F6b); (4) the mutation-guard
-- additionally enumerates activated_by_principal in its immutability
-- OR-chain (F6 implementer-added closure, see header note above).

CREATE OR REPLACE FUNCTION reject_visa_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE OR REPLACE FUNCTION reject_visa_pack_payload_mismatch()
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

CREATE OR REPLACE FUNCTION reject_visa_activation_insert()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    pack RECORD;
    head RECORD;
BEGIN
    -- F6(b): stamp the unforgeable actor identity UNCONDITIONALLY, before
    -- anything else -- session_user is the actual authenticated DB role
    -- that ran this INSERT (raw, or nested inside the writer function),
    -- never a caller-supplied value. Runs even when the INSERT statement
    -- never named this column: BEFORE ROW trigger assignment happens
    -- before Postgres evaluates NOT NULL/CHECK on the row.
    NEW.activated_by_principal := session_user;

    -- finding 3 (250, round 2): serialize ALL inserters (raw or via the
    -- writer function) for this triple so the read-then-insert logic below
    -- is race-free even for direct concurrent INSERTs that bypass this
    -- function's own lock.
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

    -- Current head: the highest-sequence pack among every OTHER activation
    -- already recorded for this triple (any system_period, open or closed --
    -- the hash-chain and sequence must never regress even against a
    -- system-closed prior activation).
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

CREATE OR REPLACE FUNCTION reject_visa_activation_mutation()
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

-- -- The activation writer itself.
-- SECURITY DEFINER: runs as its OWNER (the migration/table-owner role today;
-- visa_ledger_owner once the operator provisioning moves ownership -- see
-- F1+F2 above), so it can write the ledger even once the runtime role can no
-- longer do so directly. SET search_path is the privilege-escalation
-- hardening every SECURITY DEFINER function needs (an attacker-writable
-- earlier schema in an unpinned search_path could shadow a builtin
-- operator/function); every table reference below is schema-qualified
-- accordingly (F4), including inside the nested trigger functions this
-- INSERT/UPDATE fires (F3).
CREATE FUNCTION public.visa_activate_rule_pack(
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
    -- F6(a): reject audit-forgery-shaped inputs up front. These guard the
    -- caller-supplied free-text NARRATIVE columns (activated_by/
    -- activation_reason) -- the actual unforgeable IDENTITY stamp
    -- (activated_by_principal := session_user) happens independently,
    -- inside the insert-guard trigger, as a side effect of the INSERT
    -- below.
    IF btrim(p_activated_by) = '' OR char_length(p_activated_by) > 200 THEN
        RAISE EXCEPTION 'visa_activate_rule_pack: activated_by must be non-blank and <= 200 chars (got % chars)',
            char_length(p_activated_by);
    END IF;
    IF btrim(p_activation_reason) = '' OR char_length(p_activation_reason) > 1000 THEN
        RAISE EXCEPTION 'visa_activate_rule_pack: activation_reason must be non-blank and <= 1000 chars (got % chars)',
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
    --    correction is a separate, not-yet-built operation -- see this
    --    migration's header.)
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

-- Function is never world-executable (Postgres grants EXECUTE to PUBLIC by
-- default at CREATE FUNCTION time -- this closes that unconditionally,
-- independent of the F1+F2 role-provisioning state below).
REVOKE ALL ON FUNCTION public.visa_activate_rule_pack(uuid, text, text) FROM PUBLIC;

-- -- F1+F2: Option-1 scaffold grant (role-guarded -- no-op until the
-- operator provisioning creates visa_activation_executor; see this file's
-- header).
DO $grant_block$
DECLARE
    executor_role constant text := 'visa_activation_executor';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = executor_role) THEN
        RAISE NOTICE 'visa_activation_writer: role % absent -- skipping grants (operator provisioning not yet run; see this migration''s header, F1+F2)',
            executor_role;
        RETURN;
    END IF;

    BEGIN
        EXECUTE format('GRANT SELECT, INSERT ON TABLE public.visa_rule_packs TO %I', executor_role);
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE WARNING 'manual grant required: GRANT SELECT, INSERT ON TABLE public.visa_rule_packs TO %',
                executor_role;
    END;

    BEGIN
        EXECUTE format('GRANT EXECUTE ON FUNCTION public.visa_activate_rule_pack(uuid, text, text) TO %I', executor_role);
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE WARNING 'manual grant required: GRANT EXECUTE ON FUNCTION public.visa_activate_rule_pack(uuid, text, text) TO %',
                executor_role;
    END;
END;
$grant_block$;

-- === ROLLBACK ===
DO $revoke_block$
DECLARE
    executor_role constant text := 'visa_activation_executor';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = executor_role) THEN
        RETURN;
    END IF;
    EXECUTE format('REVOKE EXECUTE ON FUNCTION public.visa_activate_rule_pack(uuid, text, text) FROM %I', executor_role);
    EXECUTE format('REVOKE SELECT, INSERT ON TABLE public.visa_rule_packs FROM %I', executor_role);
END;
$revoke_block$;

DROP FUNCTION IF EXISTS public.visa_activate_rule_pack(uuid, text, text);

-- Restore the four trigger functions to their EXACT migration-250 bodies
-- (unqualified table names, no SET search_path, no activated_by_principal
-- stamping/guard) -- this is what "rollback" of a CREATE OR REPLACE means:
-- reverting to what 250 alone would have created.
CREATE OR REPLACE FUNCTION reject_visa_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE OR REPLACE FUNCTION reject_visa_pack_payload_mismatch()
RETURNS trigger
LANGUAGE plpgsql
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

CREATE OR REPLACE FUNCTION reject_visa_activation_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    pack RECORD;
    head RECORD;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext(NEW.environment || NEW.jurisdiction || NEW.decision_domain));

    SELECT environment, jurisdiction, decision_domain, legal_period, sequence, previous_payload_sha256
        INTO pack
        FROM visa_rule_packs
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
        FROM visa_ruleset_activations a
        JOIN visa_rule_packs p ON p.id = a.rule_pack_id
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

CREATE OR REPLACE FUNCTION reject_visa_activation_mutation()
RETURNS trigger
LANGUAGE plpgsql
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

-- `ALTER TABLE IF EXISTS` (not bare `ALTER TABLE`) so this rollback is safe
-- to run even against a DB where migration 250 itself was never applied
-- (a plain `IF EXISTS` on the CONSTRAINT/COLUMN sub-clause alone would still
-- error with "relation does not exist" if the TABLE is absent — the test
-- fixture's drop-then-recreate idiom calls this rollback defensively before
-- ever calling either migration's forward SQL).
ALTER TABLE IF EXISTS public.visa_ruleset_activations DROP CONSTRAINT IF EXISTS visa_ruleset_activations_principal_nonblank;
ALTER TABLE IF EXISTS public.visa_ruleset_activations DROP COLUMN IF EXISTS activated_by_principal;
