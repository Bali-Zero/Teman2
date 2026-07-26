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
--
-- STEP-6b FIX-FIRST round amendments (2026-07-19/20 -- cross-family verify
--   round, 9 findings; 2 explicitly deferred to PENDING-ARMS; 2 explicitly
--   rejected):
--   * P0 -- visa_decision_payloads gains UNIQUE (encryption_key_id, nonce):
--     an AEAD nonce must never repeat under the same key (nonce reuse
--     breaks GCM's confidentiality guarantee outright) -- the DB now
--     enforces this structurally rather than trusting the (not-yet-built)
--     writer alone.
--   * P0/P1 -- visa_decisions gains a search_path-pinned, public.-qualified
--     BEFORE INSERT trigger (reject_visa_decision_pack_binding) resolving
--     rule_pack_id (when NOT NULL) and enforcing: decision.environment/
--     jurisdiction/decision_domain equal the referenced pack's own values,
--     and decision.rule_pack_sha256 (when provided) equals the pack's
--     payload_sha256 -- mirrors migration 250's own payload-binding-trigger
--     style. A TEMPORARILY_UNAVAILABLE row with a NULL rule_pack_id skips
--     the whole check (there is no pack to bind against).
--   * P1 -- visa_decisions gains ruleset_activation_id (nullable FK to
--     migration 250's visa_ruleset_activations) plus effective_at/
--     observed_at (Decision.effective_at/observed_at in models.py -- the
--     evaluator's own two independent clocks, distinct from evaluated_at,
--     which is wall-clock "when the engine ran"). The same binding trigger
--     additionally enforces, ONLY when ruleset_activation_id IS NOT NULL:
--     the referenced activation's rule_pack_id equals the decision's own,
--     its legal_period contains effective_at, and its system_period
--     contains observed_at -- a decision can never claim to have been
--     evaluated against an activation window it falls outside of.
--   * P1/P2 -- per-table mutation-guard redesign (separate functions per
--     table rather than one shared TG_TABLE_NAME-branching function, now
--     that two of the three tables need real conditional bodies):
--       - visa_decisions stays blanket append-only (pure audit log, no
--         legitimate update/delete path) -- unchanged, still
--         reject_visa_write_substrate_mutation().
--       - visa_decision_payloads (reject_visa_decision_payloads_mutation):
--         the ONLY legal UPDATE flips legal_hold with every other column
--         (including the decision_id primary key) unchanged; the ONLY
--         legal DELETE requires purge_after < now() AND legal_hold = FALSE
--         -- the retention/purge worker's entire contract, enforced at the
--         DB layer independent of the worker's own correctness.
--       - visa_source_records (reject_visa_source_records_mutation): the
--         ONLY legal UPDATE closes an open recorded_period (upper NULL ->
--         finite) with every other column, including the lower bound and
--         primary key, unchanged -- mirrors migration 250's
--         reject_visa_activation_mutation() close carve-out exactly, and
--         is what makes the supersession flow real (INSERT the new row
--         with supersedes_source_record_id set, THEN close the superseded
--         row's recorded_period). DELETE stays always-forbidden (no
--         legitimate reason to erase a superseded-but-still-historical
--         source record). The triggers driving these two functions were
--         renamed from *_immutable to *_guard (the tables are no longer
--         strictly immutable -- a lying trigger name is its own bug class).
--   * P2 -- visa_source_records gains a search_path-pinned, public.-
--     qualified BEFORE INSERT trigger
--     (reject_visa_source_record_supersedes_mismatch) requiring, when
--     supersedes_source_record_id IS NOT NULL: it does not equal the new
--     row's own id (self-reference -- the bare FK alone cannot catch this,
--     since IMMEDIATE FK checks run at end-of-statement, after the new row
--     already exists), and the referenced row exists AND shares the same
--     source_key (a supersession is a same-lineage correction, never a
--     cross-source relabeling).
--   * P2 -- cheap CHECKs mirroring models.py::SourceRecord's own Pydantic
--     bounds (title/publisher/canonical_url length, locators array length,
--     version upper bound) plus encryption_algorithm pinned to the single
--     value the column defaults to, plus recorded_period gains the same
--     "lower bound is never -infinity" guard legal_period already has.
--   * DEFERRED to PENDING-ARMS (not resolved here -- see
--     .claude/skills/modus/PENDING-ARMS.md): visa_decisions.citations array
--     elements are still not validated to reference real visa_source_records
--     rows -- that needs the STEP-6c writer/repository layer, not a
--     DDL-only migration. (A second deferred item this migration's own
--     header used to list here -- migration 250's trigger functions lacking
--     SET search_path -- was independently CLOSED by migration 251
--     [STEP-6a], landed on main after this migration was first authored:
--     251's CREATE OR REPLACE FUNCTION re-declares all 4 of 250's trigger
--     functions, byte-identical logic, with SET search_path = pg_catalog,
--     pg_temp pinned on each. Verified on disk at merge time, 2026-07-20 --
--     the PENDING-ARMS line has been marked closed accordingly, not left
--     stale.)
--   * REJECTED (reviewed, deliberately NOT implemented): (1) narrowing
--     engine_mode's CHECK to drop 'ENFORCE' -- this migration's whole point
--     is that the SAME schema serves SHADOW today and ENFORCE once
--     PENDING-ARMS task #15 flips, with no later ALTER needed; narrowing it
--     now would just re-widen it later for no safety benefit. (2) a DB-side
--     CHECK/trigger recomputing ciphertext_sha256 via pgcrypto's digest()
--     -- this migration deliberately keeps cryptographic verification out
--     of SQL (same precedent as migration 250 leaving payload_sha256/
--     signature verification to the Python layer); ciphertext_sha256 here
--     is a caller-supplied integrity marker the application layer checks,
--     not a DB-computed one.

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
    -- STEP-6b FIX-FIRST P1: the specific bitemporal activation (migration
    -- 250's visa_ruleset_activations) this decision was evaluated against,
    -- when known. Nullable — a TEMPORARILY_UNAVAILABLE row has neither a
    -- pack nor an activation to bind against, and even a pack-bearing row
    -- may come from a caller that does not thread the activation id
    -- through; the binding trigger below only checks containment when
    -- this column is set.
    ruleset_activation_id UUID REFERENCES public.visa_ruleset_activations (id),
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
    -- STEP-6b FIX-FIRST P1: Decision.effective_at/observed_at (models.py) —
    -- the evaluator's own two independent bitemporal clocks ("as of when is
    -- this legally true" vs "as of when did the system consider it true"),
    -- distinct from evaluated_at below (wall-clock "when the engine
    -- actually ran"). Bound against ruleset_activation_id's own
    -- legal_period/system_period by the binding trigger when that column
    -- is set.
    effective_at         TIMESTAMPTZ NOT NULL,
    observed_at          TIMESTAMPTZ NOT NULL,
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
    -- STEP-6b FIX-FIRST P2: pinned to the single value the column defaults
    -- to — this migration does not (yet) support a second AEAD algorithm,
    -- so a row claiming otherwise is a bug, not a future-proofing choice.
    encryption_algorithm TEXT NOT NULL DEFAULT 'AES-256-GCM'
        CHECK (encryption_algorithm = 'AES-256-GCM'),
    encryption_key_id    TEXT NOT NULL,
    nonce                BYTEA NOT NULL CHECK (octet_length(nonce) = 12),
    -- The encrypted payload itself (task's "encrypted_payload BYTEA" ==
    -- this column) — ciphertext only, never cleartext, never a PII column.
    ciphertext           BYTEA NOT NULL,
    aad                  BYTEA NOT NULL,
    ciphertext_sha256    BYTEA NOT NULL CHECK (octet_length(ciphertext_sha256) = 32),
    purge_after          TIMESTAMPTZ NOT NULL,
    legal_hold           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- STEP-6b FIX-FIRST P0: an AEAD nonce must never repeat under the same
    -- key — reusing (key, nonce) breaks GCM's confidentiality guarantee
    -- outright. Structural enforcement here, independent of whether the
    -- (not-yet-built) writer gets nonce generation right.
    UNIQUE (encryption_key_id, nonce)
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
    -- STEP-6b FIX-FIRST P2: upper bound mirrors
    -- models.py::SourceRecord.version (Field(ge=1, le=9_007_199_254_740_991,
    -- strict=True)) -- BIGINT's own range is wider than the model allows,
    -- so without this a value the model would reject could still land via
    -- a raw INSERT bypassing Pydantic.
    version                     BIGINT NOT NULL CHECK (version > 0 AND version <= 9007199254740991),
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
    -- STEP-6b FIX-FIRST P2: length bounds mirror
    -- models.py::SourceRecord's own Field constraints (min_length=1,
    -- max_length=512/256 respectively) so a raw INSERT bypassing Pydantic
    -- cannot smuggle a shape the model would reject.
    title                        TEXT NOT NULL
        CHECK (char_length(title) BETWEEN 1 AND 512),
    publisher                    TEXT NOT NULL
        CHECK (char_length(publisher) BETWEEN 1 AND 256),
    -- models.py caps canonical_url at max_length=2048 with no lower bound
    -- (mirrored exactly -- no minimum added beyond the existing NOT NULL).
    canonical_url                TEXT NOT NULL
        CHECK (char_length(canonical_url) <= 2048),
    language                     TEXT NOT NULL
        CHECK (language ~ '^[a-z]{2}(-[A-Z]{2})?$'),
    document_number              TEXT,
    -- models.py caps locators at max_length=64.
    locators                     JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(locators) = 'array' AND jsonb_array_length(locators) <= 64),
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
    -- STEP-6b FIX-FIRST P2: recorded_period gains the same "lower bound is
    -- never -infinity" guard legal_period already has above.
    CHECK (
        NOT isempty(recorded_period)
        AND lower_inc(recorded_period)
        AND NOT upper_inc(recorded_period)
        AND lower(recorded_period) <> '-infinity'::timestamptz
    ),
    -- STEP-6b gate round-2 fix (2026-07-20): mirrors the trigger-level
    -- guard in reject_visa_source_records_mutation() below at the table
    -- level, so even a direct raw INSERT/UPDATE (bypassing the trigger's
    -- own re-close carve-out logic, e.g. a superuser or a future writer
    -- bug) cannot set a non-finite ('infinity') recorded_period upper
    -- bound on a row that otherwise looks "closed". `upper(...) IS NULL`
    -- is the legitimate open-ended default (unbounded -- see column
    -- default above) and stays allowed; only the explicit 'infinity'
    -- sentinel value is rejected.
    CHECK (
        upper(recorded_period) IS NULL
        OR upper(recorded_period) <> 'infinity'::timestamptz
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

-- ---------------------------------------------------------------------------
-- STEP-6b FIX-FIRST P0/P1: decision-pack scope binding. Mirrors migration
-- 250's reject_visa_pack_payload_mismatch() binding-trigger style. The
-- pack-binding checks (environment/jurisdiction/decision_domain/
-- rule_pack_sha256) are skipped when rule_pack_id IS NULL (the only legal
-- case: TEMPORARILY_UNAVAILABLE, which has no pack to bind against) -- but
-- the ruleset_activation_id containment checks are NOT: those run
-- whenever ruleset_activation_id IS NOT NULL, independent of rule_pack_id
-- (STEP-6b gate round-2 fix, 2026-07-20 -- see the function body comment
-- for why the two used to be wrongly coupled). See the header amendment
-- above for the full rationale.
-- ---------------------------------------------------------------------------
CREATE FUNCTION public.reject_visa_decision_pack_binding()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    pack RECORD;
    activation RECORD;
BEGIN
    -- Pack-binding block: only meaningful when there IS a pack to bind
    -- against. A TEMPORARILY_UNAVAILABLE row (rule_pack_id NULL) has none,
    -- so ONLY this block -- environment/jurisdiction/decision_domain/
    -- rule_pack_sha256 -- is skipped when rule_pack_id IS NULL.
    --
    -- STEP-6b gate round-2 fix (2026-07-20, Codex gpt-5.6-sol FIX-FIRST):
    -- this used to be a single early `IF NEW.rule_pack_id IS NULL THEN
    -- RETURN NEW; END IF;` that skipped the ENTIRE function, INCLUDING the
    -- ruleset_activation_id containment block below -- so a row with
    -- rule_pack_id=NULL + ruleset_activation_id NOT NULL + an arbitrary/
    -- mismatched activation was admitted with ZERO validation of that
    -- reference (nothing else forbids that combination -- the table's own
    -- CHECK only ties verdict='TEMPORARILY_UNAVAILABLE' to rule_pack_id,
    -- never to ruleset_activation_id). Per this migration's own header
    -- amendment, the activation-containment check is gated "ONLY when
    -- ruleset_activation_id IS NOT NULL" -- independent of rule_pack_id's
    -- nullness. Restructured so the rule_pack_id-NULL case skips only the
    -- pack-binding checks; the activation-containment block below always
    -- runs when ruleset_activation_id IS NOT NULL, regardless.
    IF NEW.rule_pack_id IS NOT NULL THEN
        SELECT environment, jurisdiction, decision_domain, payload_sha256
            INTO pack
            FROM public.visa_rule_packs
            WHERE id = NEW.rule_pack_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'visa_decisions references unknown rule_pack_id %', NEW.rule_pack_id;
        END IF;

        IF NEW.environment IS DISTINCT FROM pack.environment
           OR NEW.jurisdiction IS DISTINCT FROM pack.jurisdiction
           OR NEW.decision_domain IS DISTINCT FROM pack.decision_domain THEN
            RAISE EXCEPTION 'visa_decisions scope (env=% jur=% domain=%) does not match referenced rule_pack % (env=% jur=% domain=%)',
                NEW.environment, NEW.jurisdiction, NEW.decision_domain,
                NEW.rule_pack_id, pack.environment, pack.jurisdiction, pack.decision_domain;
        END IF;

        IF NEW.rule_pack_sha256 IS NOT NULL AND NEW.rule_pack_sha256 IS DISTINCT FROM pack.payload_sha256 THEN
            RAISE EXCEPTION 'visa_decisions.rule_pack_sha256 does not match referenced rule_pack % payload_sha256',
                NEW.rule_pack_id;
        END IF;
    END IF;

    -- Activation-containment block: independent of rule_pack_id's
    -- nullness, gated solely on ruleset_activation_id IS NOT NULL (see
    -- header amendment). Always resolves the activation and enforces
    -- legal_period/system_period containment, regardless of whether the
    -- pack-binding block above ran.
    IF NEW.ruleset_activation_id IS NOT NULL THEN
        SELECT rule_pack_id, legal_period, system_period
            INTO activation
            FROM public.visa_ruleset_activations
            WHERE id = NEW.ruleset_activation_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'visa_decisions references unknown ruleset_activation_id %', NEW.ruleset_activation_id;
        END IF;
        -- The activation<->rule_pack cross-check only makes sense when
        -- there IS a rule_pack_id to compare against (a TEMPORARILY_
        -- UNAVAILABLE row has none, by the table's own CHECK) -- skip it
        -- rather than comparing against NULL, which activation.rule_pack_id
        -- (itself NOT NULL) could never legitimately equal.
        IF NEW.rule_pack_id IS NOT NULL
           AND activation.rule_pack_id IS DISTINCT FROM NEW.rule_pack_id THEN
            RAISE EXCEPTION 'visa_decisions.ruleset_activation_id % belongs to a different rule_pack than rule_pack_id %',
                NEW.ruleset_activation_id, NEW.rule_pack_id;
        END IF;
        IF NOT (activation.legal_period @> NEW.effective_at) THEN
            RAISE EXCEPTION 'visa_decisions.effective_at % is outside referenced activation % legal_period %',
                NEW.effective_at, NEW.ruleset_activation_id, activation.legal_period;
        END IF;
        IF NOT (activation.system_period @> NEW.observed_at) THEN
            RAISE EXCEPTION 'visa_decisions.observed_at % is outside referenced activation % system_period %',
                NEW.observed_at, NEW.ruleset_activation_id, activation.system_period;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER visa_decisions_pack_binding
BEFORE INSERT ON public.visa_decisions
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_decision_pack_binding();

-- ---------------------------------------------------------------------------
-- STEP-6b FIX-FIRST P1/P2: visa_decision_payloads dedicated guard (replaces
-- the blanket reject_visa_write_substrate_mutation() this table used
-- before). The ONLY legal UPDATE flips legal_hold (every other column,
-- including the decision_id primary key, must be unchanged); the ONLY
-- legal DELETE requires purge_after < now() AND legal_hold = FALSE. Trigger
-- renamed from *_immutable to *_guard -- the table is no longer strictly
-- immutable, and a lying trigger name is its own bug class.
-- ---------------------------------------------------------------------------
CREATE FUNCTION public.reject_visa_decision_payloads_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.purge_after IS NOT NULL AND OLD.purge_after < now() AND OLD.legal_hold = FALSE THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION 'visa_decision_payloads is append-only (delete requires purge_after elapsed and legal_hold=false)';
    END IF;

    IF OLD.decision_id IS DISTINCT FROM NEW.decision_id
       OR OLD.encryption_algorithm IS DISTINCT FROM NEW.encryption_algorithm
       OR OLD.encryption_key_id IS DISTINCT FROM NEW.encryption_key_id
       OR OLD.nonce IS DISTINCT FROM NEW.nonce
       OR OLD.ciphertext IS DISTINCT FROM NEW.ciphertext
       OR OLD.aad IS DISTINCT FROM NEW.aad
       OR OLD.ciphertext_sha256 IS DISTINCT FROM NEW.ciphertext_sha256
       OR OLD.purge_after IS DISTINCT FROM NEW.purge_after
       OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
        RAISE EXCEPTION 'visa_decision_payloads is append-only outside the legal_hold-only carve-out';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visa_decision_payloads_guard
BEFORE UPDATE OR DELETE ON public.visa_decision_payloads
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_decision_payloads_mutation();

-- ---------------------------------------------------------------------------
-- STEP-6b FIX-FIRST P1/P2: visa_source_records dedicated guard (replaces
-- the blanket reject_visa_write_substrate_mutation() this table used
-- before). The ONLY legal UPDATE closes an open recorded_period (upper
-- NULL -> finite), mirroring migration 250's reject_visa_activation_mutation()
-- close carve-out exactly -- this is what makes the supersession flow real
-- (INSERT the new row with supersedes_source_record_id set, THEN close the
-- superseded row's recorded_period). DELETE stays always-forbidden. Trigger
-- renamed from *_immutable to *_guard for the same lying-name reason as
-- visa_decision_payloads above.
-- ---------------------------------------------------------------------------
CREATE FUNCTION public.reject_visa_source_records_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'visa_source_records is append-only (delete is never permitted)';
    END IF;

    IF OLD.id IS DISTINCT FROM NEW.id
       OR OLD.source_key IS DISTINCT FROM NEW.source_key
       OR OLD.version IS DISTINCT FROM NEW.version
       OR OLD.authority_type IS DISTINCT FROM NEW.authority_type
       OR OLD.status IS DISTINCT FROM NEW.status
       OR OLD.jurisdiction IS DISTINCT FROM NEW.jurisdiction
       OR OLD.title IS DISTINCT FROM NEW.title
       OR OLD.publisher IS DISTINCT FROM NEW.publisher
       OR OLD.canonical_url IS DISTINCT FROM NEW.canonical_url
       OR OLD.language IS DISTINCT FROM NEW.language
       OR OLD.document_number IS DISTINCT FROM NEW.document_number
       OR OLD.locators IS DISTINCT FROM NEW.locators
       OR OLD.content_sha256 IS DISTINCT FROM NEW.content_sha256
       OR OLD.legal_period IS DISTINCT FROM NEW.legal_period
       OR OLD.retrieved_at IS DISTINCT FROM NEW.retrieved_at
       OR OLD.verified_at IS DISTINCT FROM NEW.verified_at
       OR OLD.verified_by IS DISTINCT FROM NEW.verified_by
       OR OLD.supersedes_source_record_id IS DISTINCT FROM NEW.supersedes_source_record_id
       OR OLD.created_at IS DISTINCT FROM NEW.created_at
       OR lower(OLD.recorded_period) IS DISTINCT FROM lower(NEW.recorded_period) THEN
        RAISE EXCEPTION 'visa_source_records is append-only outside the recorded_period-close carve-out';
    END IF;
    IF upper(OLD.recorded_period) IS NOT NULL THEN
        RAISE EXCEPTION 'visa_source_records recorded_period already closed, cannot re-close';
    END IF;
    -- STEP-6b gate round-2 fix (2026-07-20, Codex gpt-5.6-sol FIX-FIRST):
    -- `upper(...) IS NULL` alone does not reject a non-finite close.
    -- Postgres distinguishes an unbounded range end (constructed with a
    -- NULL upper argument -- upper() returns NULL, upper_inf() = true)
    -- from a range whose upper bound is explicitly the sentinel value
    -- 'infinity'::timestamptz (upper() returns 'infinity', a NON-NULL
    -- value, yet upper_inf() is STILL false) -- so a caller "closing" a
    -- row with upper='infinity' passed the old NULL-only check while
    -- remaining functionally open-ended forever: a supersession dead-end
    -- (the row can never be re-closed -- see the guard immediately above
    -- -- and the GiST EXCLUDE constraint still treats it as overlapping
    -- any new row over the same source_key/legal_period). Reject both.
    IF upper(NEW.recorded_period) IS NULL
       OR upper(NEW.recorded_period) = 'infinity'::timestamptz THEN
        RAISE EXCEPTION 'visa_source_records close must set a finite recorded_period upper bound';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visa_source_records_guard
BEFORE UPDATE OR DELETE ON public.visa_source_records
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_source_records_mutation();

-- ---------------------------------------------------------------------------
-- STEP-6b FIX-FIRST P2: supersedes_source_record_id integrity. Requires,
-- when set: it does not equal the new row's own id (self-reference -- the
-- bare FK alone cannot catch this, since IMMEDIATE FK checks run at
-- end-of-statement, after the new row already exists), and the referenced
-- row exists AND shares the same source_key (a supersession is a
-- same-lineage correction, never a cross-source relabeling).
-- ---------------------------------------------------------------------------
CREATE FUNCTION public.reject_visa_source_record_supersedes_mismatch()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    prior RECORD;
BEGIN
    IF NEW.supersedes_source_record_id IS NULL THEN
        RETURN NEW;
    END IF;
    IF NEW.supersedes_source_record_id = NEW.id THEN
        RAISE EXCEPTION 'visa_source_records.supersedes_source_record_id cannot reference its own row (id=%)', NEW.id;
    END IF;
    SELECT source_key INTO prior
        FROM public.visa_source_records
        WHERE id = NEW.supersedes_source_record_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'visa_source_records.supersedes_source_record_id % does not reference an existing row', NEW.supersedes_source_record_id;
    END IF;
    IF prior.source_key IS DISTINCT FROM NEW.source_key THEN
        RAISE EXCEPTION 'visa_source_records supersession must share the same source_key (superseded=% new=%)',
            prior.source_key, NEW.source_key;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visa_source_records_supersedes_binding
BEFORE INSERT ON public.visa_source_records
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_source_record_supersedes_mismatch();

-- ---------------------------------------------------------------------------
-- BEFORE TRUNCATE guards (P2 fix, verify-round finding): Postgres row-level
-- triggers (FOR EACH ROW, above) do NOT fire on the TRUNCATE statement -- any
-- role holding TRUNCATE privilege on these tables could otherwise wipe the
-- SHADOW audit trail in a single statement with zero trigger enforcement.
-- Postgres only fires STATEMENT-level triggers for that statement, so these
-- are FOR EACH STATEMENT, reusing the same
-- reject_visa_write_substrate_mutation() function -- its body
-- (`RAISE EXCEPTION '% is append-only', TG_TABLE_NAME`) references only the
-- built-in TG_TABLE_NAME variable, never NEW/OLD, so it is already valid for
-- statement-level invocation on that DDL trigger event with no body change
-- required. Deliberately still the BLANKET reject for all three tables --
-- the row-level carve-outs above are narrow by design and do not extend to
-- a bulk statement-level wipe.
-- ---------------------------------------------------------------------------
CREATE TRIGGER visa_decisions_no_wipe
BEFORE TRUNCATE ON public.visa_decisions
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE TRIGGER visa_decision_payloads_no_wipe
BEFORE TRUNCATE ON public.visa_decision_payloads
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE TRIGGER visa_source_records_no_wipe
BEFORE TRUNCATE ON public.visa_source_records
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

-- === ROLLBACK ===
-- Drop tables first (their triggers/indexes/EXCLUDE constraint drop with
-- them). visa_decision_payloads references visa_decisions, so it must drop
-- first; visa_source_records self-references only, so its order relative to
-- the other two does not matter. Then drop the trigger functions this
-- migration owns. Does NOT touch migration 250's visa_rule_packs/
-- visa_ruleset_activations/reject_visa_immutable_mutation() or btree_gist
-- (shared extension) — none of those are this migration's to drop.
DROP TABLE IF EXISTS public.visa_decision_payloads;
DROP TABLE IF EXISTS public.visa_decisions;
DROP TABLE IF EXISTS public.visa_source_records;
DROP FUNCTION IF EXISTS public.reject_visa_write_substrate_mutation();
DROP FUNCTION IF EXISTS public.reject_visa_decision_pack_binding();
DROP FUNCTION IF EXISTS public.reject_visa_decision_payloads_mutation();
DROP FUNCTION IF EXISTS public.reject_visa_source_records_mutation();
DROP FUNCTION IF EXISTS public.reject_visa_source_record_supersedes_mismatch();
