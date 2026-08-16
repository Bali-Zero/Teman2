---
date: 2026-08-14
domain: operations
client_case: none
sources:
  - "live probe 2026-08-14: gpt-5.3-codex-spark PONG on M5 (codex exec -m gpt-5.3-codex-spark -c model_reasoning_effort=medium --sandbox read-only --skip-git-repo-check); on Pro only via CODEX_HOME=$HOME/.codex-acct2 (Pro's primary ~/.codex is 401)"
  - "scripts/jules_dispatch.py + docs/runbooks/jules-dispatch.md (armed 2026-07-06, dormant since — zero automation calls it)"
  - "cicatrix-superscar.md families #1 HOME-fork, #2 Esiste≠Armato, #5 Sibling-race, #7 KeepAlive misconfig"
  - "W81 firebreak: 2026-06 codex-spark-loop ecosystem disabled after runaway-alarm + 13 PR-spam"
adversarial_review: kimi-k3
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

## Amendment log — 2026-08-14 (cross-family Kimi K3 refutation, 12 items)

A cross-family refutation of this design (Kimi K3, generator≠grader per
CLAUDE.md §6) closed 12 numbered defects the same day, before either lane
was armed anywhere. Both lanes' second commit implements all 12; nothing
here shipped un-amended.

**Spark (6 items):**

1. **Atomic lock, not a pidfile write.** The single-instance guard is now a
   `mkdir`-claimed lock directory (`$STATE_DIR/run.lock/`) with a pid file
   inside, checked and reclaimed if stale. A plain pidfile write is not
   atomic against a real race, and launchd does not guarantee serialization
   against a manual run of the same script. A live-lock tick now reports
   its own distinct status (`skipped-overlap`) rather than the generic `ok`
   it shared with "queue empty" before.
2. **Content-only dedup, corruption-fatal state.** The dedup key is now
   sha256 of task **content**, not `filename:sha` — a rename/move no longer
   creates a phantom duplicate entry. The done-list is now an append-only
   JSONL of every *attempt* (`attempts.jsonl`, one line per try, not just
   successes) instead of a flat "done" list. A line that fails to parse
   HALTS the lane (`status=state-corrupt`, P0) rather than falling open
   into re-processing the whole queue — the family #2/#9 failure mode this
   repo has hit repeatedly (W88, W104: a corrupt or misread state file read
   as "nothing recorded" is worse than no state at all).
3. **Retry count + head-of-line protection.** Task selection now prefers
   never-attempted tasks over once-failed retries, and a task quarantines
   itself after 2 recorded failures — a single poisoned task can neither
   block the head of the queue behind it forever nor be retried
   unboundedly.
4. **Fixed 12h backoff, plus a format-change tripwire.** Backoff on a
   detected quota marker is now a flat 12h (never exponential-unbounded).
   New: 3 *consecutive* non-quota failures (across distinct tasks, so a
   single quarantined task can't trigger it alone) also fire the same 12h
   backoff — protection against codex's output format changing underneath
   the quota-marker regex, where every failure would otherwise misclassify
   silently.
5. **Reproducibility header.** Every report now opens with the checkout
   HEAD sha (at run time) and the task's own content sha256, not just the
   task's queue filename.
6. **Explicit WITA clock.** Every "today"/"cap"/"digest hour" computation
   goes through `TZ=Asia/Makassar date …` (fixed UTC+8, no DST — no
   zoneinfo/tzdata dependency) instead of ambient system/launchd TZ, which
   is not guaranteed to be WITA in every cron environment.

**Jules (4 items):**

7. **72h session TTL.** A session still PENDING after
   `ARMY_JULES_SESSION_TTL_HOURS` (default 72) is marked `stale`, fires
   exactly ONE escalation of its own ("investigate or cancel", not "verify
   this patch" — there is none), and is never polled again.
8. **Escalation dedup grep.** Before writing an escalation, both the
   completed-session and stale-session paths now grep
   `shared/escalations_pro.jsonl` for the same job key first. The primary
   guard is still in-process (a closed session is never re-polled); this is
   the safety net for the crash-consistency gap where an escalation write
   succeeded but the session-state save that would have prevented a repeat
   did not land.
9. **Inbox backpressure.** Dispatch refuses to send new tasks while
   `ARMY_JULES_INBOX_BACKPRESSURE` (default 6) or more harvested patches
   are still awaiting verification (`outcome` unset) — the bottleneck was
   always verification bandwidth, not dispatch volume (see Rationale
   above), so dispatch now adapts to it instead of piling on top of it. The
   count is reported in the daily digest.
10. **Base-commit recording + blocked-streak alarm.** Every dispatch tick
    resolves `origin/main`'s HEAD once and records it on each session, so a
    later verification session can `git apply --check` against the commit
    Jules actually started from. Two or more *consecutive* ticks blocked on
    a missing Keychain credential now get a distinct digest line
    (`army-jules:blocked-streak`) — a forgotten-credential machine should
    not silently read as "not applicable" forever.

**Both lanes (2 items):**

11. **Wired into the repo's existing organism staleness detector, without
    a new registry.** Before wiring this in, both `infra/fleet-watch/`
    (unrelated — a separate Pro/Mini reachability watch, `peers.json`) and
    `scripts/organism_stale_detector.py` were read in full. Findings that
    shaped the implementation: the detector auto-discovers every
    `*.json` file under `~/.organism/last_seen/` (`scan_sidecars()`) — no
    pre-registration allow-list exists for staleness detection itself, so
    `army.spark_lane`/`army.jules_lane` need no registry edit anywhere to
    be picked up. The one other registry in the repo,
    `apps/organism/organism/organs_registry.yaml`, is consumed by
    `sentinel-aggregate.py`/`healer_receptor_registry.py` for *recovery-action*
    automation, not by the stale detector — left unregistered here
    deliberately (Phase 2 candidate if automated recovery wiring is
    wanted). Also confirmed the literal word `killed` is in
    `scripts/lib/heartbeat.sh`'s recognized-status vocabulary and maps to
    `"error"` — so neither lane ever passes that word to `organism_heartbeat()`
    for an intentional kill-switch-off tick; each lane keeps its own
    richer status vocabulary (`killed`/`skipped-overlap`/`state-corrupt`/…)
    separate from the narrower heartbeat-safe one (`ok`/`degraded`/`error`/`disabled`)
    it maps down to. Every tick that completes with heartbeat status `ok`
    additionally stamps `last_success_epoch` into the SAME sidecar file —
    additive, not a second artifact, so an existing or future consumer that
    only reads `ts`/`status` is unaffected.
12. **`outcome` field + weekly produced/consumed digest line.** Both
    lanes' completed-work records (`attempts.jsonl` for Spark,
    `sessions.jsonl` for Jules) carry an `outcome` field
    (`applied`/`rejected`/`read`/`null`) a verification session updates
    later — append-only state, so an update is a new line, not an in-place
    edit; readers fold to the latest entry per key. On Mondays (WITA) the
    existing daily digest gains one extra line reporting the
    produced-vs-verified ratio, rather than standing up a second schedule
    for it.

## Adversarial review

Reviewer: Kimi K3 (`kimi -m kimi-code/k3`), cross-family per CLAUDE.md §6
(generator≠grader). Transcript: `kimi-refute-army.txt`
(session `session_faa8c7d2-4490-4a7e-a535-c39e7bc179e0`), 24 numbered
sub-findings across 6 categories. The amendment log above closes 12 of
them (mapped 1:1 to the fixes numbered 1-12). The following sub-findings
were **not** addressed by that amendment and are surviving objections as
of this PR:

- **§1.3 — unbounded queue retention.** A processed task's `.md` file is
  never removed from `infra/army/spark-queue/`; the queue grows monotone
  forever, every tick still has to scan it in full, and a completed task
  stays visible as "just a file in the repo" to any human or session that
  doesn't also check `attempts.jsonl` — inviting an accidental manual
  re-trigger. The amendment fixed *dedup correctness* (item 2) but not
  *retention*.
- **§2.3 — kill-switch has no expiry/alarm.** `ARMY_SPARK_ENABLED=false` /
  `ARMY_JULES_ENABLED=false` can be armed for an incident and forgotten;
  nothing in the design distinguishes a fresh kill from a 30-day-old one,
  and no digest line calls out "still disabled" as an anomaly.
- **§5.4 — no inter-lane mutex.** Spark (every 2h) and Jules (dispatch +
  harvest every 3h) share the same Pro host, filesystem, and (for Jules)
  git-state reads, alongside ~200 other LaunchAgents already on that box.
  The design treats the two lanes as independent; nothing serializes them
  against each other if their windows overlap.
- **§6.3 — no cost field.** Neither `attempts.jsonl` nor `sessions.jsonl`
  records estimated token/quota spend per run, so "did the bucket spend
  produce anything worth it" stays unanswerable from the receipts alone
  even after item 12's produced/consumed ratio ships.
- **§6.5 — Jules escalation has no named owner or SLA.** The
  `shared/escalations_pro.jsonl` row routes to "an interactive session"
  generically, unlike the existing verification-role convention with a
  roster (referenced in the transcript as AGENTS.md §17) — an escalation
  without an owner risks the same inbox-backpressure-then-silence failure
  mode item 9 was built to prevent on the dispatch side.
- **§1.4 — mid-run mutation is detectable, not prevented.** Item 5's
  reproducibility header records the checkout HEAD sha *at run time*, which
  lets a later reader detect that a report was built against a moving
  working tree — it does not stop a concurrent `git pull` from changing
  files while a 900s `codex exec --sandbox read-only` run is still reading
  them.

None of these six are blocking for Phase 1 (all remain within the
"built-but-not-armed until proof-of-armed" gate above, and none reopens a
firebreak-class failure mode); they are logged here as the honest residue
of the review rather than silently absorbed into the "12 items, fully
amended" claim.
