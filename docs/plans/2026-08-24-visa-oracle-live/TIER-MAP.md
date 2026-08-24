# Product -> tier map (owner switchboard #4)

Prepared 2026-08-24 for Zero to **correct and approve**, per mandate §5. Derived from the signed
pack `rulepack-prod-013` (38 products, 111 rules), not from opinion. Every product's row was
produced by reading the pack; the rule that assigns the tier is stated first so a disagreement is
about the rule, not about 38 separate judgement calls.

## The three tiers (owner's ruling, verbatim intent)

- **T1 — self-purchase puro.** Basic services. No consultant needed.
- **T2 — self-purchase + consultant included.** The significant visas. The client buys online AND
  the assigned consultant always makes contact after purchase — part of the service, inside the
  price, never a fallback.
- **T3 — assisted-only (for now).** Products whose rules are incomplete are never sold solo. The
  Oracle recognizes them and routes straight to the consultant. Never an invented answer.

## The assignment rule, and why it is not a matter of taste

Two measured properties decide it, and they agree with each other:

1. **`pricing_key.item_key` present?** 26 of 38 products carry one; 12 do not.
2. **Does the product have at least one ELIGIBILITY rule?** 29 do; 9 do not.

**These two sets nest.** All 9 products with zero ELIGIBILITY rules are also among the 12 with no
price. That is not a coincidence — a product nobody has priced is a product nobody has finished
authoring.

The frozen contracts make the consequence mandatory rather than advisory. C1: _"a candidate without
a quote cannot claim a price"_ (enforced in `api_models.py`'s projection validator). C2:
_"`quote_ref=null` forbids any downstream screen that shows a price"_. So:

> **No `pricing_key` => the product cannot be sold self-service at all => T3 by construction**,
> independent of how good its rules are.

That single line assigns 12 products without a judgement call. The remaining 26 split T1/T2 on
whether the product is a basic short-stay service or a significant status change — the one place
where the owner's business judgement, not the pack, decides.

> ⚠️ **"T3 by construction" is a POLICY of this map, not a behaviour of the engine.** Added
> 2026-08-25 after the V2 lane began transcribing this rule into code (`product-tier-map.ts`) as
> though it were derived. It is not: a product with a SUPPORT rule and no `pricing_key` is still
> returned by the engine as a `SUPPORTED_CANDIDATE` — contract C1 forbids it from _claiming a
> price_, it does not forbid it from _being a candidate_. Measured on seq-13: 29 products carry at
> least one SUPPORT rule, 26 carry a `pricing_key`, and the intersection is 26 — so the priced set
> is a strict subset of the supported set (no product is priced but unreachable), and exactly 3
> products (**E30, E30E, E30F**, all STUDY) are recommendable-but-priceless.
>
> The consequence any consumer of this map inherits: a surface that counts those 3 as
> "consultant-routed" will contradict a verdict screen that lists them as candidates. The two
> boundaries — _sellable today_ (this map) and _offerable by the engine_ (the pack) — are both
> legitimate and they are not the same set. Say which one you mean.

## T3 — assisted-only (12)

Cannot be sold self-service today. The Oracle must recognize each and route to a consultant.

| Code | Name                                            | Why T3                                                              |
| ---- | ----------------------------------------------- | ------------------------------------------------------------------- |
| E23U | Working Visa — Foreign Diplomat Household Staff | 0 eligibility rules, no price                                       |
| E23V | Working Visa — Trade/Economic Office Staff      | 0 eligibility rules, no price                                       |
| E28B | Investor Golden Visa — Company Establishment    | 0 eligibility rules, no price                                       |
| E28C | Investor Golden Visa — Capital Market           | 0 eligibility rules, no price                                       |
| E28D | Investor Golden Visa — Branch or Subsidiary     | 0 eligibility rules, no price                                       |
| E28F | Investor Golden Visa — New Capital (IKN)        | 0 eligibility rules, no price                                       |
| E33A | Second Home — Special-Expertise Guest           | 0 eligibility rules, no price                                       |
| E33B | Second Home Golden — Special-Expertise          | 0 eligibility rules, no price                                       |
| E33C | Second Home Golden — World Figure               | 0 eligibility rules, no price                                       |
| E30  | Education Visa (E30)                            | no price; also the only non-public-catalog product besides BRIDGING |
| E30E | SEZ Education Visa                              | no price                                                            |
| E30F | Student Exchange Visa                           | no price                                                            |

**Three of these are structurally permanent, not merely unfinished.** E33A/B/C turn on the
authenticity of an invitation or a claim to world-figure status. A self-declaration cannot ground
that — no interview question can make it true. They are **T3 by nature**, and the honest ceiling of
this catalogue is therefore _31 automatable + 7 consultant-routed_, not 38.

**E28B/C/D/F carry a second, separate defect** that outlives their tier: their one rule is a
`REQUIRE_REVIEW` on `intent.requested_product_code`, a fact the interview hard-codes to
`NOT_ASKED`. At `on_unknown=NEEDS_INPUT` that does not merely fail to fire — it demotes the product
to `BLOCKED_UNKNOWN`, which loses to any SUPPORTED product, so they are **invisible** rather than
merely unsold. Zero's ruling of 2026-08-24 is to do both halves: ask the question, and route
above-threshold investment to a human regardless. Lane V1 owns it.

## T1 — self-purchase puro (7 proposed)

Priced, has eligibility rules, no product-specific human-review rule, short-stay or simple
multiple-entry. These are the ones a visitor can buy without ever speaking to anyone.

| Code | Name                                                                               |
| ---- | ---------------------------------------------------------------------------------- |
| A1   | Visa-Free Tourism Visit                                                            |
| B1   | **Visa on Arrival — Tourism** (the mandate's first product: GARUDA VOA sells here) |
| C1   | Tourist Visit Visa                                                                 |
| C2   | Business Visit Visa                                                                |
| C6   | Social Activity Visit Visa                                                         |
| D1   | Visit Visa Tourism — Multiple Entry                                                |
| D2   | Visit Visa Business — Multiple Entry                                               |

## T2 — self-purchase + consultant included (19 proposed)

Priced and eligible, but a significant status change: the assigned consultant always makes contact
after purchase.

| Code     | Name                                       | Note                                                                      |
| -------- | ------------------------------------------ | ------------------------------------------------------------------------- |
| D12      | Visit Visa Pre-Investment — Multiple Entry | owner named this tier explicitly                                          |
| E23      | Working Visa                               |                                                                           |
| E28A     | Investor Visa                              | the only Investor product currently sellable                              |
| E30A     | Primary/Secondary Education Visa           |                                                                           |
| E30B     | Higher Education Visa                      |                                                                           |
| E31A     | Family — Spouse of Indonesian Citizen      | owner named E31 family explicitly                                         |
| E31B     | Family — Spouse of ITAS/ITAP Holder        |                                                                           |
| E31C     | Family — Child of Legal Mixed Marriage     |                                                                           |
| E31D     | Family — Stepchild of Foreigner            | see open defect below                                                     |
| E31E     | Family — Child of ITAS/ITAP Holder         |                                                                           |
| E31F     | Family — Child of Indonesian Citizen       |                                                                           |
| E31G     | Family — Parent of Indonesian Citizen      |                                                                           |
| E31H     | Family — Parent of Child ITAS/ITAP         |                                                                           |
| E31J     | Family — Child Joining Sibling ITAS        |                                                                           |
| E33      | Second Home Visa                           | owner named E33 explicitly; carries 1 human-review rule                   |
| E33E     | Second Home Golden — Elderly 5-Year        |                                                                           |
| E33F     | Second Home — Elderly 1-Year               |                                                                           |
| E33G     | Second Home — Remote Worker                | carries **3** human-review rules — the most review-heavy sellable product |
| BRIDGING | Bridging Visa — Transitional Stay Permit   | not in the public catalogue; sold only as a follow-on                     |

## What this map does NOT settle, and must not be read as settling

- **Tier is not readiness.** 34 of 38 products are never any gold persona's `expected_candidates`.
  A product can be T2 here and still have never been exercised end-to-end. The tier says how it is
  sold; the gold suite says whether it answers correctly. Do not conflate them — that is exactly
  the "29 reachable" trap recorded in GROUND §3.
- **Prices are not in this document on purpose.** They live in PricingTool and nowhere else
  (golden rule #11). `pricing_key` is the join, not the number. Switchboard #5 (prices and terms
  per tier) is a separate signature and a separate document.
- **One open defect inside T2 that rules cannot fix.** E31D (stepchild) is not correctable at the
  rule level: `RelationType` has no `STEPCHILD` member, so the eligibility cannot be expressed
  without extending the fact vocabulary. That is an owner decision plus a vocabulary change, not a
  rule edit. Flagged here so approving E31D as T2 is a knowing choice.
- **BRIDGING's four boundaries are not encoded.** Zero's ruling of 2026-08-23: bridging spans
  KITAS -> a DIFFERENT KITAS and kunjungan -> KITAS; never KITAS -> the same KITAS with the same
  sponsor (that is a renewal), never KITAS -> kunjungan. Sponsor identity is probably not even a
  fact today, so the pack likely over-admits. Verify before BRIDGING is offered.

## The gesture asked of the owner

Correct any row, then approve. The rule that assigns T3 is derived and should be argued with as a
rule; the T1/T2 split is business judgement and is where correction is most expected.
