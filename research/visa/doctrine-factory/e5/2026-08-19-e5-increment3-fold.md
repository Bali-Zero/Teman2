---
adversarial_review: codex
date: 2026-08-19
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/e5/2026-08-19-e5-increment3-spec.md
    note: "Build spec + Assembly decisions (post-Implementer-B, post-Implementer-A) — binding, overrides the spec's own earlier Step-3 prose"
  - path: research/visa/doctrine-factory/e5/blocked7-rule-manifest.json
    note: "Implementer A's 5 rules + this session's 2 additions (E23U/E23V review rules), compiles clean"
  - path: research/visa/doctrine-factory/e5/inc3-pack-edits/cure-e33g.json
  - path: research/visa/doctrine-factory/e5/inc3-pack-edits/cure-e33g.md
  - path: research/visa/doctrine-factory/e5/inc3-pack-edits/cure-e33e.md
  - path: research/visa/doctrine-factory/e5/inc3-pack-edits/e31e-source-edits.json
  - path: research/visa/doctrine-factory/e5/inc3-pack-edits/e31e-resource.md
  - path: research/visa/doctrine-factory/e5/inc3-pack-edits/freshness-2026-08-19.md
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.signed.json
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-008.source.json
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-009.source.json
    note: "the assembled artifact this doc describes"
  - path: apps/backend-rag/backend/tests/services/visa_engine/test_seq9_new_rule_witnesses.py
    note: "NEW (fix round), house-pattern witness suite driving the real evaluator per-product"
  - path: apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts
    note: "line ~469: intent.requested_product_code hard-coded NOT_ASKED — grounds the E23U/E23V production-inertness note below"
discovered_by: agent.air-m5.backend-rag.visa-e5-seq9-implementer-c-assembler; fix round by agent.air-m5.backend-rag.visa-e5-seq9-fixer-2026-08-19
adversarial_review: codex (gpt-5.6-sol), kimi-k3 — both cross-family refuter passes on the seq-9 fold; findings + dispositions below
---

# E5 increment 3 — seq-9 fold (assembly report)

Implementer C (assembler) role: fold Implementer A's 5 blocked7-manifest rules,
Implementer B's E33G/E31E cures and freshness edits, and this session's own 2
new product-scoped review rules (E23U/E23V) into a deterministic
`rulepack-prod-009.source.json`, then gate it.

**Fix round (2026-08-19, same date, later session):** two cross-family
refuters (Codex gpt-5.6-sol, Kimi K3) independently reviewed the assembled
artifact below and returned DO-NOT-SHIP / ship-with-findings respectively.
The orchestrator triaged both reports into a 6-item fix list; see
"## Adversarial review" at the bottom of this doc for the full disposition
of every finding. Five of the six items were applied as fixes; the sixth
(FIX-2, arbitrated "attempt cure, stop-if-ungrounded") was attempted and
STOPPED — no compilable claim grounds the specific E31C tightening
predicate, so the rule was left byte-inherited from seq-7 rather than
inventing one (see Residuals item 6 below for the full evidence trail and
both refuters' positions). The pack's
sha256 changed as a direct result (§Gates below carries the new value); all
sections below reflect the POST-FIX state, not the state either refuter
reviewed.

## What was built

- `research/visa/doctrine-factory/e5/blocked7-rule-manifest.json` — extended
  with 2 new manifest entries (`review.e23u.requested-product`,
  `review.e23v.requested-product`), mirroring the existing
  `review.e33a/b/c.*` `intent.requested_product_code` pattern (spec Assembly
  decision #7). All 7 manifest rules compile clean via
  `compile_claims.py` against the 6 claim ledgers (0 findings). **Fix round
  (FIX-1, Codex P0 finding 1):** `el.e30f-student-support`'s `when` gained a
  fourth conjunct, `eq(sponsor.type, "EDUCATION")`, cited to `CL-E30F-05`
  (VERIFIED-WITH-CAVEAT — the mandatory-sponsor requirement rests on
  internal operational sources only, no primary-law pinpoint), with a
  matching `caveats` entry added to the manifest. Before this fix, the rule
  tested only `study.admission_confirmed`/`study.sponsor_confirmed` (two
  generic booleans) and never `sponsor.type` at all — live-evaluator-proven
  by Codex to reach `SUPPORTED` for E30F under `sponsor.type` ∈
  {NONE, GOVERNMENT, INDIVIDUAL, EDUCATION} alike. Deliberately EDUCATION-only
  (not `{EDUCATION, INDIVIDUAL}` like E30E) — CL-E30F-05 names only "an
  accredited Indonesian educational institution", no individual-guarantor
  option; CL-E30E-05 is the claim that grants E30E its INDIVIDUAL option,
  and it does not apply to E30F. Re-verified this session:
  `compile_claims.py` on the updated manifest → `OK — 7 rule(s) compiled
  clean` (0 findings).
- `apps/backend-rag/backend/scripts/visa_engine/fold_pack.py` — new
  deterministic, idempotent CLI. Reads seq-7 source + seq-7 SIGNED (for
  `previous_payload_sha256`, never hardcoded) + seq-8 source + the blocked7
  manifest + `cure-e33g.json` + `e31e-source-edits.json`, writes
  `rulepack-prod-009.source.json`. Verified idempotent: two consecutive runs
  produce byte-identical output (**post-fix-round sha256**
  `e3c1457952722706ec59b0a23e66c7d7a6a7b88735cda982b54957f5e4648660` —
  changed from the pre-fix-round `819d8ea1…` as a direct, expected
  consequence of FIX-1 and FIX-3b below; see §Gates).
  Formatting: the file is written via `json.dump(..., indent=2,
  ensure_ascii=False)` then canonicalized with the repo's local
  `node_modules/.bin/prettier --write` — verified this session that the
  existing packs (`rulepack-prod-007.source.json`) ARE Prettier-formatted
  (`prettier --check` reports clean) and that this exact recipe round-trips
  seq-7 byte-for-byte, so the same recipe on seq-9 guarantees both the
  "same formatting convention" requirement and a clean, minimal diff against
  seq-7 (792 changed lines out of ~9122, almost entirely the inserted/edited
  content — see the gate output below; up from 714/~9100 pre-fix-round
  because of the new sponsor.type conjunct and the valid_period
  normalization). **Fix round (FIX-3a, Codex finding 7 — non-atomic
  write):** `_write_pack()` now stages the raw dump + Prettier
  canonicalization in a temp file in the SAME directory (`tempfile.mkstemp`,
  suffix preserved as `.json` so Prettier's parser inference still resolves)
  and only `Path.replace()`s the tracked target once BOTH steps succeed — a
  Prettier failure (binary missing, non-zero rc for any reason) now raises
  before the tracked pack file is ever touched, instead of leaving it
  half-overwritten with non-canonical content. **Fix round (FIX-3b, Kimi
  finding 5 — valid_period.from inconsistency):** every one of the 8 newly
  inserted rules now has its `valid_period.from` normalized to the fold date
  (`2026-08-19T00:00:00Z`, the new `_SEQ9_NEW_RULE_VALID_FROM` constant) at
  insertion time — before this fix, `review.e33g.income-evidence` alone
  carried `2026-07-24T00:00:00Z` (inherited verbatim from `cure-e33g.json`'s
  authoring date, before seq-9 existed) while the other 7 carried
  `2026-08-19T00:00:00Z`, an authoring-artifact date leaking into the pack
  with no doctrinal justification (module docstring documents this is a
  DIFFERENT rule from the seq-7-inherited-rules `valid_period.from`
  invariant, which stays untouched by design).
- `research/visa/doctrine-factory/e5/inc3-pack-edits/ee8fe5b8-coref-table.md`
  — generated by `fold_pack.py`, the per-rule co-source table for Assembly
  decision #5.
- `apps/backend-rag/backend/tests/services/visa_engine/test_pack_chain_and_pricing.py`
  — 21 tests originally (chain gate, pricing parity, retirement/insertion,
  inc-2 lints over every seq-9 rule, dangling-ref integrity); **fix round
  adds 4 more (25 total)**:
  - **FIX-4 (Codex finding 5 / Kimi finding 6 — chain test compared two
    declared string fields, never recomputed):**
    `test_seq9_previous_payload_sha256_chains_to_seq7_signed` now recomputes
    seq-7's canonical payload hash directly from `rulepack-prod-007.source.json`
    bytes via `canonicalize_json` + `hashlib.sha256` (the house pattern,
    `test_seq7_sponsor_witnesses.py:171`'s
    `test_previous_payload_sha256_chains_to_the_real_seq6_file`) and asserts
    seq-9's `previous_payload_sha256` against that RECOMPUTED value, plus a
    separate assertion that the signed envelope's own declared
    `payload_sha256` is itself honest (matches the recomputation) — a
    corrupted-but-64-hex-char signed file would previously have passed
    silently.
  - **FIX-5a, `TestInsertedRuleContentParity` (Codex finding 3/6, Kimi
    finding 1 — content-blind test suite, PROVEN by live mutation):** Kimi
    mutated the committed pack in place (swapped which product code
    `review.e23u/e23v.requested-product`'s `eq` leaf targets — a full
    semantic inversion) and re-ran the full targeted suite as it stood
    before this fix: **21 passed**, the mutation invisible. These new tests
    diff each inserted rule's `when`/`effect`/`scope` (which carries
    `reason_code`) in the PACK against an INDEPENDENT recompilation of the
    same source artifacts — `blocked7-rule-manifest.json` + the 6 ledgers
    re-run through a fresh `compile_manifest()` call, and `cure-e33g.json`'s
    raw JSON directly for `review.e33g.income-evidence` — never against
    `fold_pack.py`'s own already-materialized output, so this catches both
    a manifest-vs-pack drift AND a hand-tampered pack file. Re-ran Kimi's
    exact mutation against the NEW test: it now fails loud (see §Gates for
    the captured failure), then the pack was restored and re-verified
    byte-identical (sha256 unchanged) before proceeding.
  - **FIX-5a, `TestFullProductObjectParity` (Codex finding 6 — pricing
    parity checked ONLY `pricing_key`):** every one of the 38 products in
    seq-9 is now asserted field-by-field equal to its seq-7 counterpart on
    EVERY field except `pricing_key` (which the pre-existing
    `TestPricingParity` already pins against seq-8 for the 11 folded
    products) — a mutation to any other product field (Codex's own example:
    `E28A.names.en`) now goes red.
- `apps/backend-rag/backend/tests/services/visa_engine/test_seq9_new_rule_witnesses.py`
  — **NEW (FIX-5b, Codex F1/F3/F6 + Kimi F1), 21 tests.** House pattern
  (`test_seq7_sponsor_witnesses.py`): drives the REAL evaluator
  (`evaluator.evaluate_product`, called per-product directly — never the
  aggregated multi-product `Decision`, so a review-gated sibling product can
  never mask the rule under test) with guilt+innocence pairs for all 6
  content-bearing inserted rules plus the 2 UNKNOWN-semantics witnesses the
  fix list specified: E33A sponsor GOVERNMENT (not excluded) vs EMPLOYER
  (excluded); E33B/C sponsor {GOVERNMENT,NONE} (not excluded) vs EMPLOYER
  (excluded); E30F sponsor EDUCATION+confirmed (SUPPORTED, pins FIX-1) vs
  NONE (not supported); E30E EDUCATION and INDIVIDUAL (both SUPPORTED) vs
  NONE (not supported); E33G clean remote-work config (REVIEW fires, not
  SUPPORTED — the OD-1 narrowing); E23U/V explicit `requested_product_code`
  (REVIEW fires for that product only, never its sibling) vs UNKNOWN
  (BLOCKED_UNKNOWN, never a manufactured REVIEW); UNKNOWN `sponsor.type` on
  E33A/B/C (BLOCKED_UNKNOWN, never EXCLUDED).
- `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.test.ts`
  — `KNOWN_UNMAPPED_REVIEW_REASON_CODES` extended with
  `E23U_DIPLOMATIC_HOUSEHOLD_STAFF_REVIEW`, `E23V_TRADE_OFFICE_STAFF_REVIEW`,
  `E33G_INCOME_EVIDENCE_REVIEW` (alphabetically slotted, matching
  `cure-e33g.md`'s documented diff for the third). Unchanged by the fix
  round (re-verified green, 25/25).
- `research/visa/doctrine-factory/reachability/rulepack-prod-009-reachability.{json,md}`
  — reachability_report.py run against the assembled source (see headline
  below). Filename note: the tool's own naming convention strips `.source`
  from the pack filename stem (`rulepack-prod-009-reachability.md`, matching
  the existing `rulepack-prod-007-reachability.md` on disk) — this doc uses
  that verified-on-disk name rather than the `-source-reachability` name in
  this task's own instructions, since the tool's actual behavior is the
  authoritative fact here. Regenerated post-fix-round (FIX-1's added
  conjunct does not change reachability shape — E30F was already reachable
  via this same SUPPORT rule before and after, the fix only narrowed WHICH
  sponsor values reach it — numbers below are unchanged from the pre-fix
  measurement).

## Semantic delta, seq-7 -> seq-9 (rule-by-rule)

### Retired (2 rules, no replacement)

| rule_id | reason | claim |
|---|---|---|
| `el.e33e.deposit-income-basis` | UNSAT by construction (brute-force: 0/64 assignments satisfy `when`). The spec's Step-3a "cure to OR" premise does not hold: the only claim backing the deposit/income floor, `CL-E33-04` (VERIFIED), states **AND** ("plus"), not OR — matching the healthy sibling `el.e33e.retirement`, which already encodes AND and is reachable. A cured AND-version would be a literal duplicate of `el.e33e.retirement`. Behavior delta: **zero** (an UNSAT rule never fires). | `CL-E33-04` |
| `el.e33g.income-60k-manual` | VACUOUS-duplicate (`all(subtree, subtree)`, byte-identical to the pre-existing `el.e33g.remote-work`). Per Assembly decision #2, the renamed cure (`el.e33g.remote-work-configuration`) is deliberately NOT added — it would also be byte-identical to `el.e33g.remote-work`. | `CL-E33G-02` (grounds the review-gate replacement, not this rule) |

### Added (8 rules)

| rule_id | stage | product(s) | claim(s) | caveat |
|---|---|---|---|---|
| `el.e30e-student-support` | ELIGIBILITY (SUPPORT) | E30E | CL-E30E-01/-02/-03/-05 | — |
| `el.e30f-student-support` | ELIGIBILITY (SUPPORT) | E30F | CL-E30F-01/-02/-03/-05 | CL-E30F-05 (VERIFIED-WITH-CAVEAT — no primary-law pinpoint, internal operational sources only; fix round FIX-1) |
| `hf.e33a.sponsor-not-government` | HARD_FILTER (EXCLUDE) | E33A | CL-E33A-01/-02/-03 | — |
| `hf.e33b.sponsor-not-government-or-none` | HARD_FILTER (EXCLUDE) | E33B | CL-E33B-01/-02/-04 | CL-E33B-04 (PROSE_ONLY) |
| `hf.e33c.sponsor-not-government-or-none` | HARD_FILTER (EXCLUDE) | E33C | CL-E33C-01/-02/-03 | CL-E33C-01, CL-E33C-02 (PROSE_ONLY) |
| `review.e23u.requested-product` | HUMAN_REVIEW | E23U | CL-E23U-01/-02/-03 (all plain VERIFIED) | — |
| `review.e23v.requested-product` | HUMAN_REVIEW | E23V | CL-E23V-01/-02 (both plain VERIFIED; CL-E23V-03 not cited) | — |
| `review.e33g.income-evidence` | HUMAN_REVIEW | E33G | CL-E33G-02 | VERIFIED-WITH-CAVEAT (Bali Zero internal guide, not primary-law-pinned for the exact USD 60,000 figure) |

E30E/E30F shape (fix round FIX-1, FIX-6b): both rules gate on
`sponsor.type` now, but with DIFFERENT allow-lists — E30E accepts
`{EDUCATION, INDIVIDUAL}` per CL-E30E-05 ("either the KEK educational
institution itself or a WNI individual guarantor"), E30F accepts
`EDUCATION` only per CL-E30F-05 ("an accredited Indonesian educational
institution", no individual-guarantor language). **Honest over-support,
spec-sanctioned, not a regression:** neither rule can discriminate a KEK
institution (E30E's actual scope) or a bilateral-exchange program (E30F's
actual scope) from an ordinary school — the closed fact vocabulary has no
predicate for either distinction (Kimi refuter finding 3). A generic
admitted student (`STUDY` + `admission_confirmed` + `sponsor_confirmed` +
`sponsor.type=EDUCATION`) is therefore SUPPORTED-indistinguishable across
`[E30, E30E, E30F]` all at once — this is the shape Step 2 of the spec
explicitly prescribed (ELIGIBILITY narrowing on the facts available, not a
KEK/bilateral-exchange gate that does not exist in the vocabulary), and it
is unchanged by the fix round; recorded here as a CP3-visible delta, not
silently smoothed over. **Related, evaluator-inert catalog drift** (product
CATALOG metadata, never read by the evaluator — `sponsor_types` is
descriptive-only, checked directly: no reference outside `models.py`'s
field declaration and the generated JSON-Schema description): E30E's
product record declares `sponsor_types: ["EDUCATION"]` while its rule also
admits `INDIVIDUAL` (claim-faithful per CL-E30E-05 — the RULE is correct,
the catalog metadata is the stale side); E33B's product record declares
`sponsor_types: ["NONE"]` while `hf.e33b.sponsor-not-government-or-none`
admits `{GOVERNMENT, NONE}` (claim-faithful per the Pasal 57/58 two-pathway
reading). E30F's own catalog record (`sponsor_types: ["EDUCATION"]`) is NOT
drifted — post-FIX-1 it matches the rule exactly.

E33A/B/C ratified shape (Assembly decision #6): HARD_FILTER/EXCLUDE narrowing
on `sponsor.type`, **never SUPPORT** — the pre-existing
`review.e33a/b/c.central-government-invitation` / `expertise-qualification`
document-check rules are untouched and remain the only path to
`ProductProofStatus.REVIEW` for these three products.

E23U/E23V shape (Assembly decision #7): **no SUPPORT rule** — the W3
factbase found no safe discriminating condition between the pair, so each
gets one product-scoped `HUMAN_REVIEW` rule keyed on
`intent.requested_product_code`, mirroring the E33A/B/C review-rule
mechanism. Reachability effect: E23U/E23V remain in reachability_report's
"Blocked (zero SUPPORT rules)" bucket in both seq-7 and seq-9 — by design,
not an oversight (a reader who expects "added a rule" to always mean "now
reachable" should read this row).

**PRODUCTION-INERT until `intent.requested_product_code` is collected (fix
round FIX-6a, Kimi refuter finding 2).** `apps/mouth/.../fact-mapper.ts:469`
hard-codes this fact `unknownFact(NOT_ASKED)` **unconditionally** — grepped
this session, confirmed no other producer anywhere in `apps/mouth`, and the
regenerated `rulepack-prod-009-reachability.md`'s own "NOT_ASKED facts"
section lists it among the 5 facts the live interview never asks. With the
fact UNKNOWN, both rules' `eq(intent.requested_product_code, …)` leaf is
UNKNOWN, the `all(...)` is UNKNOWN, and `on_unknown=NEEDS_INPUT` resolves
this to `BLOCKED_UNKNOWN` — never `REVIEW` (pinned live by
`test_seq9_new_rule_witnesses.py::
test_unknown_requested_product_code_is_blocked_unknown_never_review`). This
is the SAME property the pre-existing `review.e33a/b/c.*` rules already
had in seq-7 (`test_seq7_sponsor_witnesses.py`'s own module docstring
documents the identical dependency), so there is **no user-visible
regression** — but the "someone explicitly pursuing E23U/E23V gets a named
review path instead of silence" framing above holds only once a future
increment wires the interview to collect this fact (E6/experience-track
scope, out of this increment). Until then, these 2 rules are on-disk and
claim-grounded but dormant on every real request.

**`review.e33g.income-evidence`'s citations are framing-only, stated
plainly (fix round FIX-6c, Codex refuter finding 4).** The rule's
`source_refs` (`6f5135f2` Kepmen M.IP-08.GR.01.01/2025, `9248b1d7`
Permenkumham 22/2023 jo. 11/2024) are the SAME framing-only citations
already on every other `el.e33g.*` rule in seq-7 — neither independently
corroborates the USD 60,000/year figure. `cure-e33g.json` itself says so
(`_new_rule_rationale`: "no pack source_record independently backs the USD
60,000 figure at primary-law level"), and the grounding claim,
`CL-E33G-02`, is itself `VERIFIED-WITH-CAVEAT` resting on Bali Zero's own
internal operational guide (`kitas_e33g_remote_work_guida_2025.txt` +
`VO-FUSED-T4-006`, `e2b-batch1-claim-ledger.md:115-124`) — corroborated
operationally, never independently confirmed against a Kepmen/Permenkumham
article pinpoint for this specific figure. A reviewer who follows the
citations attached to `E33G_INCOME_EVIDENCE_REVIEW` expecting the
threshold's legal basis finds only context, not the figure's proof — this
is disclosed here rather than left implicit in a code comment only.

### Re-sourced (source_ref repoint + record edits)

| target | change | claim |
|---|---|---|
| `hf.e31e-adult-excluded` | `source_refs`: `ecd22722` -> `c9e6f0e4` | CL-E31E-01 (VERIFIED-WITH-CAVEAT — the caveat IS the freshness flag being cured) |
| `hf.e31e-married-excluded` | `source_refs`: `ecd22722` -> `c9e6f0e4` | CL-E31E-01 |
| `c9e6f0e4` (Permenkumham 22/2023) | `locators` gains `{"kind":"ARTICLE","value":"Pasal 33"}` | CL-E31E-01's pinpoint (Pasal 33 ayat (2) huruf h angka 5) |
| `ecd22722` (E31E OFFICIAL_PORTAL page) | `verified_at`/`verified_by` bumped to `2026-08-18T21:41:23Z` / `agent.air-m5.backend-rag.visa-e5-seq9-implementer-b.qw5-recheck-2026-08-19` — record STILL backs `el.e31e-child-itas-support`/`el.e31e-sponsor-itas-itap` (re-verified live, sponsor-ITAS/ITAP clause confirmed verbatim) | freshness-2026-08-19.md §1 |
| `0497cb52` (evisa student-visa FAQ) | dropped from `source_records` | 0 active refs, grepped twice independently (Implementer B and this session) |
| `ee8fe5b8` (general landing page) | dropped from 18 RULE `source_refs` (each retained >=1 other source — 0 residuals); the 3 D1/D2/D12 PRODUCT-level co-refs deliberately untouched (Assembly decision #5's own wording scopes to "every rule", not products) — full per-rule table in `ee8fe5b8-coref-table.md` | freshness-2026-08-19.md §2 |

### Pricing (seq-8 fold)

11 products gain `pricing_key` from seq-8 (previously null in both seq-7 and
seq-9-pre-fold): E28A, E33, E33E, E33F, E33G, A1, B1, C1, C6, C2, BRIDGING.
13 products keep their seq-7 pricing_key unchanged (D1, D12, D2, E23,
E31A-E31J family). 14 products remain unpriced (E23U, E23V, E28B/C/D/F,
E30/A/B/E/F, E33A/B/C). All three groups partition the 38 products exactly
— asserted in both `fold_pack.py` (self-check) and
`test_pack_chain_and_pricing.py::TestPricingParity`.

## Gates (recorded output, this session)

**Pre-fix-round evidence (819d8ea1… sha256, 104-passed baseline) is
SUPERSEDED below — kept legible in git history only, not reproduced here,
per this doc's own "everything below is POST-FIX" framing at the top.**

**FIX-1 manifest re-compile, isolated:**

```
$ PYTHONPATH=. python -m backend.scripts.visa_engine.compile_claims \
    --claims <the 6 ledgers> --manifest e5/blocked7-rule-manifest.json
OK — 7 rule(s) compiled clean.
```

**`fold_pack.py`, two consecutive runs — idempotence proof (post-fix-round):**

```
$ PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack
wrote .../rulepack-prod-009.source.json — 110 rule(s), 38 product(s), 29 source_record(s)
inserted 8 new rule(s): ['review.e33g.income-evidence', 'el.e30e-student-support',
  'el.e30f-student-support', 'hf.e33a.sponsor-not-government',
  'hf.e33b.sponsor-not-government-or-none', 'hf.e33c.sponsor-not-government-or-none',
  'review.e23u.requested-product', 'review.e23v.requested-product']
$ shasum -a 256 rulepack-prod-009.source.json
e3c1457952722706ec59b0a23e66c7d7a6a7b88735cda982b54957f5e4648660  ...  (run 1)
e3c1457952722706ec59b0a23e66c7d7a6a7b88735cda982b54957f5e4648660  ...  (run 2, byte-identical)
```

Rule count/product count/source_record count and the 8 inserted rule_ids
are unchanged from the pre-fix-round run — only rule CONTENT (E30F's
sponsor.type conjunct, all 8 rules' valid_period.from) changed, so the
new sha256 is entirely explained by FIX-1 + FIX-3b.

**`compile_pack.py` on the assembled source:**

```
$ PYTHONPATH=. python -m backend.scripts.visa_engine.compile_pack \
    backend/services/visa_engine/contracts/packs/rulepack-prod-009.source.json
rule_pack_id=66eb0b4c-58ee-56c3-812c-2acc26fff8ce sequence=9
OK — zero compilation errors
RC=0
```

**FIX-5a guilt proof (Kimi's mutation, re-run against the NEW content-parity
test) — captured this session, then reverted:**

```
$ python3 - <<'PY'   # swap review.e23u/e23v.requested-product's eq target values
...
PY
$ PYTHONPATH=. python -m pytest backend/tests/services/visa_engine/test_pack_chain_and_pricing.py::TestInsertedRuleContentParity -p no:cacheprovider -q
F..
AssertionError: assert {'review.e23u...': {'when': {...}}} == {}
1 failed, 2 passed
$ # pack restored; sha256 re-verified e3c14579… (byte-identical to before the mutation)
```

**Full targeted pytest suite (post-fix-round, all 4 files):**

```
$ PYTHONPATH=. python -m pytest backend/tests/scripts/test_visa_engine_compile_claims.py \
    backend/tests/services/visa_engine/test_claim_ledger.py \
    backend/tests/services/visa_engine/test_pack_chain_and_pricing.py \
    backend/tests/services/visa_engine/test_seq9_new_rule_witnesses.py -p no:cacheprovider
129 passed in 2.34s
```

Per-file breakdown (dot-counted, cross-checked to sum to 129):
`test_visa_engine_compile_claims.py` 67, `test_claim_ledger.py` 16,
`test_pack_chain_and_pricing.py` 25 (21 pre-fix-round + 4 new: 3 in
`TestInsertedRuleContentParity`, 1 in `TestFullProductObjectParity`),
`test_seq9_new_rule_witnesses.py` 21 (new file, FIX-5b). (The "77 passed"
baseline named in the spec's Anchors section was measured before this
worktree's Step-1 ledger-hygiene wiring (e2b-batch3/e2c-blocked5) landed —
67+16=83 is this session's actual current baseline for the first two files
alone, confirmed by running them in isolation.)

**QW-4a reason-copy exhaustiveness (vitest, re-verified post-fix-round):**

```
$ npx vitest run "src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.test.ts"
 Test Files  1 passed (1)
      Tests  25 passed (25)
```

Environment note: this worktree's `apps/mouth` had no `node_modules` at
session start (`Cannot find module '@vitejs/plugin-react'`, blocking
`vitest.config.ts` from loading at all) — resolved via
`pnpm install --filter mouth --prefer-offline` (fully served from the local
pnpm content-addressable store, zero network downloads per the resolve log).
Pre-existing environment gap in this worktree, unrelated to this session's
diff.

**`reachability_report.py` headline (seq-7 -> seq-9, regenerated
post-fix-round — unchanged from the pre-fix-round measurement, as expected:
FIX-1 narrows WHICH sponsor values reach E30F, it does not change WHETHER
E30F is reachable at all):**

- Reachable: **27 -> 29** / 38 products (E30E, E30F newly reachable — the 2
  new `el.e30e-student-support` / `el.e30f-student-support` SUPPORT rules).
- Blocked: **11 -> 9** / 38 products (E23U, E23V, E28B, E28C, E28D, E28F,
  E33A, E33B, E33C remain blocked — by design: E23U/E23V/E33A/B/C gained
  narrowing/review rules but deliberately no SUPPORT rule, per Assembly
  decisions #6/#7).
- Fact-path coverage: 36/44 -> 37/44 (`sponsor.type` now referenced — the 3
  new HARD_FILTER rules are the first seq-9 rules to test it; it was
  authored into the fact vocabulary earlier but unused by any seq-7 rule).
- Orphan rules: none, both packs.

Full reports: `research/visa/doctrine-factory/reachability/rulepack-prod-009-reachability.{json,md}`.

## Residuals and open items for CP3

1. **E33A/B/C stay review-gated, never SUPPORT** (Assembly decision #6) — the
   pre-existing document-check `review.e33a/b/c.*` rules are the only path to
   `REVIEW`; the new HARD_FILTER rules only narrow (EXCLUDE the
   sponsor-mismatched, never grant a positive status).
2. **E23U/E23V get review-only, no SUPPORT** (Assembly decision #7) — W3
   factbase found no safe discriminating `sponsor.type`/purpose condition
   between the pair; a rule keyed on
   `intent.requested_product_code` gives an explicit review path to anyone
   pursuing either product by name, never a manufactured SUPPORT.
3. **E33E retirement, no replacement rule** — doctrine fully covered by the
   pre-existing `el.e33e.retirement`; behavior delta is zero.
4. **ee8fe5b8 residuals: 0** among the 18 rules processed (every one retained
   >=1 other source after the drop) — but the 3 D1/D2/D12 PRODUCT-level
   co-refs are UNTOUCHED, out of Assembly decision #5's literal scope
   ("for every rule"). Re-pointing those 3 to the D1/D2/D12-specific pages
   (per freshness-2026-08-19.md's own recommendation) is future CP3 scope.
5. **The "5 claim-cited source ids absent from the pack" (Assembly decision
   #8)** — per the spec, these (Kepmen/Permenkumham UUID variants + 2 nb2
   internal files) are deliberately NOT added as pack source_records; rules
   cite pack-native sources only (CF-17). This session verified the
   CONSEQUENCE empirically (`compile_pack.py` reports zero
   `UNKNOWN_SOURCE_REFERENCE` errors on all 7 blocked7-manifest rules, so
   nothing non-pack-native leaked into a `source_refs` field) but did not
   independently re-derive which exact 5 ids the decision refers to — no
   file in this worktree enumerates them by id, and inventing a specific
   list here would be exactly the fabrication this task's discipline
   forbids. Recorded as-is for CP3, not smuggled as resolved.
6. **NEW finding, out of this increment's authorized scope — 2 pre-existing
   duplicate-subtree defects, unrelated to E33E/E33G, inherited unmodified
   from seq-7 into seq-9:**
   - `el.c2.corporate-sponsor-type` (C2 product)
   - `el.e31c-mixed-marriage-parents` (E31C product) — **see fix-round
     disposition below; C2 is unchanged and still fully open.**

   Both have the exact same shape as the (now-cured) `el.e33g.income-60k-manual`
   defect: an outer `all(subtree, subtree)` with byte-identical duplicated
   children. Discovered by running the inc-2 lint functions
   (`lint_unsatisfiable_condition`, `lint_duplicate_subtree`) over EVERY
   seq-9 rule, per this task's own T3(d) instruction — the spec's text
   assumed "zero findings" pack-wide, but reality has 2 more than the 2
   named in Step 3. `test_pack_chain_and_pricing.py`'s
   `TestInc2LintsOverEverySeq9Rule` locks in this TRUE state (asserting the
   findings are exactly these 2, not "zero") rather than asserting a false
   "zero findings" — reported honestly per this task's instruction ("a red
   gate is reported red, never smoothed").

   **C2 (`el.c2.corporate-sponsor-type`): still not fixed here.** No claim
   citation or doctrine authorization exists in this increment's scope to
   touch it, and the spec's Step 3 names only `el.e33e.deposit-income-basis`
   / `el.e33g.income-60k-manual`. Recommend: a future increment authors a
   claim-backed cure, following the dedupe-and-honest-rename pattern used
   for `el.e33g.income-60k-manual`.

   **E31C (`el.e31c-mixed-marriage-parents`): fix round attempted a cure
   (FIX-2) and STOPPED, per the arbitration instruction "attempt cure,
   stop-if-ungrounded — never invent claims."** Investigation this session
   read `cards/E31C.md` §3.5/§7 in full and every `CL-E31C-*`/`CL-E31F-*`
   claim entry across all six ledgers, then compared against the live
   rule bodies of E31C's structural siblings: E31A (SPOUSE pattern —
   tests both `family.marriage_registered` AND
   `family.sponsor_nationalities`) and E31F (PARENT pattern, the closer
   sibling — tests `family.sponsor_nationalities` only, and is itself
   grounded by bare `source_refs` rather than a `claim_id`, predating
   claim-ledger discipline). No VERIFIED / VERIFIED-WITH-CAVEAT claim in
   any ledger grounds a SPECIFIC tightening predicate for E31C (which
   facts, which exact values) — `CL-E31C-01` backs only the category
   IDENTITY ("E31C is child of legal mixed marriage"), not an eligibility
   formula, and the doctrine card itself frames the gap as "a
   rule-authoring gap ... for a future E5 pass" (§7 item 3), not something
   the current claim corpus resolves. The predicate choice is also
   genuinely ambiguous between the two sibling shapes above; inventing
   either would be exactly the fabrication this task's discipline forbids.
   **Decision: left byte-inherited from seq-7, unmodified.**

   This is an explicit CP3 decision item, and the two cross-family
   refuters did not agree on it — both positions are carried verbatim-in-
   substance rather than picking a winner:
   - **Codex**: leaving it is not defensible — a live probe against the
     unmodified E31C rule reached SUPPORTED with
     `family.marriage_registered=false` and a US sponsor, i.e. the same
     duplicate-subtree defect class the increment already cured for
     E33G is live and reachable by an unfavorable applicant profile here
     too, not merely latent.
   - **Kimi**: the STOP is defensible as scope discipline (no claim
     grounds a fix, so authoring one would be fabrication) — but it is
     explicitly the SAME defect class as the cured E33G, not a milder
     one, and should not be read as lower-priority just because this
     increment left it alone.

   Both are right on their own terms: Codex on live reachability/risk,
   Kimi on why this session did not author a predicate anyway. CP3 must
   pick one of (a) source a new claim that grounds a specific E31C
   predicate, or (b) accept the Codex-demonstrated live-probe risk as a
   known gap with an explicit sign-off, before this can be closed either
   way.
7. **E33C capital-tier guarantees (USD 25M/50M) not encoded** — per spec
   Step 2's own instruction, flagged as plausibly conflated with the
   corporate Golden Visa; not authored into any rule this increment.
8. **The 26 reformed slice rules** (`slice-rule-manifest.json`) are
   deliberately NOT folded into seq-9 — HRR/flag-veto reform, post-seq-9
   scope, per the spec's non-goals.
9. **QW-4b** (the actual bilingual copy sentences for
   `E23U_DIPLOMATIC_HOUSEHOLD_STAFF_REVIEW`, `E23V_TRADE_OFFICE_STAFF_REVIEW`,
   `E33G_INCOME_EVIDENCE_REVIEW`) is separately gated on copy-deck approval —
   this session only added the `KNOWN_UNMAPPED_REVIEW_REASON_CODES` entries,
   per `cure-e33g.md`'s own documented split.

## Non-goals honored

No signing, no activation, no Fly/secret/DB change, no ENFORCE-adjacent
change, no new FactPath, no frontend behavior change (only the reason-code
copy-deck gap list), no slice-rule fold, no seq-8 signing. SHADOW posture
unchanged. `rulepack-prod-008.signed.json` does not exist (confirmed,
pinned by `test_pack_chain_and_pricing.py::test_no_seq8_signed_pack_exists`).

## Adversarial review

Two cross-family refuters (Codex `gpt-5.6-sol`, verdict DO-NOT-SHIP; Kimi
K3, verdict ship-with-findings) independently reviewed the seq-9 fold
working tree before this fix round. The orchestrator triaged their combined
findings into a 6-item fix list, applied in order. Disposition of every
named finding:

**FIX-1 (P0, Codex F1) — APPLIED.** `el.e30f-student-support` in
`blocked7-rule-manifest.json` was missing a sponsor-type constraint,
admitting any `sponsor.type` value under the SUPPORT effect. Added
`{"fact": "sponsor.type", "op": "eq", "value": "EDUCATION"}` as a fourth
`when.args` conjunct (accredited-institution only, no INDIVIDUAL option —
see `blocked7-rule-manifest.json` `el.e30f-student-support`), cited
`CL-E30F-05` with a matching VERIFIED-WITH-CAVEAT `caveats` entry
explaining the EDUCATION-only scope versus E30E's `{EDUCATION, INDIVIDUAL}`
(Permenkumham 22/2023 Pasal 42 names an individual guarantor option for
E30E; no equivalent claim exists for E30F). Verified via an isolated
`compile_claims.py` re-run ("OK — 7 rule(s) compiled clean") before folding.
Witnessed by `test_e30f_education_sponsor_with_confirmed_admission_is_supported`
and `test_e30f_none_sponsor_is_not_supported` in the new
`test_seq9_new_rule_witnesses.py`.

**FIX-2 (P1, Codex F2 / Kimi F4) — ATTEMPTED, STOPPED (ungrounded).**
`el.e31c-mixed-marriage-parents` — full investigation performed (read
`cards/E31C.md` §3.5/§7, every `CL-E31C-*`/`CL-E31F-*` claim across all six
ledgers, compared to E31A's and E31F's live rule bodies). No compilable
claim grounds a specific tightening predicate; STOPPED per the arbitration
instruction ("attempt cure, stop-if-ungrounded — never invent claims").
Full evidence trail and both refuters' un-reconciled positions (Codex: not
defensible, live-probe-reachable; Kimi: defensible scope discipline, same
defect class as cured E33G) are recorded verbatim-in-substance in
"Residuals and open items for CP3" item 6 above, as an explicit CP3
decision item — not smoothed into either a fix or a dismissal here.

**FIX-3 (P2, Codex F7 + Kimi F5) — APPLIED, both parts.**
`fold_pack.py`: (a) `_write_pack()` rewritten to write via `tempfile.mkstemp`
in the destination directory, run prettier on the temp file, and only
`Path.replace()` onto the final path after a successful prettier exit —
a mid-write crash or a failed prettier run now leaves the original pack
file completely untouched instead of a half-formatted partial write.
(b) Added `_normalize_new_rule_valid_from()`, called from
`_apply_insertions()`, which overrides `valid_period.from` to
`"2026-08-19T00:00:00Z"` on all 8 newly-inserted rules — `review.e33g`
had been silently inheriting the stale `2026-07-24` date from
`cure-e33g.json` instead of the actual fold date. Both changes documented
in the module docstring. Confirmed via two consecutive `fold_pack.py` runs
producing a byte-identical sha256 (idempotence proof, §Gates above).

**FIX-4 (P2, Codex F5 + Kimi F6) — APPLIED.**
`test_pack_chain_and_pricing.py::test_seq9_previous_payload_sha256_chains_to_seq7_signed`
previously compared two DECLARED string fields (an assertion that both
sides claim the same string, not that either is actually derived from the
real seq-7 content). Rewritten to independently RECOMPUTE the canonical
hash via `hashlib.sha256(canonicalize_json(seq7_source)).hexdigest()`
(house pattern from `test_seq7_sponsor_witnesses.py:171`), asserting both
internal self-consistency of the signed envelope AND the chain to seq-9 —
following the repo's own state-verification doctrine (verify by CONTENT
recompute, never by comparing two proxies that could both be wrong the
same way).

**FIX-5 (P2, Codex F3/F6 + Kimi F1) — APPLIED, both parts.**
(a) Content-parity: added `TestInsertedRuleContentParity` (3 tests) and
`TestFullProductObjectParity` (1 test) to `test_pack_chain_and_pricing.py`
— independently recompiles `blocked7-rule-manifest.json` via
`compile_manifest`/`load_manifest` and re-reads `cure-e33g.json` from
source, then asserts the pack's `when`/`effect`/`scope` fields for every
inserted rule match the independently-recompiled source, byte-for-byte —
plus a full-product-object parity check (non-fold products byte-equal to
seq-7; the 11 fold products equal seq-7 except `pricing_key`, which equals
seq-8). Live-mutation-verified: swapped E23U/E23V's `eq` target values
directly in the pack file and confirmed `TestInsertedRuleContentParity`
fails with a clear diff (captured in §Gates above); pack restored and
sha256 re-verified byte-identical afterward. (b) New witness file
`test_seq9_new_rule_witnesses.py` (21 tests) drives the real
`evaluate_product()` evaluator per-product (house pattern from
`test_seq7_sponsor_witnesses.py`, chosen specifically to avoid the
cross-product REVIEW-masking that file's own docstring warns about) with
guilt+innocence pairs for E33A/B/C sponsor-type hard filters, E30E/E30F
sponsor-type SUPPORT gates, E33G's clean remote-work review trigger,
E23U/E23V's requested-product-code review gate, and UNKNOWN-sponsor-type /
UNKNOWN-requested-product-code semantics (always BLOCKED_UNKNOWN, never a
false EXCLUDE/REVIEW).

**FIX-6 (P2 doc honesty, Kimi F2/F3 + Codex F4) — APPLIED, all four parts.**
(a) Documented that E23U/E23V's review rules are production-inert until
`intent.requested_product_code` is actually collected —
`fact-mapper.ts:469` hard-codes `unknownFact(NOT_ASKED)` for this fact
today, pinned by the new witness test's UNKNOWN-requested-product-code
case; no user-visible regression since seq-7's `review.e33a/b/c` rules
already had this same property. (b) Documented the E30E/E30F over-support
delta (both admit a generic student profile as SUPPORTED-indistinguishable
across E30/E30E/E30F — an unmodelable KEK/bilateral-exchange distinction,
spec-sanctioned) and the catalog-vs-rule drift for E30E (`sponsor_types:
["EDUCATION"]` in the catalog record vs the rule admitting INDIVIDUAL too)
and E33B (`sponsor_types: ["NONE"]` in the catalog vs the rule admitting
GOVERNMENT too) — E30F's own catalog record is NOT drifted post-FIX-1.
(c) Documented that `review.e33g.income-evidence`'s `source_refs`
(Kepmen M.IP-08.GR.01.01/2025, Permenkumham 22/2023 jo. 11/2024) are
framing-only citations that do not independently corroborate the
USD 60,000/year threshold — the grounding claim `CL-E33G-02` is
VERIFIED-WITH-CAVEAT, resting on Bali Zero's internal operational guide
(`e2b-batch2-claim-ledger.md:115-124`), not primary law. (d) Relabeled the
C2/E31C residual item to carry FIX-2's outcome and both refuters'
un-reconciled positions verbatim-in-substance, per "Residuals and open
items for CP3" item 6 above.

**Findings NOT separately itemized above** (folded into the fix
descriptions they map to, no independent disposition needed): Codex's
observation that the pre-fix sha256 would necessarily change once FIX-1/
FIX-3b landed (confirmed — see §Gates, new sha256
`e3c1457952722706ec59b0a23e66c7d7a6a7b88735cda982b54957f5e4648660`); Kimi's
note that the pre-fix witness coverage for the 8 newly-inserted rules was
zero (resolved by FIX-5b's 21-test file).

No finding from either refuter was DEROGATED (dismissed without a fix or a
recorded reason) — every finding maps to an APPLIED fix, or in FIX-2's
case, to a STOPPED attempt with its full evidence trail and both refuters'
positions preserved for CP3, not resolved unilaterally by this session.
