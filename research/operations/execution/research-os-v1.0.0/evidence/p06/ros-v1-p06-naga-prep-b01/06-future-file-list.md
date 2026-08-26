---
date: 2026-08-26
domain: operations
adversarial_review: kimi-k3
---

# Exact future file list (for whoever builds P06)

None of these files exist in this branch. Paths are proposed, following the existing repo
conventions verified in `01-naga-baseline-inventory.md` (mirrors NAGA's own
`services/naga/**` / `core/claims/**` / `tests/services/naga/**` layout).

## Migration

- `apps/backend-rag/backend/db/migrations_v2/NNN_research_os_naga_claims.sql` — real integer
  bound at creation time, per `03-migration-design-notes.md`. Includes `-- === ROLLBACK ===`
  section per this repo's own migration-runner convention (`apps/backend-rag/CLAUDE.md`'s
  documented scar on that exact marker).

## Canonical adapter and service layer (additive, does not touch existing `services/naga/**`)

- `apps/backend-rag/backend/services/research_os/naga_claim_adapter.py` — reads `naga_claims` +
  `naga_claim_evidence` + `naga_sources` rows, produces canonical `Claim`/`Evidence` objects per
  `02-p04-adapter-mapping.md`. Owns the abstention logic (refuse to write when G-STATEMENT/G2
  cannot be satisfied — see fixture `abstention/01_high_confidence_no_source_span.json`).
- `apps/backend-rag/backend/services/research_os/naga_bitemporal_store.py` — read/write for the
  canonical store (whichever of the two shapes `03-migration-design-notes.md` §"What this
  migration creates" point 1 resolves to), including the time-travel query functions.
- `apps/backend-rag/backend/services/research_os/naga_transition_service.py` — writes
  `ObjectSuccessorEdge`-shaped records on supersession/contradiction, with the
  reconstruct-from-claim fallback described in `02-p04-adapter-mapping.md` §3.
- `apps/backend-rag/backend/services/research_os/naga_invalidation_service.py` — emits
  `OperationalReceipt`-shaped invalidation events (deliverable #7), idempotent on trigger natural
  key (see `05-test-matrix.md` invalidation-replay row).
- `apps/backend-rag/backend/services/research_os/naga_review_queue.py` — deliverable #8's human
  review queue, built on `OperationalReceipt` rather than `ApprovalReceipt` per gap G7 — unless
  the Conductor widens `ApprovalSubjectKind` first, in which case this should be revisited.
- `apps/backend-rag/backend/services/research_os/naga_evidence_independence.py` — deliverable #4,
  the original/syndicated/translated/derived classifier referenced in the
  `evidence_independence/*` fixtures. Genuinely new logic, not an adapter.

## Migration/atomization support (resolves gaps G-STATEMENT and G2 together — they share one root cause: no structured extraction exists yet)

- `apps/backend-rag/backend/services/research_os/naga_statement_atomizer.py` — the "human/rule-
  assisted" safe-incumbent atomizer the packet mandates (deliverable #3), producing
  `statement.{subject_ref, predicate, object_ref_or_value}` + a real `source_span` together, since
  both require the same underlying "read the actual quoted text" step. Automated-extraction
  variant, if built later, is a **separate, `MetricProfile`-gated candidate** per the packet's own
  instruction — do not fold it into this file as a default path.

## Tests (see `05-test-matrix.md` for the full table; paths repeated here for a single-glance list)

```
apps/backend-rag/backend/tests/migrations/test_migration_research_os_naga_claims.py
apps/backend-rag/backend/tests/services/research_os/naga/test_bitemporal_queries.py
apps/backend-rag/backend/tests/services/research_os/naga/test_transitions.py
apps/backend-rag/backend/tests/services/research_os/naga/test_source_span.py
apps/backend-rag/backend/tests/services/research_os/naga/test_contradiction_status.py
apps/backend-rag/backend/tests/services/research_os/naga/test_time_travel.py
apps/backend-rag/backend/tests/services/research_os/naga/test_invalidation_replay.py
apps/backend-rag/backend/tests/services/research_os/naga/test_sensitivity_boundary.py
apps/backend-rag/backend/tests/services/research_os/naga/test_review_authorization.py
```

## Consumer-facing wiring (explicitly LAST — packet Non-goal forbids doing this before shadow parity)

- `apps/backend-rag/backend/app/routers/naga.py` — add a shadow-read path behind a feature flag,
  comparing canonical-store answers to legacy `naga_claims` answers without changing the response
  the caller sees (packet: "Legacy readers remain authoritative until parity is demonstrated").
- `apps/nuzantara-mcp/nuzantara_mcp/tools/naga.py` — same shadow-read treatment, once the router
  path is proven.

Neither of the two files immediately above should be touched until the shadow-read parity
measurement (packet Implementation sequence step 8: "Review mismatches and calibrate thresholds
before expanding") has run and been reviewed by someone with the authority this preparation lane
does not have.


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
