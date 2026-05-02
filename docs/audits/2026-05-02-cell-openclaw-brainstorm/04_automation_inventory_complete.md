# Automation Inventory Complete — Pro Machine 2026-05-02

**Source:** Explore agent audit, post-brainstorm round 1
**Goal:** verify "130 automations" count, surface what was missed in initial brief

## Summary counts

- **Catalog total**: 263 unique automations documented
- **Active LaunchAgents plists**: 87 files (67 nuzantara-prefixed, rest system/3rd-party)
- **Crontab entries**: 110+ (many Air retirement phase 1–1.5 ported 2026-04-24)
- **State registry files**: 63 registered in `~/.agent/decisions/state/`
- **Running services** (launchctl non-zero PID): 13+
- **Cron-agent-python jobs**: 30+ defined in run.sh
- **TRUE TOTAL: ~300+ automations** including backend services + webhooks

## Critical topic automations

| Topic | Count | Key Examples | Status |
|-------|-------|--------------|--------|
| **CRM Automations** | 13 | `client-health-monitor`, `compliance-ops`, `crm_automation_engine.py`, `practice_status_listener`, `proactive_compliance_monitor` | Active; Python SDK 2026-04-14 |
| **Compliance/Legal** | 3 | `legal_radar.py`, `legal_full_ingestion`, `run_peraturan_ingestion.sh` | Active; weekly Sun 21:30 UTC |
| **Translation/Multilang** | 2 | `com.balizero.translate.hourly`, `translate-articles.py` | Active; hourly |
| **Memory/MOS** | 6 | `mos-maintenance.sh`, `sync-memory-to-nlm.sh`, `sync-memory-ruslana.sh`, TTL sweep, backup purge | Active; daily + weekly |
| **NLM Activation Cycle** | 14 | `nlm-nb1/2/3...-daily-refresh`, `nlm-deep-research`, `rag_canary.py`, `db_nlm_sync.sh` | Active; staggered Mon-Fri 02:10-02:50 WITA |
| **Sentinel/Arch** | 9 | `com.nuzantara.sentinel`, `automap-server/telegram/watchdog`, `auto_sentinel.sh`, `intel-scraper-sentinel-bridge.sh` | Active; daemons + hourly Intel Radar |
| **Cell/Organism/Observatory** | 2 LA + 3 cron | `com.cell.organism`, `cell-weekly-report`, `cell-observatory-collector`, `organism.supervisor/control-panel/scheduled-tick` | Active; supervisor PID 1500 |
| **Drive/Workspace Sync** | 6 | `drive-poll.sh` (DISABLED 2026-04-29), `drive_token_watchdog.py`, `gdrive-backup-all.sh`, `gdrive-pg-backup.sh`, `gdrive-qdrant-backup.sh` | Mostly active; drive-poll disabled for PG load |
| **Email/Notifications** | 1 + 6 webhook | `weekly_email_reporter`, event bus notifiers (welcome, birthday, LKPM) | Webhook-based |
| **Healthcheck/Login Probes** | 1 + 2 cron | `login-healthcheck`, `pro_heartbeat`, Air SSH heartbeat | Hourly heartbeat check |
| **Federation/Air Retirement** | 2 | `ai.openclaw.monitor-air` (DISABLED), Air cron backup 2026-04-24 | Phased out; crontab ported entries |
| **Bali Zero Dispatch** | 7 LA | `com.balizero.wr2.{newsletter, canva-apply, draft-generator, image-generator, oracle, strategos, connector, dossier-compiler, topic-selector}` | LaunchAgents; 13 running + 1 supervisor |

## Infrastructure automations

| Category | Count | Examples |
|----------|-------|----------|
| **System Health & Monitoring** | 12+ | `system-doctor`, `tech-orchestrator`, `fly-health-check` (migrated to fly-watcher), `qdrant-snapshot`, `ollama-warm-pin`, `cost-advisor-*`, `cpu-monitor`, `disk-monitor` |
| **Code Quality & Testing** | 5 | `core-guardian`, `cron_ragas.py`, `cron_red_team.py`, `tdd-pipeline`, `seo-auto-fixer` |
| **SEO/Guardian Loops** | 4 | `seo-guardian-observe` (every 40min), `seo-guardian-weekly`, `seo-guardian-measure`, `seo-cell.daily/28d-check` |
| **Intelligence Pipelines** | 8 | `intel-radar` (hourly), `intel-feed-processor` (every 2h), `intel-radar-daily-digest`, `fact-checker` (every 30min), `log-anomaly-detector` (every 5min) |
| **Indexing & Knowledge** | 10+ | `kb-ingest`, `knowledge-graph-builder`, `garuda-indexer`, `garuda-gc`, `vision-doc-extractor`, `indexing-daily`, `kbli-indexing-daily` |
| **Audit & Cleanup** | 7 | `audit-trail-cleanup`, `zombie-hunter`, `cache-cleanup`, `escalations-prune`, `dlq-autopilot`, `launchagent-state-bridge` |
| **Biz Intelligence** | 9 | `bi-exchange-rate`, `imigrasi-monitor`, `oss-monitor`, `pajak-monitor`, `coverage-trend`, `job-health`, `ragas-eval` |
| **Learning/Analysis** | 5 | `conversation-trainer`, `conversation-cleanup`, `learning-pipeline`, `nightly-code-quality`, `practice-lifecycle-check` |
| **Async Webhooks & DLQ** | 2 | `post-publish-poller`, `post-publish-webhook` |

## Discovered gaps (vs original "130" count)

The "130 count" referenced **only crontab entries**. Actual system contains:

1. **87 LaunchAgent plists** (daemons + interval-scheduled) — *mostly Bali Zero & Mata Garuda*
2. **63 registered state files** — many with no visible crontab/LA counterpart (`articles_indexing_daily`, `biz_orchestrator`, `comfyui_server`, `quality_orchestrator`, `war_room`)
3. **Cron-agent-python jobs** (30+) not all listed in crontab; managed via `run.sh` dispatcher
4. **Claude Code hooks** (12 post-tool-use + session hooks)
5. **GitHub Actions** (8 workflows, not running on Pro)
6. **Backend event listeners** (35+ Fly.io managed services)
7. **Webhook receivers** (event bus, post-publish callbacks)

**Missing from earlier 130 count:**
- `vision-doc-extractor` (every 6h, added 2026-04 Sprint 2)
- `bi-exchange-rate` (daily 07:00)
- `imigrasi-monitor` (daily 06:00)
- `oss-monitor` (every 2h, 08:00-22:00)
- `pajak-monitor` (daily 00:00 UTC)
- `tdd-pipeline` (weekly Mon 01:00 UTC)
- Mata Garuda 19-automation pipeline (all LaunchAgents, added 2026-04)
- Cell observatory collectors (3 LA plists added 2026-05-02)
- Air retirement C2/C3 jobs (30+ ported 2026-04-24)

## Verdict

**130-count was approximately correct for active crontab entries pre-Air-retirement.** Full system architecture now contains **263 catalogued + 35+ backend services**, true count **~300+ total automations** once you include:
- All 87 LaunchAgent daemons
- All 63 state-tracked agents
- Backend event listeners
- Webhook receivers

**No major domain was missed** — CRM, translation, compliance, email, Drive sync, memory, NLM, Sentinel, and Cell/organism are all well-represented. The gap was breadth (infrastructure + monitoring) rather than depth (business logic).
