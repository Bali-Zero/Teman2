---
date: 2026-06-28
domain: operations
client_case: none
captured: 2026-06-30
sources:
  - scripts/hooks/organism_alert_sessionstart.sh
  - scripts/organism_stale_detector.py
  - ~/.organism/last_seen/ (122 sidecar files, live detector run 2026-06-30)
  - .claude/rules/cicatrix-superscar.md (family #2 "Esiste ≠ Armato")
---

# Heartbeat channel dead on core organs — the 28-day blindness (2026-06-28)

> **Why this file exists.** The SessionStart receptor
> (`scripts/hooks/organism_alert_sessionstart.sh:74`) cites this path in every
> alert it injects. Until 2026-06-30 the file **did not exist** — so the
> organism's own boot-time alert was emitting a *phantom citation* (cicatrix
> #6, anti-hallucination). This document closes that phantom by making the
> cited artifact real. Captured 2026-06-30; the event it documents is 2026-06-28.

## What happened

For ~28 days, multiple core organs ran **green in launchd** (`LastExitStatus=0`,
`KeepAlive` active) while their **heartbeat sidecar in `~/.organism/last_seen/`
was frozen**. No Claude Code session ever saw it, because **no hook read any
alert channel**. CLAUDE.md §14 instructed the brain to "check escalations at
session start" — but a prose instruction is not a receptor. The heartbeats
froze in silence.

This is cicatrix superscar **#2 — Esiste ≠ Armato** at *organism* scale: the
process exists and exits 0, but the work it is supposed to do is dead, and the
success signal (`status=ok`, exit 0) is **decoupled** from the actual work.

## Live detector snapshot (run 2026-06-30 against 122 sidecar files)

**Not breathing (2):**

- `cell.observatory` — stale 27.3d, `status=fail`
- `pro.federation_alert_dispatcher` — stale 20.3d, **`status=ok`** ← the green
  that lies: the heartbeat writer is dead, but the last status it managed to
  write still says `ok`. Reading `status` alone would report this organ healthy.

**Breathing but unhealthy (7):**

- `cell.organism` (degraded)
- `cell.skills_bridge_consumer_launchd` (failed)
- `pro.eventbus_meta_dispatcher` (failed)
- `pro.eventbus_observatory` (failed)
- `pro.fly_restart_loop_detector` (degraded)
- `pro.l5_2_phase2b_trigger` (failed)
- `wr2.canva_token_watchdog_launchd` (failed)

## Why "restart" is NOT the cure

These are not simply crashed processes a `launchctl kickstart` would revive.
The disease has two layers, neither cured by a restart:

1. **Observability.** Nothing inside a session read the heartbeat. Restarting an
   organ clears one symptom but restores the blindness the moment the next
   heartbeat freezes. The structural cure is the **receptor**, not the restart.
2. **Decoupled success signal.** `status=ok` while stale-20d means the field the
   monitors trust is not derived from the work. Restarting refreshes the field
   without re-coupling it to reality — the next freeze lies again.

(W2 "restart-the-organ" auto-remediation was deliberately *disarmed* for exactly
this reason: blind restart of a green-but-dead organ is theatre.)

## The structural cure (shipped 2026-06-28)

`scripts/hooks/organism_alert_sessionstart.sh` — a **SessionStart receptor**.
On every session start it runs `scripts/organism_stale_detector.py` against
`~/.organism/last_seen/` and, if any organ has stopped breathing, injects a
snapshot alert into the session context as
`hookSpecificOutput.additionalContext`. The alert reaches **the brain-session**,
not a human on Telegram who won't look.

Design constraints that keep the receptor from *becoming* the blindness:

- **FAST** — hard 4s budget, never blocks session start.
- **FAIL-OPEN** — any error ⇒ no alert, exit 0 (a broken receptor degrades to
  the pre-existing silence, never worse).
- **SNAPSHOT** — shows only currently-open alerts; cured organs vanish, so there
  is no stale-alert graveyard (the failure that killed `claude_tasks/`).
- **PATH-AWARE** — works on M5 (`balizero`) and Pro/Mini (`nuzantara`).

`organism_stale_detector.py`: `DEFAULT_STALE_DAYS=7`;
`UNHEALTHY_STATUSES={failed,fail,degraded,error}`; "stale dominates" (a frozen
organ is reported once as stale, not also as unhealthy); benign allow-list for
known false-positives.

## The general law (this is the doctrine, not the incident)

> **A success signal that is not derived, end-to-end, from the work is a lie
> waiting for the work to die.** Read the *output / heartbeat*, never the exit
> code or the `status` field. And a rule that lives only in prose
> (CLAUDE.md §14) is not enforced — **if a critical rule is violable, it must be
> a hook, not a sentence** (CLAUDE.md §7).

## Still uncured (as of 2026-06-30)

- **The escalations board has the same blindness, uncured.** The organ-heartbeat
  got a receptor; `shared/escalations_pro.jsonl` + `~/.agent/decisions/claude_tasks/`
  are still read only by the manual `/escalations` command, not by any
  SessionStart hook. Same class, fix tracked in the
  `2026-06-30-claude-code-perfect-session-doctrine.md` cure set.
- **The 9 dead organs themselves** need their heartbeat *writer/bridge*
  investigated (operator-side; restart is not the cure — see above).
