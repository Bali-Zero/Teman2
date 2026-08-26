# GARUDA VOA — the three architectural decisions the build hangs on

> Orchestrator-owned, written before CONTRACT FREEZE. Each decision below was taken against files
> read this turn, and each names what would falsify it. Lanes build against these; they do not
> re-litigate them. Changing one is an orchestrator act, and a business-visible change is an
> owner act.

---

## D1 — Two data domains, and the boundary between them is load-bearing

**Decision: the anonymous eligibility check and the identified order are SEPARATE data domains,
in separate tables, behind separate access models. `garuda_voa_checks` is never extended with
identifying columns.**

Migration `261_garuda_voa_checks.sql` does not merely happen to lack PII columns — it argues, in
its own header, that the absence IS the safety property:

> "this table carries ONLY enum / date / boolean / ISO-code columns. No name, no passport number,
> no email, no phone. This is precisely why the funnel can sit on an unauthenticated route […]
> the shape of this table IS the safety argument, not a flag. **Any future column MUST keep this
> property or the route can no longer be public.**"

The self-purchase funnel this mandate asks for needs all four of those fields — a name and a
passport number to file the visa, an email to authenticate the account, a phone to reach the
buyer. Adding them to `garuda_voa_checks` would not be an extension; it would silently revoke
the one written justification for the public route, and it would do so in a diff that looks like
four harmless columns.

So:

| Domain                          | Table family                                                         | Identifier                                                | Auth                | Contains                                                             |
| ------------------------------- | -------------------------------------------------------------------- | --------------------------------------------------------- | ------------------- | -------------------------------------------------------------------- |
| **Anonymous check** (L2)        | `garuda_voa_checks` (existing)                                       | opaque ≥128-bit id, "an identifier, never a credential"   | none — public route | enum / date / bool / ISO-3 only, exactly as today                    |
| **Identified order** (L3/L4/L5) | new `garuda_orders`, `garuda_order_documents`, `garuda_order_events` | order id, reachable only through an authenticated session | magic-link session  | name, passport, email, phone, uploaded documents, payment references |

The two are linked by a **one-way, optional** reference: an order may record which anonymous check
it originated from; a check never points at an order. That direction matters — it keeps the public
GET incapable of reaching identified data even if it is handed a valid check id, which is exactly
the property the public route's safety argument depends on.

**What falsifies D1**: a demonstration that the public result page must display something only the
order knows. It must not — the result page shows the verdict, the deadline, and the price, all of
which the anonymous row already holds.

---

## D2 — Retention extends the existing primitive with a SCOPE, not a second authority

**Decision: extend `visa_decision_retention_policies` with a policy scope, rather than hand-rolling
a parallel `garuda_retention_policies` table. One retention authority in the repo, not two.**

The binding persistence design admits both shapes ("a policy-scope column or a parallel policy
table following the identical pattern") and recommends the first, for a reason this build should
take seriously: a second authority is how you end up with two half-policies that each believe the
other covers the gap. The primitive already solves the hard parts — read this turn in
`264_visa_decision_retention_policy.sql`:

- fail-closed by construction: **no policy row is seeded**, and every insert fails until Zero
  records duration, anchor, effective period, approver, and approval reference
- `EXCLUDE USING gist (environment WITH =, effective_period WITH &&)` — no two policies can be
  live at once for one environment
- purge exposed as a bounded primitive with **no invented scheduler cadence**
- deletion batches survive only as aggregate evidence, with no stable applicant identifier
  (`266_visa_retention_evidence.sql`)

Extending it to garuda means: add a `policy_scope` column (`VISA_DECISION` | `GARUDA_CHECK` |
`GARUDA_ORDER`), widen the UNIQUE and the EXCLUDE constraint to include it, and add binding
triggers on the garuda tables that mirror `bind_visa_decision_retention_policy`.

**Three traps this lane must not walk into, all already paid for by this repo:**

1. **The binding trigger must be `SECURITY DEFINER` and owned by the ledger owner role.** Migration
   `268` exists solely because three `SECURITY INVOKER` triggers did a `SELECT … FOR SHARE` against
   a table the runtime role had only SELECT on — and `FOR SHARE` needs UPDATE privilege. Every
   INSERT started failing in production on 2026-08-07, and no test caught it because CI connects as
   a superuser, which is always both owner and invoker. A new garuda binding trigger written the
   obvious way reproduces this exactly.
2. **Do not edit 264 in place.** Applied migrations are immutable records; the correction is a new
   forward migration, which is what 268 itself documents at length.
3. **Do not reserve a migration number in advance.** Numbers bind late, at commit time — a number
   claimed in a document nobody re-reads is how W40's numbering collision happened. Highest on
   `origin/main` today is 280; the lane takes the next free one when it commits, not before.

**The retention DURATION is not ours to set.** 90 days is the proposal carried to the owner in
decision packet 3. Until a signed policy row exists, the fail-closed behaviour means the funnel
cannot persist — which is precisely why L1 lands before any lane writes a row.

**What falsifies D2**: if widening the EXCLUDE constraint on a live table in the Visa Oracle
adjudication path proves to carry unacceptable risk under review, the parallel-table shape is the
fallback — and then the cost is a written rule that both tables are amended together, forever.

---

## D3 — The contract is generated, because the last two GARUDA defects lived in the joint

**Decision: the wire contract is OpenAPI 3.1, the TypeScript client is GENERATED from it, and
hand-written DTOs or hand-rolled `fetch` calls against this product's endpoints fail CI.**

This is not a style preference; it is the direct cure for a measured defect class. The S14 lane's
capture (`research/operations/2026-08-24-garuda-voa-the-defects-were-in-the-joint.md`) found that
two of four defects were never in the engine at all — they were in the joint between the Python
engine and its only consumer, and **a fully green 202-test Python suite could not see either**,
because the contract's other half is TypeScript. The adapter carries nine hand-maintained mirrors
of Python constants, none generated, and its validator requires an _exact_ key count: add one field
on the Python side without updating the TypeScript allowlist and every request fails with one
opaque error.

That product had one internal consumer. This one will have a public API, a portal, an upload
surface, an email renderer, and a payment webhook. Hand-mirrored constants do not survive that.

Concretely, and CI-enforced:

- `products/garuda-voa/contracts/openapi.yaml` is the single source of the wire shape
- the TS client is generated into a build artifact; a `git diff --exit-code` after regeneration is
  the gate — a stale client fails the build rather than failing a customer
- the error catalog and the allowlisted public reason codes are part of the contract, generated on
  both sides from one list, so `DeclineCode` cannot drift from its TypeScript mirror again
- breaking-change diff against the previous version fails CI

ASSEMBLY-LINE's enforcement backlog already names this as item 4 — the typed-contract toolchain
wired into CI for the first product, then extracted as the platform template. GARUDA VOA is that
first product, so the toolchain is part of this build's cost, deliberately.

**What falsifies D3**: nothing about the necessity; only the scope is negotiable. If generating a
full client proves disproportionate for the two smallest surfaces, the fallback is
generated _types_ plus contract tests — never hand-written mirrors.
