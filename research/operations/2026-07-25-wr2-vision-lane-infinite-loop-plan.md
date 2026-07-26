---
date: 2026-07-25
domain: compliance
client_case: none (internal infrastructure)
sources:
  - production logs, Pro host — ~/logs/wr2-html-apply.log (2026-06-11 → 2026-07-25), ~/logs/wr2_supervisor.log
  - scripts/wr2_html_renderer/claude_vision.py, scripts/wr2_html_render_apply.py, scripts/wr2_supervisor.py
  - apps/backend-rag/backend/services/canva_renderer_v2/_pg.py (kill switch)
  - 3-seat LLM panel 2026-07-25 — Codex gpt-5.6-sol (xhigh) · Kimi K3 · Gemini 3.1 Pro (agy)
adversarial_review: glm
---

# WR2 vision lane: an infinite loop with a bounded cause — findings and plan

## 0. TL;DR

A temporary, external event — two OAuth seats hit their weekly quota on 2026-07-24 — was converted
into an **unbounded** failure by three independent code defects. The lane is not chronically broken:
it was idle, took one draft, and has burned ever since. **368 cascade failures, 201 supervisor kick
cycles, ~2 days.**

The keystone is not the quota, the timeout, or the missing cooldown. It is this: **a "transient"
verdict that is infinitely forgiving turns "retry later" into "retry forever".**

## 1. The causal chain (every link re-verified on disk 2026-07-25)

| # | Link | Evidence |
|---|---|---|
| 1 | Two seats hit the weekly quota | `claude -p` → exit 1, `You've hit your weekly limit · resets 9am (Asia/Makassar)`; measured independently on M5, so fleet-wide, not host-local |
| 2 | A cascade produces a **mixed** outcome: 2 seats quota-limited (~11s each), 3 seats time out (~53s each) | `wr2-html-apply.log`, representative cascade 22:52:28 → 22:55:19 |
| 3 | The mixed outcome is **conflated** into a pure rate-limit | `claude_vision.py:450` — `if saw_rate_limit: raise VisionRateLimited` takes precedence over `if saw_timeout` |
| 4 | The caller treats that as transient and **burns no attempt** | `wr2_html_render_apply.py:1413` — `"vision transient (%s) — no attempt burned"`, status reset to `drafts_imaged_checked` |
| 5 | The attempt counter never advances → the draft never reaches a terminal state | by construction of (4) |
| 6 | The supervisor's reconcile sees it stalled and re-kicks | `wr2_supervisor.py` — no `max_kick`/`give_up`/backoff on that path (the only backoff, l.638-725, is for asyncpg reconnect) |
| 7 | → 201 cycles, 368 cascades, ~2 days | `wr2_supervisor.log`, `wr2-html-apply.log` |

**The irony worth preserving.** Three lines below (4), the generic `except Exception` handler explains
that it *does* burn the attempt precisely "so a poisoned draft can never loop forever holding
'rendering'". This exact failure mode was anticipated. The vision-transient branch above it is the
hole left open.

## 2. Two corrections made during this research — both to my own claims

**(a) "The lane is 100% dead / chronically broken" — WRONG framing.** The log covers six weeks; all
368 failures fall in the last 36 hours. On 2026-07-23 the lane logged `no pending drafts`. It was
**idle, then poisoned** — the code defects are amplifiers, not causes. This changes the priority
order: the cure is bounding the amplifier, not resurrecting a dead component.

**(b) "937 successful vision calls" — a FALSE measurement I produced myself.** The grep pattern
included a bare `ok` alternative, and `ok` is a substring of **`token`**, so it matched the failure
lines `vision token_1 rate-limited`. Superscar #3 (over-match on a substring) committed by the
measuring instrument. Re-measured with `grep -F`: `brand_ok` = 0, `vision verdict` = 0.
**Lesson: a measurement pattern is a guard, and deserves the same innocence test as one.**

## 3. Where the three seats converged

- **The supervisor give-up outranks the vision fix.** It stops 100% of the cyclic burn regardless of
  vision health; fixing vision while every seat is exhausted stops nothing.
- **The per-seat cooldown is NOT the cure for the timeouts.** Arithmetic: the two exhausted seats fail
  fast (~11s), so skipping them frees ~22s spread over 4 seats ≈ 5s each. A cooldown cuts **waste**
  and must never be sold as fixing the timeouts. All three seats confirmed this independently.
- **Cooldown persisted PER HOST, not fleet-wide.** Each host re-learns a dead seat in ~22s; a shared
  file across three macs buys 22s and costs staleness, lock contention and scope creep.
- **Do NOT big-bang the 9 copies.** They span 5 apps with different dep trees and lifecycles, and are
  already diverged (`seat_refs` 1..13, `writes_state` 0..12). Consolidate the *policy* + contract
  tests first, then migrate one PR at a time — `dlq_autopilot.py` second, since it already has
  cooldown prior art (a persisted 4h per-job escalation window shared with the sentinel alerter).
- **The timeout number is not derivable from what we have.** 53s is what each seat was *allotted*
  before timing out, not how long a successful call takes. There are no successes to measure.

## 4. Where I dissent from the panel

**Codex ranks "flip `wr2_html_renderer_enabled` OFF" as P0. I do not.**

The kill switch is real (`system_settings.wr2_html_renderer_enabled`, fail-closed, verified at
`_pg.py:396`). But:

- the seats are **already** exhausted, so the cascade consumes no additional quota — it burns CPU and
  log volume, not budget;
- the lane **self-heals** when the weekly quota resets. Turning it OFF converts an auto-recovering
  outage into one that **requires a human to turn it back on** — precisely the state this codebase
  forgets in the `false` position for months (superscar #2, "built ≠ armed").

Keep it as the break-glass lever if the burn ever becomes costly; do not spend it on a bounded CPU cost.

**Codex's better-than-Kimi call, adopted:** the circuit breaker belongs at the **stage** level, not
per-draft. The unavailability is a property of the *dependency*, so N drafts must not produce N×K
probes. A per-draft `kick_count` would still let 10 drafts burn 5 kicks each.

**Kimi's better-than-Codex call, adopted:** whatever the give-up does, the parked state must be a
**first-class, queryable status** — *"a draft that stays in rendering forever is indistinguishable
from work-in-progress; that is silent dropping by another name."*

## 5. The plan — sequenced, falsifiable, each step independently revertible

| # | Step | Falsifiable proof | Failure mode it introduces |
|---|---|---|---|
| **P0** | **Cap the transient forgiveness.** A transient verdict may reset a draft without burning an attempt at most N consecutive times (N≈3); beyond that it burns one. Smallest possible diff, one file. | The 201-cycle draft reaches a parked state within N reconcile windows; cascades per draft ≤ N | A genuinely transient outage longer than N cycles now marks a draft failed — acceptable because the parked state is resumable, not discarded |
| **P0b** | **Stop conflating mixed outcomes** (`claude_vision.py:450`): return a structured `CascadeExhausted(outcomes=[...])` instead of letting one quota seat mask three timeouts. | An artificial cascade of 1 quota + 3 timeouts no longer raises `VisionRateLimited` | Callers matching on `VisionRateLimited` must be swept — grep before merge |
| **P1** | **Stage-level circuit breaker** in the supervisor: `closed → open(+30m) → half_open(one draft) → open(+2h) → manual_open`; state in `system_settings`, one alert, parked drafts stay queryable. | After 3 failed cascades: zero HTML kicks for 24h, and **zero drafts deleted or marked defective** | One pathological image can look like a global outage — the alert must carry the draft id so it stays diagnosable |
| **P2** | **Measure before choosing the timeout.** Run one real vision call on a healthy seat with a 300s ceiling and record the duration. *Only then* replace `remaining/(len(chain)-position)` with a fixed per-attempt timeout + global cap. | ≥3 successful calls with a recorded p95; healthy seats always receive the full per-attempt budget | A fixed timeout converts "slow but would have succeeded" into failure — derive from measured p95 × 1.25, capped |
| **P2b** | **Per-host persisted seat cooldown** — quota 4h / auth 15m / **timeout never** — keyed on a token fingerprint, atomic tmp+rename, fail-open. | An exhausted seat is probed at most once per TTL **across processes** (html-apply is a short-lived LaunchAgent, so a process-local memo is useless here) | A repaired credential can stay skipped until the TTL expires |
| **P3** | Consolidate the 9 copies: contract tests first, then a stdlib-only shared package, one consumer per PR. | Each consumer passes the shared contract tests before migrating | A bug in the shared module has a 9-lane blast radius — which is why it is last |

**Open question that gates P2**: are `token_4`/`token_5`/keychain healthy-but-starved, or also
rate-limited-but-slow? Measured so far: they answer `PONG` to `claude -p` from M5, so they are alive
**for text**. Whether vision carries its own limit is **not measured**. Codex is right that their
health is *unknown*, not *good* — P2 must not be built on the assumption that they are fine.

## 6. Traps — plausible-sounding fixes that make this worse

1. **Adding more seats** — the split budget means redundancy eats itself; more seats = more timeouts.
2. **Raising `WR2_VISION_TIMEOUT_S`** — same division, slower failure, same zero successes.
3. **Selling the cooldown as the timeout fix** — refuted by arithmetic (~5s/seat).
4. **Burning `html_render_attempts` for a quota/timeout outage** — turns an infrastructure outage into
   a permanent defect of the draft.
5. **Persisting a cooldown because a seat timed out** — a timeout is not evidence of exhaustion.
6. **Conflating a transient 429 with a durable weekly limit.** Not hypothetical: the first version of
   the backend-rag cooldown (this session) put both in one `quota` class, so a 429 that clears in
   seconds earned the same 15-minute bench as an exhaustion lasting days. Caught by a cross-family
   review and split into a separate `rate_limit` class, deliberately excluded from `_COOLDOWN_CLASSES`.
   **It is the same transient-vs-durable conflation as §1 link 3** — the theme of this whole lane.
7. **Treating `keychain` as an independent seat** without checking whether it duplicates a numbered
   token (the chain dedups by token value; keychain has no token to compare).
8. **A shared JSON across the three macs** — staleness + lock contention to save 22s of re-learning.
9. **Trying all seats in parallel** — multiplies quota consumption and load.
10. **Auto-discarding stuck drafts, or a breaker that parks the lane silently** — the worse failure:
    silent work loss.
11. **Copying the patch into all 9 implementations before the contract tests exist.**

## 7. What was NOT done in this pass

No production state was changed and no lane code was modified. The kill switch was **not** flipped
(§4). The two drafts remain in their loop; the cost is bounded (CPU + log volume, no additional quota)
and will self-clear when the weekly quota resets. Every step in §5 needs its own worktree, tests and PR.

## Adversarial review

**Seat:** GLM (`claude-glm`), probed for liveness first (replied `PONG` in ~20s) before dispatch.
Framed as an independent correctness review, not adversarial rhetoric — pointed at this file's path in
its own worktree, not pasted content. Reviewer is not this document's author (generator≠grader). Every
finding below was re-checked against the actual file text before being accepted or dismissed (a refuter
can hallucinate too — cicatrix-superscar #6/W65).

**Overall verdict:** clean bill of health with one residual worth stating and one flagged concern that
does not hold up on re-check.

**Survived (1):**

- **§5 P0b's falsifiable-proof column doesn't gate the caller sweep.** The row's stated proof is only
  "an artificial cascade of 1 quota + 3 timeouts no longer raises `VisionRateLimited`" — the caveat
  "callers matching on `VisionRateLimited` must be swept — grep before merge" lives in the *failure-mode*
  column, not as a required, falsifiable condition. The awareness is present; it just isn't wired into
  the gate that would catch a missed caller. Same shape as W99 (check≠action) and the "the FIX needs
  checking too, not just the author's assurance" pattern
  ([[lesson_a_bound_is_worthless_when_the_bounded_party_controls_it_2026_07_26]]). Not a reason to block
  P0b — a reason to add the sweep as an explicit proof condition when that step is implemented.

**Dismissed on re-check (1):**

- GLM flagged "P2's measurement precondition isn't explicit, creating a circular dependency between
  timeout-tuning and unknown seat health," citing this as an §6 gap. On re-read: the document already
  states this exact concern verbatim, in §5 (not §6) — *"Open question that gates P2: are
  `token_4`/`token_5`/keychain healthy-but-starved, or also rate-limited-but-slow? ... P2 must not be
  built on the assumption that they are fine."* The precondition is already explicit and already gates
  the step; GLM's citation was misplaced and the underlying concern was already handled by the plan as
  written.

**Noted, non-blocking (1):**

- The plan doesn't explicitly rule out kick paths other than the supervisor's reconcile loop (manual
  intervention, other supervisors/admin actions) that could bypass the §5 P1 circuit breaker. Speculative
  — the reviewer has no codebase access beyond this document — but worth a check when P1 is implemented,
  since a bypassable breaker would silently reproduce the exact failure mode this plan exists to close.

No changes were made to the plan's substance (§0-§7) as part of this review — only this section and the
`adversarial_review` frontmatter key were added.
