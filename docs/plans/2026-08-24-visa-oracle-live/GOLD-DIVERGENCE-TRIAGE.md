# Gold-persona divergence triage (owner switchboard #3)

Run 2026-08-24 on Pro: `gold_replay_driver.py --offline` against the signed pack
`rulepack-prod-013` (sequence 13, kid `prod-2026-07-1`, signature verified by the driver).

```
matches 4/20    personas_with_divergence 16    explained_divergences 0    unexplained 16
```

The 16 had never been opened. They are opened here. **They are not 16 engine defects — they are
one defect and fifteen explanations**, and the explanations matter more than the count.

## The headline

| Class                                                        | N     | What it means                                             |
| ------------------------------------------------------------ | ----- | --------------------------------------------------------- |
| The corpus tests a smaller catalogue than the engine has     | 7     | Not a defect                                              |
| The engine is deliberately MORE conservative than the corpus | 5     | Not a defect — a later safety rule firing                 |
| The engine asks a different question first                   | 2     | Not a defect — reachable either way                       |
| **A real dead end**                                          | **1** | **#15 — and it is the disease lane V1 is already curing** |

## Class 1 — the corpus tests five products; the engine has thirty-eight (7 personas)

`_gold_fixtures.py` builds a SYNTHETIC pack containing exactly five product codes: **E28A, E31,
E23, E33G, C1**. Measured, not assumed: `grep -c 'D12' _gold_fixtures.py` returns **0**. So do
E31A/E31B/E31D and B1.

Personas **7, 8, 9, 10, 16, 17, 19** diverge because the engine answers with a product the corpus
has never heard of. Their `NO_SUPPORTED_PATH` expectations do not mean _"no visa in Indonesia fits
this person"_ — they mean _"none of these five fits"_. Read against the real catalogue they are
simply wrong questions.

The sharpest example, and the one most likely to be misread as a scandal: **persona 16, "investor
capital 1 IDR below minimum -> no supported path"**, where the engine offers **D12**. D12 is the
_pre-investment_ multiple-entry visit visa. Offering it to an investor who falls just under the
KITAS threshold is plausibly the **commercially correct** answer — come and look around first. The
corpus could not say that because D12 did not exist in its world.

D12 has carried six ELIGIBILITY rules since pack 009 — this is not recent drift; the corpus has
simply never been re-based.

## Class 2 — the engine is more conservative than the corpus, on purpose (5 personas)

Each of these is a safety rule that was added AFTER the corpus was written, now correctly firing:

| #   | Persona                                        | The engine adds                                                                   |
| --- | ---------------------------------------------- | --------------------------------------------------------------------------------- |
| 1   | ID citizen excluded outright                   | `CITIZENSHIP_LIST_DIVERGENCE` — escalates to a human instead of refusing outright |
| 6   | minor child with confirmed family sponsor      | `MINOR_GUARDIAN_PRIVACY_REVIEW`                                                   |
| 11  | clean remote worker, no local footprint        | `E33G_INCOME_EVIDENCE_REVIEW`                                                     |
| 14  | tourism + remote-work purposes                 | `E33G_INCOME_EVIDENCE_REVIEW`                                                     |
| 20  | onshore conversion, status+overstay unprovided | `BRIDGING_FROM_VISIT_ITK_PROHIBITED`, `BRIDGING_TO_BRIDGING_PROHIBITED`           |

**Persona 20 is worth naming: that is Zero's bridging ruling of 2026-08-23 being enforced.** The
corpus expected the engine to ask for more facts; the engine instead recognises a prohibited
bridging transition and stops. That is the ruling working, showing up as a "failure".

A divergence in this direction costs a consultant's time. The opposite direction costs a wrong
visa. These five are the cheap side, and they should be re-based, not "fixed".

## Class 3 — a different question first (2 personas)

- **#2** conflicting nationality evidence: expected `CITIZENSHIP_EVIDENCE_CONFLICT`, got
  `CALLING_VISA_REVIEW` + `CITIZENSHIP_LIST_DIVERGENCE`. Same state, richer reasons.
- **#13** remote worker: expected to be asked `work.serves_indonesian_clients`, asked `sponsor.type`
  instead. Same state; both are real, askable facts, so the interview still terminates.

## Class 4 — the one real defect: persona 15

```
#15  tourism + employment purposes -> E23 only, never C1
     expected  SUPPORTED_CANDIDATES  candidates=[E23]
     actual    NEEDS_INPUT           missing_facts=['intent.requested_product_code']
```

The engine does not answer. It asks for **`intent.requested_product_code`** — the fact that
`fact-mapper.ts` hard-codes to `unknownFact(NOT_ASKED)`, which the interview can never populate.

**This is a dead end, not a question.** The visitor is told more information is needed, and no
answer they can give will ever supply it. Every other divergence in this report ends with the
visitor somewhere — a product, a consultant, an honest refusal. This one ends nowhere.

It is the same disease that makes E28B/C/D/F invisible, and it proves the disease is **wider than
those four products**: here it damages **E23**, a product that is otherwise healthy, priced, and
proposed T2. Lane V1 is curing it. This persona is its regression test — it must flip from
`NEEDS_INPUT` to `SUPPORTED_CANDIDATES [E23]` when the cure lands, and that flip is the
falsifiable acceptance.

## What this means for switchboard #3

The mandate asks for a "gold-persona rehearsal — zero-divergence report engine<->consultants" for
Zero to acknowledge and sign.

**"Zero divergences" is the wrong target, and reaching it by rewriting expectations to match the
engine would be reward-hacking with extra steps.** Fifteen of these sixteen are the corpus being
older and smaller than the engine; forcing them to zero teaches us nothing and destroys the record
of five safety rules working.

The target that means something:

> **Every divergence explained, and none of them a dead end.**

Today: 16 explained (this document), 1 dead end (#15, cure in flight). When #15 flips, the report
is signable — with the divergences intact and accounted for, not erased.

## What must happen to the corpus, and what must not

**Must:** re-base the corpus onto the real signed pack. Today `test_evaluator_gold.py` deliberately
drives the synthetic fixture — legitimate, it tests the ENGINE, not legal policy — while
`gold_replay_driver.py` drives the real pack. Both are honest; **reporting only the first as "the
gold tests pass" is not.** Any statement about gold coverage must say which of the two it means.

**Must:** fix the dead assertion. The corpus asserts on product code **`E31`**, which this pack
does not contain (it uses E31A..E31J). It never fails, because the fixture pack contains whatever
the fixture declares. A persona naming a code absent from the real pack is an assertion that can
never go red.

**Must:** grow. **34 of 38 products are never any persona's `expected_candidates`.** A product can
be tier-mapped, priced, and reachable and still have never been exercised end to end. Per the
frozen C4 contract, a product card without a passing persona stays T3.

**Must not:** silence a Class-2 divergence by relaxing the safety rule that caused it. Five of them
are the engine protecting someone.

## Method notes, recorded because both bit this session

1. **The first cut of this triage was wrong and looked right.** It filtered personas on
   `p.get('match')` — a key that does not exist in this report (the fields are `divergence` /
   `differences`). The filter never fired, so all 20 personas were processed and reported as
   divergent. It was caught only because 20 did not reconcile with the summary's 16. The rerun
   asserts `len(divergent) == summary['personas_with_divergence']` inside the script, so next time
   the script fails instead of a human noticing. A filter that silently matches nothing is green.
2. **`gold_replay_driver.py --offline` picks the highest signed PRODUCTION pack in
   `contracts/packs` and logs that it did not check which pack is ACTUALLY active in production.**
   That is the honest behaviour, but it means this report describes the pack on disk, not
   necessarily the one serving traffic. A `--live` run is a different claim.
