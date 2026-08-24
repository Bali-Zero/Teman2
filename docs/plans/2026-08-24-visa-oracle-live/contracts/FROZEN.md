# FROZEN CONTRACTS — Visa Oracle live

Frozen 2026-08-24 by the orchestrator session on Pro, before any lane was dispatched, per
mandate §3. A lane may CONSUME these freely. A lane may not CHANGE one: a needed change is a
request back to the orchestrator, who re-freezes and re-broadcasts. Contracts C1 and C4 are
enforceable today; C2 is a request to another product's orchestrator and is deliberately not
implementable yet; C3 is enforceable on our side of the boundary.

---

## C1 — wizard <-> engine wire

**Status: ALREADY FROZEN UPSTREAM. Do not re-author it. Declare and obey it.**

The wire is not a document we write — it is generated. `apps/mouth/.../_lib/visa-oracle-contract.ts`
derives every public boundary type from the generated OpenAPI schema:

```ts
export type VisaOracleEvaluateOperation = operations["evaluateVisaOracleV2"];
export type VisaOracleEvaluateRequest  = ...["requestBody"]["content"]["application/json"];
export type VisaOracleEvaluateResponse = ...["responses"][200]["content"]["application/json"];
```

The server side is `VisaOracleEvaluateResponse` in `services/visa_engine/api_models.py`, which is
`frozen=True, extra="forbid"` and carries a `_check_projection_integrity` validator enforcing, among
others: display candidates match decision candidates **in order**; every `source_ref` resolves;
availability claims require a CURRENT + APPLICABLE + primary + VERIFIED source; a candidate without
a quote may not claim a price.

**The five-outcome contract is the base, and its precedence is part of the freeze** (`enums.py:44`):

```
TEMPORARILY_UNAVAILABLE  >  HUMAN_REVIEW_REQUIRED  >  SUPPORTED_CANDIDATES
                         >  NEEDS_INPUT           >  NO_SUPPORTED_PATH
```

### The public projection this product freezes on top

1. **All five outcomes are expressible in the UX.** A wizard that renders only
   `SUPPORTED_CANDIDATES` well and degrades the other four into one "something went wrong" screen
   violates this contract even though it type-checks. V2's acceptance requires each of the five to
   have a designed, honest screen — including `TEMPORARILY_UNAVAILABLE`, which is the fail-closed
   state and must never be dressed as a result.
2. **The wizard never invents a candidate, a price, or a source.** Everything rendered traces to a
   field in the response. Copy may translate; it may not add.
3. **No hand-written mirror of a generated type.** If the wizard needs a shape the schema does not
   expose, the change starts at the server model and regenerates — never a local interface that
   drifts.

### Enforcement

Existing: `_check_projection_integrity` (server), the generated-schema derivation (client).
Added by this product (V2 lane owns): one test asserting each of the five outcome kinds maps to a
distinct rendered state, and one asserting no `_lib` module declares a structural type literal for a
shape the schema already provides.

---

## C2 — verdict -> checkout handoff

**Status: AMENDED 2026-08-24 after the GARUDA orchestrator answered. The amendment changes the
DESIGN, not a field name.** Still not implementable — the contract it depends on is on
`feature/garuda-voa`, not main — but the shape below is now agreed between the two products.

### What the mandate assumed, and what is actually there

The mandate said "consume GARUDA's FROZEN contracts from main". Measured (GROUND §4): no order,
checkout, or commerce module exists on main; the only public GARUDA route is `GET /voa/{hash}`.
The order contract is written but lives on GARUDA's integration branch, under a cross-family
refuter, with names explicitly provisional until that verdict returns:

```
POST /api/visa/voa/orders          operationId: createOrderFromCheck
  header  Idempotency-Key          mandatory; absent -> 400 IDEMPOTENCY_KEY_REQUIRED
  body    CreateOrderRequest       additionalProperties: false
            result_id              <- from GARUDA's createEligibilityCheck
            applicant
            review_confirmed       const true
  201  ->  OrderCheckout { order_id, order_state, price_idr, checkout_url }
```

### The boundary this exposed — and why the first design was wrong

GARUDA's order entry requires a `result_id`: the outcome of **GARUDA's own** VOA engine. It is an
order for one product, not a generic order over 38. So `VerdictHandoffIntent` as first frozen does
not fit — and forcing it to fit would have created the real defect: **two engines evaluating the
same case.** The Oracle says VOA is supported, GARUDA's check then says otherwise, and the visitor
has had two answers from one company thirty seconds apart. Hoping they agree is not a design.

The cure is not a zero-divergence gate bolted on top. That gate is a net, and we still arm it
(switchboard #3), but a net is not a structure. The cure is:

> **For any product with a downstream proprietary engine (today: VOA only), the Oracle's verdict is
> not a verdict.** It emits "this is the right route for you — let us confirm it", and the
> authoritative eligibility check is that engine's, as a STEP OF THE JOURNEY rather than a second
> opinion contradicting the first.

This removes the contradiction by construction instead of by luck, at a price we accept: **for VOA
the Oracle is a router, not the decider.** Which is what the mandate already says — "the Oracle
absorbs GARUDA: VOA becomes the first product sold inside this funnel". The funnel is ours; the
VOA decision stays theirs.

### The chain (this, not the names, is what we froze)

```
Oracle (candidate + tier)
  -> GARUDA createEligibilityCheck   -> result_id
  -> GARUDA createOrderFromCheck     -> OrderCheckout
```

Names may still change; the CHAIN may not change silently, because the design above rests on it.
Generating the `Idempotency-Key`, and not reusing it across two distinct attempts by the same
visitor, is our responsibility.

### Our side, degraded to what it actually is

For a product with a downstream engine, the intent is a **routing** intent, not an order:

```
VerdictRoutingIntent
  evaluation_id            : uuid          # the decision this came from
  product_version_id       : uuid          # exactly one; two-candidate verdicts resolve first
  tier                     : T1 | T2 | T3
  quote_ref                : uuid | null   # null iff pricing is CONTACT_REQUIRED or UNKNOWN
  locale                   : "en" | "id"
  consultant_required      : bool          # always true for T2 and T3
  created_at               : timestamptz
```

Invariants unchanged: `tier=T3` never reaches checkout; `consultant_required=false` is legal only
at T1; `quote_ref=null` forbids any downstream screen showing a price. GARUDA confirmed the last
one is already satisfied from their side by construction — `OrderCheckout.price_idr` is
`integer, minimum:1`, an absent price is not representable, and an unresolvable catalogue key
returns `503 PRICE_UNRESOLVABLE` rather than an invented number. **That shape is load-bearing for
our tier map; it must not be softened.**

### The product-agnostic entry is deferred, with its prerequisite named

A second, product-agnostic order entry accepting our intent for the other 37 products is declared
future work, and its prerequisite is ours, not GARUDA's: **someone must own price and eligibility
for 38 products.** Today we do not — 12 of 38 have no `pricing_key` at all. Claiming that entry
before owning that is how the Oracle would start inventing prices.

## C3 — consultant assignment -> CRM

**Status: enforceable on our side now. Independent of GARUDA.**

```
ConsultantAssignmentEvent
  evaluation_id      : uuid
  client_id          : uuid | null     # null while the visitor is still anonymous
  requested_at       : timestamptz
  origin_screen      : wizard | verdict | checkout | portal
  tier               : T1 | T2 | T3
  product_version_id : uuid | null     # null when invoked before a verdict exists
  locale             : "en" | "id"
```

**Law 2 boundary, absolute and load-bearing here.** This event carries **no** name, phone, email,
passport, KTP, or free-text from the applicant. Identity travels as `client_id` only, and only once
one exists. Any lane that finds itself wanting to put a contact detail in this event has found a
design error, not a missing field.

The invariant the mandate calls "the consultant thread": the control that emits this event is
present on **every** screen — wizard, verdict, checkout, portal — and is invokable at any moment,
including before buying. A screen without it fails V2's critic gate regardless of how it looks.

---

## C4 — product card (the V1 per-product output)

**Status: frozen. This is the unit of V1 delivery — one product, one session, one card.**

One file per product, `research/visa/doctrine-factory/cards/<CODE>.md`, with front-matter:

```yaml
code: E28B # the visa index in question (mandate §3 move 1)
name_en: ...
name_id: ...
definition: ... # what it is and what it does (move 2)
tier: T1 | T2 | T3 # T3 until the card passes, always
tree_placement:
  parent_question: ... # where it hangs on the decision tree (move 3)
  discriminators: [...] # the facts that separate it from its siblings
questions: # the interview questions that reach it
  - fact_path: ...
    ask_en: ...
    ask_id: ...
nb2_citations: # verbatim, with source date
  - quote: "..."
    source: ...
    source_date: YYYY-MM-DD
rules: [...] # rule ids in the pack that implement this card
gold_personas: [...] # persona ids that positively expect this code
```

### The acceptance a card must meet before it leaves T3

1. **Every `fact_path` in `questions` is actually askable.** Checked against `fact-mapper.ts` in the
   same turn — a FactPath hard-coded `NOT_ASKED` makes its rule inert AND, at
   `on_unknown=NEEDS_INPUT`, suppresses the whole product. This is the disease that made E28B/C/D/F
   invisible and poisoned E23U/E23V. **Reachability reports do not catch it.**
2. **At least one gold persona positively expects this code, and the code exists in the pack.**
   Today 34/38 products have no persona, and the corpus asserts on `E31`, which the pack does not
   contain. A card that adds a persona naming a code absent from the pack has added a dead assertion.
3. **NB-2 citations are verbatim and carry a source date**, compared against the pack's own
   provenance date. An NB verdict on a number or threshold is a LEAD until that comparison is made
   (W90).
4. **The re-derivation matches.** A cross-family refuter re-derives the eligibility outcomes on the
   card's personas from the card's own text and reaches the same verdict as the engine.

A card that cannot meet (1)-(4) **stays T3** and says why in one line. That is a completed card, not
a failure: T3 is a real, sellable tier — the Oracle recognizes the case and routes to a consultant.
Three reds on the same cause stop the lane (assembly-line rule 8).
