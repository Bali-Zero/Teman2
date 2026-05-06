# WR2 Long-term Architecture Design — 2026-05-07

> **Status**: Design — pre-implementation. Owner-approved 2026-05-07.
> **Replaces**: ad-hoc tactical fixes that have accreted since PR #299 (supervisor cutover, 26 April 2026).
> **Audience**: future Claude sessions, Antonello (owner), eventual contributors.

---

## 1. Why this document exists

WR2 went live as event-driven pipeline 26 April 2026 (PR #299, supervisor + migration 138). Six weeks later the pipeline is **structurally broken** in production: drafts pile up at `drafts_imaged` because `fact-extractor` plist was disabled but the supervisor `TRANSITIONS` dict still routes there, so every kickstart is a silent no-op. No telemetry surfaces this.

A separate, equally serious failure: `claude_invoker.py` was authored when the WR1 runbook lived at `apps/war-room/APPLICA_WAR_ROOM.md`. PR #171 (22 April) removed that directory. The invoker is unreachable code — `is_file()` returns false → `CanvaInvokeError` raised on every entry — but nobody noticed because the LaunchAgent was, until 2026-05-06, running the AppleScript path (`wr2_canva_desktop_apply.py`), which only died when Anthropic's Claude Desktop update made the app a Linux web wrapper.

These are not isolated bugs. They are the predictable outcome of:

- Multiple alternative code paths kept in repo "just in case", none of them load-bearing tested.
- Supervisor as the only contract carrier between stages, no validation that target plists exist or that target queries match upstream output.
- Deploy worktree (`~/Desktop/nuzantara-deploy`) drifting silently from `origin/main` — five days behind at the time of audit.
- No dashboard. Telegram alerts only on rendered or full failure, nothing in between.

Antonello took six decisions on 2026-05-07 to set the long-term direction. This document binds those decisions to concrete architecture and a multi-sprint plan.

---

## 2. The six decisions

| #   | Question                                                                           | Decision                                     | Implication                                                                                                                                                                                                            |
| --- | ---------------------------------------------------------------------------------- | -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Editorial model: full-auto end-to-end, or human-in-loop?                           | **Human-in-loop**, permanent.                | No Instagram publisher organ. `rendered` is the terminal automatic state. Damar (marketing) downloads from Canva and posts manually. The Telegram review gate is structural, not bottleneck.                           |
| 2   | Fact-checking: restore or decommission?                                            | **Restore + add supervisor liveness check.** | Move `fact-extractor` and `fact-checker` plists from `.disabled/` back to `~/Library/LaunchAgents/`. Add an external watchdog that pings the supervisor and raises Telegram alert if no NOTIFY processed in N minutes. |
| 3   | Cadence target                                                                     | **1 carousel/day**, status quo, but solid.   | Topic-selector cron stays at 05:10 WITA. We do not scale up volume until the chain is stable for two weeks.                                                                                                            |
| 4   | Deploy worktree governance                                                         | **Auto-pull every hour via LaunchAgent.**    | New plist `com.balizero.wr2.deploy-puller` runs `git -C ~/Desktop/nuzantara-deploy pull origin main` hourly, with Telegram alert on conflict or pull failure. Manual pull becomes the exception.                       |
| 5   | Auto-learning chain (measurer / learner-nightly / oracle / strategos / sla-worker) | **Rivitalizzare via Sprint dedicato.**       | The four organs become living daemons with clear input/output contracts. measurer needs Instagram metrics ingestion path (manual paste? GA4? IG insights API?).                                                        |
| 6   | Telemetry & alerting                                                               | **Dashboard locale**, plus tiered Telegram.  | A Pro-local web service serves a single HTML dashboard reading from Postgres. P0 alerts (pipeline blocked) Telegram immediately. P1 alerts (degradation) Telegram once per 30min. P2 alerts (info) only on dashboard.  |

These decisions are owner-binding. Future agents reading this doc must respect them unless Antonello explicitly revises.

---

## 3. Target architecture

### 3.1 Stage diagram (target state)

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT LAYER (daily)                       │
├─────────────────────────────────────────────────────────────┤
│  intel-nightly (01:00) → POST /api/intel/staging             │
│  connector (04:00)     → research_dossiers theses            │
│  trend-hunter          → REMOVED (decision 1.b below)        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  SELECTION LAYER (05:10 WITA)                │
├─────────────────────────────────────────────────────────────┤
│  topic-selector (cron)                                       │
│    • WR2_PREFER_LIVE_NEWS=true (in plist env, fixed)         │
│    • Reads /api/intel/staging/pending                        │
│    • INSERT war_room_drafts status=briefed                   │
│    • PG trigger → pg_notify('wr2_status_change')             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              PROCESSING LAYER (event-driven)                 │
├─────────────────────────────────────────────────────────────┤
│  supervisor (KeepAlive daemon, LISTEN wr2_status_change)     │
│  + supervisor-watchdog (NEW, KeepAlive daemon, liveness)     │
│                                                               │
│  TRANSITIONS (target):                                       │
│    briefed              → draft-generator                    │
│    drafts               → image-generator                    │
│    drafts_imaged        → fact-extractor      [RESTORED]     │
│    drafts_imaged_facted → fact-checker        [RESTORED]     │
│    drafts_imaged_checked→ canva-apply                        │
│    rendered             → measurer + Telegram review gate    │
│    fact_check_failed    → Telegram alert (manual triage)     │
│    image_failed         → Telegram alert (manual triage)     │
│    rejected             → Telegram alert + log               │
│                                                               │
│  Each stage is a kickstart-only LaunchAgent (no schedule),   │
│  except supervisor + supervisor-watchdog (KeepAlive daemons).│
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   REVIEW GATE (manual)                       │
├─────────────────────────────────────────────────────────────┤
│  rendered → Telegram to Damar with Canva edit_url            │
│           → Damar opens Canva, downloads, posts to IG        │
│           → Damar pastes IG URL back via Telegram /posted    │
│             (NEW command, populates war_room_posts table)    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              FEEDBACK LOOP (auto-learning)                   │
├─────────────────────────────────────────────────────────────┤
│  measurer (StartCalendarInterval daily 12:00)                │
│    • Reads war_room_posts entries 24h+ old                   │
│    • Pulls IG metrics (impressions, saves, comments)         │
│    • INSERT post_metrics_history                             │
│                                                               │
│  learner-nightly (StartCalendarInterval 03:00)               │
│    • Reads last 30 days post_metrics_history                 │
│    • Computes engagement/topic correlations                  │
│    • Updates m13_retrain_log                                 │
│                                                               │
│  oracle (Sun 22:30)                                          │
│    • Weekly editorial review based on learner output         │
│    • Suggests topic adjustments for next week                │
│                                                               │
│  strategos (Sun 22:00)                                       │
│    • Long-term strategic review                              │
│    • Topic mix balancing across visa/tax/property/business   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 What goes away

- **trend-hunter**: plist points at module path that may not exist (`backend.services.intel.trend_hunter.cli`). Audit failed to locate the module on disk. Decommission and remove from launchd. Connector (already running, 04:00) covers the same input gap.
- **`wr2_canva_desktop_apply.py`**: AppleScript GUI automation. Obsolete after the CLI subprocess pivot (commit `216fc313c`). Move to `archive/`. The current LaunchAgent for canva-apply already points at `wr2_canva_apply.py`.
- **`runbooks/APPLICA_WAR_ROOM.md` inside backend-rag**: was the WR1 runbook copy. Replaced by `~/.claude/skills/canva-apply.md` as single source of truth (snapshotted in repo at `docs/wr2/skill-snapshots/`).

### 3.3 What gets added

- **`com.balizero.wr2.supervisor-watchdog`**: KeepAlive daemon. Pings supervisor every 60 seconds. If supervisor not responding (PID gone, asyncpg lock stuck, no NOTIFY processed in 30 minutes), Telegram alert P0 + auto-restart attempt via `launchctl kickstart -k`.
- **`com.balizero.wr2.deploy-puller`**: hourly `git pull` on `~/Desktop/nuzantara-deploy`. Conflict or fetch failure → Telegram alert P1.
- **`com.balizero.wr2.dashboard`**: KeepAlive daemon serving a Pro-local web UI on `127.0.0.1:8090`. Plain Python `http.server` + jinja templating (no FastAPI overhead). Read-only views over war_room_drafts, war_room_posts, post_metrics_history, supervisor heartbeat table.
- **Telegram `/posted` command handler**: Damar replies to the Telegram review-gate message with `/posted https://www.instagram.com/p/abcXYZ/`. The IG URL gets parsed and INSERT into war_room_posts. This is the bridge between the manual publish action and the measurer auto-loop.
- **migration 161**: `wr2_supervisor_heartbeat` table. Supervisor writes a row every 60 seconds with `last_notify_at`, `last_kickstart_at`, `pending_drafts_count`, `oldest_pending_draft_age_seconds`. Watchdog and dashboard read it.

### 3.4 What gets fixed

- Supervisor `TRANSITIONS` dict aligned to actual reality. Validation at supervisor startup: every target label in the dict must resolve to a `~/Library/LaunchAgents/<label>.plist` that exists and is loaded. Startup fails loudly otherwise.
- `claude_invoker.py` `APPLICA_RUNBOOK_PATH` → `~/.claude/skills/canva-apply.md` (already done in commit `216fc313c`, pending merge).
- `wr2_canva_apply.py` query `status='drafts'` → `status IN ('drafts_imaged_checked')` once supervisor TRANSITIONS are corrected. (Status filter aligned with what supervisor actually delivers.)
- `mata_garuda.workers.base_worker.redis_cmd()` reads `GARUDA_REDIS_HOST` env var and prepends `-h $host` to redis-cli args. Currently the env var is declared in plist but ignored by code → feeder reads Pro localhost instead of Mini-Pro2.
- `topic-selector` plist gets `WR2_PREFER_LIVE_NEWS=true` and `WR2_LIVE_NEWS_FILTER_MIN=40` in EnvironmentVariables. Live-first selector is dead code in cron until this happens.
- Newsletter `NEWSLETTER_SKIP_SEND=1` flag stays for now (decision 1: human-in-loop). Document explicitly that newsletter is manual-only and the plist exists as a future hook. Do not remove the plist (preserves env+wrapper config).

---

## 4. Multi-sprint plan

### Sprint A — Unblock (this week, ~1-2 days)

**Goal**: pipeline produces 1 carousel/day end-to-end without manual intervention.

| ID  | Task                                                                                                                                              | Effort             | PR                        |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ | ------------------------- |
| A1  | Merge `fix/wr2-canva-cli-headless-2026-05-07` (commit 216fc313c)                                                                                  | 0 (already pushed) | open + merge              |
| A2  | Patch supervisor `TRANSITIONS` to bypass fact-stages temporarily (`drafts_imaged → canva-apply` direct) — Sprint A only                           | 30min              | new commit on same branch |
| A3  | Update `wr2_canva_apply.py` query: `status IN ('drafts_imaged', 'drafts_imaged_checked')` to handle both Sprint-A bypass and Sprint-B restoration | included in A2     | same                      |
| A4  | `cd ~/Desktop/nuzantara-deploy && git pull origin main` after merge                                                                               | 5min manual        | —                         |
| A5  | Re-bootstrap canva-apply LaunchAgent                                                                                                              | 5min manual        | —                         |
| A6  | E2E watch: cron 05:10 next day produces clean Canva design                                                                                        | passive            | —                         |

Gate: A6 succeeds → Sprint A done.

### Sprint B — Fact-checking restoration + supervisor liveness (next week, ~3-4 days)

**Goal**: reactivate fact-extractor and fact-checker, add supervisor watchdog.

| ID  | Task                                                                                            | Effort  | PR         |
| --- | ----------------------------------------------------------------------------------------------- | ------- | ---------- |
| B1  | Read fact-extractor + fact-checker plists in `.disabled/`, audit code freshness                 | 2h      | —          |
| B2  | Move plists back to `~/Library/LaunchAgents/`, bootstrap, test kickstart                        | 1h      | —          |
| B3  | Restore supervisor `TRANSITIONS` to full chain (drafts→fact-extractor→fact-checker→canva-apply) | 30min   | new branch |
| B4  | Migration 161: `wr2_supervisor_heartbeat` table                                                 | 1h      | new branch |
| B5  | Patch supervisor: write heartbeat every 60s, expose `pending_drafts_count` etc                  | 2h      | same       |
| B6  | New script `wr2_supervisor_watchdog.py`: read heartbeat, alert on stale                         | 2h      | same       |
| B7  | New plist `com.balizero.wr2.supervisor-watchdog` (KeepAlive daemon)                             | 30min   | same       |
| B8  | E2E watch: 1 day clean run with fact-stages active                                              | passive | —          |

Gate: B8 succeeds for 3 consecutive days → Sprint B done.

### Sprint C — Deploy governance + topic-selector hardening (week 3, ~2 days)

**Goal**: kill the manual-pull-required ritual and surface live-first.

| ID  | Task                                                                                                          | Effort  | PR                                         |
| --- | ------------------------------------------------------------------------------------------------------------- | ------- | ------------------------------------------ |
| C1  | New script `~/scripts/wr2-deploy-pull.sh`: git fetch + pull --ff-only + Telegram on conflict                  | 1h      | scripts only                               |
| C2  | New plist `com.balizero.wr2.deploy-puller` StartInterval=3600                                                 | 30min   | —                                          |
| C3  | Patch `com.balizero.wr2.topic-selector.plist`: add `WR2_PREFER_LIVE_NEWS=true`, `WR2_LIVE_NEWS_FILTER_MIN=40` | 15min   | repo plist mirror in `infra/launchagents/` |
| C4  | Verify cron next morning produces breaking-news-first selection                                               | passive | —                                          |

### Sprint D — NLM feeder Mini routing fix (week 3, ~1 day)

**Goal**: resurrect the NLM feeder so NB-INTEL gets fresh OSINT.

| ID  | Task                                                                                                    | Effort  | PR         |
| --- | ------------------------------------------------------------------------------------------------------- | ------- | ---------- |
| D1  | Verify if PR #486 (resurrect, 6 May) was merged or still open                                           | 5min    | —          |
| D2  | If merged: deploy worktree pull (Sprint C handles this hourly going forward)                            | 0       | —          |
| D3  | If not merged: patch `mata_garuda/workers/base_worker.py` `redis_cmd()` to read `GARUDA_REDIS_HOST` env | 1h      | new branch |
| D4  | E2E test: feeder hourly run shows non-zero `fed=N` for at least one NB-INTEL                            | passive | —          |

### Sprint E — Auto-learning chain rivitalizzazione (weeks 4-5, ~5-7 days)

**Goal**: measurer + learner + oracle + strategos become living daemons.

This is the largest sprint. It requires choosing the IG metrics ingestion path (decision 5 follow-up). Three concrete options:

- **E.opt-1**: GA4 ingestion. Use `mcp__ga4-analytics__*` tools (already available) to read web traffic to balizero.com. Weak proxy for IG engagement but zero manual work.
- **E.opt-2**: Manual paste via Telegram. Damar replies to review-gate message with `/posted <ig-url>` and 24h later with `/metrics likes=X saves=Y comments=Z`. Bridges manual publish to auto-learning. Clean contract, requires Damar discipline.
- **E.opt-3**: IG Graph API. Requires Meta business account, app registration, token rotation. High setup overhead, but ground truth.

Recommend starting with E.opt-2 (zero infra, immediate signal). Migrate to E.opt-3 only if E.opt-2 proves manual burden too high.

| ID  | Task                                                                                                           | Effort  | PR  |
| --- | -------------------------------------------------------------------------------------------------------------- | ------- | --- |
| E1  | Telegram bot extension: `/posted <ig_url>` and `/metrics ...` commands → war_room_posts + post_metrics_history | 4h      | —   |
| E2  | Patch measurer (`com.balizero.wr2.measurer`) to read war_room_posts + post_metrics_history daily 12:00         | 2h      | —   |
| E3  | Patch learner-nightly (03:00) to compute correlations                                                          | 4h      | —   |
| E4  | Patch oracle (Sun 22:30) to write weekly editorial suggestion to a digest table                                | 4h      | —   |
| E5  | Patch strategos (Sun 22:00) for topic mix balancing                                                            | 4h      | —   |
| E6  | E2E test: 4 weeks of data → oracle/strategos produce non-trivial output                                        | passive | —   |

### Sprint F — Dashboard + tiered alerts (weeks 5-6, ~3-4 days)

**Goal**: Antonello opens `http://127.0.0.1:8090/wr2` and sees pipeline state at a glance.

| ID  | Task                                                                                                                    | Effort | PR         |
| --- | ----------------------------------------------------------------------------------------------------------------------- | ------ | ---------- |
| F1  | Plain Python `http.server` + jinja templates, single page                                                               | 4h     | new branch |
| F2  | Views: drafts pipeline (status counts, oldest pending), supervisor health, recent posts + metrics, learner correlations | 4h     | same       |
| F3  | New plist `com.balizero.wr2.dashboard` KeepAlive                                                                        | 30min  | —          |
| F4  | Tiered Telegram alerts: P0 immediate, P1 cooldown 30min, P2 dashboard-only                                              | 2h     | —          |

### Sprint G — Decommission + cleanup (week 6, ~1 day)

| ID  | Task                                                                                    | Effort | PR  |
| --- | --------------------------------------------------------------------------------------- | ------ | --- |
| G1  | Move `wr2_canva_desktop_apply.py` to `archive/`                                         | 5min   | —   |
| G2  | Remove `runbooks/APPLICA_WAR_ROOM.md` from canva_renderer (skill is SSOT)               | 5min   | —   |
| G3  | Remove or rewrite trend-hunter plist (decommission documented)                          | 15min  | —   |
| G4  | Update `docs/wr2/SUPERVISOR.md` + `docs/wr2/sprint2-mapping.md` to reflect target state | 2h     | —   |

---

## 5. Telemetry contract

Each stage of the pipeline writes a structured log line to `~/logs/wr2_<stage>.log` AND a heartbeat row to `wr2_supervisor_heartbeat` (supervisor only) or to a per-stage marker in `system_settings` (workers).

The dashboard reads three sources:

1. **Postgres**: war_room_drafts (counts by status, oldest pending), war_room_posts, post_metrics_history, wr2_supervisor_heartbeat.
2. **Filesystem**: tail of `~/logs/wr2_<stage>.log` (last 50 lines per stage, lazy-rendered).
3. **launchctl**: `launchctl print gui/$UID/com.balizero.wr2.<label>` for state per organ.

Tiered alerts are evaluated by the watchdog daemon every 60 seconds:

- **P0** (immediate Telegram, no cooldown): supervisor PID gone, OR any draft pending in drafts_imaged for > 30 min, OR no NOTIFY processed in last 60 min while drafts pending.
- **P1** (Telegram, 30 min cooldown): pull conflict on deploy worktree, image-generator failure, fact-checker failure, canva-apply failure on a single draft (after retry envelope exhausted).
- **P2** (dashboard only, no Telegram): cron success without output ("Intel nightly OK 0 articles"), connector/trend-hunter run with empty result, learner produces no new correlation.

---

## 6. Invariants (must never violate)

These are tagged with **owner-binding** because Antonello has explicitly approved them. Future agents:

- **OB-1**: Human-in-loop is permanent. **Never** add an Instagram publisher organ without owner re-approval.
- **OB-2**: Cadence is 1 carousel/day. **Never** scale up volume without owner re-approval.
- **OB-3**: Anthropic API is OAuth-only. **Never** import `anthropic.Anthropic` or set `ANTHROPIC_API_KEY` (golden rule from project CLAUDE.md, restated here for WR2 scope).
- **OB-4**: All LLM calls in WR2 must respect cost constraint: Claude Max OAuth, Codex via ChatGPT Plus, Gemini OAuth free, DeepSeek explicit ~$0.01/query (used by article_composer, OK).
- **OB-5**: `wr2_status_change` channel is volatile by design (not in EventBus outbox). Recovery is via reconciliation loop (300s scan), not durability layer. **Never** add this channel to `PG_CHANNEL_MAP` without owner re-approval — it would require relocating the supervisor inside the FastAPI process and break the launchd-daemon invariant.
- **OB-6**: WR2 does NOT modify any client-facing data (no CRM writes, no email send to clients). All outputs are internal review artifacts (Canva designs, Telegram alerts to owner+Damar).
- **OB-7**: Test designs created during E2E verification are tagged with "TEST DELETE ME" in topic and trashed manually post-test (Canva MCP exposes no delete endpoint).

---

## 7. Risk register (long-term)

| Risk                                                                         | Likelihood       | Impact                        | Mitigation                                                                                                 |
| ---------------------------------------------------------------------------- | ---------------- | ----------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Anthropic changes Claude CLI MCP integration breaking subprocess access      | Medium           | High                          | Sprint F watchdog detects canva-apply failures; manual fallback to AppleScript path documented in archive. |
| Canva MCP server (mcp.canva.com) goes down or rate-limits                    | Low              | Critical (entire stage fails) | No mitigation feasible. Telegram alert + manual carousel build.                                            |
| Claude OAuth Max plan quota exhausted (3x MAX plans currently active)        | Low              | Critical                      | Codex fallback for draft generation already in place (PR #478).                                            |
| Codex Image-2 ($imagegen) deprecated by OpenAI                               | Low              | High                          | Playwright fallback already coded as second option.                                                        |
| Tigris CDN quota exhausted                                                   | Medium           | High                          | Sprint F P1 alert on upload failures. Migrate to Fly storage as backup.                                    |
| Mac Pro hardware failure                                                     | Low              | Critical                      | Mini-Pro2 has the same code (Modo B). Failover requires DNS + DB connection swap, ~30min manual.           |
| Anthropic Claude Desktop sandbox regression repeats (kills MCP from Desktop) | Already happened | High                          | Sprint A pivot to CLI subprocess solved this; remains the primary path.                                    |

---

## 8. What the next 7 days look like

If we execute this plan starting 2026-05-07 (today), the working week looks like:

- **Today**: design doc merged. Sprint A starts. PR #fix-wr2-canva-cli-headless merged. Supervisor TRANSITIONS bypass-patch committed. Deploy worktree pulled. Canva-apply LaunchAgent re-bootstrapped.
- **Tomorrow morning** (05:10 WITA cron): first end-to-end run. We watch logs, dashboard not yet built so manual `tail -f ~/logs/wr2_canva_apply.log`.
- **By Friday 2026-05-09**: Sprint A done. 3 consecutive days of clean runs.
- **Week of 2026-05-12**: Sprint B (fact-checking) + Sprint C (deploy governance) + Sprint D (NLM feeder) in parallel where possible.
- **Week of 2026-05-19**: Sprint E (auto-learning) starts. This is the long sprint, will spill into the following week.
- **Week of 2026-05-26**: Sprint E completes. Sprint F (dashboard) starts.
- **Week of 2026-06-02**: Sprint F completes. Sprint G cleanup. Owner sign-off.

Total elapsed: ~4 weeks. Realistic with the constraints (no full-time dev, owner is solo, lots of moving parts in parallel projects).

---

## 9. Open questions for owner (before Sprint B kickoff)

1. **Fact-checker LLM choice**: when reactivated, should fact-checker use the same Claude OPUS path as draft-generator, or a cheaper Gemini route to save Max plan tokens? (Audit later).
2. **Damar onboarding for `/posted` command**: is Damar willing to use the new Telegram contract? Decision can be deferred to Sprint E kickoff.
3. **Dashboard scope**: read-only is implied. Should we add owner-only kill switches (e.g. "pause topic-selector for today") in the dashboard? Decision can be deferred to Sprint F.
4. **Backup strategy for war_room_drafts table**: Sprint G or earlier — define retention and Tigris backup cadence.

---

## 10. Living document

This doc is binding for Sprints A through G. After G is done, it becomes the runbook reference. Cicatrici discovered during execution get added to `~/Desktop/nuzantara/.claude/rules/cicatrix-scars.md`. New decisions get appended here in dated sections (`§ Update 2026-XX-YY: ...`), not by editing prior sections.

— Authored 2026-05-07 by Claude Opus 4.7 in collaboration with Antonello Siano (owner).
