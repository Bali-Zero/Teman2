# SPEC — binding a priced amount to the service it prices (check 7)

Status: **written because the gate found a live defect, not a hypothetical one.**
Team-lead review of the client-bot engine (2026-08-25) traced `pricing_check.py`
check 7 and found that "verbatim match against the snapshot" is a weaker
guarantee than it sounds: the check verifies an amount is A real Bali Zero
price, never that it is THE price of the service the client asked about. Per
the Agent PR Contract: when a correction would itself be under-specified,
write the spec before the fix. `RED-price-service-binding` (companion test,
same commit) reproduces the defect and stays red until this spec is
implemented.

## The defect

`GroundingBundleBuilder._build_pricing_snapshot()` (`grounding.py`) calls
`PricingService.get_pricing("all")`, which returns `self.prices` — the
**entire nested catalogue**, every category, every service, unfiltered by
query or domain — and wraps it whole as `PricingSnapshot.items=(raw,)`. One
opaque item, not one item per service.

`pricing_check.check_pricing()`'s `_snapshot_values()` then walks that single
nested blob recursively and extracts **every numeric token from every string
field in every entry** into one flat `set[int]`. The check's only question is
`value not in snapshot_values` — set membership across the WHOLE catalogue,
never "is this the price of the service under discussion."

Concrete reproduction (see the companion test): the catalogue contains both
an E33G KITAS entry (`Rp 12.000.000`) and a Working KITAS entry
(`Rp 25.000.000`). A candidate answering a question about E33G KITAS states
`Rp 25.000.000` — the Working KITAS price, wrong for this question. `25000000`
IS a real Bali Zero price, so `_snapshot_values()` contains it, so
`check_pricing()` returns `None` (pass). The client receives a genuine number
that is the wrong number for their question, and every test stays green,
because the number really is in the snapshot.

Two secondary consequences of the same flattening, real but smaller:

- The walk collects every numeric string in every entry FIELD, not just
  price fields — `tier_range`, `validity`, and any other digit-bearing field
  widen the accepted set beyond actual prices.
- `_currency_amounts()` only matches currency-SHAPED tokens (`Rp`/`IDR`/`USD`/
  `$`-prefixed or -suffixed), so a bare price-tier number with no currency
  marker is invisible to the extractor in the first place — a distinct gap
  from the `_VETO_FLOORS` skip (which affects amounts that ARE extracted but
  fall below the floor), both leaving small or bare-formatted genuine prices
  unguarded in different ways.

## Why this recurs

This is the shape already on record in `branching-verdict-single-price-key`
(memory, 2026-08-23/24): a Second Home Studio wizard branched its PRODUCTS
but not its PRICE — 256 green tests, a real number, the wrong number, shipped
to a real client. Six weeks and a different module later, the same shape:
machinery that looks correct because every number it emits is a real number,
and never checks that the number belongs to the entity actually under
discussion. A system can have zero hallucinated digits and still be wrong on
every priced answer, because "real" and "correct for this question" are not
the same property, and nothing here has ever tested the difference.

## Required properties (the spec)

**P1 — A priced item's identity survives into the snapshot.** PricingTool
already has the stable identity this needs: `service_name`, the dict key
`_iter_service_entries()` yields, and the exact string
`PricingService.get_service_by_key(key)` accepts — "the deterministic
counterpart to `search_service`: no scoring, no fuzzy matching... a caller
that renders a price on a client-facing surface must get either the exact
row it asked for or nothing" (that method's own docstring, written before
this spec, for the identical failure mode one layer up). `_build_pricing_snapshot()`
must stop calling `get_pricing("all")` and instead build ONE `PricingSnapshot`
item PER SERVICE via `get_service_by_key()`/`_iter_service_entries()`, each
item carrying its `key` as a first-class field — not folded into a display
string a numeric-token walk has to re-parse.

**P2 — A price claim references a service key, not a bare number.**
`Claim(kind="price")` (`contracts.py`, frozen) has no field today that names
WHICH service its `text` prices — `evidence_ids` points at KB evidence, not
at a `PricingSnapshot` item. This needs a new field (e.g.
`price_service_key: str | None`, populated iff `kind == "price"`) so a
provider's claim is a structural assertion — "this number prices THIS
service" — not free prose a downstream regex has to re-associate by guessing.

**P3 — check_pricing verifies the (service, amount) PAIR, not amount alone.**
Given P1+P2, the check becomes: for each price claim, look up
`price_service_key` in the snapshot's per-service items; the amount(s) in the
answer attributed to that claim must match THAT item's price, and only that
item's — never "is this number anywhere in the snapshot." An amount with no
claim behind it at all remains what check 6
(`UNINVENTORIED_NUMERIC_STATEMENT`) already catches; this spec does not touch
that half.

**P4 — The snapshot itself is scoped, not exhaustive.** Independent of the
check, handing every provider the FULL catalogue on every turn (today's
`get_pricing("all")` call) is its own defect surface — a provider free-
generating from 50+ visible prices has 50+ ways to pick the wrong one, even
before check 7 runs. `GroundingBundleBuilder` should build a snapshot scoped
to the service(s) the query domain plausibly concerns (a retrieval/filter
step, analogous to how `EvidenceRetriever` scopes KB evidence to the query
rather than handing back the whole KB) — out of THIS check's ownership, but
the same builder P1 touches, so it belongs in the same follow-up, not a
separate one that reads check 7 as fixed while the snapshot stays exhaustive.

**P5 — Guilt AND innocence under test.** The RED companion test proves the
wrong-service quote passes today (guilt). The fix needs an innocence
counterpart: the SAME candidate, correctly priced for its own service, must
still pass — proving P1-P3 do not turn into a check so strict it rejects
correct answers (the failure mode `pricing_check.py`'s own docstring already
warns against: "stricter... than the existing veto it is inspired by").

## What this does NOT require

`PricingSnapshot.snapshot_sha256`, `pricing_tool_version`, and the overall
`items: tuple[dict[str, object], ...]` shape stay as-is — P1 adds a field
inside each item dict (or a sibling structural field, implementation's
choice), not a new top-level contract shape. This is smaller than the
placeholder-substitution design flagged for the "unconstructible, not
detected" pricing question (`docs/plans/2026-08-25-due-bot-live/` chat log,
2026-08-25) — but it is the SAME contract change at its base: both need a
priced item to carry a stable identity a claim can reference structurally.
One PR should do both, per the team lead's instruction that they are one
piece of work, not two.

## Arming condition

This is a `contracts.py` change (`Claim` gains a field) beyond the one
exception already authorized this session (`GateReason.PROVIDERS_EXHAUSTED`).
It requires the team lead's go-ahead before implementation, and it is a
precondition for arming real client sends (per team-lead ruling,
2026-08-25) — not a shadow-mode blocker. The RED test stays red, on the
record, until this lands.

---

## Orchestrator ruling on the frozen-fixture collision (2026-08-25)

B1b asked before writing the validator, not after, and was right to. Recording the
answer here because the lane hit a quota wall minutes later and this decision must
outlive the session that made it.

**The question.** Making `price_service_key` required-iff-`kind=="price"` via a
model_validator breaks every existing `kind="price"` construction that omits it —
including B6b's two frozen goldens, `PRICING_CORRECT` and `PRICING_INVENTED`.

**Verified, not taken on report.** `PRICING_CORRECT`'s snapshot at
`fixtures.py:154-156` already declares `{"service": "kitas_investor", ...}`, and the
claim two lines below carries no service. So the edit wires an identity the fixture
already states onto the claim beside it. It invents nothing.

**AUTHORIZED**: edit both fixtures and add the parameter to
`builders.py::make_claim()`, inside this PR, as one atomic step with the validator.

**Why construction-time, not the softer gate-level failure.** Making the field
optional and having the gate HANDOFF on a missing key looks less invasive and is
worse. `PRICING_CORRECT` is the happy-path golden: it would flip from ALLOW to
HANDOFF, silently changing what a frozen test asserts, with no diff anyone reviews.
A frozen fixture whose meaning changes without its text changing is the failure mode
freezing exists to prevent. A `ValidationError` at construction is loud, immediate,
and impossible to mistake for a passing test.

**The boundary this does NOT open.** Touching a frozen fixture is licensed here
because the change is *mechanical and additive* and the value comes from the fixture's
own data. It is not a precedent for editing a frozen fixture to make a test pass. The
distinction is the same one B6d worked under: an expectation may be updated only when
the gap it encoded was genuinely closed and the commit that closed it can be named.
If the edit ever requires inventing a value the fixture does not already declare,
stop and re-ask — that is a different question with a different answer.

**Guilt and innocence both, when the work resumes.** The rejection cases are the easy
half. The ones that decide whether this is landable are: the right price for the right
service still passes; a service mentioned without a price claim does not trip it; and
a price for a service the client asked about in a PREVIOUS turn behaves the way the
implementer decides — that decision must be stated, not left for the implementation
to settle by accident.
