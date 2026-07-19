-- Migration 252: Visa Oracle engine — SHADOW write substrate (STEP-6b)
--
-- Purpose:
--   Migration 250 landed the READ substrate (visa_rule_packs +
--   visa_ruleset_activations) the evaluator selects an active pack from.
--   This migration lands the WRITE substrate — the tables where the
--   engine's SHADOW-mode output actually LANDS once wired (STEP-6b is
--   schema-only; the writer code that INSERTs into these tables is a later
--   step, same "no dead tables ahead of their writer" discipline 250 used
--   for deferring these tables in the first place — except here the writer
--   comes AFTER, deliberately, because SHADOW mode must be able to audit an
--   evaluation the instant it runs, and schema-then-writer is the safer
--   ordering when the writer is still being designed by a sibling task).
--
-- Source: research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
--   concretization.md section 5 (same document 250 sourced its DDL from).
--   Verified against the LIVE evaluator contracts, not just the research
--   doc's DDL sketch, per this task's ground-first mandate:
--     * backend/services/visa_engine/enums.py::DecisionState — the exact
--       5-value closed vocabulary the evaluator emits (NOT the
--       ELIGIBLE/INELIGIBLE/UNKNOWN tri-state a naive reading of "verdict"
--       might suggest — the real engine has no such enum; DecisionState is
--       the one true "verdict" vocabulary, precedence documented on the
--       enum itself: TEMPORARILY_UNAVAILABLE > HUMAN_REVIEW_REQUIRED >
--       SUPPORTED_CANDIDATES > NEEDS_INPUT > NO_SUPPORTED_PATH).
--     * backend/services/visa_engine/enums.py::EngineMode/EngineSurface —
--       the mode/surface closed vocabularies (EngineMode also has OFF; OFF
--       never produces a Decision, so this migration's CHECK excludes it —
--       a SHADOW row that claims mode=OFF is definitionally impossible).
--     * backend/services/visa_engine/models.py::Decision/SourceRecord — the
--       Pydantic contracts these tables persist. models.Decision has NO
--       ``abstained`` field/enum anywhere in the package (grepped; the
--       nearest analogue, CLAUDE.md's RAG abstain-threshold vocabulary in
--       backend/services/rag/agentic/_abstain_policy.py, is a wholly
--       different subsystem) — so no ``abstained`` column is added here,
--       documented rather than silently guessed at.
--
-- SCOPE (SHADOW-minimal, per the STEP-6b task's own instruction — this is
--   deliberately NOT the full spec section 5 decision table):
--   Three tables land here:
--     * visa_decisions        — one row per engine evaluation (SHADOW or,
--                                once ENFORCE-GATE flips per PENDING-ARMS
--                                task #15, ENFORCE too — the CHECK already
--                                allows both values so no later ALTER is
--                                needed for that flip).
--     * visa_decision_payloads — the PII-bearing side, held SEPARATE from
--                                visa_decisions and containing only opaque
--                                ciphertext (UU PDP Law 2 — see the PII
--                                boundary note below).
--     * visa_source_records    — the regulatory/pricing sources a verdict's
--                                ``citations`` may point at. Landed here
--                                (not with 250) because 250's own header
--                                explicitly deferred it to "a LATER
--                                migration WITH the SHADOW write-path code
--                                that populates them" — this is that
--                                migration.
--   The spec's section 5 defines SIX more tables this migration deliberately
--   does NOT build (task instruction: "where the spec has more tables ...
--   do NOT build them — list them ... one line each"):
--     * visa_consent_receipts  — STEP-6c+. SHADOW decisions are internal
--                                diagnostics, never rendered to a user, so
--                                no consent/legal-basis binding exists yet
--                                to attach a receipt to.
--     * visa_price_quotes      — STEP-6c+, needs the product/pricing catalog
--                                wiring this migration does not touch.
--     * visa_clock_snapshots   — STEP-6c+, stay-clock feature, unrelated to
--                                the SHADOW eligibility write-path.
--     * visa_public_results    — STEP-6c+, the public-sharing surface; there
--                                is nothing to publicly share from a mode
--                                that is never rendered.
--     * visa_session_exchanges — STEP-6c+, one-time session-token exchange
--                                for the public-results surface above — has
--                                no meaning without that surface existing.
--   ``visa_decisions`` here is ALSO a deliberately reduced projection of the
--   spec's full decision table — every column that exists ONLY to serve the
--   deferred tables above is likewise deferred, not silently dropped:
--     * facts_hmac/facts_hmac_key_id, decision_hmac/decision_hmac_key_id,
--       decision_integrity — HMAC integrity binding needs a key-management
--       story this migration does not build; SHADOW rows are read by
--       operators/audits, not re-verified cryptographically by a public
--       caller, so the integrity chain can wait for the ENFORCE-grade table.
--     * processing_receipt_id  — FK target (visa_consent_receipts) does not
--       exist in this migration by design (see above).
--     * idempotency_key        — dedup key for a caller that might retry the
--       same request; SHADOW mode has no caller-facing retry contract yet
--       (nothing renders the result, so a duplicate row is a harmless
--       audit-log duplicate, not a user-visible defect).
--     * retention_until/legal_hold — full UU PDP retention-worker semantics;
--       deferred with the retention worker itself (spec section
--       "Retention", still Gate-0-pending per that section's own table).
--     * candidate_summary/missing_facts/review_reason_codes/
--       no_path_reason_codes/notice_codes — rich per-candidate detail SHADOW
--       comparison does not need; ``verdict`` (the DecisionState) plus
--       ``citations`` is enough to compare "what would the engine have
--       said" against the live system's actual answer. Full candidate
--       detail is an ENFORCE-grade concern, added when the writer that
--       needs it (STEP-6c+) lands.
--
-- Columns ADDED beyond the spec's literal section-5 sketch (all explicitly
--   requested by the STEP-6b task, justified individually):
--   * visa_decisions.environment/jurisdiction/decision_domain — the spec's
--     real decision table has NO these columns directly (only rule_pack_id,
--     joined for scope) but a SHADOW audit query needs to filter/aggregate
--     by scope even for TEMPORARILY_UNAVAILABLE rows where rule_pack_id is
--     NULL (the join path does not exist for exactly the rows most
--     interesting to a SHADOW-outage audit) — denormalized here for that
--     reason, CHECK-constrained identically to migration 250's own pack/
--     activation tables ("jurisdiction/domain CHECKs like 250").
--   * visa_decisions.engine_surface/engine_mode — spec section 5 has no
--     equivalent column; EngineSurface/EngineMode (enums.py) are call-site
--     vocabularies with no persistence anywhere in the spec's DDL. A SHADOW
--     audit row is meaningless without knowing which surface/mode produced
--     it (that is the entire point of "SHADOW substrate" — recording what
--     the engine WOULD have told which caller). engine_mode's CHECK
--     excludes 'OFF' (see above); engine_surface enumerates enums.py's
--     EngineSurface members verbatim.
--   * visa_decisions.engine_version — the running engine BUILD/RELEASE
--     identity (distinct from rule_pack.engine_contract_version/
--     engine_min_version/engine_max_version, which describe what the PACK
--     declares itself compatible with, not what code actually ran). Needed
--     to reproduce/debug a SHADOW verdict months later against a since-
--     changed evaluator.
--   * visa_decisions.rule_pack_sha256 is the spec's own "denormalized for
--     audit" field (section 5 calls it exactly this in the decisions
--     table); NOT duplicating rule_pack_sequence alongside it (spec's table
--     has both) — sequence is one join away via rule_pack_id and the task's
--     explicit column list did not ask for it; keeping the SHADOW-minimal
--     scope tight.
--   * visa_decisions.citations (JSONB array) — the spec's Decision has no
--     single flattened "citations" field (source references are scattered
--     across candidates[].source_refs / review_reasons[].source_refs /
--     no_path_reasons[].source_refs / notices[].source_refs, each a nested
--     Reason). A SHADOW audit table that does not persist candidate/reason
--     detail (see above) still needs SOME way to show what the verdict
--     cited — ``citations`` is that flattened array. Element SHAPE is
--     intentionally NOT constrained beyond "is a JSON array" (mirrors
--     migration 250's own precedent of leaving payload/protected_header
--     opaque to SQL) — the application layer decides whether an element is
--     a bare source_records.id or a richer {source_id, locator} object;
--     validating that shape is this table's writer's job, not the DDL's.
--
-- Trigger-function naming (does NOT reuse migration 250's
--   ``reject_visa_immutable_mutation()``): that function's BODY is
--   generic (``RAISE EXCEPTION '% is append-only', TG_TABLE_NAME`` — no
--   table-specific logic) and would work unmodified on these three tables
--   too, but it has no ``SET search_path`` pinned. This migration's task
--   explicitly requires search_path-hardened trigger functions, and 250 is
--   off-limits to edit (sibling isolation — another agent's worktree is
--   simultaneously touching migration 251 and must see 250 completely
--   unchanged). Rather than silently piggyback on an unhardened shared
--   function, or reach into 250 to harden it (out of scope, and a footgun
--   for the sibling's concurrent work), this migration declares its OWN
--   equivalently-generic, search_path-hardened function
--   (``reject_visa_write_substrate_mutation()``) for its own three tables.
--   Every object below is explicitly ``public.``-qualified for the same
--   reason (defense against a search_path that has been tampered with
--   ahead of this transaction) — 250 did not do this; it is this
--   migration's own additional hardening, not a claim that 250 is wrong.
--
-- House style carried over from 250 (unchanged):
--   * ROLLBACK marker is the ENFORCED padded form (=== ROLLBACK ===)
--     (backend/db/migration_base.py:29 regex).
--   * No runtime GRANTs here — same rationale as 250: the roles this would
--     target (INSERT-only runtime role) do not exist in the CI/pre-push
--     clone (nuzantara_test), and a GRANT to a missing role aborts the
--     whole migration. Runtime grants for decisions-INSERT land with the
--     STEP-6c wiring PR, once the runtime role model is confirmed —
--     structural append-only enforcement below is already role-independent
--     defense-in-depth in the meantime.
--   * btree_gist: migration 250 already creates this extension; re-issuing
--     ``CREATE EXTENSION IF NOT EXISTS`` here is a documented no-op safety
--     net (this migration's visa_source_records EXCLUDE constraint needs
--     it, and depends on migration 250 having run first regardless, via
--     visa_decisions.rule_pack_id's FK to 250's visa_rule_packs — that
--     dependency is implicit in migration numbering, same as every other
--     migration in this directory).

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ---------------------------------------------------------------------------
-- visa_decisions — one row per engine evaluation (SHADOW today; ENFORCE once
-- PENDING-ARMS task #15 flips per Legge 5 authorization). See header for the
-- full column-by-column rationale.
-- ---------------------------------------------------------------------------
CREATE TABLE public.visa_decisions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- The engine's own Decision.decision_id (models.py) — the domain
    -- identity a caller/trace correlates against, distinct from this row's
    -- own surrogate `id`. UNIQUE: one persisted SHADOW row per evaluation.
    decision_id         UUID NOT NULL UNIQUE,
    environment         TEXT NOT NULL
        CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),
    jurisdiction         CHAR(2) NOT NULL DEFAULT 'ID'
        CHECK (jurisdiction = 'ID'),
    decision_domain      TEXT NOT NULL DEFAULT 'IMMIGRATION_VISA'
        CHECK (decision_domain = 'IMMIGRATION_VISA'),
    -- enums.py::EngineSurface, verbatim.
    engine_surface       TEXT NOT NULL
        CHECK (
            engine_surface IN (
                'CLOCK', 'MATCH', 'RECOMMEND', 'CATALOG', 'CHAT_CONTEXT', 'HANDOFF'
            )
        ),
    -- enums.py::EngineMode minus 'OFF' — an 'OFF' surface never evaluates,
    -- so it can never produce a row here.
    engine_mode          TEXT NOT NULL
        CHECK (engine_mode IN ('SHADOW', 'ENFORCE')),
    rule_pack_id         UUID REFERENCES public.visa_rule_packs (id),
    -- Denormalized for audit (spec section 5's own phrase for this exact
    -- field) — lets an auditor confirm which signed pack bytes produced
    -- this verdict without trusting rule_pack_id to still resolve to the
    -- same content later (packs are append-only/immutable per 250, so in
    -- practice it always will, but the audit trail should not depend on
    -- that fact holding forever).
    rule_pack_sha256     BYTEA
        CHECK (rule_pack_sha256 IS NULL OR octet_length(rule_pack_sha256) = 32),
    -- enums.py::DecisionState, verbatim — the exact enum the evaluator
    -- emits (Decision.state in models.py), NOT a generic tri-state guess.
    verdict              TEXT NOT NULL
        CHECK (
            verdict IN (
                'NEEDS_INPUT',
                'SUPPORTED_CANDIDATES',
                'HUMAN_REVIEW_REQUIRED',
                'NO_SUPPORTED_PATH',
                'TEMPORARILY_UNAVAILABLE'
            )
        ),
    -- Flattened citation array — see header note. Element shape is
    -- deliberately NOT constrained beyond "is a JSON array" (opaque to SQL,
    -- same precedent as 250's payload/protected_header columns).
    citations            JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(citations) = 'array'),
    -- The running engine build/release identity (distinct from the pack's
    -- own engine_contract_version/engine_min_version/engine_max_version).
    engine_version       TEXT NOT NULL,
    evaluated_at         TIMESTAMPTZ NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Mirrors migration 250's own visa_decisions CHECK from the spec:
    -- only a TEMPORARILY_UNAVAILABLE verdict may have a null rule_pack_id
    -- (an outage means no pack could even be selected).
    CHECK (verdict = 'TEMPORARILY_UNAVAILABLE' OR rule_pack_id IS NOT NULL)
);

CREATE INDEX idx_visa_decisions_rule_pack
    ON public.visa_decisions (rule_pack_id);

CREATE INDEX idx_visa_decisions_evaluated_at
    ON public.visa_decisions (evaluated_at);

-- ---------------------------------------------------------------------------
-- visa_decision_payloads — the PII-bearing side, held SEPARATE from
-- visa_decisions on purpose (UU PDP Law 2 / SYMBIOSIS Law 2): this table
-- carries ONLY opaque AEAD ciphertext + key/algorithm metadata. There is no
-- cleartext PII column anywhere on this table (or on visa_decisions/
-- visa_source_records) — no name/passport/email/phone column exists, by
-- design, and the structural test in test_write_substrate.py tripwires this
-- for future drift (a column added later that smuggles a PII-shaped name
-- would fail that test immediately). Column shape follows spec section 5's
-- own AEAD sketch for this exact table (AES-256-GCM: nonce + ciphertext +
-- aad + ciphertext_sha256), which is more precise than the STEP-6b task's
-- own shorthand ("encrypted_payload BYTEA") — ``ciphertext`` below IS that
-- column; the task's paraphrase and the spec's literal column name refer to
-- the same bytes.
-- ---------------------------------------------------------------------------
CREATE TABLE public.visa_decision_payloads (
    decision_id          UUID PRIMARY KEY REFERENCES public.visa_decisions (id),
    encryption_algorithm TEXT NOT NULL DEFAULT 'AES-256-GCM',
    encryption_key_id    TEXT NOT NULL,
    nonce                BYTEA NOT NULL CHECK (octet_length(nonce) = 12),
    -- The encrypted payload itself (task's "encrypted_payload BYTEA" ==
    -- this column) — ciphertext only, never cleartext, never a PII column.
    ciphertext           BYTEA NOT NULL,
    aad                  BYTEA NOT NULL,
    ciphertext_sha256    BYTEA NOT NULL CHECK (octet_length(ciphertext_sha256) = 32),
    purge_after          TIMESTAMPTZ NOT NULL,
    legal_hold           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Companion index for the (not-yet-built, STEP-6c+) retention/purge worker —
-- landed with the table now per spec section 5's own precedent, since it is
-- a pure DDL artifact with no runtime-role dependency.
CREATE INDEX idx_visa_decision_payloads_purge
    ON public.visa_decision_payloads (purge_after)
    WHERE legal_hold = FALSE;

-- ---------------------------------------------------------------------------
-- visa_source_records — the regulatory/pricing sources a verdict's
-- `citations` may point at. Column names/types follow
-- backend/services/visa_engine/models.py::SourceRecord (the actual Pydantic
-- contract this table backs) rather than the research doc's section-5 DDL
-- sketch verbatim, where the two diverge:
--   * `language` is added — the model requires it (NOT NULL,
--     ``^[a-z]{2}(-[A-Z]{2})?$``); the spec's section-5 sketch omits it
--     entirely, which would make this table unable to losslessly persist a
--     real SourceRecord.
--   * `version`/`recorded_period`/`supersedes_source_record_id` use the
--     model's own field names (not the sketch's shorter
--     `source_version`/`system_period`/`supersedes_id`) so a future
--     repository layer can bind columns to model fields 1:1 without a
--     translation table.
--   * The bitemporal EXCLUDE constraint (source_key + legal_period +
--     recorded_period, GiST) and the `-infinity` lower-bound guard on
--     legal_period both follow migration 250's own hardened pattern
--     ("valid_period TSTZRANGE [) with -infinity guard like 250").
-- Append-only (task's explicit instruction): a source record is never
-- edited in place — a correction is a NEW row with
-- `supersedes_source_record_id` pointing at the old one, exactly mirroring
-- how visa_rule_packs itself is append-only-by-sequence. Uses this
-- migration's own hardened trigger function (see header) rather than
-- migration 250's unhardened one.
-- ---------------------------------------------------------------------------
CREATE TABLE public.visa_source_records (
    id                          UUID PRIMARY KEY,
    source_key                  TEXT NOT NULL,
    version                     BIGINT NOT NULL CHECK (version > 0),
    authority_type               TEXT NOT NULL
        CHECK (
            authority_type IN (
                'PRIMARY_LAW',
                'IMPLEMENTING_REGULATION',
                'OFFICIAL_PORTAL',
                'OFFICIAL_CIRCULAR',
                'BALI_ZERO_POLICY',
                'PRICING_CATALOG'
            )
        ),
    status                       TEXT NOT NULL
        CHECK (status IN ('VERIFIED', 'SUPERSEDED', 'REVOKED', 'UNAVAILABLE')),
    jurisdiction                 CHAR(2) NOT NULL DEFAULT 'ID'
        CHECK (jurisdiction = 'ID'),
    title                        TEXT NOT NULL,
    publisher                    TEXT NOT NULL,
    canonical_url                TEXT NOT NULL,
    language                     TEXT NOT NULL
        CHECK (language ~ '^[a-z]{2}(-[A-Z]{2})?$'),
    document_number              TEXT,
    locators                     JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(locators) = 'array'),
    content_sha256               BYTEA NOT NULL CHECK (octet_length(content_sha256) = 32),
    legal_period                 TSTZRANGE NOT NULL,
    recorded_period               TSTZRANGE NOT NULL DEFAULT tstzrange(now(), NULL, '[)'),
    retrieved_at                 TIMESTAMPTZ NOT NULL,
    verified_at                  TIMESTAMPTZ NOT NULL,
    verified_by                  TEXT NOT NULL,
    supersedes_source_record_id  UUID REFERENCES public.visa_source_records (id),
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        NOT isempty(legal_period)
        AND lower_inc(legal_period)
        AND NOT upper_inc(legal_period)
        AND lower(legal_period) <> '-infinity'::timestamptz
    ),
    CHECK (
        NOT isempty(recorded_period)
        AND lower_inc(recorded_period)
        AND NOT upper_inc(recorded_period)
    ),
    UNIQUE (source_key, version),
    EXCLUDE USING gist (
        source_key WITH =,
        legal_period WITH &&,
        recorded_period WITH &&
    )
);

-- ---------------------------------------------------------------------------
-- Append-only guard for all three tables in this migration. Search-path
-- hardened (SET search_path = pg_catalog, pg_temp) per this migration's own
-- requirement — see header for why this does NOT reuse migration 250's
-- reject_visa_immutable_mutation(). The function body needs no other
-- schema-qualified references (TG_TABLE_NAME is a built-in trigger
-- variable, not a table lookup), so pinning search_path alone is
-- sufficient hardening here.
-- ---------------------------------------------------------------------------
CREATE FUNCTION public.reject_visa_write_substrate_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER visa_decisions_immutable
BEFORE UPDATE OR DELETE ON public.visa_decisions
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE TRIGGER visa_decision_payloads_immutable
BEFORE UPDATE OR DELETE ON public.visa_decision_payloads
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE TRIGGER visa_source_records_immutable
BEFORE UPDATE OR DELETE ON public.visa_source_records
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

-- === ROLLBACK ===
-- Drop tables first (their triggers/indexes/EXCLUDE constraint drop with
-- them). visa_decision_payloads references visa_decisions, so it must drop
-- first; visa_source_records self-references only, so its order relative to
-- the other two does not matter. Then drop the trigger function this
-- migration owns. Does NOT touch migration 250's visa_rule_packs/
-- visa_ruleset_activations/reject_visa_immutable_mutation() or btree_gist
-- (shared extension) — none of those are this migration's to drop.
DROP TABLE IF EXISTS public.visa_decision_payloads;
DROP TABLE IF EXISTS public.visa_decisions;
DROP TABLE IF EXISTS public.visa_source_records;
DROP FUNCTION IF EXISTS public.reject_visa_write_substrate_mutation();
