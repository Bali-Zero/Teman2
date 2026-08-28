---
date: 2026-08-28
domain: visa
client_case: none — Visa Oracle gold coverage & divergence adjudication (offline, pack seq-13)
sources:
  - apps/backend-rag/backend/tests/services/visa_engine/test_evaluator_gold.py (the 20 canonical gold personas, spec §7)
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-013.source.json (+ .signed.json, seq 13, v2026.8.23)
  - apps/backend-rag/backend/scripts/visa_engine/gold_coverage_eval.py (offline single-persona evaluator, this PR)
  - apps/backend-rag/backend/scripts/visa_engine/gold_coverage_replay.py (corpus runner, this PR)
  - apps/backend-rag/backend/scripts/visa_engine/reachability_report.py (reachability/gap generator)
  - apps/backend-rag/backend/tests/services/visa_engine/gold_coverage/personas/*.json (18 synthetic personas, this PR)
  - research/visa/2026-08-15-gold-divergence-disposition.md (seq-7 disposition matrix, anchor for delta)
  - research/visa/2026-08-15-gold-family-refuter.md (E31B/E31D repair acceptance criteria, lines 177-195)
adversarial_review: >
  Twin-lane (generator≠grader) adjudication ran 66 of 98 planned lanes before two
  consecutive session-window caps; the 9 cross-family tie-breaks (codex/kimi) and the
  5 realism batches did NOT complete. Per-lane verdict artifacts were subsequently
  lost to a /tmp cleanup. Every number in this report was re-derived deterministically
  from the repo on 2026-08-29 (commands in §8); cause labels in §2 are this session's
  proposals informed by the 2026-08-15 disposition, not twin-agreed verdicts.
status: PROPOSED — no divergence accepted, no pack changed, no expectation edited
---

# Visa Oracle — gold coverage & divergence adjudication (offline, pack seq-13)

**TL;DR.** Replayed offline (verify → compile → evaluate → public-policy adapters), the
highest signed pack in the repo (seq-13, v2026.8.23) matches only **4 of the 20 canonical
gold personas**. Of the 16 divergences, most measure **expectation drift** — the gold
expectations were authored against the 5-product FIXTURE pack, not this 38-product
catalogue — but two are **confirmed pack defects that fail open** (E31B accepts a sponsor
with *no* status; three E31D SUPPORT rules fire on FAMILY intent alone), unchanged since
seq-7. Separately, this work adds the first **engine-proven synthetic gold corpus**: 18 of
the 25 SUPPORT-reachable-but-never-expected products now have a committed persona that the
replay proves SUPPORTED, behind a fail-closed floor test.

## 1. Measured baseline

All numbers measured 2026-08-29 against `rulepack-prod-013` (**assumption, stated not
proven: seq-13 = highest signed pack in the repo; DB activation state was not checked** —
production may pin a different sequence).

| Measure | Value |
|---|---|
| Gold personas matching in full (state + candidates + missing + review/no-path/notice codes) | **4 / 20** (personas 3, 4, 12, 18) |
| Divergent personas | **16**: 1, 2, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 19, 20 |
| Products in pack / rules | 38 / 111 |
| Products with ≥1 SUPPORT rule (reachable) | **29** |
| Products with zero SUPPORT rules (statically blocked) | **9**: E23U, E23V, E28B, E28C, E28D, E28F, E33A, E33B, E33C |
| Products never appearing in any gold expectation | **34 / 38** |
| FactRegistry paths referenced by ≥1 rule | 37 / 49 (**12 facts referenced by zero rules**) |
| E31 vocabulary drift | gold expects `E31`; the pack only has `E31A…E31J` |

The 12 zero-rule facts include `family.stepchild_birth_certificate_confirmed` and
`family.stepchild_marriage_certificate_confirmed` — the exact evidence facts the E31D
rules should require (§5).

## 2. Divergence matrix (seq-13, offline)

Expected→actual columns are machine-measured (full rows with overrides in
`gold-offline.json`, regenerable via §8). **Cause** and **risk** are PROPOSED
classifications (see adversarial_review note): the twin-lane run agreed on 7 of 16 and
disagreed on 9 (personas 1, 6, 11, 13, 14, 15, 16, 17, 20 — flagged ⚖); the per-lane
verdicts did not survive, so ⚖ rows carry reduced confidence and are first in line for a
future cross-family tie-break.

Cause taxonomy: DRIFT = expectation authored for the fixture pack · VOCAB = expects a code
the pack doesn't have · PACK = defective rule · ADAPTER = public-policy adapter ·
OWNER = legal/product decision required · CODES = same state, different reason codes.

| # | Label (short) | Expected → actual | Cause | Risk vs expectation | Delta vs 15/8 (seq-7) |
|---|---|---|---|---|---|
| 1 ⚖ | ID citizen excluded outright | NO_SUPPORTED_PATH → HUMAN_REVIEW (`CITIZENSHIP_LIST_DIVERGENCE`) | OWNER (precedence: citizen hard-filter vs list divergence) | more cautious | unchanged |
| 2 | conflicting nationality | same state; codes `CITIZENSHIP_EVIDENCE_CONFLICT` → `CALLING_VISA_REVIEW`+`CITIZENSHIP_LIST_DIVERGENCE` | CODES / OWNER (canonical review vocabulary) | same state, different codes | unchanged |
| 5 | minor, guardian unconfirmed | same state; adds `MINOR_GUARDIAN_PRIVACY_REVIEW` | ADAPTER (additive privacy hold) | more cautious | unchanged |
| 6 ⚖ | minor, guardian confirmed → E31 | SUPPORTED [E31] → HUMAN_REVIEW (privacy hold) | ADAPTER + VOCAB | more cautious | unchanged |
| 7 | adult spouse, registered marriage → E31 | SUPPORTED [E31] → SUPPORTED [C1, E31A, E31B, E31D] | VOCAB + **PACK** (E31B/E31D fail-open inflate the candidate set) | same state, inflated candidates | unchanged — defect unrepaired |
| 8 | spouse, marriage unverified → needs input | NEEDS_INPUT → SUPPORTED [C1, E31D] | **PACK** (E31D fail-open converts a missing-evidence case into support) | **more permissive** | unchanged — defect unrepaired |
| 9 | investor, direct onshore → unsupported | NO_SUPPORTED_PATH → SUPPORTED [D12] | OWNER (is D12 a legitimate alternative visit route?) | more permissive as a route substitution | unchanged |
| 10 | investor via status bridging → review | HUMAN_REVIEW → SUPPORTED [D12] | OWNER (same D12 substitution question) | more permissive | unchanged |
| 11 ⚖ | clean remote worker → E33G | SUPPORTED [E33G] → HUMAN_REVIEW (`E33G_INCOME_EVIDENCE_REVIEW`) | DRIFT/OWNER (income-evidence gate not in fixture model) | more cautious | **changed** — was `SAFETY_CRITICAL_SOURCE_STALE` on 15/8 |
| 13 ⚖ | remote worker, fact unprovided | same state; missing `work.serves_indonesian_clients` → `sponsor.type` | DRIFT (interview model differs from fixture) | same state, different question | changed axis (was stale-source adjacent) |
| 14 ⚖ | tourism + remote work → E33G only | SUPPORTED [E33G] → HUMAN_REVIEW (`E33G_INCOME_EVIDENCE_REVIEW`) | DRIFT/OWNER (as 11) | more cautious | **changed** — was `SAFETY_CRITICAL_SOURCE_STALE` on 15/8 |
| 15 ⚖ | tourism + employment → E23 only | SUPPORTED [E23] → NEEDS_INPUT (missing `intent.requested_product_code`) | OWNER (whole-intent coverage vs partial-candidate semantics) | more cautious | unchanged |
| 16 ⚖ | capital 1 IDR below minimum → no path | NO_SUPPORTED_PATH → SUPPORTED [D12] | OWNER (negative control lands on a different route; disposition warns not to call it a threshold bypass until D12 route semantics are settled) | more permissive | unchanged |
| 17 ⚖ | investor at minimum → E28A | SUPPORTED [E28A] → SUPPORTED [D12] | OWNER (E28A facts model vs fixture capital model) | same state, different product | unchanged |
| 19 | obsolete code, complete tourism facts → C1 | SUPPORTED [C1] → SUPPORTED [B1, C1] | OWNER (B1 catalogue expansion needs eligibility evidence + sibling-negative control) | same state, added candidate | notice-multiplicity half CLOSED on 15/8; B1 question open |
| 20 ⚖ | onshore conversion, status unprovided | NEEDS_INPUT → HUMAN_REVIEW (`BRIDGING_FROM_VISIT_ITK_PROHIBITED`, `BRIDGING_TO_BRIDGING_PROHIBITED`) | OWNER (unknown status: ask first vs escalate conservatively) | more cautious | unchanged |

Personas 3, 4, 12, 18 match in full (18's notice-multiplicity fix, PR #4195, held).

## 3. §Meta-pattern

**The single defective belief generating most of this table: "the 20 gold expectations
describe the production engine." They do not — they were authored for the 5-product
FIXTURE pack, and the production catalogue has evolved underneath them for three signed
sequences without the expectations ever being re-ratified.**

Evidence: the expectations use a product vocabulary the pack does not contain (`E31`,
`E23`, `E28A`-as-terminal vs the pack's `E31A…J` split and `D12` routes); 34 of the pack's
38 products appear in no expectation at all; and the divergence matrix is essentially
byte-stable across seq-7 → seq-13 (13 of 16 rows unchanged) — the pack is not drifting
away from the gold, the gold was never anchored to this pack. The practical consequence
cuts both ways: (a) a red gold suite cannot distinguish a pack regression from fixture
drift, so it protects nothing (the 2026-08-15 disposition already ruled these
explanations may only be *proposed*, never session-accepted); (b) the two real defects
this report confirms (§5) were *invisible* to the gold suite for three sequences because
they hide inside rows everyone had learned to expect red.

## 4. Coverage results — the synthetic gold corpus

New in this PR: `gold_coverage_eval.py` (single persona → offline replay, exact
verify→compile→evaluate→adapters path), `gold_coverage_replay.py` (corpus runner, exit 0
only when total>0 and failed==0), a **committed corpus of 18 synthetic personas** — one
per product, each proven `SUPPORTED_CANDIDATES` with its product among the candidates —
and `test_gold_coverage_floor.py`, a fail-closed floor: empty corpus, filename/product
mismatch, or any persona losing its product's support goes red. Verified green: 11 passed
across the three suites (independently re-run with `-v`; note: `pytest-testmon` +
`-q --no-header` silently suppresses the final summary line).

| Covered (18) | Not yet covered (7) | Statically blocked (9) |
|---|---|---|
| A1, B1, BRIDGING, C2, C6, D1, D2, D12, E30, E30A, E30B, E30E, E30F, E31A, E31B, E31C, E31D, E31F | E31E, E31G, E31H, E31J, E33, E33E, E33F | E23U, E23V, E28B, E28C, E28D, E28F, E33A, E33B, E33C |

- The 7 uncovered products are **unattempted, not proven unreachable**: their authoring
  lanes died on the session cap. Each has ≥1 SUPPORT rule; authoring them is mechanical
  follow-up with the committed helper.
- The 9 blocked products have zero SUPPORT rules by construction (census regenerable from
  the pack source; deliberately untouched — they are Pro V1's scope).
- **Realism refutation (external seats) did not run.** The corpus personas are
  engine-proven but not yet independently reviewed for applicant plausibility; treat
  `realism_notes` as unaudited.
- Fail-open smell visible even here: several family/visit personas acquire `C1` and
  `E31D` as co-candidates they did not ask for — consistent with §5.

## 5. Findings for the pack owner (fix_owner = pack)

Both confirmed on seq-13 source by rule inspection **and** by live offline probes
(2026-08-29); both byte-identical since seq-7; repair acceptance criteria already written
in `research/visa/2026-08-15-gold-family-refuter.md:177-195`.

1. **`el.e31b-spouse-itas-support` accepts a sponsor with no status.** Its predicate ends
   with `{"fact": "family.sponsor_status_code", "op": "known"}` — any KNOWN value passes,
   including `"NONE"`. Probe: spouse + registered marriage + `sponsor_status_code="NONE"`
   → `SUPPORTED_CANDIDATES ['C1','E31B','E31D']`. A spouse-ITAS support rule must require
   the sponsor to actually hold a qualifying status (ITAS/ITAP), not merely an answered
   question. (`el.e31b-sponsor-itas-itap` has the same terminal `op:known` clause.)
2. **All three `el.e31d-*` SUPPORT rules fire on FAMILY intent alone.**
   `el.e31d-stepchild-support`, `el.e31d-step-parent-relation`,
   `el.e31d-sponsor-mixed-marriage` each require only
   `intent.purposes ∩ {FAMILY}` — no relation, no marriage/birth evidence, no sponsor
   fact. Probe: a persona whose *only* fact is FAMILY intent →
   `SUPPORTED_CANDIDATES ['C1','E31D']`. This is what converts persona 8
   (marriage *unverified*) from NEEDS_INPUT into SUPPORTED — the more-permissive
   direction, on a family-reunification product.
3. **The evidence facts the E31D rules need exist and are dead.**
   `family.stepchild_birth_certificate_confirmed` and
   `family.stepchild_marriage_certificate_confirmed` are registered FactPaths referenced
   by **zero rules** (2 of the 12 zero-rule facts). The repair is not to invent new
   vocabulary — it is to wire the vocabulary that already exists into the E31D
   predicates. This is the corpus-wide scar in miniature: *a fact never asked and never
   used disarms every rule that should depend on it.*

## 6. §Owner decisions (Legge 5)

No divergence in §2 may be accepted by a session; each OWNER row reduces to a question
for Zero (with the 2026-08-15 disposition as the fuller brief):

1. **Citizen hard-filter precedence (p1):** when citizenship-list evidence conflicts,
   does the Indonesian-citizen hard filter win (expectation) or must the conflict
   escalate to review (pack)? Accepting the pack changes the terminal state vocabulary.
2. **Canonical review codes (p2):** ratify `CALLING_VISA_REVIEW`+`CITIZENSHIP_LIST_DIVERGENCE`
   as the canonical escalation vocabulary, or restore `CITIZENSHIP_EVIDENCE_CONFLICT`.
3. **Minor privacy hold (p5, p6):** is `MINOR_GUARDIAN_PRIVACY_REVIEW` always additive,
   or can a confirmed guardian + explicit consent facts ever clear it? (Do not remove
   the hold in a pack edit without an approved privacy interpretation.)
4. **D12 route substitution (p9, p10, p16, p17):** may a visit route (D12) be proposed
   when the applicant's stated intent is investment/conversion — including 1 IDR below
   the investor minimum? Either ratify D12-as-pre-investment-route with explicit framing
   guarantees, or exclude it for investment-intent requests.
5. **Multi-purpose semantics (p14, p15):** whole-intent coverage (no candidate unless
   every purpose is covered) vs partial candidates with unsupported purposes visibly
   flagged.
6. **B1 catalogue expansion (p19):** accept B1 beside C1 for complete tourism facts
   (needs eligibility evidence + a B1 sibling-negative control), or exclude it.
7. **Unknown status on conversion (p20):** ask-first (NEEDS_INPUT) vs conservative
   escalation with named prohibitions.
8. **E33G income-evidence gate (p11, p14):** ratify the always-on
   `E33G_INCOME_EVIDENCE_REVIEW` hold for remote workers, or define the income facts
   that clear it.

## 7. §Solo-operatore

Single-operator consequences of this report: (a) the gold suite is currently a
**16/20-red wall nobody reads** — every future regression lands invisibly inside it;
until the expectations are re-ratified (owner act), the committed floor test in this PR
is the only green/red signal actually wired to the production pack; (b) the two §5
defects sit on a *family-reunification* product — the population least able to absorb a
wrong "supported" answer and exactly where a solo operator has no second reviewer;
(c) every §6 decision is one WhatsApp-length answer each — none requires Zero to read
the pack.

## 8. Method & limits

- **Offline ≠ production.** Everything here replays the repo's highest *signed* pack
  through the exact engine path but outside the live service: DB activation, interview
  flow, and API adapters upstream of the evaluator are not exercised. Before treating
  seq-13 as "the" pack, check the active sequence in the DB.
- **Synthetic only.** Every persona is invented; no real applicant data exists anywhere
  in this lane.
- **What survived vs what was lost.** The twin-lane adjudication (16 personas × opus+blind,
  25 products × author+blind, blocked census, 9 refuters, 5 realism batches, report lane)
  completed 66/98 lanes across two session windows, then hit the account cap twice; the
  per-lane JSON artifacts were later destroyed by a /tmp scratch cleanup. Surviving
  machine facts used here: the 9 cause-disagreement ids, the achieved-coverage lists, and
  the committed corpus itself. **Not done: cross-family tie-breaks (codex/kimi) and
  realism refutation.** Cause labels in §2 are single-session proposals.
- **Reproduce every number** (from `apps/backend-rag`, venv active, `PYTHONPATH=.`):
  - 20-persona replay: import `PERSONAS` from
    `backend.tests.services.visa_engine.test_evaluator_gold`, evaluate each via
    `backend.scripts.visa_engine.gold_coverage_eval._evaluate` and compare all six
    expectation fields → 4/20, the §2 matrix.
  - Fail-open probes (§5): `_evaluate` on `{FAMILY intent, SPOUSE, marriage_registered,
    sponsor_status_code="NONE"}` and on `{FAMILY intent}` alone.
  - Reachability + zero-rule facts: `python -m backend.scripts.visa_engine.reachability_report
    --pack .../rulepack-prod-013.source.json --out-dir <dir>`.
  - Blocked census: group the pack's rules by named `product_version_ids`; a product with
    no SUPPORT rule (named or GLOBAL→named) is blocked → the 9 codes.
  - Corpus floor: `pytest backend/tests/services/visa_engine/test_gold_coverage_floor.py
    backend/tests/scripts/visa_engine/ -q` → 11 passed.
