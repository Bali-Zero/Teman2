---
date: 2026-09-01
domain: compliance
client_case: false
status: SPEC — not yet built
sources:
  - "measured live: WhatsApp thread 30, 22 exchanges, 2026-09-01 08:31–09:28 UTC"
  - "apps/backend-rag/backend/services/rag/agentic/reasoning_utils.py::calculate_evidence_score"
  - "apps/backend-rag/backend/services/rag/agentic/_abstain_policy.py DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT"
  - "Sufficient Context: A New Lens on Retrieval Augmented Generation Systems — arxiv.org/abs/2411.06037"
---

# The WhatsApp abstain gate measures relevance by lexical overlap, so it is blind across languages

## Verdict

`calculate_evidence_score` decides whether the bot may answer, and it derives the
load-bearing half of that decision — semantic relevance, 0.0–0.6, explicitly the
PRIMARY factor — from **English-biased keyword overlap between the query string and
the context text**. Our clients write Indonesian. Much of our corpus is English. The
gate reads that pairing as "no evidence" and abstains.

This is inherited, not introduced by the pricing-evidence change that surfaced it
(PR: "count the price book as evidence"). It is specified here rather than fixed
there because it moves the abstain behaviour of EVERY domain, not the pricing path.

## The measurement

Same catalogue entry, same price, same question — only the language of the context
differs. Run against the live scorer on 2026-09-01:

| Query | English context | Indonesian context |
|---|---|---|
| `Harga PT PMA berapa all in?` | **0.08** | **0.80** |
| `How much is a PT PMA company, all in?` | **0.80** | **0.08** |
| `Berapa biaya pendirian perusahaan PT PMA?` | 0.30 | **0.80** |
| `What is the price of new company setup?` | **0.80** | 0.08 |

A factor of ten, decided by language alone. The label threshold is 0.15.

`0.08` is not a low relevance score — it is the "**no** semantic relevance" branch:
`final = min(source_quality * 0.2, 0.1)`, with source quality already maxed at 0.4.
The scorer is not measuring weak overlap; it is measuring none.

## Two independent defects produce it

**1. Relevance is lexical, and the stop-word list is English-only.**
`reasoning_utils.py` builds `query_keywords` from the query, strips English stop
words, then computes `keyword_hits / len(query_keywords)` against the concatenated
context. Nothing in that path is language-aware. An Indonesian query and an English
chunk share almost no surface tokens even when they are about exactly the same thing.

**2. The keyword filter discards the tokens that identify the subject.**
`if len(w) > 3` (line ~400) drops every word of three characters or fewer. So
`"Harga PT PMA berapa all in?"` reduces to exactly two keywords — `harga` and
`berapa` — the two most generic words in the sentence. The entity is gone.

Casualties of that filter, all load-bearing identifiers in this business:
`PT`, `PMA`, `NIB`, `OSS`. Survivors by an accident of length: `KITAS`, `NPWP`,
`E28A`, `E33E`.

## The existing workaround, and why it must not be extended

`_abstain_policy.py` already carries the diagnosis, in its own comment:

> A single global ABSTAIN_THRESHOLD (0.15) over-rejects on Indonesian-language
> domains (tax, visa) where docs naturally have lower keyword overlap with IT/EN
> queries […] Per-domain thresholds let the gate breathe in the right direction.

The remedy chosen was to **lower the bar** — `tax: 0.10`, `visa: 0.12` — in the two
domains where the pain was loudest. That is a workaround that survives its own
ground: it relieves the symptom in two domains, leaves the measurement broken
everywhere, and *lowers the safety gate* to do it. Adding a third lowered threshold
for `company` would repeat the mistake and buy a further loss of protection.

Do not tune thresholds. Fix the measurement.

## What it actually cost, measured

Live, 2026-09-01, question 12 of cycle 359. Client asks `Harga PT PMA berapa all in?`.
`has_pricing_intent` fires, `PricingService` returns the correct **Rp 20.000.000**,
the value is sanitized into `pricing_block` and carried in the package. The evidence
score is computed from the vector chunks, comes back below threshold, `abstain=True`
is frozen at build time, and `wa_finalize` discards the drafted answer for the
localized refusal stub. The bot told a client it had no reliable source, while
holding the answer in a local variable.

The same bot quoted that same price correctly three times on 2026-07-28 in the same
thread — because those turns were phrased differently.

## Direction of the cure

The vector scores already encode cross-language relevance: the embeddings are
multilingual by construction (`text-embedding-3-small`, and `bge-m3` on the local
path). The retriever hands those scores to the scorer, which uses them only as a
**secondary bonus** and re-derives relevance from a lexical comparison that cannot
see across languages.

Invert that hierarchy: retrieval similarity becomes the primary relevance signal;
lexical overlap is kept, at most, as a corroborating check — never as the gate.

This is the shape Google's *Sufficient Context* work argues for: assess sufficiency
from what was actually retrieved, as a signal of its own, rather than from a proxy
that correlates with it only under conditions we do not control (here: the question
and the corpus happening to share a language).

## Acceptance criteria

1. The four rows of the table above must land within one threshold band of each
   other. Language must not move the score by an order of magnitude.
2. `PT`, `PMA`, `NIB`, `OSS` must survive into the relevance computation. A rule
   keyed on token LENGTH cannot express that; the filter must go or become
   vocabulary-aware.
3. **Innocence, mandatory**: the genuine mismatch cases the current scorer catches
   must still abstain — a KITAS query returning KBLI documents, and a nonsense
   query. The existing `entity_type_mismatch` tests are the floor, not the ceiling;
   they may not be weakened to let the new metric pass.
4. A golden set — a few dozen questions with hand-verified answerable /
   not-answerable status, in Indonesian AND English — run as a regression, with
   the abstain rate reported **separately** for the two subsets. A single blended
   abstain rate hides exactly this defect: an over-cautious gate and a healthy one
   post the same number.
5. Re-examine `DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT` once the metric is fixed. The
   `tax: 0.10` and `visa: 0.12` reliefs exist to compensate for this defect; if
   they survive the cure unchanged, they are now compensating for nothing and are
   a silent reduction in safety.

## Not in scope

The abstain has no observable record. `wa_outbox` and `meta_inbox_messages` carry
**no** confidence, evidence or abstain column — an abstain is stored as
`status='done'`, indistinguishable from a good answer. Criterion 4 above cannot be
measured in production until that exists. Separate ledger item.
