# GARUDA VOA — the open questions the journeys raised, answered

> The architect seat left nine `TODO(ground)` markers rather than guessing. That was correct.
> This file closes the ones that are the orchestrator's to close, and says explicitly who owns each
> of the rest. Nothing here may be re-decided by a lane; a lane that thinks one of these is wrong
> stops and says so.
>
> Numbered Q1-Q9 in the order they appear in `journeys/`.

---

## Q1 — Magic-link lifetime and single-use authority · DECIDED

- **Lifetime 15 minutes** from issue. Long enough for a phone to switch to a mail app and back,
  short enough that a link sitting in an inbox is not a standing key.
- **Single use.** The token is consumed on first successful exchange and cannot authenticate twice,
  which is what `magic-link-security.feature`'s replay scenario asserts.
- **A consumed token and an expired token return the identical response.** Different responses
  would tell an attacker holding a leaked link whether it had already been used — an oracle worth
  nothing to us and something to them.
- The token is bound to the email address that requested it. Exchanging it establishes a **session**
  whose lifetime is a separate decision (proposed: 30 days, re-authenticated by a new link), because
  conflating link lifetime with session lifetime is how a 15-minute link becomes a 15-minute portal.

## Q2 — Provider event taxonomy, checkout expiry, and a late `paid` · DECIDED, and it matters

**The provider is authoritative for money; our `expired` is a reconciliation, not a truth.**

`OP-04` (`awaiting_payment → expired`) records that we stopped waiting. It does not record that the
customer did not pay. If a signed, reconciled `paid` event arrives afterwards, **the money is real
and dropping it would be theft by bookkeeping.** So:

- A late `paid` after `expired` or `failed` is NOT ignored and NOT silently swallowed. It commits a
  compensating transition, appends `payment.late_paid_after_terminal`, opens one staff remediation
  case, and pages. The customer is not left with a charge and no practice.
- Staff then take one of exactly two paths, and the contract must make both expressible: honour the
  order (create the practice, deliver late) or refund in full. Never neither.
- The provider's event taxonomy is mapped to ours at the port boundary, not scattered through the
  code — one translation table, one place to fix when the provider renames a status.

## Q3 — Customer-safe blocked/rejected reason codes · DECIDED (by precedent, not invention)

Reuse the discipline `eligibility.py::DeclineCode` already establishes and states in its own
docstring: **a stable, neutral machine code crosses the wire; the English audit prose never does.**
Blocked and rejected practice states get their own enum on the same terms — no threshold number, no
internal checkpoint name, no "D-N" wording, nothing that leaks an internal SOP to a visitor. The
staff-facing reason is a separate field that the public serializer cannot reach.

## Q4 — DeclineCode → alternative product mapping · NOT OURS. Belongs to Visa Oracle.

Every DECLINE must propose the right alternative and route to WhatsApp — but _which_ visa is the
right alternative for a given decline is exactly the question the Visa Oracle product exists to
answer, across all 38 products, with the doctrine corpus and NB-2 behind it
(`docs/plans/2026-08-24-visa-oracle-live/MANDATE.md`, home Pro).

**Building a second mapping here would be a duplicate authority on a client-facing recommendation** —
the same mistake the retention design refused to make with a second policy table. GARUDA therefore
emits the decline code and calls the Oracle for the alternative; it does not carry its own table.

Until that call exists, a DECLINE routes to WhatsApp **without naming a specific alternative** — an
honest handoff rather than a guessed recommendation. Interface question for the two lanes to settle
at the contract boundary; the copy is L6's.

## Q5 — "Signed" retention policy: cryptographic or not? · DECIDED — NOT cryptographic

The architect was right to ask, because this repo uses the word "signed" for two different things
and they are one sentence apart in the mandate.

- **Rule packs** (`visa_rule_packs`) ARE cryptographically signed — Ed25519 bundles with a
  two-login activation ceremony. That is the Visa Oracle engine's mechanism.
- **The retention policy is NOT.** Migration `264_visa_decision_retention_policy.sql` requires a row
  carrying `approved_by`, `approval_reference`, a duration, an anchor and an effective period,
  guarded by a mutation trigger and a non-overlap EXCLUDE constraint. The authority is the
  guarded append-only row and its named approver — there is no key, no signature, no verification
  step.

Wherever this product's documents say "signed retention policy", read "recorded, approved, and
guarded" — the fail-closed behaviour is identical, and no lane should go looking for a key that
does not exist.

## Q6 — Precedence when a verdict carries several decline codes · DECIDED

The engine can emit several. The customer must be told the one that is most useful to them, and the
order must be deterministic or the same case yields different copy on different days.

Precedence, most-decisive first:

1. **Immovable facts about the person**: `NATIONALITY_NOT_ELIGIBLE`, `SPECIAL_PASSPORT`,
   `PASSPORT_TYPE` — no action by the customer changes these, so say them first.
2. **Fixable facts about the document**: `PASSPORT_VALIDITY`.
3. **Facts about the purpose**: `PURPOSE_NOT_ELIGIBLE`, `GROUP_CASE`.
4. **Facts about the timing**: the arrival-window codes.
5. **Facts about the arrangement**: `NOT_SELF_PAY`, `FASTLANE_REQUEST`, `URGENT_CASE`,
   `PRIOR_ISSUE`, `FEEDBACK_REQUIRED`.

The full ordered list lives in the contract's `reason-codes.yaml`, is generated to both sides, and
is test-owned. All codes stay in the response; only the _primary_ one drives the headline copy.

## Q7 — OCR confidence threshold · DEFERRED TO L5, and it must be MEASURED

A threshold picked by argument is a threshold that will be wrong. L5 runs the real local model
(`qwen2.5vl:7b`) over a corpus of genuine passport photographs — good ones, dim ones, glare, angle,
partial crop — and sets the cut where the false-confident rate goes to zero, because the expensive
error is not "we asked again", it is "we filed a wrong passport number".

Contract requirement now, so the shape is frozen even though the number is not: the OCR result
carries a confidence, and the customer-visible outcome is one of exactly three —
verified fields, `LOW_CONFIDENCE`, `UNREADABLE_DOCUMENT`. No numeric confidence ever reaches the
customer.

## Q8 — Provider-neutral terminal-failure taxonomy · DECIDED in shape, filled by L3

Our vocabulary, not the provider's: `DECLINED_BY_ISSUER`, `INSUFFICIENT_FUNDS`,
`AUTHENTICATION_FAILED`, `PROVIDER_UNAVAILABLE`, `EXPIRED`, `CANCELLED_BY_CUSTOMER`. The provider's
own codes map INTO these at the port and are never surfaced. Two properties the mapping must have:
an unrecognised provider code maps to a **generic retryable** state and pages — it is never silently
treated as terminal; and the customer copy distinguishes "try a different card" from "try again
later", because those ask the customer for different things.

## Q9 — Truth-sheet authorities and freshness windows · DECIDED (orchestrator-set, cheap to revise)

`GROUND.md` §2 established that no staleness signal exists today outside the operating calendar.
The smallest honest mechanism: each truth-source carries a machine-read stamp next to the data it
covers, and a maximum age. Past the age, the funnel declines to sell rather than quote.

| Truth source                                               | Stamp                                                                    | Max age          | Why this number                                                                                                        |
| ---------------------------------------------------------- | ------------------------------------------------------------------------ | ---------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Nationality eligibility list                               | `nationality_eligibility.py::RETRIEVED_ON` (exists, unread)              | **90 days**      | Changes on an amending Kepmenkumham with no notice; a quarter is the longest we could defend having not looked.        |
| Rule constants (D-7, D-14, eVOA window, passport validity) | new `RULES_VERIFIED_ON` in `constants.py`                                | **180 days**     | These move on regulation, not on administration — slower, and each is already individually dated in a docstring today. |
| Price catalogue                                            | `metadata.last_updated` in the prices JSON (exists, unread by this path) | **90 days**      | Bali Zero republishes prices on its own schedule; a stale price is the one staleness a customer feels directly.        |
| Operating calendar                                         | `COVERAGE_START` / `COVERAGE_END`                                        | already enforced | The only one that works today. Leave it exactly as it is; it is the pattern the other three copy.                      |

The stamp changes in the same commit as the re-verification — the convention
`nationality_eligibility.py` already states in prose, now with a reader behind it. Readers are
`build_verdict` (declines) and `price_for_case` (price unavailable), matching the calendar's
existing fail-closed path. One test per stamp pins the comparison.

**These four numbers are the orchestrator's, not the owner's** — they are engineering safety
margins, not commercial terms. If operations finds a window too tight in practice, changing it is a
one-line diff plus a test, not a re-decision.
