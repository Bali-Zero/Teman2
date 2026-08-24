# There are two visa funnels in production, and the public one is not the audited one

Measured 2026-08-24 (Pro), live against `balizero.com`. Surfaced by the V2 lane while auditing
the wizard; the numbers below were then re-measured directly by the orchestrator.

## The inversion

| URL                        | HTTP | `<meta name="robots">` |
| -------------------------- | ---- | ---------------------- |
| `balizero.com/visa`        | 200  | **`index, follow`**    |
| `balizero.com/visa/match`  | 200  | **`index, follow`**    |
| `balizero.com/visa-oracle` | 200  | `noindex, nofollow`    |

The mandate's premise is that Visa Oracle becomes **"the single front door of every Bali Zero visa
sale"**. Today the opposite holds: a **second, older funnel is the public, indexable one**, and the
audited engine — the one with a signed rule pack, a five-outcome abstention contract, and a
projection validator — is the one search engines cannot see.

Neither tree appears in `sitemap.xml` (which lists `/services/visa` and `/visas/*` articles only),
but `index, follow` is sufficient for discovery through any inbound link.

## What the public page promises, verbatim from the served HTML

> "**24 visa types. One fits you. We know which.**"
> "5,021 visas filed since 2019 · 24+ visa categories supported"
> "Answer **4 short questions**. We'll recommend the right visa **and show the cost**."
> "Buying property or keeping **USD 130,000+** in savings? See the Second Home Visa (E33)"

Set against the signed pack that the Oracle actually runs on:

- **24 vs 38.** The catalogue has 38 products. The public page advertises a smaller world and
  presents it as complete.
- **"We know which", from 4 questions.** The audited engine asks roughly fifty and still reaches
  only 29 of 38 products, abstaining honestly on the other nine — that abstention is the
  five-outcome contract's whole point. The public page makes a stronger promise than the verified
  engine is permitted to make.
- **"show the cost".** Frozen contract C1 forbids a candidate without a resolved quote from
  claiming a price, and C2 forbids any downstream screen showing one when `quote_ref` is null.
  Twelve of 38 products have no `pricing_key` at all.
- **USD 130,000+ for E33.** A client-facing regulatory number on an indexable page. Not
  adjudicated here — it belongs to the Second Home lane — but it is exactly the class of figure
  that must trace to a verified primary source, and this page is not under the Oracle's source
  discipline.

## Correction received and verified: the public funnel does NOT invent prices

The GARUDA orchestrator independently re-measured all four URLs (4/4 identical) and then
corrected this document. Re-verified here on disk rather than accepted on their word:

- `visa_oracle.py:1289` — `price = server_top.get("price") or "contact for pricing"`.
- The `/handoff` docstring is explicit: the server-side PricingTool value comes from the
  persisted session's own data, and _"the caller must then proceed WITHOUT a price rather than
  fall back to the client-posted handoff body"_.
- A client/server price divergence is **logged, not silenced**.

So the old funnel is bound to PricingTool and degrades to "contact for pricing". **The original
phrasing of this document implied a pricing risk that does not exist**, and the correction makes
the case narrower and stronger: the defect is not a wrong number — it is the **claims** ("24" vs
38, "we know which" vs nine contractual abstentions, "show the cost" vs 12 products with no
`pricing_key`) plus the indexing inversion. A fabricated price would have to be switched off
tonight; wrong claims are two lines of copy, which is exactly what the recommendation asks for.

## And the divergence is sharper than "a different code path"

Measured while verifying the correction — the two doors do not merely differ in front-end logic,
they call **different backend services**:

| Door                        | Endpoint                                                  | Decision engine                                                    |
| --------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------ |
| `/visa` (public, indexable) | `POST /api/v1/visa-oracle/recommend`                      | `VisaOracleService.recommend_visas` (`visa_oracle_service.py:210`) |
| `/visa-oracle` (shadow)     | `POST /api/visa-oracle/evaluate` (`evaluateVisaOracleV2`) | the deterministic evaluator over the signed rule pack              |

Two engines, two catalogues, two notions of what may be asserted — and the one under a signed
pack, an abstention contract and a projection validator is the hidden one. This makes divergence
more likely by construction, not less, and it is what the V2 lane is now measuring.

## Why this is a defect NOW, not at ignition

Every argument for keeping the Oracle in shadow — the engine is unproven, the DPIA is unsigned,
nine products are blocked, sixteen gold divergences were untriaged until today — applies with
**more** force to a funnel that is public, indexed, running different logic, and promising a
definite answer plus a price in four questions.

The shadow discipline is protecting the wrong surface.

## What is NOT claimed here

- Not measured: whether the old funnel's recommendations actually diverge from the engine's on the
  same inputs. That is the obvious next measurement and it is not done. It runs on
  `apps/mouth/src/lib/visa-oracle/quiz-logic.ts`, a different code path from the signed engine, so
  divergence is possible by construction — but "possible" is not "measured", and this document
  does not pretend otherwise.
- Not claimed: that the page is actually indexed. `index, follow` plus no sitemap entry means
  _eligible_ for indexing, not _indexed_. Confirming that needs Search Console, which is an
  operator surface.
- Not touched: `apps/mouth/src/app/visa/voa/` is GARUDA's tombstone (404 by design, PR #4344) and
  `second-home/` belongs to the Second Home lane. Neither is this lane's to change.

## The decision this needs

Consolidation is a **business decision (Legge 5)**, not a technical cleanup, because it trades a
live lead-generating surface against correctness. The options, stated so they can be chosen
between rather than drifted into:

1. **Noindex the old funnel now**, leaving it reachable by direct link, and consolidate at
   ignition. Cheapest, reversible, removes the inversion immediately.
2. **Retire it now** and redirect `/visa` to `/visa-oracle`. Cleanest, but hands traffic to a
   surface that is itself still in shadow — arguably worse until ignition.
3. **Leave it and accept the divergence** until ignition, with the claims corrected (24 → 38, drop
   "we know which", drop the cost promise) so the public page stops over-promising in the meantime.

The orchestrator's recommendation is **(1) plus the claim corrections from (3)**: it costs one
metadata change plus copy edits, removes the inversion today, and does not depend on ignition
landing on any particular date.
