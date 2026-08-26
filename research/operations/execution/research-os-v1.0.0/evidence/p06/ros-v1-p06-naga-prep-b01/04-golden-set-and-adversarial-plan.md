# Golden-set plan and adversarial-case checklist

## What this bundle does and does not deliver

The packet asks for a "200–300 claim golden set with exact source spans, temporal truth,
contradictions, supersessions, and no-answer cases" (Implementation sequence step 2). **This
bundle delivers the plan for that set — categories, target counts, sourcing method, labeling
schema — plus a representative sample of 14 synthetic fixtures, one or more per adversarial
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

14 synthetic, clearly-labeled files, one or more per category above. Every fixture:

- Uses a fictional or explicitly-marked-synthetic Indonesian regulation number (e.g.
  `"Permenkumham SYNTH-12/2026"`), a `example.go.id` / `example.org` source domain, and a
  `SYNTHETIC — do not treat as regulatory fact` field at the top level.
- Contains **no real client data, no real NAGA claim/evidence row content, no real case
  identifiers**. This is not "real data with names changed" — it is invented from the category
  description, matching the packet's forbidden-list line "PII: absolutely no real NAGA
  claim/evidence rows anywhere — not in a fixture."
- Is shaped as a `{claim, evidence[]}` pair using the field names from
  `02-p04-adapter-mapping.md` (i.e. these are draft canonical objects, not NAGA DB rows) so a
  future adapter-conformance test can validate them directly against `claim.schema.json` /
  `evidence.schema.json` once real code exists to run that validation — this bundle does not run
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
