# L7 control tower — what's built, what makes each alarm go RED

Owner: lane L7 (`products/garuda-voa/LANES.md`). Code lives in
`apps/backend-rag/backend/services/garuda_ops/`; tests in
`apps/backend-rag/backend/tests/services/garuda_ops/`.

## Why this looks like ports instead of a live dashboard

At the time this lane was first built, **L1 (retention/migrations), L3
(orders/payments) and L4 (portal) had not merged** into `feature/garuda-voa`
(LANES.md: L3 `blocked (owner decision 1)`; no `garuda_orders` /
`garuda_portal` package existed; no order/practice journal table migration
existed under `apps/backend-rag/backend/db/migrations_v2/` — the only
GARUDA table present was the unrelated legacy `garuda_voa_checks`, and L2's
own public router was explicitly "not wired into the running app"). There
was no live journal to read a funnel dashboard from.

**Corrected 2026-08-25 (staleness tripwire finding)**: that description is
now stale for L1/L3. L1's retention-policy migration (281) merged, and L3
merged as `#4893` — `garuda_orders/` (8 modules) and `payments/xendit.py`
both exist, and `garuda_orders_router.py` is mounted. Neither has actually
unblocked persistence or checkout, though: L1 seeds no GARUDA_CHECK policy
row (fail-closed by design until Zero signs one), and no production code
wires a real adapter onto `app.state.garuda_order_repository` /
`app.state.garuda_payment_provider` yet — every request still 503s. L4 is
`PARTIAL (#4871)` with no practice-serving module under `garuda_portal/`
yet.

Rather than fake a dashboard against data that doesn't exist, every module
in `garuda_ops/` is written against `ports.py` — `Protocol`s that mirror the
FROZEN contract (`contracts/events.yaml`, `journeys/STATE-MACHINE.md`,
`journeys/SLO.md`) field for field. Every alarm and the CRM handoff are
fully exercised today with fakes; wiring a concrete Postgres-backed adapter
once L1/L3/L4 land — and the orchestrator wires the result onto `app.state`
— is a pure implementation task with zero change to this package's public
functions. `test_blocked_stage_staleness.py` is the tripwire that keeps
this paragraph (and `synthetic_probe.py`'s own reasons) from drifting out
of sync with the codebase again.

## Each alarm, and what makes it RED

| Module                    | What it answers                            | What makes it RED                                                                                                                    | Bite-proof                                              |
| -------------------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| `deadman.py`               | Is the SYN-01 synthetic probe still alive?  | No success recorded within `max_silence` of the last success (or of monitoring start, for a probe that never succeeded) → `DEAD`, pages, and signals flag-off | `test_deadman.py` — pushes the last success 1s past the window, asserts DEAD+page+disable; restores it, asserts HEALTHY again |
| `invariants.py` BI-01      | Are paid orders happening at all?           | Zero qualifying (real, deduped, post-activation) `payment.paid` events in the rolling 24h → `PAGE`. Synthetic traffic never clears a real page. | `test_bi01_pages_when_zero_qualifying_orders...` / `test_bi01_synthetic_orders_never_count_toward_the_page_clear` |
| `invariants.py` BI-02      | Is upload→OCR feedback fast enough?         | Median (including unresolved uploads counted at their **current age**, never dropped) ≥ 60s → `PAGE`                                    | `test_bi02_pages_when_median_exceeds_60s` / `test_bi02_a_stuck_upload_cannot_be_hidden_by_many_fast_resolved_ones` |
| `sla_timer.py` (work-item) | Is staff sitting on a practice too long?    | Time in `Received`/`In_review`/`Blocked`/`Submitted` exceeds its threshold → `OVERDUE`                                                   | `test_blocked_practice_past_threshold_is_overdue`       |
| `sla_timer.py` (filing)    | Will a practice miss the D-7 deadline?      | ≤2 days remaining (or already passed) and the practice hasn't reached `Submitted`/`Approved`/`Delivered`/`Rejected` → pages              | `test_filing_deadline_pages_when_two_days_or_fewer_remain` |
| `crm_handoff.py`           | Did PR-01 create exactly one CRM practice?  | A duplicate `practice.received` delivery creates a SECOND practice (SM-G08 violation) — the test breaks this by delivering the same event twice and asserting only one write happened | `test_duplicate_pr01_delivery_never_creates_a_second_practice` |
| `funnel_dashboard.py`      | Is the funnel converting, or silently dead? | A zero denominator renders `unknown`, never `0%` — the WhatsApp-bot 24-day-silent-failure shape (a dead funnel and an empty-but-fine funnel must never look identical) | `test_zero_checks_started_renders_conversion_as_unknown_not_zero` |
| `synthetic_probe.py`       | Can a real purchase journey complete today? | Today, honestly, **no** — see below                                                                                                      | `test_full_probe_today_is_honestly_incomplete_not_falsely_green` |

## The synthetic probe (SYN-01) is honestly incomplete today

SLO.md's SYN-01 path is: *eligibility → local OCR feedback → sandbox
checkout → signed sandbox webhook → paid → one Received practice*, every 15
minutes, dead-man 15 minutes.

Only stage 1 (`EligibilityVerdictStage`, the pure verdict+price computation)
runs against real code today. Stages 2-5 are `_blocked_stage` placeholders
that report `BLOCKED` and name the real remaining blocker (L1's unsigned
GARUDA_CHECK retention policy; the orchestrator's not-yet-done composition
wiring for L3's checkout/webhook, corrected 2026-08-25 — L3's code itself
is merged; L4's missing portal practice module). `run_probe` stops at the
first non-`SUCCEEDED` stage — it does not attempt stages whose precondition
never held. Faking success here would be exactly the "esiste != armato"
failure this lane was warned against (`cicatrix-superscar.md` family #2): a
probe that always reports green would mask the fact that no purchase can
complete in production yet.

**Consequence, stated plainly**: wiring `evaluate_deadman()` to this probe's
result today would correctly report `DEAD` forever, because the full journey
genuinely cannot complete. That is not a bug in the alarm — the product is
"ship dark, flag off" (MANDATE.md §7) and has not shipped. The dead-man
switch becomes meaningful the moment L1/L3/L4/L5 land and each `_blocked_stage`
is replaced by a real implementation; `run_probe`/`evaluate_deadman` need no
change when that happens.

## Real, independent finding: the price catalogue is stale right now

Running `EligibilityVerdictStage` against the real `PricingService` (no
mocking) on 2026-08-25 raised `PriceUnresolvable` because
`price_catalogue_freshness` found the catalogue's `metadata.last_updated`
stamp **111 days old against a 90-day max** (SM-G05 fail-closed). This means
**any real customer hitting the public funnel today would get a 503
`PRICE_UNRESOLVABLE`**, independent of anything L1-L7 build. This is not
owned by any GARUDA VOA lane — it is whoever maintains the `PricingTool`
catalogue's `metadata.last_updated` stamp for `B1 Visa on Arrival (VOA)` /
`B1 Visa on Arrival Extension`. Flagged to the orchestrator; not fixed here
(out of L7's file ownership and out of scope for this PR).

## Cross-family refuter round (Kimi K3, 2026-08-25)

Kimi K3 reviewed a frozen extracted commit (per ASSEMBLY-LINE's "extract to a
throwaway worktree, never review a live ref" rule) against the actual
contract files in this repo, not just the diff. Verdict: FAIL, 7 findings.
All seven were real and are fixed in this PR:

1. **SM-G08 idempotency was check-then-act, racing under the contract's own
   at-least-once delivery model.** `ports.CrmWriter`'s docstring now states
   the concrete-adapter obligation explicitly (a DB `UNIQUE` constraint +
   `INSERT ... ON CONFLICT`), and `test_crm_handoff.py` carries a fake that
   reproduces the race deterministically (via a two-party barrier standing
   in for a real DB round-trip) plus one that closes it with a lock — proof
   that the fix is load-bearing, not merely documented.
2. **`ports.EventEnvelope` dropped `idempotency_identity`**, which
   `events.yaml` marks required and which STATE-MACHINE.md/`events.yaml`
   name as PR-01's actual retry-idempotency key ("the paid journal event
   ID" / "committed payment.paid journal event identity") — NOT the
   `practice.received` event's own `event_id`, which the first version of
   `crm_handoff.py` dedup'd on. Added the field + `IdempotencyIdentity`
   dataclass; `crm_handoff.py` now dedups on
   `event.idempotency_identity.key_digest`.
   `test_journal_level_retry_with_a_fresh_event_id_still_dedups` proves two
   *distinct* wire events sharing the same paid-event identity collapse to
   one CRM practice.
3. **The practice aggregate id was being passed to a lookup documented as
   order-keyed.** PR-01's `aggregate_type` is `practice`, and `events.yaml`
   carries no practice->order correlation field, so the old
   `OrderSnapshotProvider` contract ("order id in") could never be
   satisfied by what the caller actually has. `ports.py` now documents the
   parameter as the practice aggregate id and states explicitly that a
   concrete adapter resolves practice->order internally.
4. **M-05/SM-G03 log-field violation**: `crm_handoff.py` logged
   `practice_aggregate_id` (an order/practice identifier) and
   `crm_practice_id` (an account identifier) in `extra={...}` — both banned
   as log fields by SLO.md M-05 regardless of PII status. Removed; logs now
   carry only the idempotency key digest (an opaque SHA-256 the contract
   does not name as a banned identifier).
5. **BI-02 accepted negative durations** — a resolved sample whose OCR
   feedback timestamp precedes its upload timestamp, or an unresolved
   sample with a future `upload_committed_at` (both possible under M-01's
   multi-writer clock model), silently lowered the median: the exact
   fail-open direction M-03's censoring rule exists to prevent.
   `median_upload_to_ocr` now raises `ValueError` on either, matching the
   convention `deadman.py`/`sla_timer.py` already used for future
   timestamps.
6. **BI-01/funnel dedup was per-event, not per-order** — M-02's stated unit
   is "one logical order", but the code only guarded against a retried
   *event_id*, not two distinct `payment.paid` event ids for the same order
   (the same fault class as finding 2). Both `invariants.paid_orders_24h`
   and `funnel_dashboard.build_funnel_snapshot` now dedup by event_id THEN
   by order `aggregate_id`.
7. **`filing_deadline=None` silently never paged**, conflating "no deadline
   applies" (a cleared state) with "deadline unknown" (a data gap upstream,
   e.g. L5's calendar pipeline failing to populate it) on an *active*
   practice. `time_to_filing_deadline` now pages (`WARNING`) when the
   deadline is missing on a practice that hasn't reached
   `Submitted`/`Approved`/`Delivered`/`Rejected` — per M-06's doctrine that
   unknown is never healthy.

Also fixed, a residual gap Kimi flagged as sound-but-fragile: `run_probe`
previously let any exception other than `StageBlockedOnDependency` escape
uncaught, leaving no bound `ProbeRunResult` for a real stage crash. It now
converts any exception into a `FAILED` result, so SYN-01's "one signed
result binds ALL stage outcomes" holds even when a stage genuinely crashes.

Noted but not changed (lower severity, judgment calls rather than defects):
BI-01's activation check reads "currently enabled" rather than literally
"remained enabled" since launch (a funnel toggled off/on within the
window could false-page); `funnel_dashboard`'s `checks_started`/
`checks_declined` denominators are caller-supplied ints with no window
binding the function can verify against the windowed numerator. Both are
documented in the modules' docstrings for whoever wires a concrete
scheduler.

## Not built in this PR — sequencing problems, not files to edit

- **Wiring the dead-man cron and the paged alerts to a real scheduler.**
  `.github/workflows/**` is explicitly "shared and forbidden to lanes"
  (`LANES.md`); L2's own router is deliberately left unregistered for the
  same reason ("mounting this router ... is the orchestrator's sequencing
  step, not this lane's"). The evaluators (`deadman.py`, `invariants.py`)
  are ready to be invoked by whatever scheduler the orchestrator chooses at
  landing time.
- **A concrete Postgres `JournalReader`/`OrderSnapshotProvider`/`CrmWriter`.**
  Corrected 2026-08-25: L1's migrations and L3's order schema now exist on
  this branch (migration 281, `garuda_orders/`) — what's still missing is
  the concrete adapter implementation and the orchestrator wiring it onto
  the running app. The `Protocol`s in `ports.py` are the frozen interface a
  future adapter implements.
- **Seeding `practice_types.code = 'garuda_voa'`.** `migrations_v2/` is L1's
  exclusive path (`LANES.md` file-ownership table); `crm_handoff.py` names
  the expected code as a constant and fails closed via
  `HandoffOutcome.ORDER_SNAPSHOT_MISSING`-style errors rather than guessing.
