---
date: 2026-08-12
domain: visa
client_case: none
sources:
  - Live replay against production rule pack sequence 7 (2026-08-12, this session)
  - research/visa/2026-08-12-gold-replay-live-report.json (machine-readable evidence artifact)
  - backend/tests/services/visa_engine/_gold_fixtures.py (the 20 canonical spec §7 personas)
adversarial_review: codex
---

# G-b measured for the first time: 6/20 against the active pack

## What was measured, and why it had never been measured before

Gate criterion **G-b** requires the 20 canonical gold personas to replay through the engine with
zero *unexplained* divergences. Until today the only replay that existed ran the personas against a
**hand-written fixture pack** (`_gold_fixtures.build_gold_compiled_pack`), never against the signed
pack actually serving production; `shadow_evidence.py` says so itself, reporting G-b as permanently
"unmeasured here". The endpoint has accepted `traffic_source=synthetic_gold` behind
`X-Visa-Driver-Token` since the SHADOW wiring landed, but no consumer was ever written for it.

The consumer now exists (`backend/scripts/visa_engine/gold_replay_driver.py`). This is its first
live run.

**Result: 6/20 match, 14 divergences, 0 of them explained.** G-b is therefore **RED with numbers**,
where before it was red for want of any measurement at all.

- Pack served: sequence **7**, version `2026.8.11`, `rule_pack_id 453ee842-7f35-5d77-b460-31d67e2784c2`,
  `payload_sha256 3d068aef…9f82` — consistent across all 20 calls (no mid-run activation).
- Rows written: 20, labelled `traffic_source=synthetic_gold`, so they feed G-a-**breadth** and do
  **not** contaminate G-a-vol.

## Arming step required to run it at all

The live run first returned `400 Synthetic traffic_source classes are not accepted from anonymous
callers`. The gate needs **both** the class armed in `VISA_ENGINE_EVALUATE_ALLOW_SYNTHETIC_SOURCES`
**and** a valid driver token (`visa_oracle_evaluate.py:345-354`). The token was valid — the same
token had just been accepted for `synthetic_driver` — so the deployed allow-list contained only
`synthetic_driver`. Since the parser keeps only migration 256's two synthetic classes and discards
everything else, the live set was provably exactly `{synthetic_driver}`, which made adding
`synthetic_gold` a non-destructive edit rather than a guess. Set on `nuzantara-rag` this session;
rolling restart clean, all machines healthy. Reverting is a single secret edit.

## The divergences

Most of these are **expected by construction and are not defects**: the personas encode the fixture
pack's product catalogue, while sequence 7 carries the real 38-product catalogue, so a persona whose
fixture expectation was `NO_SUPPORTED_PATH` can legitimately find a real product today. They still
must each be dispositioned in writing before G-b can go green — that is precisely what the criterion
demands, and the report carries a `null` explanation field per row to be filled in.

| # | Persona | Expected (fixture) | Actual (seq-7) |
|---|---|---|---|
| 1 | ID citizen excluded outright | `NO_SUPPORTED_PATH` | `HUMAN_REVIEW_REQUIRED` — `CITIZENSHIP_LIST_DIVERGENCE` |
| 2 | conflicting nationality evidence | `HUMAN_REVIEW_REQUIRED` | same state, extra `CALLING_VISA_REVIEW` |
| 5 | minor without confirmed guardian | `HUMAN_REVIEW_REQUIRED` | same state, different reason codes |
| 6 | minor child **with** confirmed guardian | `SUPPORTED_CANDIDATES [E31]` | `HUMAN_REVIEW_REQUIRED` — `MINOR_GUARDIAN_PRIVACY_REVIEW` |
| 7 | adult spouse, registered marriage | `SUPPORTED_CANDIDATES [E31]` | `SUPPORTED_CANDIDATES [C1, E31A, E31B, E31]` |
| 8 | as #7, marriage not registered | `NEEDS_INPUT` | `SUPPORTED_CANDIDATES [C1, E31D]` |
| 9 | investor, direct onshore | `NO_SUPPORTED_PATH` | `SUPPORTED_CANDIDATES [D12]` |
| 10 | same investor facts via structure | `HUMAN_REVIEW_REQUIRED` | `SUPPORTED_CANDIDATES [D12]` |
| 15 | tourism + employment purpose | `SUPPORTED_CANDIDATES [E23]` | `NEEDS_INPUT` |
| 16 | **investor capital 1 IDR below minimum** | `NO_SUPPORTED_PATH` | **`SUPPORTED_CANDIDATES [D12]`** |
| 17 | investor at fixture minimum | `SUPPORTED_CANDIDATES [E28A]` | `SUPPORTED_CANDIDATES [D12]` |
| 18 | obsolete code, plain | `NEEDS_INPUT` | same state, `OBSOLETE_PRODUCT_CODE` count 1→3 |
| 19 | obsolete code, corrected | `SUPPORTED_CANDIDATES [C1]` | `SUPPORTED_CANDIDATES [B1, C1]` |
| 20 | onshore conversion wanted | `NEEDS_INPUT` | `HUMAN_REVIEW_REQUIRED` — `BRIDGING_FROM_VISIT_ITK_PROHIBITED` |

## The one that is not routine — read this before dispositioning the rest

**Persona 16 is a deliberate negative control**: an investor sitting **one rupiah below** the capital
minimum, authored to prove the engine refuses. Against sequence 7 it returns `SUPPORTED_CANDIDATES
[D12]`. Personas 9, 10 and 17 land on the same product from adjacent investor facts, so this is a
family, not a one-off.

Two readings are possible and they are **not** equally comfortable: either D12's rules in the active
pack carry no capital threshold at all, or they carry one whose value and shape differ from the
fixture's. The first would mean the engine can propose an investor route to an applicant who does not
meet the statutory floor — the exact class of error this whole programme exists to prevent, and worth
noting that BKPM 5/2025 moved paid-up PMA to IDR 2.5 bn while the fixture predates it.

**This has not been diagnosed here.** Deciding which reading is true requires reading D12's rules in
the sequence-7 pack source, and that read is the first thing the next session should do — before any
disposition text is written for the other thirteen rows, because a divergence that is actually a
missing legal gate must not be filed away as "expected by construction" alongside its neighbours.

Direction matters when triaging the rest: rows 1, 5, 6, 15 and 20 diverge **toward abstention**
(review or needs-input where support was expected), which is the fail-safe direction and is a PASS
under G-c's own wording. Rows 8, 9, 10, 16 and 17 diverge **toward support**, and every one of those
needs an affirmative reason before it is accepted.

## Adversarial review

The driver was written by an external Codex GPT-5.6 seat and its diff reviewed cross-family before
commit; the live run, the arming step and this reading of the results were performed and verified by
a separate session (generator ≠ grader). Surviving objections and their dispositions:

- *"Divergences prove the driver is wrong."* Refuted by construction: the report records the pack
  identity returned by the endpoint, the pack was consistent across all 20 calls, and 6 personas do
  match — a broken mapper would fail uniformly, not selectively.
- *"6/20 means the engine is broken."* Not supported. The personas encode a fixture catalogue; the
  divergence set is dominated by catalogue difference. The claim this document makes is narrower and
  survives that objection: G-b is unproven, and one negative control fails toward support.
- *"The offline mode could have answered this without touching production."* It could not. Offline
  replays a pack **source file** in the repo and says so explicitly; only the live path proves what
  the deployed engine answers, which is what G-b is about.
