-- Migration 254: Visa Oracle engine — activation ledger system_period
-- sentinel-timestamp guard (upper 'infinity' close-bypass AND lower
-- '-infinity' start-bypass; ENFORCE-prereq hardening, roll-forward against
-- ALREADY-APPLIED migrations 250/251/253)
--
-- ============================================================================
-- WHY THIS IS A NEW MIGRATION, NOT AN EDIT TO 250/251/253
-- ============================================================================
--   Migrations 250/251/253 are already merged to `main` and applied
--   (253's own header: 251 merged+deployed 2026-07-19; 253 itself is the
--   already-landed FIX-ROUND roll-forward on top of it). `migration_base.py`/
--   `migration_manager.py` never re-run an already-applied migration's SQL
--   body once recorded in `_schema_versions` — so 250/251/253's on-disk text
--   is an immutable historical record of what already executed (cicatrix
--   family #9, "state-schema mutation drift" / W88 extended to migration
--   files themselves). This migration is the roll-forward correction; it
--   targets the LIVE, POST-253 schema state and does not edit any of the
--   three files above.
--
-- ============================================================================
-- THE DEFECT
-- ============================================================================
--   253's current (latest-declared) `reject_visa_activation_mutation()`
--   guards closing an open `visa_ruleset_activations.system_period` with
--   only:
--       IF upper(NEW.system_period) IS NULL THEN
--           RAISE EXCEPTION '... close must set a finite system_period
--           upper bound';
--       END IF;
--   Postgres distinguishes an UNBOUNDED range end (constructed with a NULL
--   upper argument — `upper()` returns NULL, `upper_inf()` = true) from a
--   range whose upper bound is explicitly the sentinel value
--   `'infinity'::timestamptz` (`upper()` returns `'infinity'`, a NON-NULL
--   value, yet `upper_inf()` is STILL false). An UPDATE that "closes" a row
--   by setting `upper(system_period) = 'infinity'::timestamptz` is
--   therefore non-NULL and PASSES the existing guard while remaining
--   functionally open-ended forever — it never really closes the period: a
--   supersession dead-end (the row can never be re-closed — the "already
--   closed" guard immediately above this one only fires on a NON-NULL upper
--   bound — and the GiST EXCLUDE constraint on
--   `(environment, jurisdiction, decision_domain, legal_period,
--   system_period)` still treats the row as overlapping any new activation
--   over the same scope/legal_period, silently blocking every future
--   supersession attempt for that triple). Separately, the
--   `visa_ruleset_activations.system_period` table CHECK (migration 250) has
--   NO guard at all on EITHER bound: not the upper bound (above), and not
--   the lower bound either — unlike `legal_period` (this table's own sibling
--   column, migration 250) and `visa_source_records.recorded_period`
--   (migration 252), BOTH of which guard their lower bound against the
--   `-infinity` sentinel (`lower(...) <> '-infinity'::timestamptz`),
--   `system_period` has no equivalent guard at all. `system_period` is a
--   TRANSACTION-time column (when the system considered a pack current) —
--   it must always have a finite, real start; `-infinity` lower is never
--   legitimate here, same reasoning as `legal_period`'s existing guard.
--
-- ============================================================================
-- THE FIX — closes the FULL sentinel-timestamp family on system_period,
-- mirroring migration 252's `reject_visa_source_records_mutation()` +
-- `visa_source_records` CHECK (upper 'infinity' close-bypass, "STEP-6b gate
-- round-2 fix", 2026-07-20) AND migration 250's own `legal_period` lower
-- '-infinity' guard (same table, same sentinel-timestamp class) — after
-- this migration, system_period is guarded against BOTH sentinel timestamps
-- exactly as legal_period/recorded_period already are.
-- ============================================================================
--   1. `reject_visa_activation_mutation()` is `CREATE OR REPLACE`d (its
--      declaration re-qualified `public.` per 253's own P1-3 convention) —
--      every line of logic is byte-identical to 253's applied body EXCEPT
--      the close-validation IF, which is widened from a bare
--      `upper(NEW.system_period) IS NULL` to
--      `upper(NEW.system_period) IS NULL OR upper(NEW.system_period) =
--      'infinity'::timestamptz` — same OR-shape, same single RAISE
--      EXCEPTION, as migration 252's fix for `visa_source_records`. The
--      message text is unchanged (253's own established wording for this
--      table/trigger — "visa_ruleset_activations: close must set a finite
--      system_period upper bound").
--   2. A table CHECK constraint is added on `visa_ruleset_activations.
--      system_period` forbidding an explicit `'infinity'` upper bound —
--      `upper(system_period) IS NULL OR upper(system_period) <>
--      'infinity'::timestamptz` — mirroring migration 252's identical CHECK
--      on `visa_source_records.recorded_period` verbatim in shape. An OPEN
--      period (upper NULL) remains legal — only the 'infinity' sentinel is
--      rejected. Added `NOT VALID` + a separate `VALIDATE CONSTRAINT`,
--      mirroring migration 253's OWN precedent for ALTERing this exact
--      table (253's P2 token-format CHECKs) rather than 252's (252 added its
--      CHECK inline at CREATE TABLE time, since visa_source_records was a
--      brand-new table in that migration — there is no ALTER-on-existing-
--      table precedent in 252 itself to mirror byte-for-byte). Per 253's own
--      recorded verification, both `visa_ruleset_activations` and
--      `visa_rule_packs` held 0 rows in prod as of 2026-07-19 (SHADOW-only,
--      no ENFORCE HTTP surface consults this ledger yet per 251/253's
--      firebreak) — `constraint-missing-not-valid` is excluded fleet-wide in
--      `.github/workflows/migration-lint.yml` regardless, so NOT VALID here
--      is a safety choice matching this table's own established style, not a
--      lint-suppression one.
--   3. A SECOND, independent table CHECK constraint is added on
--      `visa_ruleset_activations.system_period` forbidding an explicit
--      `-infinity` LOWER bound — `lower(system_period) <>
--      '-infinity'::timestamptz` — mirroring `legal_period`'s own guard on
--      this exact table (migration 250: `lower(legal_period) <>
--      '-infinity'::timestamptz`) verbatim in shape. A bare `<>` (no `IS
--      NULL OR` prefix) is sufficient here because migration 250's own
--      system_period CHECK already enforces `lower_inc(system_period)`, so
--      `lower(system_period)` can never be NULL — same reasoning as
--      legal_period's guard, which is likewise a bare `<>`. Kept as a
--      SEPARATE constraint from `..._not_infinite` above (not folded into
--      one CHECK) because migration 250's original system_period CHECK is
--      immutable on-disk (roll-forward only, never edited) — this is an
--      ADD, not a widen of an existing clause. Same NOT VALID + VALIDATE
--      pattern as point 2.
--
-- Firebreak (unchanged from 251/253): SHADOW-only. No HTTP surface consults
--   this writer yet (STEP-6c). ENFORCE flip = Zero (Legge 5), and per 251/
--   253's own header, ENFORCE must not ship before the operator provisioning
--   (ownership transfer + role creation) has run — this migration does not
--   change that boundary in any way, it only closes an independent
--   correctness gap in the close-carve-out guard.
--
-- NOTE: `-- === ROLLBACK ===` marker is mandatory (migration_base.py:29) for
--   migrations > 111. `migration_base.py` wraps the forward SQL in a single
--   transaction (same as every migration in this directory).

-- -- Re-declare reject_visa_activation_mutation(): byte-identical to 253's
-- applied body except the widened close-validation IF (see header). CREATE
-- OR REPLACE keeps the existing CREATE TRIGGER pointer
-- (visa_ruleset_activations_append_only, migration 250) valid unchanged --
-- no trigger needs re-declaring.
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
    -- Migration 254 fix (mirrors migration 252's reject_visa_source_records_
    -- mutation() fix for visa_source_records.recorded_period, "STEP-6b gate
    -- round-2 fix", 2026-07-20): `upper(...) IS NULL` alone does not reject a
    -- non-finite close via the explicit 'infinity' sentinel -- Postgres
    -- treats an upper bound literally set to 'infinity'::timestamptz as a
    -- present (non-NULL) value distinct from an unbounded range end, so this
    -- used to slip past the old NULL-only guard while remaining functionally
    -- open-ended forever (a supersession dead-end: the row could never be
    -- re-closed by the guard immediately above, and the GiST EXCLUDE
    -- constraint would still treat it as overlapping any new activation over
    -- the same scope/legal_period). Reject both.
    IF upper(NEW.system_period) IS NULL
       OR upper(NEW.system_period) = 'infinity'::timestamptz THEN
        RAISE EXCEPTION 'visa_ruleset_activations: close must set a finite system_period upper bound';
    END IF;
    RETURN NEW;
END;
$$;

-- -- Table CHECK mirroring migration 252's identical guard on
-- visa_source_records.recorded_period. NOT VALID + separately VALIDATED,
-- mirroring migration 253's own ALTER-on-this-table precedent (both columns/
-- rows are empty on prod per 253's own recorded verification, so this could
-- not fail against existing data at authoring time; kept as a safety choice
-- matching this table's established style regardless).
ALTER TABLE public.visa_ruleset_activations
    ADD CONSTRAINT visa_ruleset_activations_system_period_not_infinite
    CHECK (upper(system_period) IS NULL OR upper(system_period) <> 'infinity'::timestamptz) NOT VALID;
ALTER TABLE public.visa_ruleset_activations
    VALIDATE CONSTRAINT visa_ruleset_activations_system_period_not_infinite;

-- -- Second, independent table CHECK mirroring legal_period's own
-- migration-250 lower '-infinity' guard on this exact table (bare `<>`, no
-- `IS NULL OR` prefix needed -- migration 250's own system_period CHECK
-- already enforces lower_inc(system_period), so lower(system_period) can
-- never be NULL). NOT VALID + separately VALIDATED, same reasoning as the
-- not_infinite constraint above (0 rows on prod per 253's own recorded
-- verification).
ALTER TABLE public.visa_ruleset_activations
    ADD CONSTRAINT visa_ruleset_activations_system_period_lower_finite
    CHECK (lower(system_period) <> '-infinity'::timestamptz) NOT VALID;
ALTER TABLE public.visa_ruleset_activations
    VALIDATE CONSTRAINT visa_ruleset_activations_system_period_lower_finite;

-- === ROLLBACK ===
ALTER TABLE IF EXISTS public.visa_ruleset_activations
    DROP CONSTRAINT IF EXISTS visa_ruleset_activations_system_period_not_infinite;
ALTER TABLE IF EXISTS public.visa_ruleset_activations
    DROP CONSTRAINT IF EXISTS visa_ruleset_activations_system_period_lower_finite;

-- Restore reject_visa_activation_mutation() to its EXACT migration-253-
-- applied body (bare `upper(NEW.system_period) IS NULL` close-validation,
-- no 'infinity' rejection) -- this is what "rollback of the 254 fix" means:
-- reverting to what 253 alone left live. CREATE OR REPLACE (not DROP)
-- because 250/251/253 are not being rolled back here -- only 254's own
-- contribution is undone, leaving the trigger pointer and every prior
-- migration's contribution intact. Declaration stays schema-qualified
-- (`public.`) even on rollback, same convention 253 established for its own
-- rollback of these trigger functions.
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
