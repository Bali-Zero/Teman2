---
date: 2026-08-28
domain: design
client_case: garuda-voa-case-code
adversarial_review: codex
sources:
  - apps/backend-rag/backend/services/garuda_orders/models.py
  - apps/backend-rag/backend/services/garuda_orders/journal.py
  - apps/backend-rag/backend/services/garuda_orders/repository.py
  - apps/backend-rag/backend/db/migrations_v2/284_garuda_orders.sql
  - apps/backend-rag/backend/db/migrations_v2/286_garuda_voa_check_results.sql
  - apps/mouth/src/app/visa/voa/orders/OrderTracker.tsx
  - apps/mouth/src/app/visa/voa/checkout/[resultId]/useCheckout.ts
  - apps/mouth/src/lib/whatsapp-utm.ts
  - research/design/2026-08-27-r4-identity-merah-putih-token-spec.md
  - research/design/2026-08-27-r6-walkthrough-perception-runtime.md
  - research/design/2026-08-27-r7-doctrine-loop-closure.md
---

# Case code BZ-26-0001 — design dossier (Design Study Loop, follow-on lane)

**Mandate.** Zero approved the customer-visible case code on 2026-08-28 (format `BZ-26-0001`,
four-digit progressive). No generator exists anywhere in the repo today — the `BZ-7Q4K` /
`BZ-3M8A` codes in the R5/R6 mockups are design placeholders (repo-wide search, checkout
dossier §1). This dossier fixes where the code is born, what unit it names, where it lives,
and which surfaces carry it, so the build lane starts from a settled contract. It went
through a two-seat cross-family adversarial pass (codex gpt-5.6-sol xhigh with in-repo
verification, kimi k3) whose findings reshaped it — see §6.

## §1 Ground (measured, file:line)

- **Orders.** `garuda_orders.order_id TEXT PRIMARY KEY` with regex `^[A-Za-z0-9_-]{16,128}$`
  (284:36-38), generated as `new_opaque_id("ord")` — the generic prefix-parameterised helper
  at journal.py:19-22, prefix bound at the call site repository.py:162. `result_id_ref` is a
  soft reference to the anonymous check — compatible regex, wider band (16-128 vs the check's
  22-128; 284:39 vs 286:94), deliberately NOT a foreign key (284:41-46). One live order per
  check via the PARTIAL unique index `uq_garuda_orders_result_id_ref_live` (284:121-123) —
  terminal states (`failed`/`expired`/`refunded`) do NOT block a fresh order for the same
  check. The `Order` dataclass (models.py:25-42) has no customer-visible number.
- **Order creation vs provider.** The order row is inserted and committed BEFORE the payment
  provider is contacted (repository.py:164-197 vs :224). A provider failure surfaces as a
  503 whose body today carries only `PAYMENT_PROVIDER_UNAVAILABLE` (garuda_orders_router.py:265);
  the frontend keeps only `message`/`retryable` in its error state (useCheckout.ts:12,53).
- **Checks.** `garuda_voa_check_results.result_id` = `token_urlsafe(24)`
  (check_store.py:69,174). The magic-link session resolves to the **result_id**, the
  ownership key every order read/write filters on (garuda_orders_router.py:116-150; the
  tracker additionally filters `result_id_ref = actor`, :303,:310). Check rows are governed
  by the ACTIVE retention policy (90 days today — policy data, not a schema constant) and are
  customer-deletable.
- **Tracker.** `OrderTracker.tsx` never renders `order_id` in visible markup — the customer
  today sees no identifier. The WhatsApp link (`buildWhatsAppLink`, whatsapp-utm.ts:30-45;
  call sites OrderTracker.tsx:255-258, 334-337, 378-381) carries a generic greeting and UTM
  tags only.
- **Progressive-number precedent.** The only customer-visible progressive in the repo is
  `invoice_number = INV-YYYYMM-{practice_id:05d}` (invoice_generator.py:141-144), composed
  from the CRM's global integer PK. No explicit `CREATE SEQUENCE` exists in `migrations_v2/`.
- **Ownership (measured live 2026-08-28 via the readonly proxy).** `garuda_orders`,
  `garuda_order_journal`, `garuda_order_idempotency` are all owned by `backend_rag_v2` — the
  new objects below join them, so the migration runs under the runtime DSN without the
  ledger-owned-DDL deploy-abort trap.
- **Binding design law.** R4:118 — the wa.me link carries "an OPAQUE case code only — never
  DOB, nationality, overstay or sponsor facts in the URL"; "the human resolves the case
  server-side from the code". R6:269-277 — the code is "the spine": it survives verdicts,
  failures, WhatsApp handoffs and the tracker, and must appear on the payment receipt and in
  the first WhatsApp message. R7:180-183 (backlog item 3) counts receipt + first WA message
  as the spine's two missing links.

## §2 What unit does the code name? A JOURNEY, not an order

The adversarial pass killed the naive "column on garuda_orders" design twice over: the
partial unique index means a failed/expired order allows a fresh order for the same check —
a per-order code would fork the customer's identity on exactly the failure→retry path the R6
spine was built for; and a wedged order would hold a code forever. So:

**The case code names the customer journey, keyed by `result_id_ref`.** Every order created
for the same check carries the same code — retries, expiries and re-orders inherit it. This
is what makes "survives verdicts, failures, WhatsApp handoffs and the tracker" literally
true.

## §3 The contract

### §3.1 Format

`BZ-YY-NNNN` — `YY` = last two digits of the counter year, `NNNN` = zero-padded per-year
counter starting at 1. Overflow past 9999 widens the number (`BZ-26-10001`), never fails an
allocation — stated plainly: the four-digit promise is the *starting* width, not a cap.
Validator regex: `^BZ-[0-9]{2}-[0-9]{4,}$` (format only; year/counter coherence is enforced
by the allocator, not the regex — a CHECK cannot see the counter).

### §3.2 Storage

Two new tables plus one column, all on `backend_rag_v2`-owned objects:

```sql
CREATE TABLE public.garuda_case_code_counters (
    counter_year INTEGER PRIMARY KEY CHECK (counter_year BETWEEN 2000 AND 9999),
    last_value   INTEGER NOT NULL CHECK (last_value >= 0)
);

CREATE TABLE public.garuda_case_codes (
    case_code     TEXT PRIMARY KEY CHECK (case_code ~ '^BZ-[0-9]{2}-[0-9]{4,}$'),
    result_id_ref TEXT NOT NULL UNIQUE CHECK (result_id_ref ~ '^[A-Za-z0-9_-]{16,128}$'),
    counter_year  INTEGER NOT NULL,
    allocated_at  TIMESTAMPTZ NOT NULL
);

ALTER TABLE public.garuda_orders
    ADD COLUMN case_code TEXT REFERENCES public.garuda_case_codes (case_code);
ALTER TABLE public.garuda_orders
    ADD CONSTRAINT garuda_orders_case_code_required
        CHECK (case_code IS NOT NULL) NOT VALID;
```

- The full-year `INTEGER` key (not `CHAR(2)`) makes the counter genuinely per-year — no
  modulo-100 aliasing at 2100.
- `garuda_case_codes.result_id_ref UNIQUE` IS the journey invariant: one code per journey,
  one journey per code, enforced by the schema rather than a tripwire.
- The `NOT VALID` check is this repo's own 281 pattern (281:250-253): every NEW order row
  must carry a code; legacy rows (if any) keep NULL with no fabricated retroactive codes. A
  future insert path that forgets the code fails loudly instead of silently breaking the
  spine.

### §3.3 Allocation (inside the order-creation transaction)

1. Look up `garuda_case_codes` by `result_id_ref` — if a code exists, the new order inherits
   it (retry/re-order path).
2. Otherwise mint one:

   ```sql
   INSERT INTO public.garuda_case_code_counters AS c (counter_year, last_value)
   VALUES ($1, 1)
   ON CONFLICT (counter_year) DO UPDATE SET last_value = c.last_value + 1
   RETURNING last_value;
   ```

   then insert the `garuda_case_codes` row and stamp the order.
3. **One clock.** The counter year and the order row's `created_at` derive from the same
   `transaction_timestamp()` value, passed explicitly to both — never two independent clock
   reads across a midnight-UTC rollover. (Timezone note, accepted: the code year is UTC; a
   WITA customer ordering in the first eight hours of Jan 1 local time holds a code from the
   previous UTC year. Cosmetic, documented for support.)
4. Failure semantics, stated honestly: a rolled-back creation reuses the number (the counter
   bump rolls back with it — no gaps), but an order that COMMITS and then dies at the
   provider or is abandoned keeps its code forever. The counter therefore counts purchase
   attempts at journey granularity — inheritance means an abandoned-then-retried journey
   consumes ONE code, not one per attempt, which is what keeps the enumerable set close to
   real cases.

### §3.4 The two identifiers, and why this needs NO deviation from R4

The first draft declared a deviation (progressive code in the wa.me link). The adversarial
pass refuted it as a false dilemma, and the refuted design is withdrawn:

- **The BZ code is the customer-visible identity**: tracker header, receipt, and every human
  conversation. It authorizes nothing (tracker access stays gated by the opaque `order_id`
  route + `garuda_session` cookie with the `result_id_ref = actor` ownership filter).
- **The wa.me link carries only the opaque locator that already exists — `order_id`** (e.g.
  "Hi Bali Zero, I need help with my Visa on Arrival order. Ref: ord_…"). Staff resolve the
  ref server-side to the case and answer citing the BZ code. R4:118 is honoured to the
  letter — the URL payload stays opaque and PII-free — and R6's "code in the first WhatsApp
  message" is satisfied in the first staff REPLY, declared here as the binding
  interpretation: the BZ code never travels in a URL, in either direction.
- **The progressive's residual exposure** is therefore: visible to the customer on their own
  surfaces, never enumerable from links. The volume signal (two of your own receipts a month
  apart reveal throughput delta) is accepted-by-format — Zero's ruling — and recorded with
  its honest edge: switching future codes to a random format would stop NEW leakage but
  cannot un-publish history.

### §3.5 The human channel is a surface (SOP, binding on the build)

The staff CRM lookup is an authenticated route whose OUTPUT flows to an unauthenticated
WhatsApp counterparty, and a dense progressive fails OPEN on typos (a one-digit slip lands
on another real customer). Two binding rules, recorded here and owed to the CRM/SOP lane:

- **Identify before you disclose.** Staff match the WA sender against the order's own
  contact (applicant phone/email) before sharing any case detail. The code selects the case;
  it never authenticates the person.
- **The code never asks for money.** Bali Zero never requests payment via WhatsApp citing a
  case code; the receipt/tracker copy says so, which is the cheap structural answer to
  forged "your order BZ-26-NNNN requires payment" messages made plausible by an enumerable
  format.

### §3.6 M8 failure-path requirement (contractual, closes the CRITICAL)

The checkout response carries `case_code` **on the provider-failure path too**: the 503 body
gains the code (and order ref) alongside `PAYMENT_PROVIDER_UNAVAILABLE`, and the frontend
error state keeps it so M8's recovery screen can honour "saved under case code X". Copy
correction bound with it: the promise is "your CASE continues under code X" — the order and
its code are the durable record; the check ANSWERS remain governed by retention/deletion and
are not what the code preserves.

### §3.7 Surfaces (build order)

1. **Backend PR** — migration (two tables + column + NOT VALID check) + allocation in
   `createOrderFromCheck` + `case_code` in tracker payload + 503 body per §3.6. Migration
   class ⇒ auto-merge OFF, session merges after its gates. Tripwire tests: journey
   inheritance on re-order; no route accepts `case_code` as a selector without BOTH an
   authenticated session AND the ownership filter (IDOR, not just auth); one-clock rollover.
2. **Tracker + WhatsApp PR** — header shows the BZ code; the three `buildWhatsAppLink` call
   sites move to the locator greeting (§3.4).
3. **Receipt PR** — the code on the payment-confirmation surface (closes half of R7 backlog
   item 3).
4. Out of scope: portal/CRM rendering (follows the weld prove-live lane), pre-order
   surfaces (the anonymous result screen has NO code — a code is born with the first order).

## §4 Repo findings surfaced by the pass, NOT of this lane

- **Wedge state (pre-existing bug, flagged for the GARUDA mandate):** an order stuck in
  `created` (provider call failed, customer never retried) can never expire — the state
  trigger forbids `created→expired/failed` (284:140) — and the partial unique index counts
  `created` as live, so it blocks any new order for that check forever. Intersects this lane
  only in that codes are born at that state; the cure (state-machine or sweeper) belongs to
  its own lane.
- **`result_id_ref` regex band** is wider (16-128) than real result ids (22-128) — cosmetic
  today, noted.

## §5 Open questions deliberately NOT decided here

- Whether the CRM practice record adopts the same code once the portal weld creates
  practices from paid orders (owner call).
- Whether e-mail templates adopt the code before the receipt PR lands (copy lane).
- Mockup copy showing a code BEFORE any order exists (M4a "saved under case code" on
  pre-order screens) overreaches the mechanism and goes to the copy lane for adjustment.

## Adversarial review

Two-seat cross-family pass on the first draft, 2026-08-28: **codex gpt-5.6-sol** (xhigh,
sandbox read-only in the lane worktree — verified every file:line claim in-repo, 13
findings) and **kimi k3** (11 findings). Raw outputs: session scratchpad
`case-code-panel/{codex-sol,kimi-k3}.txt`. Joint disposition — 20 unique findings after
dedup, 17 APPLIED / 3 REJECTED-with-reason:

| # | Seat | Sev | Finding (compressed) | Disposition |
|---|------|-----|----------------------|-------------|
| 1 | codex | CRITICAL | 503 provider-failure path drops order/code — M8 can never show it | APPLIED §3.6 (contractual requirement on the 503 body + frontend error state) |
| 2 | both | CRITICAL | failed/expired order → fresh order → NEW code; spine breaks on exactly the failure path | APPLIED §2/§3.3 (journey table keyed by result_id_ref; inheritance; schema-enforced one-code-per-journey) |
| 3 | kimi | CRITICAL | staff resolve codes for unauthenticated WA counterparts — impersonation via enumerable codes | APPLIED §3.5 (identify-before-disclose SOP; code selects, never authenticates) |
| 4 | codex | MAJOR | allocator SQL not executable; first-insert-of-year undefined | APPLIED §3.3 (full `VALUES ($1,1) ON CONFLICT … RETURNING`) |
| 5 | both | MAJOR | NULLable column + UNIQUE enforces nothing for new rows — spine breaks silently | APPLIED §3.2 (`CHECK (case_code IS NOT NULL) NOT VALID`, the repo's own 281 pattern — kimi's "CHECK can't express this" is answered by NOT VALID semantics) |
| 6 | both | MAJOR | year rollover has no defined clock; app/DB skew can misfile the year | APPLIED §3.3 (one `transaction_timestamp()` passed to both; UTC-vs-WITA edge documented) |
| 7 | codex | MINOR | CHAR(2) counter key aliases years modulo 100 | APPLIED §3.2 (full-year INTEGER key) |
| 8 | codex | MAJOR | proposed tripwire checks auth, not ownership — authenticated IDOR passes | APPLIED §3.7 (tripwire asserts ownership filter, mirroring router :303,:310) |
| 9 | both | MAJOR | CC-D1 widens Zero's ruling beyond what is documented; opacity re-scoped without covering R4's own threat model | APPLIED §3.4 (deviation withdrawn entirely) |
| 10 | codex | MAJOR | option B rejection is a false dilemma — an opaque transport locator preserves both the spine and R4 | APPLIED §3.4 (adopted: `order_id` as the locator; BZ code never in URLs) |
| 11 | kimi | MAJOR | dense progressive fails OPEN on typos — wrong customer's case pulled | APPLIED §3.5 (identity match before disclosure) |
| 12 | kimi | MAJOR | phishing plausibility: forged payment requests citing structurally-valid codes | APPLIED §3.5 ("the code never asks for money" copy rule) |
| 13 | codex | MAJOR | "orders are the durable record of your answers" — orders don't store check answers | APPLIED §3.6 (copy corrected: the CASE continues; answers stay under retention/deletion) |
| 14 | kimi | MAJOR | orders wedged in `created` hold codes forever and block re-order (repo bug) | APPLIED §4 (recorded as pre-existing repo finding, own lane; inheritance limits the code-side damage) |
| 15 | codex | MAJOR | DDL ownership asserted, not verified | APPLIED §1 (measured live: all three garuda_order* tables owned by backend_rag_v2) |
| 16 | both | MINOR | "reversible later" overstated — historical leak is irreversible | APPLIED §3.4 (restated honestly) |
| 17 | kimi | MINOR | "90d purge" stated as schema fact — it is policy data | APPLIED §1 (restated as active-policy-governed) |
| 18 | kimi | MINOR | "format caps ~10⁴/year" contradicts the overflow clause | APPLIED §3.1 (starting width, not a cap; the counter-table serialization rationale no longer leans on a cap) |
| 19 | codex | MINOR | citation nits: regex band 16-128 vs 22-128; `ord_` prefix bound at repository.py:162 not journal.py | APPLIED §1/§4 |
| 20 | kimi | MAJOR | M8 promise implies the code recovers something, but the invariant makes it useless to the holder | REJECTED as stated — the code is wayfinding for the HUMAN channel (quote it to a person), which M8's copy already frames ("a named person who can pick your case up"); §3.6's copy correction removes the "answers" overreach that gave the finding its bite. Partial credit absorbed there. |

Rejected beyond #20: kimi's procedural point that CC-D1 was self-declared where R4's D4 was
panel-forced (moot — the deviation is withdrawn), and kimi's suggestion of a check-digit
format (would amend Zero's ruled format; the SOP identity-match covers the same risk without
touching the ruling — recorded in §5 as available if Zero ever wants it).
