---
date: 2026-08-30
domain: compliance
client_case: none
adversarial_review: kimi-k3
sources:
  - wa_outbox rows 379, 385, 387 (measured live, prod release 2026-08-30T17:24Z)
  - /api/wa-package/build, production, measured
  - adversarial rounds: codex gpt-5.6-sol xhigh (x2), kimi-code/k3
---

# The WhatsApp price veto needs a typed operand contract, not a better predicate

## Why this is a spec and not a fourth patch

Three adversarial rounds on `price_tokens_outside_sources` reached the same
conclusion by different routes, and two of the three said it in their own final
paragraph: **the guard cannot be made both sound and complete while its input is
a flat list of strings.** Each round broke the previous predicate with concrete
values, each fix was correct, and each fix revealed that the next question was
also unanswerable from the available data.

The Agent PR Contract's rule 8 says a surface that goes red three times for the
same cause is under-specified: write the spec, do not open the third correction.
This is that spec. PR #5346 ships the part that is defensible today; everything
below is what it cannot do and why no predicate over the current input could.

## What was measured, not argued

All three on the running prod release, `wa_finalize.py` byte-identical to
`origin/main` a53ea0f29f.

| row | question | outcome |
|---|---|---|
| 379 | Investor KITAS price (ID) | answered by SPLITTING the levy out of the client price |
| 385 | Investor KITAS price (EN) | correct all-in answer, but only after 3 attempts fell off |
| 387 | overstay 5 days, fine per day | **failed 5/5**, client apologised to |

Row 387 was fired **alone into a quiet thread**, so it is not the coalescing
artifact that confounded two other cases in the same cycle. The evidence package
for that query does carry the rate — `IDR 1,000,000`/day, PP 45/2024, confirmed
against the production build endpoint. The answer was rejected for multiplying
it by the five days the client asked about.

Attempt, defined: the retry ladder is 5 attempts, backoff `30·2^(n-1)` seconds,
45s per-attempt deadline, ~495s total span. "3 attempts fell off" (row 385) and
"failed 5/5" (row 387) both name positions on this same ladder, not an
undefined manual count. All three rows are reproducible against the prod
`wa_outbox` table via `~/Desktop/live-bot-test-loop/run_remote.sh _grade.py <id>`.

The same mechanism made Zero's 2026-07-17 ruling — one all-inclusive
client-facing price — unshippable, while its violation passed:

    "Total all-in ... Rp26.500.000"                  -> VETOED
    "biaya layanan Rp17.000.000. PNBP Rp9.500.000"   -> passes

**The anchoring veto was manufacturing the split-price defect.** Splitting is
the only presentation that keeps every figure verbatim-anchored.

## What the three rounds established

Round 1 (codex, BLOCK) killed *integer multiples*: the predicate divided the
GENERATED figure by a source figure and accepted any whole quotient, so one
`IDR 1,000,000/day` source authorized every whole million to 366 million.
**Divisibility is not derivation** — the multiplier must come from the
customer's question, and the function never receives it.

Round 2 (kimi K3, FIX-FIRST) killed the *magnitude floor* that replaced it:
`USD 59 = 45 + 14` from "Pasal 45" and "14 hari kerja"; `Rp7.275.000` from a
tourist statistic plus a real levy. Its diagnosis is the load-bearing sentence
of this whole document: **a number's role is not recoverable from its size.**

Round 3 (codex) found no new hole introduced by the fix, and concluded that
family, value, role, provenance and occurrence identity must travel with each
operand — which is round 1's closing recommendation, reached independently.

## The contract

`price_sources: Sequence[str]` becomes a sequence of typed operands:

```python
@dataclass(frozen=True)
class PriceOperand:
    family: str          # "IDR" | "USD" | ...  never inferred from a neighbour
    value: int           # canonical minor-unit-free integer
    role: PriceRole      # SERVICE_FEE | GOVERNMENT_LEVY | RATE_PER_UNIT
                         # | STATUTORY_MINIMUM | PENALTY | NON_MONETARY
    source_id: str       # chunk or PricingTool row it came from
    group_id: str | None # the product/package it belongs to
    occurrence: int      # so one fee cannot be charged twice
    unit: str | None     # "day" | "month" | None -- only for RATE_PER_UNIT
```

`NON_MONETARY` is not a courtesy: years, article numbers, KBLI codes,
quantities and statistics must be REPRESENTED and excluded, not silently
absent, or the next reader re-derives them from bare tokens.

### Two new classifiers this contract introduces, not zero

`role` and the question-side count are not free — assigning them is itself a
classification task, and the exact risk the contract must not paper over is
that moving a judgment upstream makes it LESS auditable, not more: a
mislabeled operand now carries the guard's blessing instead of the guard's
veto, which is worse than today's blunt block.

- **Role/unit extraction (index-time).** Owner: the ingestion pipeline that
  populates `PriceOperand.role` and `.unit` from PricingTool rows and retrieved
  chunks (see "Where the data already exists" below). Accuracy expectation:
  every operand a chunk carries resolves to a role, or explicitly to
  `NON_MONETARY` — there is no silent third state. Failure mode, fixed here so
  it cannot drift later: an operand whose role cannot be resolved with
  confidence is **not treated as authorizing**. The guard fails closed on it,
  the same as it would on an operand it never saw. A confident wrong label is a
  defect to fix in the extractor; a low-confidence label waved through is a
  defect in the contract, and this line forecloses it.
- **Count binding (question-time).** Owner: `_load_thread_context`, which
  already holds the customer's text and today drops it before finalization.
  Accuracy expectation: an NL count ("5 hari" / "seminggu" / "una settimana")
  binds to at most one `RATE_PER_UNIT` operand's multiplier. Failure mode: an
  unresolved or ambiguous count means the multiplied figure is **not
  authorized** — the guard vetoes rather than guesses, exactly as it does today
  for every other unrecoverable case.

## What the contract buys, item by item

| today's residual | closed by |
|---|---|
| honest multiplication (`5 x Rp1.000.000`) vetoed | `RATE_PER_UNIT` + `unit`, with the count bound to the QUESTION, never to the answer |
| percentage of a base (PPh 5%) vetoed | same: a typed base plus a rate from the source |
| 3-component total (PNBP + telex + fee) vetoed | `group_id` — same package, each `occurrence` used once, so N terms is safe where 3 was not |
| two real amounts from unrelated chunks summing | `group_id` mismatch |
| a bare token authorizing an amount by membership | `role=NON_MONETARY` |
| cross-family laundering in the membership path | `family` carried, not inferred |

Note what this does NOT need: a bigger model, a heuristic, or a threshold. Every
one of these is a field that exists upstream and is thrown away at the boundary.

## Where the data already exists

- **PricingTool rows** know their own role and package — they are the canonical
  source of `SERVICE_FEE` and the all-inclusive note. The all-in total should be
  COMPUTED there deterministically and passed as a `STATUTORY_MINIMUM`-style
  authorized figure, not reconstructed by a predicate guessing at arithmetic.
- **Retrieved chunks** carry the levy and the statutory rate; `role` and `unit`
  are a small extraction at index time, not at answer time.
- **The customer's question** carries the count ("5 hari"). It is present in
  `_load_thread_context` and dropped before finalization.

## Sequencing

1. **#5346** (armed) — adds `_summable_operands` / `_is_two_component_total`, a
   same-currency-family two-term sum over the raw source values. It does NOT
   type anything: it unblocks only the two-component all-in price, closing the
   six holes in the table above (not eleven — that count did not match the
   table and is corrected here). It is an ad-hoc precursor to the contract
   below, to be REPLACED once `PriceOperand` ships, not extended with more
   special-cased arithmetic. Ships now.
2. **#5337** (disarmed, code finished, 88 tests) — the split-fee veto. Re-arms
   only after #5346 is live, because merged alone it turns a wrong answer into
   NO answer: every shape then fails one veto or the other except an accidental
   parsing loophole (`IDR 26.5m` canonicalizes to 265, under the floor).
3. **This contract** — one PR for the dataclass and the extraction, one for each
   consumer. `RATE_PER_UNIT` first: it is the one that is currently costing a
   real client a real apology.

## The asymmetry: sources are typed, the answer is still free prose

Everything above types what the guard is allowed to draw FROM. It does nothing
about what the guard reads: the generated answer stays a flat string,
extracted by the same regex surface that broke three times. Typing the sources
closes the holes in the table above; it does not make the guard sound, because
soundness also depends on correctly reading the number back out of prose the
model wrote — and that side of the boundary is untouched by this contract.

Five texts a typed-source guard still cannot resolve, because the failure is
on the answer side, not the source side:

    "Kurang lebih Rp5 juta untuk 5 hari overstay."
      -- multiplier word ("kurang lebih") + approximation, no bare product to anchor

    "Totalnya lima juta rupiah."
      -- zero digit tokens: pass vacuously (unsound) or veto (incomplete)?

    "USD 1.650 (~Rp26,5 juta)"
      -- derived conversion; no exchange rate is a typed field

    "Con lo sconto 10%: Rp23.850.000"
      -- a conversational discount rate is not in any source

    "Rp1.000.000 per hari -- quindi per 5 giorni, 5 x Rp1.000.000 = Rp5.000.000"
      -- cites the same rate twice; occurrence-per-use enforced on the answer
         side would veto a correct pedagogical restatement

This document does not propose a solution for the answer side — that would be
inventing a fourth patch under a different name. It names the gap as the next
surface after this contract ships, and fixes these five texts as its
acceptance corpus: nothing closing this surface should claim done without
resolving all five correctly.

## Declared and deliberately unclosed even after this contract

An amount whose role and group are right but whose VALUE is wrong for the
client's actual case (wrong package, expired price) is not an arithmetic
problem and no veto over source text can catch it. That belongs to the label
gate and to PricingTool freshness, and it should stay there.

## Adversarial review

**Seat:** `kimi-k3` (Moonshot Kimi K3, `kimi -m kimi-code/k3`) — a known seat
in `scripts/check_adversarial_review.py`'s `KNOWN_SEATS`, run on the frozen
text of this spec. **Date:** 2026-08-31. **Verdict:** FIX-FIRST.

A Codex round was ATTEMPTED on this same spec and ABANDONED: it ran past 250KB
of output writing test code instead of a review, and was killed without
returning a verdict. It is not counted as a seat here.

Five findings, all ACCEPTED and folded in:

1. **`role` relocates the ambiguity upstream, where it is less auditable than
   the flat-string guard it replaces.** Folded into "Two new classifiers this
   contract introduces, not zero" — owner, accuracy expectation, and a
   fail-closed failure mode for the role/unit extractor.
2. **Unsupported "measured" claims** — "eleven" demonstrated holes against a
   six-row table, "attempts" used without a definition, no reproducible query
   for rows 379/385/387. Folded into "Sequencing" (eleven corrected to six)
   and "What was measured, not argued" (attempt-ladder definition plus the
   `run_remote.sh` reproduction path).
3. **Sequencing forward dependency** — #5346 was credited with unblocking the
   all-in price as though it typed operands; it does not. Folded into
   "Sequencing" item 1: #5346 is now described as the ad-hoc same-currency
   two-term-sum precursor it actually is, to be replaced rather than extended.
4. **The contract types the sources; the answer stays free prose** — the
   load-bearing finding. Folded into the new "The asymmetry: sources are typed,
   the answer is still free prose" section, naming the gap openly and fixing
   the reviewer's five texts as the acceptance corpus for whatever closes it
   next.
5. **The two classifiers this contract introduces (role/unit extraction,
   question-side count binding) were underspecified.** Folded into the same
   "Two new classifiers" subsection as finding 1, with the count-binding half
   given the same three requirements: mechanism, error mode, fail-closed
   fallback.

No finding was rejected.
