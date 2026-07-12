# modus autonomous loop — design spec

> **Status:** DESIGN approved (Zero: 4 core decisions + "vai in totale autonomia, procedi senza me", 2026-07-12).
> Built behind a default-OFF kill switch — nothing auto-runs until Zero flips `MODUS_AUTOLOOP_ENABLED=true`.
> **Date:** 2026-07-12 · **Author:** session (Opus 4.8) + adversarial input from Codex (GPT-5.5) & Gemini 3.1 Pro.

---

## 0. Why this exists (the trigger)

Two external LLMs (Codex, Gemini), run blind to each other with an explicitly adversarial mandate
("find where `modus` is BEHIND loop-engineering SOTA, not ahead"), **both ranked the same defect #1**:

> `modus` is **reactive**. It starts from a human mandate (`TRIAGE the mandate`). Steinberger's
> loop-engineering thesis (June 2026) is that the loop must **discover work autonomously**. Gemini,
> verbatim: _"because modus requires a human mandate, it is functionally a sophisticated CLI macro,
> not an autonomous agentic loop."_

This spec closes that gap **without** touching the invariant that governs the whole ecosystem: the
final gate stays Fable, never cascades; window dead → task SUSPENDS.

### What the review got wrong (grounded on disk, this turn)

- Not "18 cron" — there are **124 LaunchAgent** plists.
- The queue is **not missing**. `shared/escalations_pro.jsonl` exists (empty now) with a full
  apparatus already built: `scripts/sentinel_lib/escalations.py` (exposes `write_escalation()` +
  `_mirror_to_sqlite()` + `read_all_escalations()` + `mark_resolved()`), a SQLite schema at
  `~/.agent/decisions/escalations.sqlite` with `severity / status='pending' / machine /
dedup_key UNIQUE` (idempotent dedup — Codex's "state machine" ask is **already half-built**), and a
  SessionStart receptor hook `scripts/hooks/escalations_alert_sessionstart.sh` that already surfaces
  the board HIGH-first every session. **modus already CONSUMES this queue at TRIAGE.**

**Therefore the real gap is one missing wire, not a new engine:** the domain cron (regulatory-watcher,
wr2, intel) discover work but only emit Telegram/reports — they never call `write_escalation()`. And
nothing yet _auto-consumes_ pending queue items into a headless modus session. Two wires: producer→queue,
and queue→autonomous-consumer.

---

## 1. The four approved decisions

| #       | Decision                    | Choice                                                 | Meaning                                                                                                                                                                                                                                                                                                                                                                                   |
| ------- | --------------------------- | ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **B**   | Autonomy level              | **B (full loop)**                                      | Queue fills itself AND consumes itself. Morning = PRs already open, awaiting Zero's merge.                                                                                                                                                                                                                                                                                                |
| **2.1** | What may auto-execute       | **Green-class only**                                   | Only low-blast-radius, in-perimeter work auto-runs (probe-found broken test, regulatory delta capture, known-endpoint 500, lint/format). Anything touching migration / auth / billing / deploy / secret / business → deposited as **proposal (A-mode)**, waits for Zero. Line = modus Gear-3 "cure-while-diagnosing" + CLAUDE.md §2 operator carve-out. No new safety threshold invented. |
| **3.1** | Model routing + quota-death | **Opus director, Fable gate, quota-dead → `deferred`** | Loop sessions run **Opus** as director (Zero's 2026-07-12 "non voglio pagare"). At the final gate, if the Fable window is dead, the session **does not degrade** — it returns the task as `deferred`, surfacing next morning as "ready but awaiting gate". Never-cascade made persistent in the queue.                                                                                    |
| **3.3** | Consumption budget          | **Hard cap K/night**                                   | At most K green tasks per quota window, then stop. A bad night cannot burn the whole MAX window.                                                                                                                                                                                                                                                                                          |

---

## 2. Architecture — three units, well-bounded

### Unit 1 — Producer adapter (`cron → queue`)

Wrapper `scripts/modus_enqueue.py`: normalizes any cron's finding into the queue schema and classifies
green vs proposal, then calls the EXISTING `write_escalation()`. Pilot wires **one** cron. Task record
(additive to existing schema; `dedup_key` from `job` keeps re-runs idempotent):

```jsonc
{
  "job": "regulatory-delta-2026-07-12",
  "source": "regulatory-watcher",
  "severity": "normal",
  "class": "green" | "proposal",
  "perimeter": "research/regulatory/**",
  "mandate": "Capture the PP-28 delta into research/regulatory/...",
  "status": "pending"
}
```

### Unit 2 — Green-class gate (`is_green(task) -> bool`)

Pure deterministic predicate. Re-uses modus's existing disqualifiers (migration/auth/billing/deploy/
secret/business → NOT green). No LLM. Heaviest test coverage (scar #3: no guard without guilt+innocence
corpus). This is the load-bearing safety unit.

### Unit 3 — Autonomous consumer (`queue → headless modus session`)

LaunchAgent `com.balizero.modus.autoloop.nightly`, single-machine:

1. read `pending`+`class=green` (via `read_all_escalations`),
2. apply K cap (3.3),
3. per task: `agent_start.py` worktree → headless `claude` (Opus director) + modus skill + mandate,
4. success → PR `--auto --squash` (green-only, VERIFY passed in-session),
5. final-gate window dead → task `deferred`, no degrade (3.1),
6. mark `resolved`/`deferred`.
   Runs on ONE machine (`machine`-field guard; scar #10 split-brain).

### Data flow

```
domain cron → [U1 write_escalation] → queue (JSONL + SQLite mirror, dedup UNIQUE)
                                          │  SessionStart receptor (exists) → Zero sees board
                     [U3 nightly] reads pending+green, cap K
                          [U2 is_green] → green? → worktree → headless modus (Opus) → VERIFY → final gate
                                        │                                                        │
                                   proposal? → stays pending (Zero)            Fable dead? → deferred (no cascade)
                                                                               Fable alive? → PR --auto → Zero merges AM
```

---

## 3. Invariants it must never break

- **Never-cascade final gate (HARD):** dead Fable window → `deferred`, never the gate on a weaker model. Zero exceptions.
- **Scar #5 sibling-race:** every session in its own `agent_start.py` worktree; main untouched.
- **Scar #10 split-brain:** consumer on ONE machine; second host graceful-exits on `machine` guard.
- **Scar #2 esiste≠armato:** consumer health proved by queue state (pending→resolved), not launchd exit 0.
- **Scar #6 phantom:** cron findings re-checked by U2 perimeter + modus GROUND re-verifies on disk in-session.
- **L2 autonomy:** auto-armed PRs green-only + VERIFY-passed, so `--auto --squash` never merges unreviewed. Zero still merges.
- **Kill switch (DEFAULT OFF):** `MODUS_AUTOLOOP_ENABLED` defaults to `false`. Even merged, nothing auto-runs until Zero sets it true.

---

## 4. Testing

- **U2 `is_green`** (critical): guilt corpus (migration/auth/secret/deploy/business → rejected) + innocence corpus (test-fix/regulatory-capture/lint → pass). Scar #3.
- **U1**: re-run of same finding does NOT double-enqueue (dedup_key UNIQUE).
- **U3**: dry-run logs "would launch X" without spawning; K-cap respected; quota-dead → `deferred` not `resolved`; second-machine guard exits.
- **E2E pilot**: regulatory-watcher delta → green task → consumer worktree run → PR → resolved.

---

## 5. Scope (YAGNI)

**In (pilot):** U1 wrapper + wire regulatory-watcher only · U2 predicate + full corpus · U3 nightly consumer LaunchAgent (single-machine, K-cap, deferred-on-dead-gate) · all default-OFF.
**Out (later, separate specs):** wiring the other 123 cron (one-line each once proven) · splitting monolithic SKILL.md (finding #2) · full PENDING-ARMS SQLite state-machine (finding #3).

---

## 6. Two defaults (assumed on "vai", Zero to confirm-or-correct)

1. **Cadence + cap:** `03:00 WITA` + `K=5`/night.
2. **Pilot cron:** `regulatory-watcher`. Other 123 untouched until pilot proven live.

---

## 7. What we keep that Steinberger lacks (confirmed by both external LLMs, unprompted)

- never-cascade final gate (Codex), 10 scar families (Gemini). This design makes modus _proactive_ while
  keeping its _discipline_: green-class gate in front of execution, un-cascadable Fable gate at the end.
