# Contract adversarial review — round 1

> Generator: Codex (GPT-5.6) · Refuter: an independent Sonnet seat on fresh context, which wrote
> none of what it reviewed · Money/date re-derivation: a third seat, separate again.
> Orchestrator disposition below. Nothing here was accepted on the refuter's word: every finding
> kept is one I re-measured myself against the tree, and the two I confirmed are recorded with the
> command that confirmed them.

## A process fact that matters more than any single finding

**The candidate was being rewritten underneath the review.** The refuter reported the contract
hashes changing twice mid-session and froze its own read only after the tree held one md5 across a
10-second window. I then measured the same thing from the outside: `codex exec --sandbox
workspace-write` (PID 43803) was still alive at 32 minutes elapsed with `errors.yaml` written at
22:19, i.e. **after** the refuter's 22:09:57 freeze point.

That is superscar family #5 (sibling-race) arriving inside a review rather than inside a merge, and
it cuts both ways. It invalidated the refuter's line numbers — but it also silently _fixed_ three
things the refuter was about to report, which is why the report reads cleaner than the work was:

- two dead error codes (`WEBHOOK_EVENT_UNSUPPORTED`, `WEBHOOK_RECONCILIATION_FAILED`) declared in
  `errors.yaml` and referenced by nothing, removed mid-review;
- an invalid `discriminator: {propertyName: transition_id}` with no `mapping`, whose branch schema
  names did not match their `transition_id` consts (`BlockPracticeTransition` vs const `PR-03`);
- `requestMagicLink`'s security tightened from optional `{}`/`ResultSession` to `ResultSession`
  only — which closed a PII-on-unauthenticated-operation gap.

**The rule this establishes for the rest of this product: the generator must be dead before the
refuter is dispatched.** A review of a moving target cannot be relied on in either direction — it
can miss what appears after it looks, and it can report what has already been cured.

## Findings kept

### 1 · HIGH — the late `paid` after a terminal state has no wire representation

`DECISIONS.md` Q2 is explicit that a signed, reconciled `paid` arriving after `expired`/`failed`
must commit a compensating transition, append `payment.late_paid_after_terminal`, open one staff
remediation case and page — and that **the contract must make both staff paths expressible**
(honour the order, or refund in full; never neither).

Re-measured by me on the current tree:

```
grep -n "late_paid\|LatePaid\|after_terminal" products/garuda-voa/contracts/*.yaml
  events.yaml:203  PaymentLatePaidAfterRefund
  events.yaml:204  x-event-name: payment.late_paid_after_refund
  events.yaml:216  event_name: { const: payment.late_paid_after_refund }
```

One late-paid event exists and it is the **other** case (OP-F04, `refunded → paid`), whose own
comment keeps the order `refunded` and never releases the practice — no remediation choice at all.
`payment.late_paid_after_terminal` does not exist as an event, an operation, or a staff-facing
schema. `STATE-MACHINE.md` OP-F05 says only "quarantine and page", naming no event and attaching no
staff-actionable transition.

So money that really arrives after we have told the customer "expired" has no representable way for
staff to either deliver or refund. Q2's own words for that outcome are "theft by bookkeeping".
**Disposition: FIX BEFORE FREEZE.** Additive — a `payment.late_paid_after_terminal` event plus a
staff transition that can resolve it either way. The `transition_id` needs the same grounding
decision already flagged as a TODO on its sibling.

### 2 · MEDIUM — the privacy response headers cover 3 public operations out of 8

The `&publicPrivacyHeaders` anchor (`Cache-Control: no-store, private`, `Referrer-Policy:
no-referrer`, `X-Robots-Tag: noindex, nofollow, noarchive`) is attached to every response of the
three eligibility operations and to nothing else. Counted by me: 19 occurrences of the anchor name,
1 of them the definition, the other 18 spread across exactly `createEligibilityCheck`,
`getEligibilityResult` and `deleteEligibilityResult`.

The five remaining `GARUDA_PUBLIC_ENABLED`-gated operations — `requestMagicLink`,
`exchangeMagicLink`, `uploadIntakeDocument`, `listIntakeDocuments`, `createOrderFromCheck`,
`getOrderAndPractice` — carry none of them, on success or on error. That leaves
`OrderCheckout.checkout_url`, order and practice state, and document-processing metadata with no
contractual no-store / no-referrer / no-index guarantee, while the surface immediately next to them
has one. Given how much weight SM-G02/G03 put on exactly this posture, this reads as an oversight
rather than a deliberate narrowing. **Disposition: FIX BEFORE FREEZE.** One pattern, copied.

### 3 · LOW — `PR-12` has no slot in the `TransitionId` enum and `OP-09` does

`STATE-MACHINE.md` names both as must-be-idempotent replays; `events.yaml` lists `OP-09` (in
`x-no-event-transition-ids`, i.e. a valid value that never emits its own event) and has no `PR-12`
member at all, with no comment saying why. The asymmetry is probably correct — a practice replay
always already carries the real `PR-0x` id it is replaying, whereas a webhook retry may need a
generic slot — but the contract does not say so. **Disposition: NOT A BLOCKER.** Add one line of
comment stating the reason, or add the member for symmetry; either closes it.

## Checked and confirmed sound (machine-verified, not skimmed)

- **Price.** `price_idr` is a single integer `minimum: 1`, appearing three times, each pointing at
  `pricing.py::price_for_case`. A grep across all four contract files for fee / pnbp / subtotal /
  discount / tax / component / breakdown / surcharge returns nothing outside prose that disclaims
  them. `price_for_case` returns one all-inclusive amount and fails closed to `None` on any
  catalogue mismatch, so a split is not constructible even server-side. This is the defect that was
  in the mandate's own seed text; it is not in the contract.
- **The PII boundary (architecture D1).** `EligibilityCheckRequest`, the unauthenticated POST,
  carries no PII — enums, dates, booleans and an ISO-3 code, matching the `garuda_voa_checks` shape.
  `CreateOrderRequest.applicant` (name, email, phone, passport) sits behind `MagicSession`.
  `deleteEligibilityResult` always answers 204 regardless of ownership, so its optional auth cannot
  enumerate. `exchangeMagicLink` carrying `security: []` is correct — presenting the token _is_ the
  authentication act.
- **State machine.** Every `OP-00..OP-09` and `PR-01..PR-11` id is representable. There is no
  client-writable order-transition endpoint at all: only the signed webhook moves `OrderState`, so a
  forbidden transition such as `paid → awaiting_payment` is unreachable by construction rather than
  by a rule. `browser_observation` is explicitly non-authoritative and cannot produce `paid`.
- **Idempotency.** All eight mutating operations require `Idempotency-Key`; all three GETs omit it.
- **Reason codes.** Diffed programmatically against the live `eligibility.py::DeclineCode` enum,
  imported rather than regexed: exact 18/18, both directions empty. I ran this independently of the
  refuter and got the same answer. No internal vocabulary leaks.
- **Error catalogue.** Every `x-error-codes` value used in `openapi.yaml` diffed against
  `errors.yaml`: 27/27, no dead codes, no undeclared ones — true only after the mid-review removal
  noted above. The four fail-closed causes map to four distinct machine-distinguishable codes.
- **Validity.** All four files parse; all 39 `$ref`s, internal and cross-file, resolve.

## Verdict

`FREEZE_WITH_FIXES`. The architecture is sound and the two hardest properties — a price that cannot
be split and an anonymous/identified split that cannot leak — are airtight. Findings 1 and 2 are
both additive and neither needs a re-design. The freeze is not final until they land **and** until
the generator process is confirmed dead, so that what is frozen is a tree that has stopped moving.

---

## Disposition — both blocking findings fixed, and pinned so they stay fixed

Applied after the generator was confirmed dead (PID 43803 gone) and the tree held one md5
across a settling window — the rule this review discovered, obeyed on its own output.

**Finding 1.** The grounding decision the two recovery events were waiting on is now made:
`DECISIONS.md` Q10 admits `OP-F04` and `OP-F05` to the `TransitionId` enum, deliberately keeping
the `F` rather than flattening them into `OP-10`/`OP-11`. `PaymentLatePaidAfterRefund` is
inhabitable at last (`transition_id: {const: OP-F04}`, the `x-disabled-until-grounded` pair gone),
`PaymentLatePaidAfterTerminal` exists (`OP-F05`), and Q2's two staff outcomes are now expressible
through `POST /api/visa/voa/staff/orders/{order_id}/late-resolution` → `resolveLateOrder`, whose
request admits exactly `honoured` or `refunded_in_full` and no third value. The terminal order
state is kept, as OP-F05 requires; the compensation is recorded beside it rather than by rewriting
history to pretend the order never expired.

**Finding 2.** Every response of every `GARUDA_PUBLIC_ENABLED` operation now carries all three
privacy headers. Measured by parsing the document, which expands the anchors: **91 of 91**. The
scope grew during the fix — the refuter counted five uncovered operations, and parsing found eight,
because `observePaymentBrowserReturn`, `receivePaymentWebhook` and `transitionPractice` were also
bare. They are covered too. On the webhook the headers are inert (a payment provider is not a
browser), and they are applied anyway: a rule with exceptions has to be re-reasoned at every new
operation, and inert headers cost nothing.

**Finding 3** stays open as written — a question for the owner, not a blocker.

### What actually holds the freeze

`contracts/tests/test_contract_invariants.py`, 7 tests, all green, and **proven to bite**: blanking
the headers on one response of one operation turns the privacy test red; removing `OP-F05` from the
enum turns the late-payment test red; both go green again on restore. Both of those tests exist
because this review found the property broken, which is exactly the pair most likely to be quietly
relaxed later by someone making a diff pass.

The suite parses the YAML or imports the Python enum in every case. Nothing here greps the source,
because a regex agrees with a file that does not mean what it says. One of these checks was itself
wrong first: the `$ref` walker reported 87 of 181 refs unresolved until it learned that
`./errors.yaml#/...` needs a `basename`. The probe was broken, not the contract — which is the same
lesson in miniature.

**FREEZE: FINAL.** Seven build lanes and the Visa Oracle V3 lane may build against these four files.

---

## Round 2 — and a correction to how round 1 was closed

**I wrote "FREEZE: FINAL" above while the third leg of the adversarial pass was still running.**
The corrected ASSEMBLY-LINE defines a full pass as three things — refuter on the diff, attack
session, and an independent money/date re-derivation — and I declared the freeze on the strength of
the first alone, because it was the one that had reported. That is the same mistake as reviewing a
moving target, pointed the other way: instead of judging an artifact before it settled, I closed a
gate before its evidence had arrived. The money/date leg then found four real things. Round 1's
verdict stands on its merits; the word "FINAL" on it did not.

The re-derivation ran on a cross-family seat (Kimi K3) after the Sonnet seat went idle twice without
delivering — at the second silent idle, change the door rather than ask again. It confirmed the
money path is clean and **ran** the resolver rather than reading it: issuance 790.000 IDR, extension
850.000 IDR, both from catalogue keys, failing closed on any mismatch. What it found instead was
that several numbers we had _decided_ were binding nobody.

### Fixed in this round

**The prose decisions now bind.** Q1's 15-minute magic-link TTL lived only in a portal service that
nothing connects to this product, and the contract said merely "invalid, expired, or consumed" with
no window — so an implementer could ship any lifetime and stay contract-valid. Q9's 90/180/90
freshness windows existed **nowhere machine-readable at all**, which means `G-FRESHNESS-FAIL-CLOSED`,
a guardrail this product declares, had no number to fail closed on. A guardrail whose threshold does
not exist is a sentence, not a guardrail — and "declared and does not exist" is precisely the shape
that already bit this product once. Both are now `x-magic-link` and `x-truth-freshness-max-age-days`
in the contract, and both are asserted.

**Every date field now says which civil day it means.** The engine already carries this scar:
`civil_clock.py::garuda_today` exists because the backend runs in UTC and reading a Bali civil day
as a UTC day moves the ACCEPT/DECLINE cutoff and the published deadline by a full day for the first
eight hours of every Bali day. A bare `format: date` on the wire lets that straight back in, and
three inbound fields had exactly that. The one outbound date named the Python symbol
`GARUDA_CIVIL_TIMEZONE`, which a client cannot resolve — so the zone is now written literally too.

**The published deadline is now scoped on the wire.** `published_filing_deadline` carries
`x-published-by-office: Ngurah Rai` and states the constraint from GROUND.md §5 in full: the engine
attaches "verify per office" to this exact checkpoint while the intake collects no office at all, so
it is the one externally sourced number we show a visitor whose correctness depends on a fact we
never ask for. Until owner decision 6 lands, a surface may show it only when the office is known to
be Ngurah Rai, and otherwise suppresses it and routes to WhatsApp.

### Carried forward, not fixed

- **The 2027 cliff has a date on it.** `COVERAGE_END = 2026-12-31`. From 2027-01-02 no open day is
  certifiable and every arrival declines with `CALENDAR_COVERAGE_EXCEEDED`. Correct-by-design and
  already pinned by a test — but it is a hard product cliff, and the 2027 SKB is expected around
  September 2026. It belongs in the ledger, not in a contract fix.
- **A JSON-Schema nit**: under 2020-12, `790000.0` satisfies `type: integer`. Not worth a `multipleOf`
  today; recorded so the next reader does not rediscover it.
- **Finding 3** (PR-12's missing enum slot) is still the open question it was.

Nine tests now, all green, and every one of the four added across both rounds proven to bite by
mutation — change the TTL, strip a civil zone, blank a response's headers, drop `OP-F05`, each turns
its own test red and only its own.

**FREEZE: FINAL — this time with all three legs reported.**
