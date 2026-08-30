---
date: 2026-08-30
domain: compliance
client_case: none
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

1. **#5346** (armed) — two typed-by-currency components. Closes eleven
   demonstrated holes and unblocks the all-in price. Ships now.
2. **#5337** (disarmed, code finished, 88 tests) — the split-fee veto. Re-arms
   only after #5346 is live, because merged alone it turns a wrong answer into
   NO answer: every shape then fails one veto or the other except an accidental
   parsing loophole (`IDR 26.5m` canonicalizes to 265, under the floor).
3. **This contract** — one PR for the dataclass and the extraction, one for each
   consumer. `RATE_PER_UNIT` first: it is the one that is currently costing a
   real client a real apology.

## Declared and deliberately unclosed even after this contract

An amount whose role and group are right but whose VALUE is wrong for the
client's actual case (wrong package, expired price) is not an arithmetic
problem and no veto over source text can catch it. That belongs to the label
gate and to PricingTool freshness, and it should stay there.
