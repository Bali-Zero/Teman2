---
date: 2026-08-14
domain: operations
client_case: none
sources:
  - "live probe 2026-08-14: gpt-5.3-codex-spark PONG on M5 (codex exec -m gpt-5.3-codex-spark -c model_reasoning_effort=medium --sandbox read-only --skip-git-repo-check); on Pro only via CODEX_HOME=$HOME/.codex-acct2 (Pro's primary ~/.codex is 401)"
  - "scripts/jules_dispatch.py + docs/runbooks/jules-dispatch.md (armed 2026-07-06, dormant since — zero automation calls it)"
  - "cicatrix-superscar.md families #1 HOME-fork, #2 Esiste≠Armato, #5 Sibling-race, #7 KeepAlive misconfig"
  - "W81 firebreak: 2026-06 codex-spark-loop ecosystem disabled after runaway-alarm + 13 PR-spam"
---

# Armata H24 — Fase 1: standing lanes on idle flat-sub capacity

## Rationale

Two paid capabilities sit idle today, measured 2026-08-14:

1. **`gpt-5.3-codex-spark`** — a Codex model with its own **weekly bucket, separate
   from the primary Codex quota**. PONG-verified live on M5 (Pro needs the
   secondary `CODEX_HOME=$HOME/.codex-acct2` account since Pro's primary
   `~/.codex` seat is 401). Historically 100% idle — nothing in this repo has
   ever dispatched to it.
2. **Jules** (Google's async cloud implementer) — armed since 2026-07-06
   (`scripts/jules_dispatch.py`, Keychain key `jules-api-key` on M5), first
   session ran the same day, and then **dormant**: zero automation has called
   it since. Quota is ~300 sessions/day; the real constraint was never
   dispatch volume, it was verification bandwidth on the receiving end.

Both are flat-subscription capacity Bali Zero already pays for. Phase 1 turns
each into a standing, capped, read-only (Spark) / dispatch-then-harvest
(Jules) lane that produces artifacts an interactive session can act on —
without ever landing anything itself.

## Constraints carried forward from cicatrix-superscar.md (non-negotiable)

- **#1 HOME-fork**: every script here is invoked by its repo-canonical path
  directly (no `~/scripts/` copy). Where a plist needs a live path it points
  straight at `/Users/nuzantara/nuzantara/...`.
- **#2 Esiste≠Armato**: every tick writes a heartbeat sidecar
  (`~/.organism/last_seen/army.<lane>.json`) regardless of outcome, and a
  wrapper-level crash still surfaces via `cron-runner.sh`'s own P0 (it wraps
  both lanes' entrypoints).
- **#5 Sibling-race**: neither lane writes to the repo. Spark reads the
  queue and its main checkout read-only (`--sandbox read-only`); Jules reads
  its own queue and appends to `shared/escalations_pro.jsonl` (an
  append-only, multi-writer-safe log already used by other automation, see
  its existing `_writer` field convention) — never a `git` mutation.
- **#7 KeepAlive**: both plists use `StartInterval`, `KeepAlive=false`.
- **No auto-PR, no self-grading**: neither lane opens a PR, commits, or
  merges. Spark's output is a report file; Jules's output is a patch the
  lane can only point at (`inbox/<session-id>/`) — landing is always an
  interactive session's job (CLAUDE.md §2, and the existing Jules contract
  "Jules generates; Fable grades").
- **Quota-aware, capped, kill-switched**: see the per-lane sections below.
  Neither lane retries in a tight loop on quota exhaustion — it backs off
  and reports `status=quota`/`status=blocked`, once, per condition.

## What this deliberately does NOT repeat

The 2026-06 "codex-spark-loop" ecosystem (`~/scripts/codex/` on Pro) died of
runaway-alarm plus 13 PR-spam and was firebroken (W81,
`.disabled-W81-*` plists). The differences here are structural, not just
"be more careful":

- read-only sandbox for Spark (the old loop wrote and opened PRs)
- repo-canonical invocation (the old loop was a HOME-fork from day one)
- a hard daily cap + backoff state file (the old loop had neither)
- `cron-runner.sh` wrapping for fail-visible receipts, `tg_notify.py` as the
  single alert gateway with tiered dedup keys (the old loop alarmed raw and
  often)

## Lane 1 — Spark (read-only analysis)

`scripts/army/spark_lane.sh`, ticks every 2h on Pro (`StartInterval 7200`).
Each tick either dispatches the oldest not-yet-done task from
`infra/army/spark-queue/*.md` (one task per tick, `--sandbox read-only`,
900s cap, max 6 dispatches/day) or is a fast no-op. A daily digest fires
once, at the first tick at/after 07:00 local, summarizing what ran the day
before. Full contract in `scripts/army/spark_lane.sh`'s own header comment
and `infra/army/spark-queue/README.md`.

## Lane 2 — Jules (dispatch + harvest)

`scripts/army/jules_lane.py`, two modes on one cron cadence family:
`--dispatch` (09:00 WITA, up to 3 tasks/day from
`infra/army/jules-queue/*.md`) and `--harvest` (every 3h, polls open
sessions; on completion, downloads the patch to
`~/army/jules/inbox/<session-id>/` and appends ONE `NORMAL`-priority row to
`shared/escalations_pro.jsonl` so an interactive session picks it up for
independent verification — never a merge). Runs where the Keychain key is
present; fails visible (`status=blocked`) elsewhere rather than copying the
key. Full contract in `scripts/army/jules_lane.py`'s own module docstring
and `infra/army/jules-queue/README.md`.

## Proof-of-armed (per lane)

A lane counts as *armed*, not merely *built*, only when all four hold:

| # | Check | Spark | Jules |
|---|---|---|---|
| 1 | plist loaded (`launchctl print gui/$(id -u)/com.nuzantara.army-<lane>`) | required | required |
| 2 | a REAL tick ran (heartbeat sidecar `~/.organism/last_seen/army.<lane>*.json` age < 2× the tick interval) | required | required |
| 3 | the tick did real work at least once (a report under `~/army/spark/reports/` OR a session id in `~/army/jules/state/sessions.jsonl`) — not just "0 pending, skip" every time | required | required |
| 4 | the kill switch actually kills it (`ARMY_SPARK_ENABLED=false` / `ARMY_JULES_ENABLED=false` → next tick heartbeat `status=disabled`) | required | required |

Until an interactive session verifies all four on the target machine and
records it here (or in the PENDING-ARMS ledger), this lane is
**built-but-not-armed** per cicatrix superscar #2 — "esiste ≠ armato".
Neither plist ships with `RunAtLoad=true` for exactly this reason: install
is a deliberate, checked act, not an accident of `git pull`.

## Phase 2 (not this PR — after ~1 week of Phase 1 running clean)

- **Gemini corpus-sweep lane**: `agy` (Gemini 3.1 Pro, free OAuth, 1M
  context) standing lane for whole-corpus read-only sweeps too wide for a
  single interactive session's context — natural fit for the KBLI
  1,559-code re-validation backlog (`kbli-navigator` corner) once Phase 1's
  operational pattern (queue → capped dispatch → report → interactive
  landing) is proven stable.
- **Kimi overnight-review lane**: Kimi K3 (`kimi-code/k3`, Allegro flat
  subscription) as a standing refuter over open PRs overnight — same
  generator≠grader discipline the repo already uses for the 4-LLM panel,
  just scheduled instead of ad-hoc. PII boundary applies unchanged (Kimi is
  a Chinese cloud seat — aggregate/health/intel/KBLI only, never
  CRM/client rows, per CLAUDE.md §5's Kimi seat rules).

Both are deliberately deferred: Phase 1 is the first time this repo runs
*any* standing multi-task queue against a paid seat since the W81 firebreak,
and the design bet here is "prove the pattern narrow and capped before
widening it," not "land all four lanes at once."
