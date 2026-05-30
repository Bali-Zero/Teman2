---
date: 2026-05-31
domain: operations
client_case: none
sources:
  - "live MCP: nuzantara-mcp check_health / check_health_detailed / check_fly_status / search_kbli"
  - "live MCP: postgres-nuzantara query (nuzantara_readonly, PG 17.7)"
  - "external curl https://nuzantara-rag.fly.dev/health + /health/ready (200)"
  - "launchctl list (Pro) + PlistBuddy + on-disk wrapper inspection"
  - "gh pr list; git worktree/branch inventory"
auditor: Claude Opus 4.8 (1M context) subagent — L2 autonomous empirical audit
frozen_snapshot: ~/logs/2026-05-31-empirical-audit-FROZEN.json
---

# Empirical System Audit — Nuzantara (2026-05-31, ~02:00 WITA / [Pro])

> Read-only FASE A freeze. Every number is tool-derived in the audit turn
> (anti-hallucination discipline). First-pass *guesses* (40 escalations, 0 DLQ,
> 218 migrations, 60,817 vectors) were WRONG and discarded before any write —
> the rule held. The canva root cause was also corrected mid-audit (it is a
> MISSING wrapper, not a PATH gap). Machine-readable freeze:
> `~/logs/2026-05-31-empirical-audit-FROZEN.json`.
>
> NOTE: the environment was CONTESTED — a parallel audit session flipped the
> main checkout to `chore/system-audit-2026-05-31` and wrote its own
> `research/operations/audits/FROZEN-2026-05-31.json` during this run; ~34 live
> `claude` procs. Counts below are one snapshot of a moving target.

## Verdict: HEALTHY (non-blocking debt flagged to operator)

Backend up, Postgres tracker pristine (0 dup migrations), DLQ all-TERMINAL,
required CI green, 0 gone/zombie branches at snapshot time. Open items are all
non-blocking operational/durability debt, not outages.

---

## 1. Backend / Fly (nuzantara-rag)

| Probe | Result |
|---|---|
| `curl /health` | **200** `{"status":"ok","ready":true,"process":"light"}` |
| `curl /health/ready` | **200** |
| `api` machine 7847d95ce257d8 | `started`, host ok, **2 cpu / 3072 MB** (W60 fix landed; was 1cpu/2048) |
| `rag` machine 1781e5eda03438 | `started`, host ok, 2 cpu / 2048 MB |
| Deployed image GH_SHA | `be06d86ba` |
| main HEAD | `7bd5b9aa5` — **3 dependabot commits ahead, undeployed** (#962 openai-stack, #966 prometheus-instrumentator, **#967 redis 7.4→8.0**) |

`check_health_detailed` returns **`critical` — BENIGN**: `search/ai/router`
`unavailable` because that probe hits the **api** process group; the RAG stack
runs in a **separate `rag` process** (`/health` note: "RAG handled by rag process
group"). RAG verified live earlier via `search_kbli`. `get_critical_alerts` MCP →
HTTP 401 (intel endpoint needs auth; not an outage).

---

## 2. Postgres (PG 17.7, nuzantara_rag, readonly MCP)

| Probe | Result |
|---|---|
| `schema_migrations` | **131 rows, 131 distinct, min 0, max 205, 0 duplicates** |
| `_schema_versions` (legacy) | **131 rows** (now parity) |
| `events_outbox` total / consumed | 37,427 / 36,920 |
| `events_outbox` **unconsumed** | **507 — ALL older than 60 min** |
| last consumed | 2026-05-30T17:58:49Z (live) |

### 2a. EventBus outbox — 507 permanently-stuck events (real durability debt)

| Channel | Unconsumed | Oldest | Newest (hrs ago) |
|---|---|---|---|
| client_changed | 178 | 2026-05-12 | 215.8 |
| inbound_webhook_queued | 164 | 2026-05-13 | **1.9 (still accreting)** |
| practice_changed | 78 | 2026-05-13 | 38.5 |
| cell_pulse_sustained_red | 50 | 2026-05-22 | 64.1 |
| intel_lake_event | 24 | 2026-05-12 | 378.0 |
| whatsapp_message_received | 8 | 2026-05-22 | 152.0 |
| war_room_event | 5 | 2026-05-14 | 377.8 |

All 507 are **older than the 60-min reconnect-replay window** (`max_age_minutes=60`,
SYMBIOSIS Law 3), so `_replay_outbox_on_reconnect` will **never** pick them up.
This is the **EventBus Phase-3 `prune_consumed` retention cron** that was specced
but never shipped (scar: "`events_outbox` is unbounded until phase 3"). Two
channels (`inbound_webhook_queued` 1.9h, `practice_changed` 38.5h) are **still
accreting** unconsumed rows → their consumers may be dead/behind.

---

## 3. Qdrant

`check_health` confirms embeddings **operational**, `text-embedding-3-small`
(1536 dims, FROZEN). **Vector counts NOT captured**: the only reachable MCP
(`get_collection_stats` / `get_qdrant_metrics`) returns **operation counters**
(all 0 in this idle window), not per-collection totals. I did **not** invent
counts. Memory cites 93,283 frozen vectors — left **unverified**; confirm via a
direct Qdrant client if a number is needed.

---

## 4. Operational state

| Item | State |
|---|---|
| `shared/escalations.json` | **DOES NOT EXIST** on disk |
| `~/.agent/decisions/dlq.json` | **13 entries, all TERMINAL** (healthy — W61 storm resolved) |
| `~/.agent/decisions/claude_tasks/` | 419 task files; `_cleared-expiry-noise-20260530` subdir exists (operator already swept) |
| `shared/escalations_pro.jsonl` | **4,519 entries, all `pending`** — see below |

### 4a. 4,519 stale escalation records (hygiene debt, NOT a storm)

All `dlq_autopilot_escalation`, **1,553 HIGH + 2,966 NORMAL**, spanning
**2026-04-07 → 2026-05-22** (newest 9 days old → not active). 65+ distinct jobs
(zombie_hunter ~107, daily_ops_autopilot ~105, comfyui_server ~105,
gdrive_pg_backup ~105). No consumer archives this JSONL (1.17 MB). Telegram
suppression (W57) is why the operator never saw 4,519 alerts. Fix = an
escalation-archiver / retention policy — not a safe autonomous edit on a
contested checkout.

### 4b. LaunchAgent exit codes (Pro)

| Job | last_exit |
|---|---|
| `com.balizero.regulatory-watcher.daily` | **0** |
| `com.balizero.regulatory-watcher.fix-b-verify` | **0** |
| `com.balizero.intel.nightly` | **0** |
| `com.matagaruda.kg-linker` | **0** |
| `com.nuzantara.launchagent-state-bridge` | **0** (W61 KeepAlive fix holding) |
| `com.balizero.wr2.canva-renderer` | **78** (ONLY failing cron) |

**wr2-canva-renderer exit-78 = MISSING wrapper.** The plist
`ProgramArguments[0]` is `~/.openclaw/bin/wr2/wr2-canva-renderer-wrapper.sh`,
but that file **does not exist** — the dir holds only `wr2-cron-wrapper.sh` and
`wr2-script-wrapper.sh` (mtime 2026-05-29 05:31). With `RunAtLoad=true` +
`StartInterval=300` + no `KeepAlive`, launchd tries to exec a missing binary
every 5 min → `exit=78`. Almost certainly the wrapper was renamed/consolidated
during the 2026-05-29 WR2 work and the plist `ProgramArguments` was never
repointed. Separately, the plist sets **no PATH** and **no `WR2_CANVA_ACTUATOR`**.
**Needs operator** — coupled to PR #970 / the active `recover-codex-launchd`
branch; editing live plists with ~34 claude procs would race in-flight work.

`com.nuzantara.regulatory-watcher.plist` does **not exist** — the active
regulatory jobs are the healthy `com.balizero.*` ones.

---

## 5. Git / CI (snapshot of a moving target)

| Metric | Count (at snapshot) |
|---|---|
| Worktrees | **9–10** (main + `/private/tmp` detached + `nuzantara-deploy` + ~6 stale agent worktrees under `.worktrees/` — W62 broker debt; a new `codex-overnight-runner-runs/...` worktree appeared mid-audit) |
| Local branches | 35–62 (fluctuating with the parallel session; **0–6 gone-upstream**) |
| Remote branches | 142–419 (read fluctuated; remote is authoritative) |
| `origin/claude/*` zombies | 0–2 |
| Open PRs | **PR #970** (operator `recover-codex-launchd`) + dependabot redis PR(s) |
| main required checks | **GREEN** |

Branch hygiene effectively clean (near-zero gone-local / zombies). Repo debt:
stale `.worktrees/` + the `nuzantara-deploy` worktree. (Counts unstable because a
parallel audit session is mutating the main checkout live.)

---

## 6. Fix queue

### Shipped by this audit (docs-only, blast-radius 0)
- This report + one corrected cicatrix scar (canva-renderer missing-wrapper root
  cause + the bare-plist-PATH cascade gap).

### Waiting for Antonello (operator decision / coordination)
1. **wr2-canva-renderer exit-78:** repoint the plist `ProgramArguments` to a
   wrapper that exists (or restore `wr2-canva-renderer-wrapper.sh`); coupled to
   PR #970.
2. **EventBus 507 stuck events:** ship the Phase-3 `prune_consumed` retention
   cron; investigate the still-accreting `inbound_webhook_queued` /
   `practice_changed` consumers. The 507 pre-date the 60-min replay window and
   will never self-clear.
3. **4,519 stale escalation records** in `shared/escalations_pro.jsonl` (1.17 MB):
   archive + add a retention policy.
4. **Qdrant vector-count verification:** confirm 93,283 via a direct Qdrant client.
5. **redis 7.4→8.0** (#967 backend on main undeployed; mouth PR open): a redis
   major bump is not a safe blind audit-deploy — verify client compat, deploy in
   a monitored window (CLAUDE.md §11).
6. **Repo hygiene:** prune stale `.worktrees/` (W62) + the `nuzantara-deploy`
   worktree in a quiet window.
7. **Two parallel audit sessions ran tonight** — reconcile this report's PR with
   the sibling `chore/system-audit-2026-05-31` artifacts to avoid a duplicate
   scar landing on main.
