---
date: 2026-08-26
domain: operations
adversarial_review: kimi-k3
---

# Test matrix

Maps the packet's own "Tests and metrics" list (verbatim category names) to concrete future test
files and the fixture(s) each would consume. **No test file exists in this branch.** This is a
plan a build lane implements; writing it here satisfies the packet's "test matrix" deliverable at
the preparation stage without writing code this lane is forbidden from writing (no NAGA runtime
edits, no migration).

For every row, the "what would make this FALSE" column exists because a test plan without a
falsification condition is not a test plan — it is a checklist item, per this session's own
anti-hallucination discipline.

| Packet test category | Future file (proposed) | Consumes fixture(s) | What would make this test FALSE (i.e. what it actually proves) |
|---|---|---|---|
| migration apply/rollback | `apps/backend-rag/backend/tests/migrations/test_migration_research_os_naga_claims.py` | none (schema-level) | Table exists after apply, absent after rollback, re-apply succeeds a second time from clean. Mirrors the proof `contract-pass-001.md §7` already ran for `research_os_objects` — see `03-migration-design-notes.md` "Rollback proof obligation." FALSE if: table survives rollback, or re-apply errors on "already exists" instead of being idempotent. |
| temporal exclusion tests | `apps/backend-rag/backend/tests/services/research_os/naga/test_bitemporal_queries.py` | `fixtures/bitemporal/*.json` | Given two overlapping-`valid_from`/non-overlapping-`recorded_at` revisions (fixture 01), a query at a fixed instant returns exactly one row, never two, never zero when one is genuinely valid. **CORRECTED 2026-08-26 (B1):** that guarantee cannot come from valid-time alone. Both revisions in fixture 01 share `valid_from` and both keep `valid_to: null` -- because B1 forbids closing the predecessor's interval as a side effect of supersession -- so a pure valid-time predicate returns BOTH, which is this row's own FALSE condition. The query under test is therefore the composite one: valid-time interval **and** the system-time cutoff (`recorded_at <= instant`, which fixture 01's `expected_behavior` already names as the gate) **and** exclusion of any row that has a successor edge. FALSE if: the composite query returns both revisions for one instant, returns none when one is genuinely in-interval, or achieves the single-row answer by writing `valid_to` onto the predecessor. |
| transition property tests | `apps/backend-rag/backend/tests/services/research_os/naga/test_transitions.py` | `fixtures/supersession/01_amendment_supersedes_original.json` | A predecessor that has a successor edge is excluded from "current claim" queries **while remaining byte-identical to how it was written** -- per RULING Zero 2026-08-26 (B1) the `superseded` state is derived at read from the edge, never stored on the object; the edge is independently reconstructible from the successor's own `supersedes_claim_ref` (see fixture's `expected_behavior`). FALSE if: a predecessor with a successor still appears in a "current" query, or the edge cannot be reconstructed after being deleted, **or any field of the predecessor differs after supersession from what was originally persisted** -- the last one is the ruling's own tripwire, and the earlier wording of this row ("is marked `superseded`") demanded exactly the write it forbids. |
| source-span hash/locator tests | `apps/backend-rag/backend/tests/services/research_os/naga/test_source_span.py` | `fixtures/source_span/01_structured_span_example.json` | `sha256(document_text[start:end]) == quote_hash` for every stored `Evidence.source_span`. FALSE if: any canonical Evidence object exists whose `quote_hash` does not match a re-slice of its own `locator` content, OR if the adapter accepted an object with a synthesized/placeholder hash (the abstention fixture `01_high_confidence_no_source_span.json` is the negative control for this — the adapter must refuse, not fabricate). |
| contradiction and supersession tests | `apps/backend-rag/backend/tests/services/research_os/naga/test_contradiction_status.py` | `fixtures/contradiction/*.json` | Aggregate `status` derivation follows the rule proposed in `02-p04-adapter-mapping.md` G4 (any `contradicts` present → `contradicted`, never silently outvoted by a majority of `supports`). FALSE if: fixture `02_partial_contradiction_mixed_evidence.json` (2 supports, 1 contradicts) resolves to `supported`. |
| time-travel correctness tests | `apps/backend-rag/backend/tests/services/research_os/naga/test_time_travel.py` | `fixtures/bitemporal/03_time_travel_query_example.json` | Both named query types (`valid_time` and `system_time`) in the fixture return their stated `expected_answer_claim_id` (including the `null` case, which must abstain, not error or guess). FALSE if: any of the 3 queries in that fixture returns a claim_id other than the one stated. |
| invalidation idempotency and replay tests | `apps/backend-rag/backend/tests/services/research_os/naga/test_invalidation_replay.py` | `fixtures/invalidation/*.json` | Replaying the same `evidence_withdrawn` event twice produces exactly one `OperationalReceipt` / review action, not two (idempotency keyed on the trigger's natural key, e.g. `evidence_id + withdrawn_at`), and produces zero automatic content mutations (per fixture's "must_not_happen" list). This is the test that stands in for the atomicity D10/D11 does not provide — see `02-p04-adapter-mapping.md` §3's "Caveat, explicit per the contract-pass boundary." FALSE if: replay creates a duplicate receipt, OR any public content/draft changes as a side effect. |
| privacy/sensitivity boundary tests | `apps/backend-rag/backend/tests/services/research_os/naga/test_sensitivity_boundary.py` | none in this bundle — see `07-open-questions-and-corrections.md` for why `classification.sensitivity` policy is an open question, not yet assignable | Dual-write to canonical storage only proceeds for claims whose derived `classification.sensitivity == "public"`; anything `internal`/`confidential`/`restricted_osint`/`client_pii` stays legacy-only during the shadow phase, per packet's "Dual-write one public domain first." FALSE if: any non-public-sensitivity claim reaches canonical storage during the shadow/canary phase. |
| critical claim review authorization tests | `apps/backend-rag/backend/tests/services/research_os/naga/test_review_authorization.py` | none in this bundle | Whatever mechanism P06 build chooses in place of `ApprovalReceipt` (see gap G7 — `OperationalReceipt` recommended) enforces that only an authorized `actor_ref` can move a claim's `review.state` from `unreviewed`/`machine_checked` to `human_approved`. FALSE if: a claim reaches `human_approved` with no `actor_ref` recorded, or with an `actor_ref` whose `purpose` (per `ActorRef.purpose` enum in the schema) is not `"approval"`. |

## Exit-threshold traceability (packet's own numbers, mapped to the above)

| Packet exit threshold | Which test(s) above must pass for it to hold |
|---|---|
| 100% source-span coverage for critical claims | source-span hash/locator tests + abstention enforcement (the negative-control fixture) |
| ≥98% precision for reviewed supported critical claims on the golden set | Requires the full 200-300 golden set (not delivered — see `04-golden-set-and-adversarial-plan.md`) and is therefore **not testable from this bundle alone**. Flagged, not claimed closed. |
| zero unsupported critical claims eligible for public use | contradiction/status-derivation tests + sensitivity-boundary tests together (a claim must be both evidentially `supported` AND `sensitivity: public` before reaching a public-facing consumer) |
| ≥95% bitemporal query correctness | temporal exclusion tests + time-travel correctness tests, run against the full golden set once it exists — this bundle's 3 bitemporal fixtures are a necessary but not sufficient sample size for a percentage claim |
| every claim transition and downstream invalidation traceable | transition property tests + invalidation idempotency/replay tests |
| bounded invalidation emitted within 15 min canary / 60 min max SLA | **Not testable from static fixtures** — requires a running system with a clock; this is an operational/canary-phase measurement, out of scope for a preparation bundle by construction. |
| independent legal/factual reviewer passes the sampled claims | **Not a code test at all** — a human/process step. Not something any file in this bundle can satisfy; noted so no future reader mistakes an automated test's PASS for this threshold being met. |


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
