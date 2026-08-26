---
date: 2026-08-26
domain: operations
adversarial_review: kimi-k3
---

# Golden-set plan and adversarial-case checklist

## What this bundle does and does not deliver

The packet asks for a "200–300 claim golden set with exact source spans, temporal truth,
contradictions, supersessions, and no-answer cases" (Implementation sequence step 2). **This
bundle delivers the plan for that set — categories, target counts, sourcing method, labeling
schema — plus a representative sample of 15 synthetic fixtures, one or more per adversarial
category from the packet's own list.** It does not deliver 200–300 labeled claims. Producing the
full set requires either (a) real Indonesian regulatory source documents hand-annotated by
someone with the domain authority to certify "this is the correct claim/status/span," which is
review/certification work outside a preparation-only lane's forbidden list boundary
("consumer invalidation, draft mutation, publishing, or any client-facing action" — labeling a
golden set that downstream review treats as ground truth is adjacent enough to "publishing
truth" that this lane should not self-certify it), or (b) a defined extraction+review pipeline
that does not exist yet (see `02-p04-adapter-mapping.md` G-STATEMENT/G2, both blocking).
Claiming the full 200–300 set as delivered here would be exactly the "true but partial finding"
this repo's own doctrine warns against — a plan that reads as complete while missing the part
nobody would think to check for. Stating the gap here is the deliverable, not a hedge around it.

## Target composition (plan, not yet executed)

| Category (from packet's "Golden set and adversarial cases") | Target count | Sourcing method |
|---|---:|---|
| Indonesian regulatory changes (general) | 40 | Real Permenkumham/PP/Perpres text, hand-selected for unambiguous claim extraction, reviewed by a domain owner before certification |
| Effective dates distinct from publication dates | 25 | Regulations with an explicit "berlaku sejak" clause dated after the announcement/publication date |
| Amended/repealed rules | 25 | Pairs: original rule + its amendment/repeal, to exercise supersession |
| Conflicting secondary sources | 20 | Two or more outlets reporting the same regulatory event with materially different details (fee amount, deadline, scope) |
| Currency/units | 15 | Fee/price claims in IDR vs. USD, or ambiguous unit claims (per-year vs. per-application) |
| Ambiguous subjects | 15 | Claims whose subject (which visa class, which company type) is underspecified in the source text |
| Translated passages | 15 | A claim whose only source is a non-Indonesian, non-English translation (evidence-independence: translated stance) |
| Expired prices/deadlines | 15 | Claims whose `valid_to` has passed relative to a fixed "as of" query date |
| Missing official sources | 10 | Claims corroborated only by secondary/syndicated sources, no primary government source found |
| Intentionally unanswerable questions | 15 | Queries with no supporting claim in the set at all — pure abstention cases |
| **Total** | **~195** | Below the packet's 200-300 floor by design — the remaining 5-105 are reserved for the adversarial cases below, several of which need dedicated claims not covered by the table rows above. |

Plus the packet's explicit adversarial-case list (deliverable-adjacent, listed separately because
several need a *pair* of claims, not one row):

1. A high-confidence model has no source span → **abstention** fixture category.
2. Five websites repeat one original story → **evidence-independence (syndicated)** fixture
   category.
3. A later correction predates Nuzantara's discovery → **bitemporal** fixture category (the
   `recorded_at` of the correcting claim is after `recorded_at` of the original, but the
   correction's `valid_from` predates it — this is the "what did Nuzantara believe at date Y"
   test case, and it is the single case that most directly exercises the packet's mandatory
   distinction between valid-time and system-time).
4. The same sentence contains two atomic claims → **statement-atomization boundary** fixture
   category (directly exercises G-STATEMENT from the adapter mapping).
5. A claim is true nationally but false in a local jurisdiction → **scope/jurisdiction** fixture
   category.
6. Evidence is restricted and only a sanitized projection is permitted → **sanitization boundary**
   fixture category — this one must stay entirely synthetic/schematic (no real restricted content
   exists in this bundle at all, per the forbidden-list PII rule) and shows the *shape* of the
   projection, not real restricted material.

## Representative sample delivered in `fixtures/`

15 synthetic, clearly-labeled files, one or more per category above. **CORRECTED 2026-08-26:
the original set was 14 and claimed "one or more per category" while case 6 (the
sanitization boundary) had NO fixture — the one category where a missing negative control
costs the most. `fixtures/sanitization/01_restricted_evidence_sanitized_projection.json`
was added to close it.** Every fixture:

- Uses a fictional or explicitly-marked-synthetic Indonesian regulation number (e.g.
  `"Permenkumham SYNTH-12/2026"`), a `example.go.id` / `example.org` source domain, and a
  `SYNTHETIC — do not treat as regulatory fact` field at the top level.
- Contains **no real client data, no real NAGA claim/evidence row content, no real case
  identifiers**, matching the packet's forbidden-list line "PII: absolutely no real NAGA
  claim/evidence rows anywhere — not in a fixture." **CORRECTED 2026-08-26 (adversarial
  review, `07` §B4): the stronger claim that once stood here — "this is not 'real data with
  names changed' — it is invented from the category description" — was false as a blanket
  statement.** The PII guarantee above holds and is the one that matters; the purity claim did
  not. `supersession/01` embeds the real IDR 2,500,000,000 PMA paid-up figure and the IDR 10B
  exception threshold; `scope_jurisdiction/01` embeds a real "paling lambat 7 hari" finding.
  None of it is client PII and each is noted in place, so this was never deception — but a file
  stamped `SYNTHETIC — do not treat as regulatory fact` carries real regulatory figures that
  this bundle did NOT re-verify, which is the worst of both readings. Whoever builds the golden
  set must either replace them with invented numbers or re-ground them against the live corpus.
  Do not cite them as validated.
- Is shaped as a `{claim, evidence[]}` pair using the field names from
  `02-p04-adapter-mapping.md` (i.e. these are draft canonical objects, not NAGA DB rows) so a
  future adapter-conformance test can validate them directly against `claim.schema.json` /
  `evidence.schema.json` once real code exists to run that validation. **CORRECTED 2026-08-26
  (adversarial review): as delivered they would NOT validate, and the original hedge covered
  only "we did not run it", not "it would fail." Both schemas are `additionalProperties: false`
  at every level (14 occurrences in `claim.schema.json`, 9 in `evidence.schema.json`), and the
  fixtures (a) carry an extraneous `note` key the schema rejects outright and (b) omit most
  required fields — Claim requires `evidence_refs, classification, review, lineage, retention,
  object_hash`; Evidence requires `evidence_family_id, source_event_ref, document_version_id,
  document_content_hash, source_tier, provenance, classification.rights, review_state,
  retention, object_hash`. These fixtures are BEHAVIOUR SPECS, not schema instances; whoever
  builds the conformance test must fill the required fields first.** This bundle does not run
  such validation itself (no Python execution was performed in this lane; see README "What I did
  NOT do").

| File | Adversarial case it targets |
|---|---|
| `fixtures/bitemporal/01_correction_predates_discovery.json` | Case 3 — later correction predates discovery |
| `fixtures/bitemporal/02_effective_date_after_publication.json` | "effective dates distinct from publication dates" |
| `fixtures/bitemporal/03_time_travel_query_example.json` | Packet deliverable #2 — "what was true at date X / what did Nuzantara believe at date Y" worked example, showing two revisions and the two different query answers |
| `fixtures/contradiction/01_two_sources_conflict_on_fee.json` | "conflicting secondary sources" |
| `fixtures/contradiction/02_partial_contradiction_mixed_evidence.json` | The G4 aggregate-status derivation case from the adapter mapping — one claim, one supporting evidence_ref, one contradicting evidence_ref |
| `fixtures/supersession/01_amendment_supersedes_original.json` | "amended/repealed rules" — uses the `ObjectSuccessorEdge` shape from `02-p04-adapter-mapping.md` §3 |
| `fixtures/abstention/01_high_confidence_no_source_span.json` | Case 1 — high-confidence model, no source span (must be REJECTED at canonical-write time per G2, not silently accepted — fixture shows the expected rejection, not an accepted bad object) |
| `fixtures/abstention/02_intentionally_unanswerable.json` | "intentionally unanswerable questions" — a query with zero matching claims, and the expected abstention response shape |
| `fixtures/source_span/01_structured_span_example.json` | Shows the structured `source_span` shape (`locator`, `start`/`end`, `quote_hash`) that G2 requires and NAGA's `source_span_hint` today cannot produce |
| `fixtures/evidence_independence/01_syndicated_five_sources.json` | Case 2 — five sources, one original story, tagged `original`/`syndicated` |
| `fixtures/evidence_independence/02_translated_passage.json` | "translated passages" |
| `fixtures/scope_jurisdiction/01_national_true_local_false.json` | Case 5 — true nationally, false in a local jurisdiction |
| `fixtures/invalidation/01_evidence_withdrawn_event.json` | Packet deliverable #7 — invalidation event shape when a source is withdrawn, using the `OperationalReceipt` queue-only profile per `02-p04-adapter-mapping.md` §4 |
| `fixtures/invalidation/02_two_atomic_claims_one_sentence.json` | Case 4 — statement-atomization boundary |

## Labeling schema used across all fixtures

```json
{
  "synthetic": true,
  "fixture_category": "<one of the table rows above>",
  "adversarial_case_ref": "<packet section reference, e.g. 'packet §Golden set and adversarial cases, case 3'>",
  "expected_behavior": "<what a correct P06 implementation must do with this input — the falsifiable claim>",
  "claim": { ... draft Claim-shaped object, or 'null' if the case is pre-atomization ... },
  "evidence": [ ... draft Evidence-shaped objects ... ]
}
```

The `expected_behavior` field exists specifically so this bundle answers, per fixture, "what
would make this fixture's use FALSE" — the anti-hallucination discipline's own standing question
for every verification claim. A fixture with no stated `expected_behavior` is not useful as a
test input, only as a data sample; every fixture in this bundle has one.


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
