-- Migration 250: Visa Oracle engine — bitemporal rule-pack substrate (PR4)
--
-- Purpose:
--   The persistence read-substrate for the signed Visa Oracle rule packs the
--   evaluator consumes (PR1 models / PR2b bundle.py loader / PR3 evaluator, all
--   live on main). Two tables + the append-only guard:
--     * visa_rule_packs        — the immutable, Ed25519-signed pack envelope
--                                (payload stays an opaque JSONB blob for RULE
--                                EVALUATION — it is verified/compiled in Python
--                                by bundle.py + compiler.py, never queried by
--                                SQL predicate for business logic. A handful of
--                                envelope-IDENTITY scalars ARE compared by the
--                                payload-binding trigger below — see the PR4
--                                FIX-FIRST round 2 note — but that is integrity
--                                binding, not rule evaluation).
--     * visa_ruleset_activations — the bitemporal activation ledger. Which pack
--                                is "active" is expressed as two independent
--                                clocks: legal_period (when the rule set is
--                                legally in force) and system_period (when Visa
--                                Oracle's system considered it current). A GiST
--                                EXCLUDE constraint makes overlapping activations
--                                impossible at the DB level — there is never more
--                                than one active pack per (env,jurisdiction,
--                                domain) at any (effective_at, observed_at).
--   Runtime selection is a pure range-containment join (no ACTIVE/DEPRECATED
--   enum): legal_period @> effective_at AND system_period @> observed_at.
--
-- Source: research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
--   concretization.md section 5 (R1-gated, SURVIVES-WITH-CAVEATS). DDL is the
--   spec's, verbatim, with two deliberate deviations documented below.
--
-- SCOPE (deliberately narrow — read substrate only):
--   The spec's section 5 defines 9 tables. This migration lands ONLY the
--   read/selection substrate (packs + activations). The WRITE substrate
--   (visa_decisions, visa_decision_payloads, visa_price_quotes,
--   visa_consent_receipts, visa_clock_snapshots, visa_public_results,
--   visa_session_exchanges) and visa_source_records land in a LATER migration
--   WITH the SHADOW write-path code that populates them — no dead tables ahead
--   of their writer. Signed pack sources travel inline in the JSONB payload, so
--   no FK dependency is broken by deferring visa_source_records.
--
-- DEVIATIONS from the spec's literal section 5 text:
--   1) ROLLBACK marker uses the ENFORCED padded form (=== ROLLBACK ===)
--      (backend/db/migration_base.py:29 regex, mandatory for migrations > 111);
--      the spec's inline unpadded example would not match and would make the
--      whole file the "forward" section.
--   2) Runtime GRANTs (spec section 5 "Runtime grants") are NOT issued here.
--      They target roles (the FastAPI runtime role, activation role, retention
--      role) that do not exist in the CI/pre-push clone nuzantara_test (owned by
--      the test role), where GRANT ... TO <missing_role> would abort the whole
--      migration. Immutability is already enforced structurally by the
--      append-only trigger below (defense-in-depth, role-independent); the
--      SELECT/INSERT-only grant layer lands in a follow-up migration guarded by
--      role-existence DO-blocks once the runtime role model is confirmed.
--
-- PR4 FIX-FIRST amendments (2026-07-19 — cross-family adversarial gate, 6 P0 +
--   3 P1, all verified real on disk except P1-7 which was refuted empirically):
--   * visa_rule_packs gains two structural JSONB-object CHECKs (P0-1) so a
--     double-encoded scalar (the codec-double-encode bug the repository's
--     insert_rule_pack fix addresses) can never silently land as a valid row —
--     it fails the CHECK at INSERT time instead of failing silently at
--     verify-on-load time.
--   * visa_ruleset_activations gains the same jurisdiction/decision_domain
--     CHECKs the pack table already has (P0-2 mirror), plus a NEW
--     BEFORE INSERT trigger (reject_visa_activation_insert) that binds every
--     activation's (environment, jurisdiction, decision_domain, legal_period)
--     to EXACTLY its referenced pack's own values — a TEST pack can never be
--     activated into PRODUCTION by mistake or malice — and enforces
--     sequence-monotonicity across ALL prior activations for the same triple
--     (P0-3 DB-level anti-rollback, independent of and in addition to
--     bundle.validate_activation's Python-level hash-chain check).
--   * visa_ruleset_activations gains a second NEW trigger
--     (reject_visa_activation_mutation, BEFORE UPDATE OR DELETE) making the
--     ledger append-only-WITH-CLOSE (P0-5): DELETE is always rejected; the
--     ONLY legal UPDATE is closing an still-open system_period (finite upper
--     bound), with every other column — including the system_period LOWER
--     bound — unchanged, and re-closing an already-closed row rejected. The
--     pack table's own immutability trigger stays untouched; the ledger needs
--     this narrower carve-out because activate_rule_pack's supersession step
--     legitimately closes prior rows.
--   * Both tables' legal_period CHECK gains
--     "AND lower(legal_period) <> '-infinity'::timestamptz" (P1-9) — an
--     unbounded-into-the-past legal period is nonsensical for a dated
--     regulation and would defeat the P0-4 disjoint-legal-period-overlap
--     scoping in activate_rule_pack (a '-infinity' lower bound overlaps
--     everything).
--   * ROLLBACK reordered table-first (drops cascade each table's own
--     triggers/index/EXCLUDE with it) then the three trigger functions —
--     mooting the now-obsolete P1-7 finding (refuted empirically: DROP
--     TRIGGER IF EXISTS on an absent table did not error on our PG either
--     way, but table-first is still the structurally correct FK-safe order
--     for the two NEW activation triggers introduced here).
--
-- PR4 FIX-FIRST round 2 amendments (2026-07-19 — second cross-family gate,
--   found the round-1 write path still open on 5 more findings — KEY INSIGHT
--   driving all of these: the hash-chain (finding 2) is a comparison of
--   STORED payload_sha256 BYTES, not cryptography, so it belongs in the DB
--   trigger (caller-independent) rather than only a Python docstring
--   instruction. Only the Ed25519 signature + SHA256(JCS(payload)) genuinely
--   cannot be done in SQL — those stay verify_rule_pack's read-time job):
--   * visa_rule_packs gains a NEW BEFORE INSERT trigger
--     (reject_visa_pack_payload_mismatch, finding 1) binding the
--     security-critical relational columns to what the SIGNED payload
--     declares (id/environment/sequence/previous_payload_sha256) — a row can
--     never claim a scope/sequence/identity its own signed payload does not
--     (e.g. a signed TEST/seq1 envelope inserted as a PRODUCTION/seq11 row).
--     payload_sha256 itself and the Ed25519 signature stay unbindable in SQL
--     (they need RFC 8785 JCS canonicalization / Ed25519 verification) — that
--     remains verify_rule_pack's read-time job, unchanged.
--   * reject_visa_activation_insert() (the existing P0-2/P0-3 trigger) is
--     REWRITTEN to add: (a) a pg_advisory_xact_lock at the TOP of the trigger
--     body (finding 3) — this closes the raw-INSERT-concurrency gap the
--     round-1 trigger left open (only activate_rule_pack's own Python path
--     took the lock; a raw concurrent INSERT bypassing that method was not
--     serialized against a sibling raw INSERT's read-then-decide window); and
--     (b) a DB-level hash-chain check (finding 2) — the activating pack's
--     previous_payload_sha256 must equal the CURRENT head activation's own
--     pack's payload_sha256 for the same (environment, jurisdiction,
--     decision_domain) triple (or be NULL, with the pack's own sequence,
--     for the very first/bootstrap activation of that triple) — independent
--     of, and in addition to, bundle.validate_activation's Python-level
--     hash-chain check.
--   * reject_visa_activation_mutation() gains an OLD.id IS DISTINCT FROM
--     NEW.id guard (finding 5) — an UPDATE that swaps the primary key value
--     itself (while otherwise appearing to satisfy the close carve-out) is
--     now explicitly rejected, closing an identity-substitution gap the
--     round-1 OR-chain did not enumerate.
--   * ROLLBACK gains DROP FUNCTION IF EXISTS
--     reject_visa_pack_payload_mismatch() for the new trigger function.
--   * (finding 4, partial-legal-overlap rejection, needs to compare the
--     CANDIDATE's legal_period against every open activation's, which the
--     INSERT-time trigger here does not have visibility into before the
--     close step runs — this check belongs to the activation WRITER, and
--     per the PR4/STEP-6 BOUNDARY note immediately below, that writer is
--     deferred to STEP 6 in its entirety.)
--
-- PR4/STEP-6 BOUNDARY (2026-07-19, fourth cross-family adversarial gate):
--   round-4 finding 1 (P0) proved the activation WRITER (bitemporal
--   supersession — closing every still-open, legal-period-overlapping
--   prior activation for a triple and inserting the new one at one shared
--   clock_timestamp() read) cannot be closed by a Python method plus these
--   triggers alone: the raw-SQL system_period-timestamp backdating and the
--   partial-legal-overlap bypass immediately above both need a single
--   SECURITY DEFINER DB function (visa_activate_rule_pack(...)) plus a
--   GRANT model that REVOKEs direct INSERT/UPDATE/DELETE on
--   visa_ruleset_activations from the runtime role and grants only EXECUTE
--   on that function — closing the gap by construction rather than by
--   convention. That function + GRANT model is STEP 6. PR4 therefore ships
--   NO activation writer at all (repository.py no longer defines
--   activate_rule_pack); it ships only the read substrate
--   (load_active_rule_pack), the signed-pack insert (insert_rule_pack), and
--   the five triggers in this migration — which are exactly the
--   caller-independent guards STEP-6's SECURITY DEFINER function will
--   itself run under, so they are correct and load-bearing from day 1, not
--   something STEP-6 introduces later.
--   round-4 finding 2 (P1, key-presence) — reject_visa_pack_payload_mismatch
--   below is hardened once more: round-3's IS DISTINCT FROM fix still could
--   not tell a MISSING payload key apart from an explicit JSON null (a
--   bootstrap pack's previous_payload_sha256 is legitimately null, but the
--   KEY must still be PRESENT — the contract mandates the key exists, not
--   merely that a value-comparison happens to evaluate true against a NULL
--   coalesced from a missing key). Every bound field now requires jsonb `?`
--   key presence explicitly, in addition to the existing value comparison.
--
-- NOTE: backend/db/migration_base.py wraps the forward SQL in a SINGLE
--   transaction. CREATE EXTENSION / CREATE TABLE / CREATE FUNCTION all commit
--   together; on rollback they are undone in FK-safe order. btree_gist is a
--   PG13+ "trusted" extension, so a database owner can create it without
--   superuser; IF NOT EXISTS makes it a no-op where a sibling already added it.

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE visa_rule_packs (
    id                      UUID PRIMARY KEY,
    environment             TEXT NOT NULL
        CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),
    jurisdiction            CHAR(2) NOT NULL DEFAULT 'ID'
        CHECK (jurisdiction = 'ID'),
    decision_domain         TEXT NOT NULL DEFAULT 'IMMIGRATION_VISA'
        CHECK (decision_domain = 'IMMIGRATION_VISA'),
    sequence                BIGINT NOT NULL CHECK (sequence > 0),
    pack_version            TEXT NOT NULL,
    engine_contract_version TEXT NOT NULL,
    engine_min_version      TEXT NOT NULL,
    engine_max_version      TEXT NOT NULL,
    legal_period            TSTZRANGE NOT NULL,
    protected_header        JSONB NOT NULL,
    payload                 JSONB NOT NULL,
    payload_sha256          BYTEA NOT NULL CHECK (octet_length(payload_sha256) = 32),
    previous_payload_sha256 BYTEA CHECK (
        previous_payload_sha256 IS NULL
        OR octet_length(previous_payload_sha256) = 32
    ),
    signature               BYTEA NOT NULL CHECK (octet_length(signature) = 64),
    signing_key_id          TEXT NOT NULL,
    signed_at               TIMESTAMPTZ NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        NOT isempty(legal_period)
        AND lower_inc(legal_period)
        AND NOT upper_inc(legal_period)
        AND lower(legal_period) <> '-infinity'::timestamptz
    ),
    CHECK (jsonb_typeof(protected_header) = 'object'),
    CHECK (jsonb_typeof(payload) = 'object'),
    UNIQUE (environment, jurisdiction, decision_domain, sequence),
    UNIQUE (payload_sha256)
);

CREATE TABLE visa_ruleset_activations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_pack_id      UUID NOT NULL REFERENCES visa_rule_packs(id),
    environment       TEXT NOT NULL,
    jurisdiction      CHAR(2) NOT NULL DEFAULT 'ID'
        CHECK (jurisdiction = 'ID'),
    decision_domain   TEXT NOT NULL DEFAULT 'IMMIGRATION_VISA'
        CHECK (decision_domain = 'IMMIGRATION_VISA'),
    legal_period      TSTZRANGE NOT NULL,
    system_period     TSTZRANGE NOT NULL DEFAULT tstzrange(now(), NULL, '[)'),
    activated_by      TEXT NOT NULL,
    activation_reason TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        NOT isempty(legal_period)
        AND lower_inc(legal_period)
        AND NOT upper_inc(legal_period)
        AND lower(legal_period) <> '-infinity'::timestamptz
    ),
    CHECK (
        NOT isempty(system_period)
        AND lower_inc(system_period)
        AND NOT upper_inc(system_period)
    ),
    EXCLUDE USING gist (
        environment WITH =,
        jurisdiction WITH =,
        decision_domain WITH =,
        legal_period WITH &&,
        system_period WITH &&
    )
);

CREATE INDEX idx_visa_ruleset_activations_pack
    ON visa_ruleset_activations (rule_pack_id);

-- Append-only guard: the signed pack table can only ever be INSERTed into.
-- Any UPDATE or DELETE raises — the sole way to change the active rule set is to
-- INSERT a new pack (higher sequence) and a new activation (the activation
-- ledger closes the prior system_period via UPDATE, which is why the trigger is
-- on visa_rule_packs, NOT on visa_ruleset_activations).
CREATE FUNCTION reject_visa_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER visa_rule_packs_immutable
BEFORE UPDATE OR DELETE ON visa_rule_packs
FOR EACH ROW EXECUTE FUNCTION reject_visa_immutable_mutation();

-- Pack-payload binding (PR4 FIX-FIRST round 2, finding 1; hardened round 3,
-- findings 1 + 2; hardened again round 4, finding 2): the security-critical
-- relational columns must equal what the SIGNED payload declares, so a row
-- can never claim a scope/sequence/identity/legal-period its signed payload
-- does not (e.g. a signed TEST/seq1/[2026,2027) envelope inserted as a
-- PRODUCTION/seq11/[2026,infinity) row). This compares a handful of envelope
-- IDENTITY scalars — it is integrity binding, NOT rule evaluation (the
-- payload stays opaque to business logic). payload_sha256 + signature are
-- NOT bindable in SQL (they need JCS canonicalization / Ed25519
-- verification) — those stay verify_rule_pack's read-time check. Round 3
-- hardening:
--   * finding 1 (P0) — the row's legal_period is now bound to the signed
--     payload's valid_period, so a row can never widen a pack's legally-in-
--     force window beyond what was signed (which would let the runtime
--     selection query serve EXPIRED rules past the signed upper bound).
--   * finding 2 (P1) — every comparison now uses IS DISTINCT FROM (NULL-safe)
--     instead of <>/= : a MISSING payload key used to make the `<>` NULL-
--     valued and never fire (silently passing), and a JSON STRING sequence
--     (e.g. "11") used to silently cast-and-match a bigint row sequence —
--     both are now rejected up front (sequence additionally requires
--     jsonb_typeof = 'number').
-- Round 4 hardening (key-presence, see the PR4/STEP-6 BOUNDARY note above):
--   * finding 2 (P1) — IS DISTINCT FROM alone still could not tell a
--     MISSING payload key apart from an explicit JSON null (round-3's fix
--     made the VALUE comparison NULL-safe, but `NEW.payload->>'x'` is NULL
--     both when the key is absent and when it holds an explicit null — the
--     comparison could not distinguish the two). Every bound field now
--     requires the key be PRESENT via jsonb `?` explicitly, in addition to
--     the value comparison — the contract mandates the key exists (even
--     previous_payload_sha256, whose legitimate bootstrap VALUE is null,
--     must still have the KEY present).
CREATE FUNCTION reject_visa_pack_payload_mismatch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Every comparison uses IS DISTINCT FROM (NULL-safe: a missing/null payload
    -- key makes the RHS NULL, and `<col> IS DISTINCT FROM NULL` is TRUE for a
    -- NOT NULL column, so a missing key is REJECTED, never slipped through — the
    -- `<>` form returned NULL and silently passed, round-3 finding 2) AND an
    -- explicit `? '<key>'` presence check (round-4 finding 2: IS DISTINCT FROM
    -- alone cannot tell a MISSING key apart from an explicit JSON null — both
    -- read back as SQL NULL via ->>).
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
    -- sequence must be a JSON number (a string "11" must NOT satisfy the binding
    -- even though ("11")::bigint would equal the row) AND equal the row AND the
    -- key must be present (a missing key already fails jsonb_typeof(NULL) above,
    -- but the explicit `?` check makes the requirement unambiguous and gives a
    -- clearer error).
    IF NOT (NEW.payload ? 'sequence')
       OR jsonb_typeof(NEW.payload->'sequence') IS DISTINCT FROM 'number'
       OR NEW.sequence IS DISTINCT FROM (NEW.payload->>'sequence')::bigint THEN
        RAISE EXCEPTION 'visa_rule_packs.sequence % does not match signed payload sequence % (must be a present JSON number)',
            NEW.sequence, NEW.payload->>'sequence';
    END IF;
    -- previous_payload_sha256's legitimate bootstrap VALUE is null — but the
    -- KEY itself must still be present (round-4 finding 2: a payload that
    -- OMITS the key entirely must be rejected just like one with a wrong hash).
    IF NOT (NEW.payload ? 'previous_payload_sha256')
       OR encode(NEW.previous_payload_sha256, 'hex') IS DISTINCT FROM NEW.payload->>'previous_payload_sha256' THEN
        RAISE EXCEPTION 'visa_rule_packs.previous_payload_sha256 does not match signed payload (key must be present, may be null)';
    END IF;
    -- P0 (round-3 finding 1): the row's legal_period must equal the tstzrange the
    -- signed payload.valid_period declares, so a row can never widen a pack's
    -- legally-in-force window beyond what was signed (which would serve expired
    -- rules). valid_period is {"from": <iso>, "to": <iso|null>}; a null/absent
    -- "to" is an open-ended upper bound. verify_rule_pack cannot catch this — it
    -- is not given effective_at — so the binding must live here. Round-4 finding
    -- 2 additionally requires BOTH the "from" and "to" keys be present (a "to"
    -- key entirely absent must be rejected the same as one holding an explicit
    -- null, since the contract mandates the key exists).
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

CREATE TRIGGER visa_rule_packs_payload_binding
BEFORE INSERT ON visa_rule_packs
FOR EACH ROW EXECUTE FUNCTION reject_visa_pack_payload_mismatch();

-- Activation INSERT guard: (1) serializes ALL inserters (raw INSERT or via
-- activate_rule_pack) for the same (environment, jurisdiction, decision_domain)
-- triple with an advisory lock taken FIRST (PR4 FIX-FIRST round 2, finding 3 —
-- round 1 only serialized activate_rule_pack's own Python path; a raw
-- concurrent INSERT bypassing that method raced against a sibling raw INSERT's
-- read-then-decide window); (2) binds the activation to its referenced pack's
-- exact (environment, jurisdiction, decision_domain, legal_period) — a TEST
-- pack can never be activated into PRODUCTION (P0-2); (3) anti-rollback — a
-- pack's sequence must strictly exceed every previously-activated pack's
-- sequence for the same triple, so an older signed pack can never be
-- reactivated (P0-3); (4) DB-level hash-chain (round 2, finding 2) — the
-- activating pack's previous_payload_sha256 must equal the CURRENT head
-- activation's own pack's payload_sha256 (or be NULL, with the pack's own
-- sequence, for the first/bootstrap activation of the triple) — a stored-bytes
-- comparison, not cryptography, so it belongs here rather than only in the
-- service layer. The full cryptographic anti-rollback (signature, engine
-- compatibility) remains the service layer's validate_activation() job — this
-- trigger is the caller-independent DB-level defense-in-depth.
CREATE FUNCTION reject_visa_activation_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    pack RECORD;
    head RECORD;
BEGIN
    -- finding 3: serialize ALL inserters (raw or via activate_rule_pack) for
    -- this triple so the read-then-insert logic below is race-free even for
    -- direct concurrent INSERTs that bypass the Python method's own lock.
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

    -- Current head: the highest-sequence pack among every OTHER activation
    -- already recorded for this triple (any system_period, open or closed —
    -- the hash-chain and sequence must never regress even against a
    -- system-closed prior activation).
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

CREATE TRIGGER visa_activation_insert_guard
BEFORE INSERT ON visa_ruleset_activations
FOR EACH ROW EXECUTE FUNCTION reject_visa_activation_insert();

-- Activation ledger is append-only-with-close (P0-5): DELETE forbidden; the ONLY
-- permitted UPDATE is closing an open system_period (upper NULL -> finite) with every
-- other column and the system_period lower bound unchanged, INCLUDING the primary
-- key itself (round 2, finding 5 — an UPDATE that swaps id while otherwise matching
-- the close carve-out is rejected too). Re-closing an already closed row is
-- forbidden. (The pack table has its own stricter no-mutation trigger; the ledger
-- needs the close carve-out because activate_rule_pack closes prior rows.)
CREATE FUNCTION reject_visa_activation_mutation()
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

CREATE TRIGGER visa_ruleset_activations_append_only
BEFORE UPDATE OR DELETE ON visa_ruleset_activations
FOR EACH ROW EXECUTE FUNCTION reject_visa_activation_mutation();

-- === ROLLBACK ===
-- Drop tables first (their triggers, indexes and the EXCLUDE constraint drop with
-- them, FK-safe: activations references packs so activations first), then the
-- trigger functions. btree_gist is intentionally NOT dropped — shared extension.
DROP TABLE IF EXISTS visa_ruleset_activations;
DROP TABLE IF EXISTS visa_rule_packs;
DROP FUNCTION IF EXISTS reject_visa_activation_insert();
DROP FUNCTION IF EXISTS reject_visa_activation_mutation();
DROP FUNCTION IF EXISTS reject_visa_immutable_mutation();
DROP FUNCTION IF EXISTS reject_visa_pack_payload_mismatch();
