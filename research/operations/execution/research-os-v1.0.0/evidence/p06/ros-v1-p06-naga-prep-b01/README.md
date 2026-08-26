# P06 NAGA Claim Ledger — Preparation Bundle (lane B2, ros-v1-p06-naga-prep-b01)

**Status:** PREPARATION ONLY. Nothing in this bundle claims P06 implementation readiness.
**Scope:** read-only NAGA inventory, adapter mapping against P04 canonical types, migration
*design notes* (no migration file created or applied), a golden-set plan with a representative
synthetic fixture sample, and a test matrix. No NAGA runtime or schema was edited. No migration
was created or applied, at any number, in this branch.

## How to read this bundle

| File | Contents |
|---|---|
| `01-naga-baseline-inventory.md` | What exists today in NAGA — tables, services, consumers, tests. Measured this session. |
| `02-p04-adapter-mapping.md` | Field-by-field mapping from NAGA's live schema to the P04 canonical `Claim`/`Evidence` typed models, with every vocabulary/semantic gap named explicitly. |
| `03-migration-design-notes.md` | Design for the additive canonical store. Symbolic name only (`research_os_naga_claims`) — no integer, no SQL file, per the corrected packet instruction. |
| `04-golden-set-and-adversarial-plan.md` | The 200–300 claim golden-set design (categories, counts, sourcing method) plus the adversarial-case checklist from the packet, each case pointed at a fixture in `fixtures/`. |
| `fixtures/**` | A **representative sample** (14 items) of synthetic/public fixtures, one or more per adversarial category. This is NOT the golden set itself — see `04-golden-set-and-adversarial-plan.md` §"What this bundle does and does not deliver". |
| `05-test-matrix.md` | Maps the packet's "Tests and metrics" list to concrete (unwritten) test files and what each must prove false to count as evidence. |
| `06-future-file-list.md` | Exact file paths for the eventual implementation, owned by whoever picks up P06 build. |
| `07-open-questions-and-corrections.md` | Everything I could not close, plus corrections found in frozen documents (dispatch prompt, contract-pass-001, and the packet spec itself) during this session. |

## Corrections applied from the dispatch prompt (re-verified independently, not taken on faith)

1. **Migration numbering.** The packet spec (`06-naga-claim-ledger.md` line 16) says "Migration
   `273` is reserved for this packet." Measured on disk this session:
   `apps/backend-rag/backend/db/migrations_v2/273_wa_broker_completion_digest.sql` exists and is
   unrelated (WhatsApp broker). The real head is
   `apps/backend-rag/backend/db/migrations_v2/287_garuda_practices.sql`, and the sequence is
   **not dense** — `282` is missing between `281_garuda_voa_retention.sql` and
   `283_wa_reply_claims.sql`. So "count the files" and "take the packet's literal number" both
   give a wrong integer; only "max + 1, re-measured at the moment of integration" is correct.
   This bundle therefore uses the **symbolic name `research_os_naga_claims`** everywhere a
   migration is discussed, and states explicitly in `03-migration-design-notes.md` that the
   integer is bound at integration time, never copied from any document including this one.
2. **What "migration 273 forbidden" actually protects.** WAVE-0-DISPATCH.md line 327 forbids
   "applying or creating migration 273 in the preparation branch." Since 273 is the WhatsApp
   broker's own migration, read literally this would forbid nothing relevant to NAGA. I read it,
   per the dispatching session's correction, as the intended rule: **do not create, edit, or
   apply ANY migration file, under any number, in this branch.** No migration file exists
   anywhere in this branch — verified with `git status` and `find` before writing this file and
   again before the final commit (see `07-open-questions-and-corrections.md` for the exact
   commands run).

## What I did NOT do (explicit, per the anti-hallucination discipline in the dispatch)

- Did not read the full `apps/backend-rag/backend/services/naga/orchestrator.py`,
  `gateway.py`, `actions/action_engine.py`, or any `quality/*.py` file line-by-line — I read
  `persist.py` in full (it is the single write path into the tables this packet must supersede)
  and grepped the rest for table/model references to build the consumer index. Anyone
  implementing P06 should read those files before writing adapters against them; this bundle's
  claims about their *behavior* are limited to what `persist.py` and the grep hits show.
- Did not run the existing NAGA test suite (`backend/tests/services/naga/**`,
  `backend/tests/migrations/test_migration_079_naga.py`) — this branch has no Python environment
  action requested and running tests was not necessary to produce read-only design artifacts.
  Whoever builds P06 should run it first as a baseline.
- Did not query any live database. `research_os_objects` and `naga_claims` states asserted here
  come from `contract-pass-001.md §7` (for `research_os_objects`) and from migration source
  files `079`/`081` (for `naga_claims`), not from a live query — this branch has no DB
  credentials and querying one would be outside a preparation-only lane in any case.
- Did not touch `apps/nuzantara-mcp/**` beyond `grep`-locating it as a consumer.
