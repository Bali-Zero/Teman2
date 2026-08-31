---
date: 2026-08-26
domain: operations
adversarial_review: kimi-k3
---

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


## Adversarial review

**Seat:** Kimi K3 (`kimi -m kimi-code/k3`), cross-family — neither the model that wrote this
bundle nor the session that gated it. Run 2026-08-26 against a FROZEN diff (head `bb6d9ceb9`):
the generator was dead before the refuter was dispatched.

**Verdict: DEFECTIVE.** The bundle is unusually honest about what it did not do, and its two
load-bearing corrections (migration numbering, the G7 `ApprovalSubjectKind` gap) check out
independently. But its fixture set was internally inconsistent in exactly the D11 area the review
was aimed at, and its central baseline claim rested on one search pattern. Every finding was
re-verified against disk by the gating session before acceptance — the refuter is not trusted
either (superscar #6). That re-verification made finding 1 **worse** than reported.

| # | Finding | Verified | Disposition |
|---|---|---|---|
| 1 | "`persist.py` is the only writer" came from an `INSERT INTO naga_` grep, blind to UPDATE by construction | TRUE, **and worse** | **FIXED** — four UPDATE writers named (`dedup.py:144`, `claim_scorer.py:202`, `expiry.py:58`, `:174`). The gating session also found the cited INSERT grep is *itself* wrong: `dedup.py:155` and `expiry.py:154` insert into `naga_claim_transitions`, one of the same 5 tables, and `persist.py` never writes it. Five writers across three files, not one |
| 2 | "`quality_score` written once" contradicted by two post-insertion UPDATEs | TRUE | **FIXED** — written *first*, not once |
| 3 | §2 point 5's open mystery ("what moves a claim out of `active`") is answered in a file it listed but never searched | TRUE | **FIXED** — `expiry.py:58` / `dedup.py:144`. The `review_status` half STANDS: nothing moves a claim out of `auto_extracted`, so the human-review gate has no exit path in code |
| 4 | Supersession requires two coupled writes on an immutable content-hashed object; D10/D11 forbidden by §7 | TRUE (`object_hash` required, `claim.schema.json:618`) | **NOT FIXED — RAISED AS BLOCKING** (`07` §B1). Patching it means choosing an answer this bundle has no authority to choose |
| 5 | `bitemporal/01` and `supersession/01` encode contradictory predecessor conventions; `bitemporal/01` trips the test matrix's own "FALSE if" | TRUE | **NOT FIXED — RAISED AS BLOCKING** (`07` §B2). Picking a convention IS answering §B1; both left visible |
| 6 | `bitemporal/03` uses `supersedes_claim_ref` for calendared succession, not correction | TRUE | **RAISED** (`07` §B3) |
| 7 | `invalidation/01` withdraws evidence `...e7` and asserts it affects claim `...0030` — a citation that exists nowhere in the fixture set | TRUE | **FIXED** — trigger now withdraws `...e2`, which `0030` genuinely cites. A PASS on the original data would have proven nothing |
| 8 | "one or more per adversarial category" false — case 6 (sanitization boundary) had no fixture | TRUE (14 files, 8 dirs, no sanitization) | **FIXED** — fixture added; 15 files. This was the one category where a missing negative control costs most |
| 9 | Evidence adapter mapping is four required fields short: `evidence_family_id`, `review_state`, `classification.rights`, `times.recorded_at` | TRUE (0 grep hits each; all four in the schema's required sets) | **FIXED** — §2's completeness claim corrected; closing them is a build precondition |
| 10 | "Fixtures validate directly against the schemas" — they would fail today (extraneous `note`, most required fields absent, `additionalProperties: false` throughout) | TRUE | **FIXED** — restated as behaviour specs; the old hedge covered "we did not run it", not "it would fail" |
| 11 | "100% invented, not real-data-renamed" overstated — real PMA capital figures embedded | TRUE | **RAISED** (`07` §B4) — transparent, no PII, but a synthetic-stamped file now carries an unverified real figure |
| 12 | G5 attributes a URL hash to "the migration" (it is `persist.py:102`), and omits the `[:16]` / `[:32]` truncations | TRUE, low severity | **ACCEPTED AS LIMIT** — substance (hash of URL, not content) is correct |

**Not a finding** (refuter checked, found sound): migration numbering — `273` is WhatsApp-broker,
head is 287, 282 absent, symbolic name correct; the G7 `ApprovalSubjectKind` closed-enum gap;
`ObjectSuccessorEdge` and `OperationalReceipt` required-field claims; the abstention fixture's
`reasoning.py` attribution (re-exported from `reasoning_utils.py`); and implementation-readiness,
which is disclaimed consistently throughout.

**Bottom line:** usable as an inventory and a gap list. **Not** to be handed to a build lane until
§B1 and §B2 in `07-open-questions-and-corrections.md` are ruled on.
