# There are two visa funnels in production, and the public one is not the audited one

> ✅ **RISPOSTO da Zero 2026-08-25 — scelta: RITIRARE la vecchia porta con 301 → `/visa-oracle`.**
> «Mai un motore non verificato indicizzato col nostro nome sopra.» Il redirect conserva la SEO. Il
> **noindex sulla porta nuova cade SOLO dopo il fix della riga T2** — ordine vincolante: toglierlo
> prima indicizzerebbe una pagina che ai clienti T2 dice il contrario del vero. Autorità:
> `OWNER-RULINGS-2026-08-25.md` §4.

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

> ⚠️ **Measured false — corrected in "Second correction" near the end of this document.** As of
> this document's own 2026-08-24 snapshot, `/visa` and `/visa/match` **did** appear in
> `sitemap.ts`. The false claim understated the exposure, not overstated it.

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

> ⚠️ **The `/visa` row is measured false — corrected in "Second correction" near the end of this
> document.** `POST /api/v1/visa-oracle/recommend` is real code, but it is dead from the live
> frontend — nothing on the live page calls it.

Two engines, two catalogues, two notions of what may be asserted — and the one under a signed
pack, an abstention contract and a projection validator is the hidden one. This makes divergence
more likely by construction, not less, and it is what the V2 lane is now measuring.

## Second correction, received and verified: wrong backend, and the sitemap error understated the exposure

Both measured directly on disk in this worktree, not accepted on anyone's word — because this
document is what Zero read before issuing ruling #4, its errors are load-bearing enough to record
in full rather than silently fix.

**What was claimed.** The table above: the public `/visa` door runs on
`POST /api/v1/visa-oracle/recommend` → `VisaOracleService.recommend_visas`. And in _The
inversion_, above: neither `/visa` nor `/visa/match` appeared in `sitemap.xml`.

**What is true.**

- The live public page, `apps/mouth/src/app/visa/match/page.tsx:260`, calls
  `fetch("/api/visa/match", ...)`. That path is served by a **separate router**:
  `apps/backend-rag/backend/app/routers/visa_check.py` (`prefix="/api/visa"`,
  `@router.post("/match", ...)` at line 225, handler `submit_match`), which calls
  `match_tree.recommend_visa` (`backend/services/visa_check/match_tree.py:300`) and reads/writes
  through `VisaCheckRepository` (`backend/services/visa_check/repository.py:56`).
  `VisaOracleService` and `POST /api/v1/visa-oracle/recommend` are real, live code
  (`visa_oracle.py:796`, registered under `API_V1_STR="/api/v1"`) — but **dead from the live
  frontend**. Their only client, `recommendVisas()` in
  `apps/mouth/src/lib/visa-oracle/api.ts:238-241`, is never imported by any page component (the
  only page-level importer of that module, `VisaChat.tsx`, pulls `sendChatMessage`/
  `triggerHandoff`, not `recommendVisas`) — its sole caller anywhere in the repo is its own unit
  test, `apps/mouth/src/lib/visa-oracle/api.test.ts`.
- At the time of this document's 2026-08-24 snapshot, `/visa` and `/visa/match` **did** appear in
  `sitemap.ts` — confirmed via `git show 4d1eae0b3^:apps/mouth/src/app/sitemap.ts`, lines 145-146
  of the `visaPaths` array. Commit `4d1eae0b3` (2026-08-25, implementing ruling #4) is what
  removed them and recorded both as a deliberate post-redirect omission in `sitemap.test.ts`'s
  `INTENTIONALLY_UNLISTED` guard — that commit's own message already named both corrections above,
  independently of this edit.

**How the false claims were produced.** The endpoint table inferred the live backend from the
funnel's dedicated API client module (`api.ts`'s `recommendVisas()`, which genuinely does call
`/api/v1/visa-oracle/recommend`) rather than from the page component that actually renders
`/visa/match` and issues the request — the two disagree, and only the page component's `fetch`
call is live traffic. The sitemap claim appears to have been checked against a state where the
2026-08-25 removal had already happened, rather than the state that was actually live on
2026-08-24 when `balizero.com` was measured for this document.

**What this does not change.** Ruling #4 — retire the old door with a 301, lift the noindex on
`/visa-oracle` only after the T2-copy fix lands — stands unaffected. Both errors were about _which
code_ the old door ran and _whether it was in the sitemap_; neither is a reason to keep an
unverified engine indexed under our name. If anything, the sitemap correction makes the SEO
exposure **larger than this document claimed, not smaller**: `/visa` and `/visa/match` were not
merely `index, follow`-eligible through inbound links, they were formally submitted to search
engines via `sitemap.xml` itself.

**Honest re-reading required.** The "Correction received and verified: the public funnel does NOT
invent prices" section above drew its evidence entirely from `visa_oracle.py` — the same wrong
module identified here. Its finding (bound to PricingTool, degrades to "contact for pricing",
divergence logged not silenced) may well be true of `VisaOracleService`, but it says nothing about
what the _actually live_ path — `visa_check.py::submit_match` / `match_tree.recommend_visa` /
`VisaCheckRepository` — does with price. Any claim in this document about the legacy funnel's
backend evaluation behavior that rests on `VisaOracleService` must be re-read as **untested**: it
was measured against the wrong module. Re-verifying pricing/behavior against the real live path is
the obvious next step and is not done here.

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
- Not claimed: that the page is actually indexed. `index, follow` — plus, as corrected above, an
  actual `sitemap.xml` entry at the time of measurement — means _eligible_ for indexing, not
  _indexed_. Confirming that needs Search Console, which is an operator surface.
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
