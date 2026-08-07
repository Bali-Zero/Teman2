-- Migration 267: atomic replacement of the open Visa RulePack activation set.
--
-- Migration 251 deliberately rejects a partial legal-period overlap. That is
-- correct for the single-pack writer, but it also means a legitimate signed
-- correction cannot narrow one segment while preserving the rest of the
-- currently active legal coverage. This migration adds a separate set writer:
-- callers provide the COMPLETE replacement set of signed pack IDs (including
-- signed carry-forward segments). Scope and legal periods are derived only
-- from immutable visa_rule_packs rows.
--
-- Invariants enforced under the same scope advisory lock as migrations
-- 250/251/253:
--   * the replacement IDs are non-empty, unique, known, and share one scope;
--   * replacement legal periods do not overlap and their tstzmultirange is
--     exactly the current open set's coverage (no implicit gap or orphan);
--   * replacement packs form the next sequence/hash chain from the historic
--     activation head; the existing insert trigger independently rechecks it;
--   * all old rows close and all new rows open at one clock_timestamp();
--   * an exact retry is read-only/idempotent; audit-token drift on replay is
--     rejected rather than silently attributed to a different actor/reason.
--
-- Ed25519/JCS verification remains the caller's mandatory pre-gate. This
-- function never modifies or synthesizes a pack and cannot accept a caller-
-- supplied legal interval. The immutable pack table and activation triggers
-- remain the final database authority for scope, sequence, and hash-chain.

CREATE FUNCTION public.visa_replace_activation_set(
    p_rule_pack_ids    uuid[],
    p_activated_by     text,
    p_activation_reason text
)
RETURNS uuid[]
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_env                 text;
    v_jur                 text;
    v_domain              text;
    v_requested_count     integer;
    v_pack_count          integer;
    v_overlap_count       integer;
    v_now                 timestamptz;
    v_current_coverage    tstzmultirange;
    v_replacement_coverage tstzmultirange;
    v_current_pack_ids    uuid[];
    v_replacement_pack_ids uuid[];
    v_current_activation_ids uuid[];
    v_replay_tokens_match boolean;
    v_head_sequence       bigint;
    v_head_hash           bytea;
    v_previous_sequence   bigint;
    v_previous_hash       bytea;
    v_activation_ids      uuid[] := ARRAY[]::uuid[];
    v_activation_id       uuid;
    replacement           record;
BEGIN
    IF p_activated_by IS NULL
       OR NOT (p_activated_by ~ '^[A-Za-z0-9._:-]{1,120}$') THEN
        RAISE EXCEPTION 'visa_replace_activation_set: activated_by must be an opaque token (letters/digits/./_/:/- only, 1-120 chars)';
    END IF;
    IF p_activation_reason IS NULL
       OR NOT (p_activation_reason ~ '^[A-Za-z0-9._:-]{1,120}$') THEN
        RAISE EXCEPTION 'visa_replace_activation_set: activation_reason must be an opaque reason-code (letters/digits/./_/:/- only, 1-120 chars)';
    END IF;

    v_requested_count := cardinality(p_rule_pack_ids);
    IF v_requested_count IS NULL OR v_requested_count = 0 THEN
        RAISE EXCEPTION 'visa_replace_activation_set: replacement pack set must be non-empty';
    END IF;
    IF array_position(p_rule_pack_ids, NULL) IS NOT NULL THEN
        RAISE EXCEPTION 'visa_replace_activation_set: replacement pack set cannot contain null';
    END IF;
    IF (SELECT count(DISTINCT pack_id) FROM unnest(p_rule_pack_ids) AS requested(pack_id))
       <> v_requested_count THEN
        RAISE EXCEPTION 'visa_replace_activation_set: replacement pack IDs must be unique';
    END IF;

    -- Resolve the lock scope from an immutable pack row, never caller input.
    SELECT environment, jurisdiction, decision_domain
      INTO v_env, v_jur, v_domain
      FROM public.visa_rule_packs
     WHERE id = p_rule_pack_ids[1];
    IF NOT FOUND THEN
        RAISE EXCEPTION 'visa_replace_activation_set: unknown rule_pack_id %', p_rule_pack_ids[1];
    END IF;

    PERFORM pg_advisory_xact_lock(hashtext(v_env || v_jur || v_domain));

    SELECT count(*),
           array_agg(p.id ORDER BY p.sequence),
           range_agg(p.legal_period ORDER BY lower(p.legal_period), upper(p.legal_period))
      INTO v_pack_count, v_replacement_pack_ids, v_replacement_coverage
      FROM public.visa_rule_packs p
     WHERE p.id = ANY(p_rule_pack_ids)
       AND p.environment = v_env
       AND p.jurisdiction = v_jur
       AND p.decision_domain = v_domain;
    IF v_pack_count <> v_requested_count THEN
        RAISE EXCEPTION 'visa_replace_activation_set: every replacement pack must exist in the same scope';
    END IF;

    SELECT count(*)
      INTO v_overlap_count
      FROM unnest(p_rule_pack_ids) WITH ORDINALITY AS left_id(pack_id, ordinal)
      JOIN unnest(p_rule_pack_ids) WITH ORDINALITY AS right_id(pack_id, ordinal)
        ON left_id.ordinal < right_id.ordinal
      JOIN public.visa_rule_packs left_pack ON left_pack.id = left_id.pack_id
      JOIN public.visa_rule_packs right_pack ON right_pack.id = right_id.pack_id
     WHERE left_pack.legal_period && right_pack.legal_period;
    IF v_overlap_count > 0 THEN
        RAISE EXCEPTION 'visa_replace_activation_set: replacement legal periods overlap (% pair(s))',
            v_overlap_count;
    END IF;

    SELECT range_agg(a.legal_period ORDER BY lower(a.legal_period), upper(a.legal_period)),
           array_agg(a.rule_pack_id ORDER BY p.sequence),
           array_agg(a.id ORDER BY p.sequence),
           bool_and(a.activated_by = p_activated_by
                    AND a.activation_reason = p_activation_reason)
      INTO v_current_coverage, v_current_pack_ids,
           v_current_activation_ids, v_replay_tokens_match
      FROM public.visa_ruleset_activations a
      JOIN public.visa_rule_packs p ON p.id = a.rule_pack_id
     WHERE a.environment = v_env
       AND a.jurisdiction = v_jur
       AND a.decision_domain = v_domain
       AND upper(a.system_period) IS NULL;
    IF v_current_coverage IS NULL THEN
        RAISE EXCEPTION 'visa_replace_activation_set: scope has no open activation set to replace';
    END IF;

    -- Exact retry: no clock read and no ledger mutation.
    IF v_current_pack_ids = v_replacement_pack_ids THEN
        IF NOT v_replay_tokens_match THEN
            RAISE EXCEPTION 'visa_replace_activation_set: replay conflicts with existing actor/reason tokens';
        END IF;
        RETURN v_current_activation_ids;
    END IF;

    IF v_replacement_coverage IS DISTINCT FROM v_current_coverage THEN
        RAISE EXCEPTION 'visa_replace_activation_set: replacement coverage % must exactly equal current open coverage %',
            v_replacement_coverage, v_current_coverage;
    END IF;

    -- Preflight the entire sequence/hash chain before closing a single row.
    SELECT p.sequence, p.payload_sha256
      INTO v_head_sequence, v_head_hash
      FROM public.visa_ruleset_activations a
      JOIN public.visa_rule_packs p ON p.id = a.rule_pack_id
     WHERE a.environment = v_env
       AND a.jurisdiction = v_jur
       AND a.decision_domain = v_domain
     ORDER BY p.sequence DESC
     LIMIT 1;
    v_previous_sequence := v_head_sequence;
    v_previous_hash := v_head_hash;

    FOR replacement IN
        SELECT p.id, p.sequence, p.payload_sha256, p.previous_payload_sha256,
               p.legal_period
          FROM public.visa_rule_packs p
         WHERE p.id = ANY(p_rule_pack_ids)
         ORDER BY p.sequence
    LOOP
        IF replacement.sequence <= v_previous_sequence THEN
            RAISE EXCEPTION 'visa_replace_activation_set: rollback/replay rejected: pack sequence % <= activated head sequence %',
                replacement.sequence, v_previous_sequence;
        END IF;
        IF replacement.previous_payload_sha256 IS DISTINCT FROM v_previous_hash THEN
            RAISE EXCEPTION 'visa_replace_activation_set: replacement hash chain is not continuous at pack %',
                replacement.id;
        END IF;
        v_previous_sequence := replacement.sequence;
        v_previous_hash := replacement.payload_sha256;
    END LOOP;

    -- One database clock instant for every close/open boundary.
    v_now := clock_timestamp();

    UPDATE public.visa_ruleset_activations a
       SET system_period = tstzrange(lower(a.system_period), v_now, '[)')
     WHERE a.environment = v_env
       AND a.jurisdiction = v_jur
       AND a.decision_domain = v_domain
       AND upper(a.system_period) IS NULL;

    FOR replacement IN
        SELECT p.id, p.sequence, p.legal_period
          FROM public.visa_rule_packs p
         WHERE p.id = ANY(p_rule_pack_ids)
         ORDER BY p.sequence
    LOOP
        INSERT INTO public.visa_ruleset_activations
            (rule_pack_id, environment, jurisdiction, decision_domain,
             legal_period, system_period, activated_by, activation_reason)
        VALUES
            (replacement.id, v_env, v_jur, v_domain,
             replacement.legal_period, tstzrange(v_now, NULL, '[)'),
             p_activated_by, p_activation_reason)
        RETURNING id INTO v_activation_id;
        v_activation_ids := array_append(v_activation_ids, v_activation_id);
    END LOOP;

    RETURN v_activation_ids;
END;
$$;

REVOKE ALL ON FUNCTION public.visa_replace_activation_set(uuid[], text, text) FROM PUBLIC;

-- The existing activation capability remains distinct from pack insertion and
-- signing. Role creation/ownership transfer remains an operator provisioning
-- action shared with migrations 251/253.
DO $grant_block_267$
DECLARE
    executor_role constant text := 'visa_activation_executor';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = executor_role) THEN
        RAISE NOTICE 'visa activation-set writer (267): role % absent -- skipping grant',
            executor_role;
        RETURN;
    END IF;

    EXECUTE format(
        'REVOKE ALL PRIVILEGES ON TABLE public.visa_rule_packs, public.visa_ruleset_activations FROM %I',
        executor_role
    );
    BEGIN
        EXECUTE format(
            'GRANT EXECUTE ON FUNCTION public.visa_replace_activation_set(uuid[], text, text) TO %I',
            executor_role
        );
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE EXCEPTION 'visa activation-set writer (267): refusing half-armed capability; grant EXECUTE manually to %',
                executor_role;
    END;
END;
$grant_block_267$;

-- === ROLLBACK ===
DO $rollback_grant_block_267$
DECLARE
    executor_role constant text := 'visa_activation_executor';
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = executor_role) THEN
        EXECUTE format(
            'REVOKE EXECUTE ON FUNCTION public.visa_replace_activation_set(uuid[], text, text) FROM %I',
            executor_role
        );
    END IF;
END;
$rollback_grant_block_267$;

DROP FUNCTION IF EXISTS public.visa_replace_activation_set(uuid[], text, text);
