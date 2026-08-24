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

**Status: NOT IMPLEMENTABLE. This is a request to the GARUDA orchestrator, not a contract we can
consume today.**

The mandate assumed GARUDA's order contract was on main. Measured (GROUND §4): it is not.
`garuda_flow/` has no order, checkout, or commerce module; the only public GARUDA route is
`GET /voa/{hash}`, a read-only archive; `balizero.com/visa/voa` is 404 since PR #4344 withdrew the
public surface.

### What we freeze on OUR side, so the graft is a one-line swap when the rails land

The Oracle emits a single, self-contained handoff intent. It does not know what checkout looks like.

```
VerdictHandoffIntent
  evaluation_id            : uuid          # the decision this came from, already emitted by the engine
  product_version_id       : uuid          # the chosen candidate (exactly one; two-candidate verdicts
                                           #   resolve to one before handoff)
  tier                     : T1 | T2 | T3  # from the product->tier map (owner switchboard #4)
  quote_ref                : uuid | null   # the decision quote; null iff pricing status is
                                           #   CONTACT_REQUIRED or UNKNOWN
  locale                   : "en" | "id"
  consultant_required      : bool          # true for T2 and T3, always
  created_at               : timestamptz
```

Invariants: `tier=T3` implies the intent routes to a consultant and NEVER to checkout.
`consultant_required=false` is legal only when `tier=T1`. `quote_ref=null` forbids any downstream
screen that shows a price.

Until the GARUDA rails exist, the emitter is behind a flag and its only consumer is a test double.
The request to the GARUDA orchestrator (sent by fleet mailbox) is: publish an order-creation
contract on main that accepts this intent, and tell us its name. We adapt to theirs — we do not ask
them to adopt ours.

---

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
