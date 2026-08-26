# Migration design notes — symbolic name `research_os_naga_claims`

**No migration file exists anywhere in this branch.** This document is design notes only, per
the corrected packet instruction (see README "Corrections applied"). Whoever builds P06 turns
this into a real file under `apps/backend-rag/backend/db/migrations_v2/` at that time, with a
**real integer prefix re-measured at the moment of creation** — never the number in this
document, never a number copied from `SESSION-BOARD.md`, `WAVE-0-DISPATCH.md`, or the packet spec
(all three have been observed stale on numbers at least once in this repo's history this week;
see `07-open-questions-and-corrections.md` for the specific instance found in *this* session).

## Which migration system

`grep` confirms two independent migration systems in this repo:

1. `apps/backend-rag/backend/migrations/migration_0NN_*.py` — the system NAGA's own tables (079,
   081) live under. Async Python `apply(conn)`/`rollback(conn)` functions, run by
   `backend/db/migration_manager.py` (per the project's own architecture notes in
   `apps/backend-rag/CLAUDE.md`, not independently re-verified this session).
2. `apps/backend-rag/backend/db/migrations_v2/NNN_*.sql` — the system `research_os_contract_core`
   (279) and the WhatsApp-broker migrations (270-274) live under, with the `-- ===
   ROLLBACK ===` marker convention documented in `apps/backend-rag/CLAUDE.md` ("Migration Runner
   Was Executing ROLLBACK Section In-Transaction" scar).

**`research_os_objects` (P04's own substrate) is a `migrations_v2` (`.sql`) migration** —
confirmed by `279_research_os_contract_core.sql` existing on disk and matching the file name
`contract-pass-001.md §7` and §8's table both cite. Since this packet's deliverables extend P04's
object model (not NAGA's legacy tables), **`research_os_naga_claims` belongs in
`migrations_v2/`, as a `.sql` file, not in `backend/migrations/`** — it is additive to the P04
object substrate, not to the legacy NAGA tables (which are untouched — see §"What this migration
does NOT do" below). This is a design recommendation, not something this lane can verify by
running a migration (forbidden by this lane's mandate regardless of correctness).

## What this migration creates (design, not SQL)

Additive only, mirroring `279_research_os_contract_core.sql`'s and `280_research_os_objects_
truncate_guard.sql`'s pattern (both exist on disk; not read in full this session — flagged as
unread in the README — but their file names and `contract-pass-001.md §7`'s description of
`research_os_objects` as "additive... carries a real rollback section" give enough to design
against without risking a hallucinated column list for a table this lane cannot query).

1. **No new bespoke tables for `Claim`/`Evidence` if `research_os_objects` already provides a
   generic typed-object store** — per `contract-pass-001.md §7`, `research_os_objects` is
   "schema-ready in the strict sense," additive, and its apply→rollback→re-apply cycle has been
   proven against a throwaway DB. If its shape is a generic object store keyed by
   `(object_kind, object_id, object_hash)` (consistent with every P04 schema's shared
   `ExactObjectRef` shape), NAGA's canonical claims and evidence should be **rows in that same
   table** with `object_kind = "claim"` / `"evidence"`, not a parallel `naga_claims_canonical`
   table. **This is a recommendation this lane cannot confirm**, because `research_os_objects` is
   applied in no environment and its actual column list was not read from the migration file
   this session (out of this lane's write perimeter to open and re-derive without risking scope
   creep into P04 territory the packet reserves for the P04 lane). Flagged as an open question:
   whoever builds P06 must read `279_research_os_contract_core.sql` directly before deciding
   table-per-kind vs. shared-table.
2. **If a shared table is not the right fit**, the fallback design is two additive tables,
   `research_os_naga_claims` and `research_os_naga_evidence`, column-for-column mirroring the
   `Claim`/`Evidence` JSON Schemas' **required** fields (see `02-p04-adapter-mapping.md` §1/§2
   for the exact field list and types), plus a `raw_object JSONB` column holding the full
   validated object (schema-first, not column-first — the JSON Schema is the source of truth,
   the relational columns exist only for the indexes the packet's exit thresholds need: by
   `claim_family_id`, by `status`, by `time.valid_from`/`valid_to` for the bitemporal queries, by
   `review.state` for the review queue).
3. **Successor/transition record**: no new table — reuse the `ObjectSuccessorEdge` shape (see
   `02-p04-adapter-mapping.md` §3), stored the same way (`research_os_objects` row with
   `object_kind = "object_successor_edge"`, or a dedicated additive table if §1 resolves to
   table-per-kind).
4. **Rollback section**: drops only what this migration creates. It must **never** touch
   `naga_claims`, `naga_sources`, `naga_claim_evidence`, `naga_claim_transitions`, or
   `naga_sessions` — those are owned by migrations 079/081 and are explicitly out of this
   packet's file ownership ("Do not own... " boundary in the packet, and the dispatch's forbidden
   list: "editing NAGA runtime or schema").

## What this migration does NOT do

- Does not alter `naga_claims` or any of the other 4 legacy tables in any way (no new column, no
  new index, no trigger). The packet's own "Shadow, canary, and rollback" section requires
  "Legacy readers remain authoritative until parity is demonstrated" — an unmodified legacy
  schema is the simplest way to guarantee that requirement is not accidentally violated by a
  well-meaning ALTER TABLE.
- Does not backfill. Migration 081's own backfill `UPDATE` (see baseline §1) is the pattern to
  avoid repeating here for anything but a throwaway/test dataset: canonical objects should be
  produced by the adapter's normal write path (dual-write, packet step 7), not by a one-time bulk
  SQL backfill that a later code change cannot retroactively correct (the exact problem flagged in
  baseline §2 point 4, where the Python expiry rule and the migration-081 SQL backfill rule are
  two independent copies of one policy).
- Does not touch `apps/nuzantara-mcp/**` or `app/routers/naga.py`. Both are consumers (baseline
  §5/§6); wiring them to read/write canonical objects is explicitly downstream build work, not
  migration work, and is out of this lane's forbidden-list ("consumer invalidation, draft
  mutation, publishing, or any client-facing action").

## Rollback proof obligation (per packet's own test list: "migration apply/rollback and temporal exclusion tests")

Whoever creates the real migration file must, at minimum, reproduce the proof
`contract-pass-001.md §7` already ran for `research_os_objects` itself: apply → rollback →
re-apply against a throwaway database, and confirm via `to_regclass()` (or the `migrations_v2`
equivalent) that the table is genuinely absent after rollback, not just that the migration runner
reported success. `01-naga-baseline-inventory.md §1` notes NAGA's own migration 079 has a test
file (`test_migration_079_naga.py`) but migration 081 apparently does not — this migration should
not repeat that omission.

## The symbolic name itself

`research_os_naga_claims` is the exact string the dispatching session assigned this packet. It
should be used as: the migration file's descriptive suffix once a real integer is assigned
(`NNN_research_os_naga_claims.sql`), and as a stable string key anywhere design notes,
fixtures, or the eventual PR need to refer to "this packet's migration" before an integer exists.
It is **not** a table name commitment — see §"What this migration creates" point 1, where the
actual table(s) may end up being `research_os_objects` rows rather than a table literally named
`research_os_naga_claims`.
