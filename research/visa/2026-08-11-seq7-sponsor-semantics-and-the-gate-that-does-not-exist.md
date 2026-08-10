---
date: 2026-08-11
domain: visa
client_case: none (Visa Oracle V2 rule pack seq-7)
adversarial_review: codex
sources:
  - research/visa/2026-08-11-w3-sponsor-rules-factbase.md
  - research/visa/2026-08-10-seq6-requirements-are-not-walls.md
  - rulepack-prod-006.source.json (seq-6, active in SHADOW)
  - rulepack-prod-007.source.json (seq-7, this note, unsigned and unactivated)
  - evaluator.py (evaluate_product precedence)
  - backend/tests/services/visa_engine/test_seq6_refuter_witnesses.py
  - backend/tests/services/visa_engine/test_seq7_sponsor_witnesses.py
---

# seq-7 — a mandate to conjoin sponsor.type with "the existing gate" found no gate

The mandate for this pack asked for two ELIGIBILITY rules —
`el.e33a.sponsor-government` and `el.e33c.sponsor-government`, each
`sponsor.type eq GOVERNMENT` conjoined with "the genuine E33A/E33C gate
existing in the pack" — plus a judgment call on a third
(`el.e33b.sponsor-none`) if E33B's gate turned out unexpressible with
current facts. It also asked for a plain data fix on E28C and documentation
work on `enums.py`.

The data fix and the documentation shipped as asked. The two ELIGIBILITY
rules did not, because the premise checked false: E33A and E33C have no
existing gate in `rulepack-prod-006.source.json` to conjoin with, and the
reason E33B was flagged as possibly unwritable applies to all three, for the
same structural reason, not a coincidence of overlapping gaps.

## What "no existing gate" means, measured

`rulepack-prod-006.source.json` binds exactly one rule to each of E33A,
E33B, E33C and E28C's `product_version_id`, and it is a `HUMAN_REVIEW` rule
in every case — `review.e33a.central-government-invitation`,
`review.e33b.expertise-qualification`, `review.e33c.central-government-
invitation`, `review.e28c.usd-threshold-manual`. None of the four has any
`HARD_FILTER` or `ELIGIBILITY` rule bound to it. This is not an inference
from reading the JSON; `test_seq6_refuter_witnesses.py::
test_reachability_is_what_the_document_claims` already pins it: 38 products,
27 reachable as `SUPPORTED_CANDIDATES`, and the 11 unreachable list names
E23U, E23V, E28C, E28B, E28D, E28F, E30E, E30F, E33A, E33B, E33C by name.

`evaluate_product()`'s own algorithm (spec §4.2, `evaluator.py:549-`) checks
`HUMAN_REVIEW` before `ELIGIBILITY` and returns `REVIEW` immediately on any
`HUMAN_REVIEW` rule firing true, without even computing whether `SUPPORT`
rules would have covered the applicant's purposes. So "conjoin the new rule
with the genuine gate" presupposes a gate distinct from the review
condition. For E33A/E33C there is none: the only structural condition
already in the pack is the review rule's own `intersects(purposes,
[EMPLOYMENT])` / `intersects(purposes, [INVESTMENT])`.

## Why both readings of "conjoin with it anyway" fail, reproduced empirically

Two ways to write `el.e33a.sponsor-government` were tried against a live
copy of the compiled seq-6 evaluator (script discarded after the run, output
kept below) — not reasoned about in the abstract, executed:

**Narrow**: `when = all(product_code eq E33A, sponsor.type eq GOVERNMENT)`,
`covered_purposes = [EMPLOYMENT]` (mirrors the review rule's own purpose
scope).

- GOVERNMENT sponsor + EMPLOYMENT purpose → `HUMAN_REVIEW_REQUIRED`, no
  candidates. The review rule's condition is implied whenever this rule's
  condition holds, so it always fires first. Dead code — it can never
  change the decision for any applicant who states EMPLOYMENT.
- GOVERNMENT sponsor + TOURISM-only purpose → `NO_SUPPORTED_PATH`. The
  purpose isn't in `covered_purposes`, so coverage fails; the rule cannot
  even reach TOURISM/FAMILY-only applicants either. Dead code, full stop.

**Broad**: same `when`, `covered_purposes = [EMPLOYMENT, TOURISM, FAMILY]`
(matches E33A's own `covered_purposes` on the product record).

- GOVERNMENT sponsor + EMPLOYMENT purpose → still `HUMAN_REVIEW_REQUIRED`
  (review still dominates whenever EMPLOYMENT is declared).
- GOVERNMENT sponsor + TOURISM-only purpose →
  **`SUPPORTED_CANDIDATES`, E33A offered.** This is the manufactured offer
  the seq-6 lesson names directly: "a requirement true for everyone with
  the purpose carries the product on its own." An applicant who declares
  only a tourism purpose and answers "government" to a sponsor-category
  question — with no invitation, no special-expertise justification, none
  of Pasal 57's actual content checked — is offered the Second Home Visa
  reserved for people the central government specifically invited.

There is no third shape: any `when` loose enough to fire outside the
review's own purpose scope is loose enough to fire on TOURISM/FAMILY-only
requests, because `sponsor.type` carries no purpose information of its own.
E33C's Pasal 59 is the same shape as E33A's Pasal 57 (Penjamin from a
central-government instansi, no other statutory content the interview can
check), so the same two outcomes apply to `el.e33c.sponsor-government`
without a separate simulation.

## E33B: the mandate's own standard, applied consistently

The mandate already asked for this evaluation on E33B and pre-authorized
"no rule" as the answer if the gate wasn't expressible. The factbase's own
gap #4 — no fact for certification, university ranking/recency/GPA, or the
90-day cooperation-proof commitment — means it isn't. `el.e33b.sponsor-none`
was not written, for the same reason as E33A/E33C: `sponsor.type == NONE`
is real and verbatim (Pasal 58(1) "tanpa Penjamin"), but it is necessary,
not sufficient, and nothing in the current fact vocabulary can check the
sufficient half.

## What this pack actually contains

- `enums.py`: `SponsorType` gets a class docstring with per-value semantics
  and citations (Pasal 57/58/59 for GOVERNMENT/NONE, Pasal 39/40 for E28C's
  NONE reading); the `FactPath.SPONSOR_TYPE` comment is corrected — it
  previously asserted E23V/E23U's sponsor category was "always known" and
  that unblocking the six flagged products was a matter of "the future pack
  must add legally grounded rules," both overclaims the factbase and this
  note retract.
- `rulepack-prod-007.source.json`: `sequence: 7`, `version: "2026.8.11"`,
  `previous_payload_sha256` chained to seq-6's canonical hash
  (`9691534c15e95821992d975f8f03a529aa5c46702b94ccf6f71fe7aba3ca83f6`,
  recomputed via `bundle.canonicalize_json` + sha256 in this session, not
  copied from the mandate). Every rule is byte-identical to seq-6 — 104
  rules, 0 added, 0 removed. The only product-record change is E28C:
  `sponsor_types` `["INDIVIDUAL"]` → `["NONE"]`, plus adding the
  already-declared Permenkumham 22/2023/11/2024 source record
  (`9248b1d7-9172-54d9-ad61-251e83a2285b`) to its `source_refs` — the same
  source E33A/E33B/E33C already cite for their own Pasal 39/40/57/58/59
  bases. This is a metadata correction only: `sponsor_types` on a product
  record is descriptive (a rule author's reference point, per
  `contract.schema.json`'s own description of the field), not read by the
  evaluator, so the change cannot itself alter any decision.
- `rule_pack_id`: no code in this repo derives or verifies a UUID5
  convention for this field (checked `compiler.py`, `models.py`, both
  `compile_pack.py`/`sign_pack.py` test suites — `rule_pack_id` is typed as
  a bare `UUID`, nothing more). A prior corner note describes a forward
  convention, `uuid5(NAMESPACE_URL, "https://balizero.com/visa-oracle/
  rule-pack/<ENV>/<JURISDICTION>/<DOMAIN>/<sequence>")`, adopted after the
  historical values (seq 1/2/4/5/6, none of which reproduce under that
  formula) were found "not reconstructable." seq-7 follows that documented
  forward convention: `453ee842-7f35-5d77-b460-31d67e2784c2`.
- `test_seq7_sponsor_witnesses.py`: chain integrity (previous_payload_sha256
  recomputed against the live seq-6 file), the E28C data correction pinned,
  zero rule delta, reachability set unchanged from seq-6 (same 27/11 split,
  same named products unreachable), and the manufacture-risk finding above
  pinned as a regression test against a synthetic pack — so a future author
  who tries either shape of `el.e33a.sponsor-government` without reading
  this note gets a red test, not a silent ship.

## What this pack does not contain, and why that is the correct scope

No new `ELIGIBILITY` or `HARD_FILTER` rule for E23U, E23V, E28C, E33A, E33B
or E33C. E23U/E23V stay exactly as seq-6 left them (fail-closed, zero
rules), per the mandate's own instruction and the factbase's confirmation
that no dedicated Pasal exists for either. E28C, E33A, E33B and E33C remain
unreachable as `SUPPORTED_CANDIDATES` — unchanged from seq-6, not a
regression, because they were never reachable and this pack was never
positioned to make them reachable without inventing facts the interview
doesn't collect.

## Adversarial review

Codex CLI (`gpt-5.6-sol`, `xhigh`, read-only sandbox) reviewed the diff
against seq-6 plus this note before the PR opened. Findings and dispositions
are recorded in this file's own PR thread / commit history rather than
duplicated here a second time; none required changing the pack's rule
content (0 rules added or removed either way survived review).
