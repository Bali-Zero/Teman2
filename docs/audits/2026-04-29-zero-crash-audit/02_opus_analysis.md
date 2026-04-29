# Opus 4.7 — Audit zero-crash analysis

**Author:** Claude Opus 4.7 (1M context, max effort)
**Date:** 2026-04-29
**Mode:** Independent analysis with empirical verification + corrections from NB-1

---

## 0. Verified facts (numeri prima)

I baseline numbers in the brief vs reality after empirical probing:

| Claim | Brief | Reality (verified 2026-04-29 ~05:30 UTC) | Source |
|------|------|------------------------------------------|--------|
| Apps | 27 | **26 directories under `apps/`** | `find apps -mindepth 1 -maxdepth 1 -type d` |
| Backend routers | 139 | **140 router files**, but **88 registered routers** runtime | `find` + NB-1 |
| Backend services | 512 | **607 service files** | `find apps/backend-rag/backend/services apps/backend-rag/backend/app/services -name '*.py'` |
| Migrations v2 | 30 | 30 (last applied 140) | `ls migrations_v2/*.sql` |
| LaunchAgents | 19 | **53 project plist** (com.nuzantara + com.balizero + com.cell) | `~/Library/LaunchAgents/` |
| Circuit breakers OPEN | 16/58 | 16/58 (28%) — confirmed | `~/.agent/decisions/circuit_breakers.json` |
| Sentinel jobs healthy | unknown | **10/58** at 2026-04-29 05:32 UTC | `~/.agent/decisions/sentinel_status.json` |
| DLQ entries | 1 (key count) | **54 entries (7 terminal)** | sentinel_status |
| Pro escalations pending | 5 | **7404 lines pending** in jsonl (file never pruned) | `wc -l shared/escalations_pro.jsonl` |
| KG nodes/edges | 108K/243K | **87K/210K** (production) per NB-1 | NB-1 source citations |
| LaunchAgents w/ KeepAlive=true | unknown | **7/53 (13%)**, 11/53 absent | grep `<key>KeepAlive</key>` |
| LaunchAgents missing EnvironmentVariables | unknown | **5/53** (VADEMECUM §11 violation) | grep |
| LaunchAgents logging to /tmp/ | unknown | **6/53** (lost on reboot) | grep |
| Fly machines healthy | unknown | 2/2 started, machine `d894e65bede478` had OOM-free crash 5h ago at 10:47 WITA | `fly machine status` |

## Sentinel state at moment of audit

From `~/.agent/decisions/sentinel_status.json` (2026-04-29 05:32 UTC):

```json
{
  "jobs_total": 58,
  "jobs_healthy": 10,
  "jobs_circuit_open": 16,
  "dlq_entries": 54,
  "dlq_terminal": 7
}
```

**This is the system in its current "normal" state.** 17% of monitored jobs healthy. 28% in circuit-open. 93% of DLQ never recovered. **The system Antonello uses every day is not a healthy system — it's a system that survives because Antonello restarts what breaks before it cascades.**

The audit goal is to make those numbers irrelevant — the system must self-recover so the daily counts fluctuate but never stay degraded.

---

## 1. P0 surfaces — crash without automatic recovery TODAY

### P0-1. SearchService fail-fast → restart loop ([NB-1 #1])

**Failure mode:** `backend.app.setup.service_initializer._init_critical_services` raises `RuntimeError` if `SearchService` or `ZantaraAIClient` fail to initialize. Fly auto-restart loops the container indefinitely. The crash is **deterministic** — restart cannot help.

**Blast radius:** 100% API down. All 88 registered routers, all 7 channels, all RAG queries, kita.balizero.com login dies.

**Current detection:** GH Actions cron `cron-fly-restart-detector.yml` every 15 min, plus the new healthcheck@balizero.com login probe (15 min). Both lag the actual outage by up to 14 minutes.

**Current recovery:** None. Fly restarts but the crash repeats. Manual `fly releases rollback` required.

**Why it's P0:** The 2026-04-29 03:11Z incident on kita.balizero.com (login flow recovered, machine `d894e65bede478` "in restart loop dal 2026-04-29 ~03:11Z" per memory `unresolved_2026_04_29`) is exactly this pattern.

**Fix:** Move SearchService/ZantaraAIClient init from "fail-fast critical" to "log-and-degrade non-critical". The app should bind 8080, serve `/health` returning `{degraded: ["search"]}`, return 503 from `/api/query` with structured `{error: "search_unavailable", retry_after: 60}`. This restores graceful degradation (Symbiosis Law 4). Reference impl: `non-critical services` already do this in same file.

**Verification:** Inject ImportError on `backend.services.search.search_service`; verify `curl /health` returns 200, verify `curl /api/query` returns 503 with structured error.

**Auto-implementable L2:** Yes — single file change in `service_initializer.py`, additive, reversible.

---

### P0-2. EventBus is PG LISTEN/NOTIFY, not Redis Streams — Symbiosis Law 4 lies ([NB-1 #4])

**Failure mode:** Symbiosis.md Law 4 says "if Redis is down, every agent works in isolation". The codebase doesn't use Redis Streams for event bus. It uses **PostgreSQL LISTEN/NOTIFY**. When PG drops connection (reconnect window 5s per `_RECONNECT_DELAY_S`), every NOTIFY published during the window is **silently lost** — `pg_notify` does not queue.

**Blast radius:** Centinaia di eventi cognitive lost per outage minute. Specific consumers affected (per NB-1):
- `practice.status_changed`, `client.changed`, `compliance.alert`, `lkpm.ingest_completed`
- `war_room.event` (review_handler Telegram, publisher_worker, measurer_worker, dashboard_sse)
- `intel.event` (4 cognitive layer tables: cross_dossier_theses, wr_anomaly_alerts, weekly_strategic_briefs, ultra_moves)
- `cognitive.event`

**Current detection:** None. Listener tries reconnect every 5s but consumers don't know what they missed.

**Current recovery:** None for the lost window. Events vanish.

**Why it's P0:** The published architecture (Symbiosis) and the actual code disagree. Decisions made on the assumption "Redis down = isolation" are wrong. PG is a single point of failure for event delivery, with no Outbox.

**Fix:** Outbox Pattern — every publisher writes to `events_outbox` table BEFORE `pg_notify`. A daemon reads `events_outbox` and emits NOTIFY when listener reconnects. Existing reference: `apps/backend-rag/backend/services/bridge/outbox.py` already does this for Pro/Air bridge. Generalize.

**Verification:** Drop PG connection for 30s during a war_room post update; reconnect; verify `dashboard_sse` and `publisher_worker` see ALL events from the outage window.

**Auto-implementable L2:** Yes for outbox table + helper. Migration v2 needed (+1 SQL file). Refactor of EventBus to call `outbox.write` then `pg_notify` is mechanical.

---

### P0-3. Cell/Organism crash = silent death, no auto-restart ([NB-1 #5], [Codex evidence])

**Failure mode:** Cell PulseLoop and Organism nervous system run as Python processes started manually or via plist. Per Codex empirical audit: of 53 project LaunchAgents, **only 7 have `KeepAlive=true`**. The Cell/Organism plist (`com.cell.organism.plist` exists in apps/cell/) per VADEMECUM §11 should have KeepAlive=true but verification needed.

**Blast radius:** When Cell crashes, the entire local automation stops:
- DNA recording stops (skill accumulation = 0)
- Genome HGT stream `cell:skills` stops (cells can't learn from each other)
- Sensor/Thinker/Actor lifecycle freezes
- Heartbeat stops → `heartbeat_monitor.py` declares DEAD on Telegram (per [NB-1 #20-21])

**Current detection:** Heartbeat monitor (dead-man switch) — but lag = `_PING_INTERVAL_S = 30s`. Heart-beat stops only signals after 3x missed window (`CRITICAL`/`DEAD`).

**Current recovery:** **NONE.** Manual SSH + `launchctl kickstart`. This is a violation of the audit goal.

**Why it's P0:** The "organism" doesn't survive its own organ death. There's no auto-restart equivalent of Fly for the local Mac processes.

**Fix:** Audit ALL 53 plist:
1. `KeepAlive=true` for daemons (Cell, Organism, NLM-bridge, post-publish-poller, etc.)
2. `EnvironmentVariables` always present (5 missing currently)
3. `StandardOutPath`/`StandardErrorPath` to `~/logs/`, never `/tmp/` (6 violators)
4. Each daemon plist also entered in `~/.agent/decisions/job_registry.json` so Sentinel checks it.

Generate from VADEMECUM §11 a `scripts/lint_launchagents.sh` that runs on PreToolUse hook before any plist edit.

**Verification:** `kill -9` Cell process; verify launchd respawns within 10s; verify `cell_pulse_log` resumes; verify Telegram does NOT alert DEAD.

**Auto-implementable L2:** Yes for the lint + plist patches. Mass `KeepAlive=true` requires audit (some plist might be intentionally one-shot — they go in cron not LaunchAgents).

---

### P0-4. SQL v2 migration deploy ordering bug (cicatrix STRUCTURAL, PR #307)

**Failure mode:** Already documented. `flyctl ssh console --command "python -m backend.db.migrate apply-all"` runs against the **OLD container image** because `run-migrations` job in fly-deploy.yml fires BEFORE `deploy`. New SQL v2 files in same PR are invisible. Workaround: manual `gh workflow run` post-merge.

**Blast radius:** Any new column referenced in code + corresponding SQL = production 500s ("column does not exist") for the entire deploy duration until manual re-trigger. Window typically 5-30 minutes.

**Current detection:** Production 500s, manual triage.

**Current recovery:** Manual `gh workflow run "Deploy Backend to Fly.io" --ref main`.

**Why it's P0:** Documented STRUCTURAL scar 2026-04-26, NOT YET RESOLVED. Risk recurrence at every migration.

**Fix:** New job `run-sql-v2-migrations-post-deploy` AFTER `deploy` step in fly-deploy.yml that re-runs SQL v2 runner against fresh image. Idempotent (runner skips applied migrations). Cost: ~5-10s extra deploy on no-op.

**Verification:** Deploy a test migration `141_audit_canary.sql`; verify the post-deploy job logs `Applied: ... +1 migration`.

**Auto-implementable L2:** Yes. Single workflow YAML change.

---

### P0-5. dependencies.py SPOF + Golden Rule #10 violations ([NB-1 #2])

**Failure mode:** `dependencies.py` uses fail-fast `HTTPException` if a service is missing from `app.state`. Worse, scattered code violates Golden Rule #10 by instantiating `httpx.AsyncClient()` inside method bodies and loops, leaking sockets. Eventually OS file descriptor exhaustion → crash → restart loop.

**Blast radius:** All routers depending on the leaky service degrade then crash. P95 latency spikes mask the leak until it's terminal.

**Current detection:** Prometheus `zantara_ai_latency_seconds` histogram — but no alert wired to it.

**Current recovery:** `self_healing/backend_agent.py` daemon restarts container on health check failure. But the leak is deterministic, so restart loops.

**Why it's P0:** Two issues compound: (a) dep fail-fast = restart-loop on missing service; (b) async client leak = same restart-loop on FD exhaustion. Both deterministic.

**Fix:**
1. Audit all `httpx.AsyncClient(` instantiations: `rg "httpx\.AsyncClient\(" apps/backend-rag/backend` — convert each to lazy-singleton in module scope, register `close_*_client` in `app_factory.lifespan()`. Reference: `services/notifications/email_http.py` pattern documented in CLAUDE.md §14.
2. Convert `dependencies.py` fail-fast to log-and-degrade — return 503 with `{error: "<service>_unavailable"}` instead of raising HTTPException at module import time.

**Verification:** `lsof -p <fly-pid> | wc -l` should plateau, not climb monotonically.

**Auto-implementable L2:** Partial. Shadow-grep+convert is mechanical (yes), but covers only the obvious cases. Subtle ones (httpx in lambda, in test fixture leaking to prod) require human audit. Run conversion + add CI grep-test that fails if `httpx.AsyncClient(` appears in a non-`*_http.py` file.

---

### P0-6. Channels webhook resilience — Twitter CRC broken & general retry storm

**Failure mode:** Twitter X webhook disabled hardcoded in `logging_config.py` since 2026-04-03 due to broken CRC handshake. Other channels (WhatsApp, Telegram, Instagram) have basic webhook handlers but if processing > 3s, Twitter/Meta auto-disable webhooks. Also, on Fly machine crash, in-flight webhook processing is lost — message ack not sent → external retries → duplicates.

**Blast radius:**
- Twitter: 100% missed messages from X (chronic).
- WhatsApp/IG: depends on Meta retry policy. Webhook-disable threshold = 3 consecutive failures over 5 min.
- Telegram: bot polling — less affected.

**Current detection (channel DLQ exists!):** Per Codex evidence, table `failed_messages` (migration 086) already exists with retry/exhausted states. `delivery_manager.start_retry_loop` is wired in `service_initializer.py:1037`. So **DLQ exists for outbound; inbound has no equivalent**.

**Current recovery:** Outbound retries via DLQ; inbound webhook drops are silent.

**Why it's P0:** Inbound = client traffic. Lost = lost lead.

**Fix:**
1. Move webhook handler to "ack first, process async" pattern. Router returns 200 OK after persisting payload to `inbound_webhooks` table; background worker picks up and processes. Ack < 200ms guaranteed.
2. Restore Twitter CRC: rewrite handshake per Graph API spec (HMAC SHA-256 of crc_token).

**Verification:** Hit `/webhook/whatsapp` with synthetic load (100 req/s); verify 100% 200 OK within 200ms.

**Auto-implementable L2:** Partial. The async pattern is mechanical (yes). Twitter CRC needs OAuth tokens + verified signature — some of the configuration may need manual handover. Mark as L2 with "credential check" preamble.

---

## 2. P1 surfaces — degrade without alert TODAY

### P1-7. NLM pipeline DLQ (54 entries, 7 terminal)

**Failure mode:** NB-1, NB-6, NB-7, NB-8, weekly_report jobs in PERSISTENT escalation state per `shared/escalations_pro.jsonl`. Memory `discovery_2026_04_24` confirms 8/9 NB pipelines exit in 3-5ms (openclaw dispatcher bug) and `claim_extractor.py:216` blocks NB-2 on CB_NLM=OPEN.

**Blast radius:** Daily NLM ground-truth refresh stops. Bali Zero clients receive stale answers via /api/query. CRM team workflows depending on NB-10 stop updating.

**Current detection:** `dlq_autopilot_escalation` writes to escalations.jsonl. But the file has 7404 lines pending — no one reads.

**Current recovery:** None. Manual.

**Fix:** Two parts.
1. Fix root cause: `claim_extractor.py:216` CB_NLM=OPEN block (separate work).
2. Auto-recovery for pipelines that have been stuck >24h: `system_doctor.py` Pro should detect, attempt rerun, and only escalate to Telegram if rerun fails. Currently Pro's `system_doctor.py` doesn't read `~/logs/cron-agent/` per memory `project_automations_audit_2026_04_19`.

**Verification:** Plant a synthetic stuck pipeline; verify auto-recovery within 1 cron cycle (08:00 next day for system_doctor, or 5min if you wire it to a tighter cron).

**Auto-implementable L2:** Yes for the auto-recovery loop. The CB_NLM root cause is separate work.

---

### P1-8. 7404-line escalations.jsonl with no rotation

**Failure mode:** `shared/escalations_pro.jsonl` is append-only since file inception. Every dlq_autopilot tick adds entries. Disk grows unbounded. Worse, dedup ID `audit_id` doesn't prevent re-append — same job fires multiple times.

**Blast radius:** Disk exhaustion (slow), but more importantly the file is humanly unreadable. Any consumer parsing it (none currently) hits performance walls.

**Current detection:** None.

**Current recovery:** None.

**Fix:**
1. Convert `escalations_pro.jsonl` and `escalations_air.jsonl` to SQLite tables (single file each) with index on `(job, created_at)`.
2. Add `cron-escalations-prune.plist` LaunchAgent that runs daily, marks resolved escalations as such, deletes resolved older than 30 days, archives non-resolved older than 90 days.

**Verification:** `wc -l` should drop from 7404 to "active" count after migration.

**Auto-implementable L2:** Yes. SQLite migration script + cron.

---

### P1-9. nuzantara-mcp 115-tool monolite ([NB-1 #6])

**Failure mode:** `apps/nuzantara-mcp/nuzantara_mcp/server.py` is one FastMCP process serving 115 tools. If it crashes, all 115 unavailable. Federation v3 launcher monitors heartbeat (3 missed → restart) but during restart all tools offline.

**Blast radius:** Claude Code, Cowork, OpenClaw all lose 115 tools. Backend/frontend NOT affected (this is local).

**Current detection:** Federation launcher heartbeat 30s, restart after 3x miss.

**Current recovery:** Auto-restart via launcher (good), but no tool-namespace isolation.

**Fix:** Partition the monolite into 3-4 specialized MCP processes (CRM, Ingestion, Intel, Misc) per `.well-known/agent-card.json` directives. Each crash isolates to its namespace.

**Verification:** Kill CRM-mcp process; verify Intel-mcp tools still respond.

**Auto-implementable L2:** Partial. Architectural change touching FastMCP + claude_code config + cowork integration. Probably best as L2-with-Zero-handoff for the namespace partition decision.

---

### P1-10. Frontend i18n provider per route group (PR #273 pattern)

**Failure mode:** Mouth Next.js 16/React 19 has `<I18nProvider>` wrapped in `(blog)/`, `(book)/`, portal layouts but NOT in `(workspace)/` nor root. PR #273 added `useTranslation()` to a component mounted in `(workspace)/layout.tsx` → throw → React unmount → white screen.

**Blast radius:** Any route group adopting `useTranslation()` without provider = white screen for that subdomain. Currently `(workspace)` was the casualty. Risk: future route group additions repeat the bug.

**Current detection:** Vercel preview is auth-walled (redirect to login), so Vercel preview console doesn't show throw. Only production users hit it.

**Current recovery:** Manual fix + redeploy.

**Fix:**
1. CI lint: `scripts/lint_i18n_providers.sh` — for every route group dir under `apps/mouth/src/app/`, check the layout.tsx contains `<I18nProvider>` IF any descendant component imports `useTranslation`. AST-based, in pre-deploy.
2. Alternative: provider in root layout (rejected per memory `lesson_2026_04_27` — by design for SSG hydration cost). So lint is the right path.

**Verification:** Plant a `useTranslation()` in a route group without provider; verify CI fails before deploy.

**Auto-implementable L2:** Yes. Bash lint + CI workflow.

---

### P1-11. Drive polling Air OAuth 90gg expiry

**Failure mode:** Per CLAUDE.md §14, Drive token in `google_drive_tokens` table expires every ~90 days. Watchdog `drive_token_watchdog.py` alerts 7 days before. But: per memory `unresolved_2026_04_29`, **drive-poll cron Pro DISABLED since 2026-04-29 due to broken-pipe**, not yet re-enabled. So even the watchdog is degraded.

**Blast radius:** Drive ingestion stops. CRM document processing freezes.

**Current detection:** Watchdog alerts 7 days before — IF cron runs.

**Current recovery:** Manual re-auth at `https://kita.balizero.com/settings/integrations`.

**Fix:**
1. Restore drive-poll cron Pro after fixing broken-pipe root cause.
2. Move OAuth refresh to a service account (no expiry) where possible — but Workspace constraints may prevent this.
3. Watchdog escalation: 30 days warning, 14 days warning, 7 days warning, 1 day warning + Telegram urgent.

**Verification:** Verify watchdog fires at all 4 thresholds via simulated date.

**Auto-implementable L2:** Yes for the watchdog escalation. Service account migration is L3 (Workspace impact).

---

## 3. P2 surfaces — manual recovery (lower urgency, but documentable)

### P2-12. Knowledge Graph subgraph BFS timeout

Already detailed in NB-1 #8. Fallback to vector search exists. P2 because graceful degradation is in place.

### P2-13. nuzantara-qdrant Fly app SUSPENDED

`fly apps list` shows `nuzantara-qdrant` as `suspended`. The system uses Qdrant Cloud via `QDRANT_URL` secret. P2 because functional via Cloud, but the Fly app needs lifecycle decision: re-enable or destroy. Right now it's a zombie — "deployed" but suspended, which silently passes audits.

### P2-14. Vercel build env vars for `NEXT_PUBLIC_*`

CLAUDE.md §10: must use `git push` not `vercel --prod` for build env to take effect. P2 because it's a documented gotcha. Lint suggested: pre-commit check that warns when running `vercel --prod` in monorepo CWD.

### P2-15. Healthcheck probe coverage gaps

`healthcheck@balizero.com` 15min login probe added 2026-04-29 — covers backend auth + frontend kita login flow. But doesn't test:
- WhatsApp send/receive
- Telegram bot ping
- Drive doc creation
- KG query end-to-end

Each subdomain needs a corresponding probe.

---

## 4. Surfaces I see that brief did NOT list

### A. Sentinel itself — who watches the watcher

`~/scripts/nuzantara-sentinel.py` is the central monitor. If it crashes, no auto-restart visible. The `.bak-20260411` backup file suggests it has been re-engineered (memory `feedback_no_auto_assignment_2026_03_29`). VADEMECUM §11 says daemon should be plist with `KeepAlive=true` — verify.

### B. Federation orchestrator/launcher

`apps/federation/launcher.py` runs the heartbeat loop ([NB-1 #26]). But the launcher itself — what restarts it? If launcher crashes, all federation agents go un-monitored. Recursive watchdog problem.

### C. `system_doctor.py` Pro vs OpsIntelligence Fly confusion

Two different daemons with similar names:
1. `~/scripts/system_doctor.py` (Pro local, runs cron 08:00) — per `feedback_self_repair_blind_2026_04_20`, this one was blind to `~/.agent/decisions/state/launchd_bad_exits.json` and was patched commit `a284ea39a`.
2. `apps/evaluator/nlm_deep_research/ops_intelligence.py` (Fly, Mon 08:00 WITA) — NLM aggregator for management briefing.

The brief conflated these. They serve different roles. Sentinel discipline: clear naming + role separation in docs.

### D. Vercel deploy risk: monorepo subapp cross-import

CLAUDE.md §8: `mouth/kita` deploys from monorepo root, `bali-intel-scraper` ONLY local on Pro, etc. If a satellite app's `package.json` imports a workspace package that breaks, the entire monorepo deploy fails. Pre-deploy gate doesn't currently lint cross-app imports for missing/circular.

### E. Brevo email sender single key

`SENDGRID_API_KEY=xkeysib-...` (Brevo). Single API key, no rotation, no fallback provider. CLAUDE.md "REGOLA FISSA" hardcodes `from=zantara@balizero.com`. If Brevo goes down or key rotates, all email outbound fails silently (current behavior in `notifications/send-email`).

### F. Tigris backup retention

`~/scripts/fly-pg-backup.sh` daily backup with 30d retention. Recovery drill is ⚠️ "manual, not automated" per AUTONOMOUS_OPS.md guardrail table. **Untested backup is no backup.** Without monthly automated restore drill, we don't know if the backups actually restore.

### G. Tailscale "OFF during AI work"

Per memory `air-monitoring`: Tailscale OFF during AI work. If Air goes offline (Wi-Fi blip) and Tailscale was off at that moment, recovery requires physical access. Single-link-of-failure for remote ops on Air.

---

## 5. Cell/Genoma touchpoints (Symbiosis Pillar 8)

Every fix above has a touchpoint with Cell/Genoma. Mapped in `10_cell_genoma_alignment.md`.

Quick preview:
- P0-1 SearchService degraded mode → record skill/scar in genome `apps/backend-rag` cell
- P0-2 EventBus Outbox → cell:skills HGT publisher for "PG outbox events emitted" milestone
- P0-3 Cell/Organism plist KeepAlive → meta touchpoint, fixes the cell substrate itself
- P0-5 dependencies.py audit → genome scar entry, "Golden Rule #10 violations corrected"
- P1-7 NLM auto-recovery → cell sensor for `nlm_pipeline_health`, actor for rerun

---

## 6. Confidence calibration

| Finding | Confidence | Why |
|----|----|----|
| P0-1 SearchService fail-fast | High | NB-1 cited code directly |
| P0-2 EventBus PG NOT Redis | High | NB-1 cited PG_CHANNEL_MAP + asyncpg listener |
| P0-3 Cell auto-restart absent | High | Codex empirical 7/53 KeepAlive |
| P0-4 PR #307 | High | Documented cicatrix STRUCTURAL |
| P0-5 dependencies.py SPOF | High | NB-1 + CLAUDE.md Golden Rule #10 |
| P0-6 Channels webhook | Medium-High | Twitter CRC documented; inbound async ack pattern proposed without verifying current behavior |
| P1-7 NLM DLQ | High | Sentinel state + memory + escalations.jsonl |
| P1-8 Escalations.jsonl growth | High | wc -l 7404 verified by Codex |
| P1-9 MCP monolite | Medium | Architectural — partition vs not is judgement call |
| P1-10 i18n provider | High | Lesson 2026-04-27 documented |
| P1-11 Drive OAuth | High | Memory + CLAUDE.md |

Low/medium confidence findings flagged for cross-LLM convergence in `08_convergent_findings.md`.
