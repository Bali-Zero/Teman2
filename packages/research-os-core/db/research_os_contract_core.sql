-- DRAFT migration for symbolic reservation `research_os_contract_core`
-- (Research OS v1.0.0, Work Packet 04, sub-task D2 — persistence).
--
-- NOT YET INTEGRATED. Per the 2026-08-23 Conductor migration-ledger
-- decision (research/operations/execution/research-os-v1.0.0/SESSION-BOARD.md
-- §"Migration-ledger decision 001"): a packet reserves a SYMBOLIC name, never
-- an integer; the integer is bound at INTEGRATION time by the integrating
-- session, re-measured from a fresh `ls apps/backend-rag/backend/db/
-- migrations_v2/ | sort | tail` (`ls` is `eza` on this fleet — use the real
-- binary) plus an open-PR check, never copied from a document. Measured at
-- draft time (this file's own commit): head is migration 278
-- (278_reassign_orphaned_clients_setup_team.sql), base commit
-- 37a02fb721af68a0451451dba6e358297e314a06, zero open PRs touching
-- migrations_v2/ at that moment. DO NOT trust that number by the time this
-- file is copied into migrations_v2/ as `<N>_research_os_contract_core.sql`
-- — re-measure then. This file intentionally has NO numeric prefix so nothing
-- discovers or applies it from this location.
--
-- Purpose
-- -------
-- The canonical contract-core persistence substrate for `research-os/v1.0.0`
-- (research/operations/specs/evidence-to-action-freeze-2026-08-15/CONTRACTS.md,
-- frozen). CONTRACTS.md §21.1 assigns Work Packet 04 to "map existing schemas
-- to these semantics and own canonical validators and repositories" — this
-- migration is the repository half. §21.2: "Domain packets import the
-- canonical models; they may add adapters and namespaced extensions, not
-- parallel cores" — so this is deliberately ONE generic, polymorphic,
-- append-only object store spanning all 25 canonical kinds the freeze
-- defines (ObjectSuccessorEdge, RevocationReceipt, IntelEvent, Evidence,
-- Claim, DecisionPacket, TopicLock, CreativeLock, RequestedActionSpec,
-- ContentObject, MediaManifest, StoryCluster, WorkflowRun, ActionItem,
-- ActionIntent, ApprovalReceipt, ExecutionAttempt, OperationalReceipt,
-- VerificationReceipt, ConductorHandoff, OutcomeEvent, SanitizationReceipt,
-- RiskReclassificationReceipt, MetricProfile, MetricResult) — NOT 25 typed
-- tables. Domain packets (P02, P05, P06, P09, P12, P13, ...) build their own
-- projections/adapters on top of this substrate in their own migrations;
-- they do not get a parallel core (rule 21.2).
--
-- Why one generic table, not 25
-- ------------------------------
-- 1. CONTRACTS.md §2 makes every canonical object JSON-compatible, with a
--    frozen hash rule (RFC 8785 JCS canonicalization + SHA-256) implemented
--    once in Python (packages/research-os-core/research_os/hashing.py,
--    primitives.py) — never in SQL. This migration does NOT recompute or
--    verify `object_hash` in the database: JCS canonicalization (exact key
--    ordering, number formatting) is not something Postgres's `jsonb` text
--    output reproduces, and re-implementing RFC 8785 in PL/pgSQL would be a
--    second, driftable implementation of a rule this repo has already frozen
--    once in Python. Hash verification stays an application-layer
--    responsibility (D3/D4's adapters + parity probe).
-- 2. CONTRACTS.md §1.10: "Additive optional fields are minor." A generic
--    JSONB payload column absorbs additive schema growth for all 25 kinds
--    with zero ALTER TABLE — the kind-specific shape lives in the Pydantic
--    models (D1) and the checked-in `research_os/schemas/*.schema.json`,
--    not in a per-kind SQL column list that would fight that same rule.
-- 3. CONTRACTS.md §1.4 / §21 rule set: canonical objects are never
--    overwritten — corrections append a successor object plus an explicit
--    `ObjectSuccessorEdge`. `ObjectSuccessorEdge` is itself one of the 25
--    kinds and is stored as an ordinary row in this same table
--    (object_kind = 'object_successor_edge') — there is no separate
--    successor-tracking table in this migration; that would duplicate what
--    the canonical object already expresses.
--
-- Presence-preserving null semantics (WIRE RULE — do not violate)
-- -----------------------------------------------------------------
-- `research-os/v1.0.0` distinguishes an ABSENT field (omitted key) from a
-- field explicitly set to `None`/`null` (present key, JSON `null` value) —
-- see primitives.py module docstring: "an absent Pydantic field is omitted,
-- while a field explicitly set to None is serialized as JSON null... the
-- two are DIFFERENT documents that hash differently." PostgreSQL `jsonb`
-- already preserves this distinction natively: `'{"a": null}'::jsonb` keeps
-- the `"a"` key with a JSON null value, and a key never written is simply
-- absent from the object — `jsonb` does not coerce missing keys to nulls or
-- drop null-valued keys on storage or `->`/`->>` access. The `payload`
-- column below stores the exact canonical wire object bytes (the same JSON
-- an implementation hashes, INCLUDING the object's own `object_hash` field
-- as one of its keys — `object_hash` is excluded only from what gets fed
-- into the hash function itself, per hashing.py's `HASH_OMISSION_FIELDS`,
-- never from the stored/transmitted object). The one thing this migration
-- must NOT do, and does not do, is round-trip `payload` through any process
-- that would normalize/drop explicit nulls before it reaches this column —
-- that responsibility belongs to the writer (D3 adapters), not this schema.
--
-- object_kind / object_id are DERIVED sidecar columns, not copied JSON keys
-- ---------------------------------------------------------------------------
-- No canonical object carries literal top-level `object_kind` / `object_id`
-- fields on itself (those generic names are only used inside REFERENCE
-- substructures like `ExactObjectRef` and `inputs: [{object_kind, object_id,
-- object_hash}]` — see primitives.py `ExactObjectRef`). Each kind has its
-- own identity field name (`workflow_run_id`, `claim_id`, `evidence_id`,
-- ...). The `object_kind`/`object_id` columns here are therefore supplied
-- by the writer at insert time (it always knows which Pydantic model it is
-- persisting) — they are an indexing/identity sidecar over the polymorphic
-- payload, matching the `ExactObjectRef{object_kind, object_id, object_hash}`
-- shape CONTRACTS.md §3 defines as "never a family ID alone".
--
-- Global uniqueness (CONTRACTS.md §1.1)
-- ---------------------------------------
-- "IDs are globally unique, immutable, and never reused." `object_id` is
-- therefore UNIQUE across the whole table, not scoped per kind — a stronger
-- constraint than `(object_kind, object_id)`, and it is what the rule
-- actually says.
--
-- Append-only enforcement
-- ------------------------
-- Mirrors the established convention in
-- `apps/backend-rag/backend/db/migrations_v2/252_visa_engine_write_substrate.sql`
-- (`reject_visa_write_substrate_mutation`): a schema-qualified, search-path
-- hardened PL/pgSQL trigger function that unconditionally rejects UPDATE and
-- DELETE. This migration intentionally does NOT implement 252's more
-- elaborate retention-conditional DELETE guard (legal_hold / purge_after) —
-- CONTRACTS.md's `retention` primitive (retain_until / legal_hold /
-- rights_expires_at) implies a future controlled-purge process will need
-- one, but designing that policy is out of scope for a first, additive D2
-- migration and belongs with Work Packet 16 ("Controlled retirement") or a
-- dedicated follow-up once a purge policy is actually specified — not
-- guessed at here. Today: DELETE is always rejected, UPDATE is always
-- rejected, no exception.
--
-- PostgreSQL 15 compatibility (target is PG15, NOT 17 — CI runs
-- `postgres:15` per `tests.yml` ×2, `fly-deploy.yml`,
-- `intel-router-tests.yml`, `scripts-tests-sweep.yml`, and
-- `docker-compose.yml` pins `postgres:15-alpine`)
-- -----------------------------------------------------------------------
-- Every feature used here predates PG15 by a wide margin and none is
-- PG16+-only:
--   * `BIGSERIAL`            — SQL-standard-adjacent, present since PG7.x.
--   * `TEXT` / `CHAR(64)`    — core types, no version gate.
--   * `TIMESTAMPTZ`          — core type, no version gate.
--   * `JSONB`                — added PG9.4 (2014).
--   * `CHECK (... ~ ...)`    — POSIX regex operator, core since PG7.x.
--   * `jsonb_typeof()`       — added alongside `jsonb` itself, PG9.4.
--   * `CREATE INDEX ... USING gin (payload jsonb_path_ops)`
--                            — `jsonb_path_ops` GIN opclass added PG9.4.
--   * `BEFORE UPDATE OR DELETE ... FOR EACH ROW` trigger + PL/pgSQL
--     `RAISE EXCEPTION`      — core trigger mechanism, pre-PG8.
-- Nothing here is `CREATE INDEX CONCURRENTLY` (which cannot run inside a
-- transaction block, and `backend/db/migration_base.py::BaseMigration.apply()`
-- runs the entire forward SQL inside one `async with conn.transaction():`)
-- and nothing here is `MERGE`/`NULLS NOT DISTINCT`/any other PG15-or-later
-- addition — this migration would apply unchanged on PG12+.
--
-- Rollback marker convention
-- ----------------------------
-- Per `backend/db/migration_base.py:29`, the `-- === ROLLBACK ===` marker
-- below is mandatory for migrations numbered > 111 (this one will be, once
-- bound) and the runner's `split_migration_sql()` executes ONLY the forward
-- portion above the marker — the rollback portion is stored separately and
-- replayed only via `MigrationManager.rollback_migration()`, never appended
-- to the same transaction as the forward DDL.

CREATE TABLE public.research_os_objects (
    id BIGSERIAL PRIMARY KEY,

    -- Sidecar identity, supplied by the writer (see header) — not a copied
    -- JSON key.
    object_kind TEXT NOT NULL,

    -- CONTRACTS.md §1.1: globally unique, immutable, never reused.
    object_id TEXT NOT NULL,

    -- CONTRACTS.md §2: lowercase hex SHA-256, no algorithm prefix.
    object_hash CHAR(64) NOT NULL,

    -- CONTRACTS.md §3 primitives table: "Exact schema and semantics,
    -- initially research-os/v1.0.0". Pattern matches
    -- research_os/version.py::CONTRACT_FAMILY + SemanticVersion.
    contract_version TEXT NOT NULL,

    -- CONTRACTS.md §3 primitives table: "bali-zero unless a separately
    -- approved tenant exists".
    tenant TEXT NOT NULL DEFAULT 'bali-zero',

    -- The complete canonical wire object (RFC 8785 JCS input/output shape),
    -- INCLUDING its own object_hash field. Presence-preserving: an absent
    -- field is an absent JSON key, an explicit None is a present key with
    -- JSON null — jsonb preserves both natively. See header.
    payload JSONB NOT NULL,

    -- CONTRACTS.md §3 primitives table: "Immutable system-time instant at
    -- which this object version entered Nuzantara". Defaults to insertion
    -- time but is explicitly settable by the writer for replay/backfill
    -- (CONTRACTS.md §21.7: "Replay and rollback survive at least two
    -- complete, predeclared operating windows").
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT research_os_objects_object_id_key
        UNIQUE (object_id),

    CONSTRAINT research_os_objects_object_id_nonempty
        CHECK (object_id <> ''),

    -- Mirrors research_os/primitives.py::Identifier
    -- (`^[a-z][a-z0-9_-]*(?:\.[a-z0-9_-]+)*$`) — the closed identifier shape
    -- shared by every canonical field this pattern types, object_kind values
    -- included (e.g. 'workflow_run', 'object_successor_edge').
    CONSTRAINT research_os_objects_kind_format
        CHECK (object_kind ~ '^[a-z][a-z0-9_-]*(?:\.[a-z0-9_-]+)*$'),

    -- Mirrors research_os/hashing.py::SHA256_HEX_PATTERN.
    CONSTRAINT research_os_objects_hash_format
        CHECK (object_hash ~ '^[0-9a-f]{64}$'),

    -- Mirrors research_os/version.py::CONTRACT_FAMILY ("research-os") +
    -- SemanticVersion's strict N.N.N grammar. Deliberately NOT pinned to
    -- v1.0.0 alone so a future minor/major contract version can still be
    -- written without a schema change here.
    CONSTRAINT research_os_objects_contract_version_format
        CHECK (contract_version ~ '^research-os/v[0-9]+\.[0-9]+\.[0-9]+$'),

    CONSTRAINT research_os_objects_payload_is_object
        CHECK (jsonb_typeof(payload) = 'object')
);

COMMENT ON TABLE public.research_os_objects IS
    'Research OS v1.0.0 canonical contract-core: append-only polymorphic '
    'store for all 25 canonical object kinds frozen in '
    'research/operations/specs/evidence-to-action-freeze-2026-08-15/CONTRACTS.md. '
    'Work Packet 04 owns this table; domain packets build adapters/'
    'projections on top, never a parallel core (CONTRACTS.md 21.2).';

CREATE INDEX research_os_objects_kind_recorded_idx
    ON public.research_os_objects (object_kind, recorded_at DESC);

CREATE INDEX research_os_objects_payload_gin_idx
    ON public.research_os_objects USING gin (payload jsonb_path_ops);

-- ---------------------------------------------------------------------------
-- Append-only guard. Search-path hardened (SET search_path = pg_catalog,
-- pg_temp) — the function body needs no other schema-qualified reference
-- (TG_TABLE_NAME is a built-in trigger variable, not a table lookup), so
-- pinning search_path alone is sufficient hardening, same as migration 252's
-- reject_visa_write_substrate_mutation().
-- ---------------------------------------------------------------------------
CREATE FUNCTION public.reject_research_os_objects_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER research_os_objects_immutable
BEFORE UPDATE OR DELETE ON public.research_os_objects
FOR EACH ROW EXECUTE FUNCTION public.reject_research_os_objects_mutation();

-- === ROLLBACK ===

DROP TRIGGER IF EXISTS research_os_objects_immutable ON public.research_os_objects;
DROP FUNCTION IF EXISTS public.reject_research_os_objects_mutation();
DROP TABLE IF EXISTS public.research_os_objects;
