---
date: 2026-05-31
domain: operations
client_case: none
sources:
  - "live MCP: nuzantara-mcp check_health / check_health_detailed / check_fly_status / search_kbli"
  - "live MCP: postgres-nuzantara query (nuzantara_readonly, PG 17.7)"
  - "external curl https://nuzantara-rag.fly.dev/health + /health/ready (200)"
  - "launchctl list (Pro) + PlistBuddy + wrapper source"
  - "gh pr list / gh run list; git worktree/branch inventory"
auditor: Claude Opus 4.8 (1M context) subagent — L2 autonomous empirical audit
frozen_snapshot: ~/logs/2026-05-31-empirical-audit-FROZEN.json
---

# Empirical System Audit — Nuzantara (2026-05-31, ~02:00 WITA / [Pro])

> Read-only FASE A freeze. Every number is tool-derived in the audit turn
> (anti-hallucination discipline). Several first-pass *guesses* (40 escalations,
> 0 DLQ, 218 migrations, 60,817 vectors, 18 gone-branches, 28 zombies) were
> WRONG and were caught + discarded before any write — the rule held.
> Machine-readable freeze: `~/logs/2026-05-31-empirical-audit-FROZEN.json`.

## Verdict: HEALTHY (non-blocking debt flagged to operator)

Backend up, Postgres tracker pristine (0 dup migrations), DLQ all-TERMINAL,
required CI green on main, 0 gone/zombie branches. Open items are all
**non-blocking operational/durability debt**, not outages.

---

## 1. Backend / Fly (nuzantara-rag)

| Probe | Result |
|---|---|
| `curl /health` | **200** `{"status":"ok","ready":true,"process":"light"}` |
| `curl /health/ready` | **200** |
| `api` machine (7847d95ce257d8) | `started`, host ok, **2 cpu / 3072 MB** (W60 fix landed; was 1cpu/2048) |
| `rag` machine (1781e5eda03438) | `started`, host ok, 2 cpu / 2048 MB |
| Deployed image GH_SHA | `be06d86ba` |
| main HEAD | `7bd5b9aa5` — **3 dependabot commits ahead, undeployed** (#962 openai-stack, #966 prometheus-instrumentator, **#967 redis 7.4→8.0**) |

`check_health_detailed` returns **`critical` — BENIGN**: `search/ai/router`
`unavailable` because that probe hits the **api** process group; the RAG stack
runs in a **separate `rag` process** (`/health` note: "RAG handled by rag process
group"). RAG verified live: `search_kbli("restaurant")` returned a valid hit.
`get_critical_alerts` MCP → HTTP 401 (intel endpoint needs auth; not an outage).

---

## 2. Postgres (PG 17.7, nuzantara_rag, readonly MCP)

| Probe | Result |
|---|---|
| `schema_migrations` | **131 rows, 131 distinct, min 0, max 205, 0 duplicates** |
| `_schema_versions` (legacy) | **131 rows** (now parity with schema_migrations) |
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
They will sit unconsumed forever. This is exactly the **EventBus Phase-3
`prune_consumed` cron** that was specced but never shipped (scar: "`events_outbox`
is unbounded until phase 3"). Two channels (`inbound_webhook_queued` newest 1.9h,
`practice_changed` 38.5h) are **still accreting** unconsumed rows → their consumers
may be dead/behind. Non-blocking for live ops, but it's real un-drained-event debt.

Migration-tracker note: `schema_migrations` (131) and legacy `_schema_versions`
(131) now report identical counts (a cicatrix once said 88 vs 6). Not an incident;
flag for the migration-consolidation follow-up.

---

## 3. Qdrant

`check_health` confirms embeddings **operational**, `text-embedding-3-small`
(1536 dims, FROZEN). **Vector counts NOT captured**: the only reachable MCP
(`get_collection_stats` / `get_qdrant_metrics`) returns **operation counters**
(all 0 in this idle window), not per-collection totals. I did **not** invent
counts. Memory cites 93,283 frozen vectors — left **unverified**; operator should
confirm via a direct Qdrant client if a number is needed.

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
**2026-04-07 → 2026-05-22** (newest is 9 days old → not active). 65+ distinct
jobs (zombie_hunter ~107, daily_ops_autopilot ~105, comfyui_server ~105,
gdrive_pg_backup ~105, …). No consumer ever archives this JSONL (1.17 MB).
Telegram suppression (W57) is why the operator never saw 4,519 alerts. The fix is
an **escalation-archiver / retention policy** — not in scope for a safe autonomous
edit on a contested checkout.

### 4b. LaunchAgent exit codes (Pro)

| Job | last_exit |
|---|---|
| `com.balizero.regulatory-watcher.daily` | **0** |
| `com.balizero.regulatory-watcher.fix-b-verify` | **0** |
| `com.balizero.intel.nightly` | **0** |
| `com.matagaruda.kg-linker` | **0** |
| `com.nuzantara.launchagent-state-bridge` | **0** (W61 KeepAlive fix holding) |
| `com.balizero.wr2.canva-renderer` | **78** (ONLY failing cron) |

`com.nuzantara.regulatory-watcher.plist` does **not exist** — the active
regulatory jobs are the `com.balizero.*` ones, and they're healthy.

**wr2-canva-renderer exit-78** (`~/scripts/wr2-canva-renderer-run.sh`): flock
lease, `REPO_ROOT=nuzantara-deploy`, `CLAUDE_BIN="$(command -v claude || echo
/opt/homebrew/bin/claude)"` (hardcoded fallback ⇒ Claude **is** resolvable
despite the bare plist PATH). Plist `PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin`
**omits `~/.local/bin`** (so `agy`/Gemini-Tier-2 is unreachable), and
`WR2_CANVA_ACTUATOR` is **unset** ⇒ defaults to the **desktop AppleScript**
actuator, which is chronically fragile ("si rompe sempre", 2026-05-29
headless-actuator scar). exit-78 = renderer cascade/actuator failure. Most likely
the desktop AppleScript path (Claude Desktop not open / skill unregistered) or the
headless path tripping on the missing `agy`. **Needs operator** — coupled to the
operator's **active `chore/recover-codex-launchd-fixes-2026-05-31` branch** (staged
`claude_oauth_client.py` `_resolve_claude_cli()` fix, 34 live claude procs);
editing live plists/wrappers now would race in-flight work + hit the
plist-overwrite + sibling-race scar class.

---

## 5. Git / CI

| Metric | Count |
|---|---|
| Worktrees | **9** (main + `/private/tmp` detached + `nuzantara-deploy` **PRUNABLE** + 6 stale agent worktrees under `.worktrees/` — W62 broker debt) |
| Local branches | 62 (**0 gone-upstream** → no `clean_gone` needed) |
| Remote branches | 419 (**0 `origin/claude/*` zombies**) |
| Open PRs | **1** — PR#963 dependabot redis 7.4→8.0 in `/apps/mouth` (not authored by audit) |
| main required checks | **GREEN** |

Branch hygiene is clean (0 gone-local, 0 zombies). Only repo debt: 6 stale
`.worktrees/` and the prunable `nuzantara-deploy`.

---

## 6. Fix queue

### Shipped by this audit (docs-only, blast-radius 0)
- This report.
- 1 cicatrix scar: cron multi-LLM cascade silently N-deep because cron plist
  PATHs omit `~/.local/bin` (Tier-2 `agy` unreachable → deprecated `gemini`),
  generalized from the wr2-canva-renderer exit-78 + the verified
  "`claude`/`agy` NOT_FOUND under plist PATH" probe.

### Waiting for Antonello (operator decision / coordination)
1. **EventBus 507 stuck events:** ship the Phase-3 `prune_consumed` retention cron
   (and investigate why `inbound_webhook_queued` + `practice_changed` consumers are
   still accreting unconsumed rows). The 507 pre-date the 60-min replay window and
   will never self-clear.
2. **wr2-canva-renderer exit-78:** the only failing cron, coupled to your active
   `recover-codex-launchd` branch. Decide actuator (`WR2_CANVA_ACTUATOR=headless`?)
   and add `~/.local/bin` to its plist PATH so `agy` resolves.
3. **4,519 stale escalation records** in `shared/escalations_pro.jsonl` (1.17 MB):
   archive + add a retention policy / archiver.
4. **Qdrant vector-count verification:** confirm the 93,283 figure via a direct
   Qdrant client (no reachable MCP returns per-collection totals).
5. **redis 7.4→8.0 bumps** (#967 backend on main undeployed; #963 mouth PR open):
   a redis major bump is not a safe blind audit-deploy — verify client compat,
   then deploy in a monitored window (CLAUDE.md §11).
6. **Repo hygiene:** prune the 6 stale `.worktrees/` (W62) + `git worktree prune`
   the `nuzantara-deploy` entry, in a quiet window (34 live claude procs now).
