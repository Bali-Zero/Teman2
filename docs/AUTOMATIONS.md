# Automations

This file is the operational catalog of all scheduled, event-driven, and background jobs
across the Nuzantara ecosystem — cross-host, cross-orchestrator. It covers Pro, Air,
backend (Fly.io), CI, and CRM flows in one place. The companion machine-readable source
is `scripts/automation_catalog.json`. The live system-health snapshot — per-job status,
last-run timestamps, error counts — lives in `docs/AUTOMATIONS_REFERENCE.md` (auto-generated
nightly at 23:15 WITA by `scripts/generate_automations_reference.py`; do not edit that file
directly and do not archive it).

---

## Summary

| Host / Layer          | Orchestrator     | Jobs |
| --------------------- | ---------------- | ---- |
| Pro (M4 Pro 48GB)     | OpenClaw         | 24   |
| Pro                   | Crontab          | 47   |
| Pro                   | LaunchAgents     | 38   |
| Air (M4 16GB)         | OpenClaw         | 12   |
| Air                   | Crontab          | 29   |
| Air                   | LaunchAgents     | 18   |
| Backend Fly.io        | Event-driven     | 16   |
| CI                    | GitHub Actions   | 8    |
| Claude Code           | Hooks            | 12   |
| **Total catalogued**  |                  | **204** |

Orchestrators: OpenClaw (agent runtime, gateway `loopback:18789`), macOS crontab,
launchd (LaunchAgents), GitHub Actions, Fly.io BackgroundTasks + PG NOTIFY.
CRM backend also runs 6 autonomous scheduled tasks and 2 background services (see
§ CRM Flows below).

---

## Pro — Jobs (M4 Pro 48GB)

For per-job health and last-run status, see `docs/AUTOMATIONS_REFERENCE.md` (Pro section).

### OpenClaw Cron Jobs (24)

| #     | Job                    | Schedule (WITA) | LLM / Type        | Model                 | Purpose                     |
| ----- | ---------------------- | --------------- | ----------------- | --------------------- | --------------------------- |
| 1     | core-guardian          | */3h            | LLM (OpenClaw)    | qwen3.5:9b (warm)     | Lint guardian, auto-fix     |
| 2     | seo-guardian-observe   | every 40min     | LLM (OpenClaw)    | qwen3.5:9b (warm)     | SEO signal parse            |
| 3     | system-doctor          | */4h            | LLM (OpenClaw)    | qwen3.5:9b (warm)     | Diagnose + auto-fix         |
| 4     | tech-orchestrator      | every 4h        | LLM (OpenClaw)    | qwen3.5:9b (warm)     | Guard + orchestrate         |
| 5     | compliance-ops         | every 6h        | LLM (OpenClaw)    | qwen3.5:9b (warm)     | Compliance check            |
| 6     | daily-ops              | 08:00           | LLM (OpenClaw)    | qwen3.5:9b (warm)     | Morning sweep               |
| 7     | client-health-monitor  | 14:00           | LLM (OpenClaw)    | qwen3.5:9b (warm)     | mcporter chain              |
| 8     | conversation-cleanup   | 02:00           | LLM (OpenClaw)    | qwen3.5:9b (warm)     | curl API + parse            |
| 9     | indexing-daily         | 09:00           | LLM (OpenClaw)    | qwen3.5:9b (warm)     | GSC indexing                |
| 10    | seo-guardian-weekly    | Mon 08:00       | LLM (OpenClaw)    | qwen3.5:9b (warm)     | Weekly SEO analysis         |
| 11    | weekly-review          | Mon 09:00       | LLM (OpenClaw)    | qwen3.5:9b (warm)     | KPI review                  |
| 12    | weekly-dep-audit       | Mon 03:30       | LLM (OpenClaw)    | qwen3.5:9b (warm)     | pip-audit                   |
| 13    | learning-pipeline      | Sun 23:00       | LLM (OpenClaw)    | qwen3.5:9b (warm)     | Training pipeline           |
| 14    | t4-monitor-daily       | 03:35           | LLM (OpenClaw)    | qwen3.5:9b (warm)     | bash script exec            |
| 15    | nlm-nb1-daily-refresh  | 04:30           | LLM (OpenClaw)    | qwen3.5:9b (warm)     | NotebookLM NB-1 refresh     |
| 16-22 | nlm-nb3..nb10          | 02:20-02:50     | — (empty task)    | Skipped               | Slots reserved, not wired   |
| 23    | nlm-deep-research      | 01:10           | — (empty task)    | Skipped               | Slot reserved               |
| 24    | cell-weekly-report     | Sun 08:00       | — (empty task)    | Skipped               | Slot reserved               |

### Crontab Jobs (47)

Selected entries with LLM or operational significance:

| #     | Job                             | Schedule (WITA)     | LLM / Type | Model / Note                                  |
| ----- | ------------------------------- | ------------------- | ---------- | --------------------------------------------- |
| 1     | translate-articles.py           | every hour :30      | LLM        | gemma4:26b → gemma4:e4b, IT/ID/RU/FR          |
| 2     | qwen-code-review.sh             | 10:00 (NOT LOADED)  | LLM        | **DEAD** — qwen2.5-coder:32b not installed    |
| 3     | legal_radar.py                  | Sun 08:00           | SHELL      | Python pure, no LLM                           |
| 4     | fly-health-check.sh             | */30min             | SHELL      | curl Fly.io health                            |
| 5     | drive-poll.sh                   | */5min              | SHELL      | Google Drive poll                             |
| 6-11  | infra bridges + heartbeat       | */4-5min + hourly   | SHELL      | state bridge, pro_heartbeat, nlm_bridge       |
| 12    | fly-backup.sh                   | 03:00               | SHELL      | pg_dump + qdrant backup → Tigris              |
| 13    | mos-maintenance.sh              | 04:00               | SHELL      | SQLite vacuum                                 |
| 14    | expiry_alerter.py               | 08:00               | SHELL      | Practice expiry alerting                      |
| 15    | sync-memory-to-nlm.sh           | Sun 03:00           | NLM        | Memory → NotebookLM                           |
| 16-19 | monitoring + sync               | various             | SHELL      | cert, fly-loop-detector, fly-cost, sync-damar |
| 20    | cache-cleanup                   | 1st+15th 03:30      | SHELL      | npm+pip+brew cleanup                          |
| 21    | bali-zero-akta overnight        | 19:00 Sun-Fri       | SHELL      | Bulk akta processor, no direct LLM            |
| 22-28 | NLM nb2-nb10 pipelines (7)      | 02:10-02:50 Mon-Sat | NLM        | nlm CLI → NotebookLM cloud (domain KBs)       |
| 29    | NLM nb1 refresh (cron)          | 20:30               | NLM        | nlm CLI                                       |
| 30    | NLM peraturan ingestion         | Sun 21:30           | NLM        | nlm CLI                                       |
| 31-36 | NLM multimodal (6)              | 22:00 Mon-Sat       | NLM        | nlm CLI                                       |
| 37-39 | NLM gap scanner (layer-a/b/rem) | 19:00-21:30         | NLM        | nlm CLI + Gemini search (cloud)               |
| 40-47 | NLM monitoring + ops (8)        | */6h / 00:00 / Sun  | NLM        | freshness, heartbeat, briefing, yt, t4, db    |

### LaunchAgents (38 plist)

LLM-consuming agents:

| Label                              | Type      | Model                     | Purpose                    |
| ---------------------------------- | --------- | ------------------------- | -------------------------- |
| com.balizero.translate.hourly      | Scheduled | gemma4:26b → e4b          | Article translation        |
| com.nuzantara.qwen-code-review     | Scheduled | qwen2.5-coder:32b (DEAD)  | Not loaded — needs fix     |
| com.nuzantara.dlq-autopilot        | Scheduled | claude CLI (OAuth)        | DLQ reasoning every 30min  |
| com.nuzantara.sentinel             | Scheduled | claude CLI (OAuth)        | Classifier fallback 5min   |
| com.cell.organism                  | DAEMON    | qwen3.5:9b / gemma4:26b   | Cell reasoner Tier 0/1     |
| com.matagaruda.sentinel.daily      | Scheduled | — (check)                 | Mata Garuda sentinel       |

Selected infrastructure LaunchAgents (no LLM):

| Label                               | Type           | Purpose                         |
| ----------------------------------- | -------------- | ------------------------------- |
| com.balizero.nlm-bridge             | DAEMON :18790  | HTTP bridge for NLM             |
| com.nuzantara.automations-reference | Scheduled 23:15| Auto-gen doc generator          |
| com.nuzantara.prime-tunnel          | DAEMON         | Cloudflared tunnel              |
| com.nuzantara.zombie-hunter         | Scheduled 1min | Process cleanup                 |
| ai.openclaw.gateway                 | DAEMON         | OpenClaw gateway                |
| ai.openclaw.tunnel                  | DAEMON         | AutoSSH tunnel to Air           |
| com.garuda.gap-detector.twice-daily | Scheduled      | KG gap detection                |
| com.claude-max-api                  | DAEMON         | Claude MAX OAuth proxy          |
| homebrew.mxcl.{ollama,pg,redis}     | DAEMON         | Core services                   |

Full LaunchAgent list (38 entries): see `docs/AUTOMATIONS_REFERENCE.md` Pro section.

---

## Air — Jobs (M4 16GB)

For per-job health and last-run status, see `docs/AUTOMATIONS_REFERENCE.md` (Air section).

### OpenClaw Cron Jobs (12)

| #   | Job                      | Schedule    | LLM / Type     | Model            | Purpose               |
| --- | ------------------------ | ----------- | -------------- | ---------------- | --------------------- |
| 1   | ecosystem-healthcheck    | every 6h    | LLM (OpenClaw) | qwen3:4b (warm)  | Health ping           |
| 2   | fly-health-30m           | every 30min | LLM (OpenClaw) | qwen3:4b (warm)  | MCP check             |
| 3   | system-doctor            | —           | LLM (OpenClaw) | qwen3:4b (warm)  | System diagnostics    |
| 4   | pg-sync                  | 03:00       | SHELL          | —                | pg_dump, no LLM       |
| 5   | pg-sync-verify           | 05:00       | LLM (OpenClaw) | qwen3:4b (warm)  | Verify dump           |
| 6   | intel-pipeline           | 06:00       | LLM (OpenClaw) | qwen3:4b (warm)  | Scraper orchestration |
| 7   | intel-retry              | 08:00       | LLM (OpenClaw) | qwen3:4b (warm)  | Failed scrape retry   |
| 8   | source-enrichment-weekly | Sun 03:00   | LLM (OpenClaw) | qwen3:4b (warm)  | Source enrichment     |
| 9   | nuz-intel-radar          | —           | LLM (OpenClaw) | qwen3:4b (warm)  | Intel monitor         |
| 10  | nuz-normativa-daily      | —           | LLM (OpenClaw) | qwen3:4b (warm)  | Regulation check      |
| 11  | nuz-codebase-audit       | —           | LLM (OpenClaw) | qwen3:4b (warm)  | Code audit            |
| 12  | nuz-weekly-report        | —           | LLM (OpenClaw) | qwen3:4b (warm)  | Weekly report         |

### Crontab Jobs (29)

| #     | Job                       | Schedule (WITA)  | LLM / Type | Model / Note                          |
| ----- | ------------------------- | ---------------- | ---------- | ------------------------------------- |
| 1     | auto_test.sh              | 02:15            | LLM        | qwen2.5:latest (Ollama window 01-06)  |
| 2     | system_doctor.py          | 08:00            | —          | Parses logs, no LLM generation        |
| 3     | auto_sentinel.sh          | 03:00            | SHELL      | Sentinel wrapper                      |
| 4     | auto_kb_ingest.sh         | 05:00            | SHELL      | Spider pipeline                       |
| 5     | auto_judgement_day.sh     | Sun 16:00        | SHELL      | RAGAS eval (Python, no direct LLM)    |
| 6     | rag_canary.py             | */6h :30         | SHELL      | Embedding check (OpenAI API)          |
| 7     | ragas_eval.py             | Sat 06:00        | SHELL      | RAGAS framework                       |
| 8-9   | ollama_cron_window        | 01:00 / 06:05    | SHELL      | Start/stop Ollama for test window     |
| 10    | crm_automation_engine.py  | 23:00            | API        | Calls Fly.io API                      |
| 11-13 | notifiers (all/bday/wlcm) | 00:00-*/15min    | API        | curl Fly.io notification endpoints    |
| 14    | lkpm-notifier             | 23:00            | API        | LKPM compliance deadline alerts       |
| 15    | auto-practice-creator     | 07:30            | API        | Creates renewal practices (T-60)      |
| 16-17 | backups (PG + Qdrant)     | 03:20 / Sun 04:00| SHELL      | pg_dump + Qdrant snapshot             |
| 18-22 | infra + MOS               | various          | SHELL      | drive watchdog, damar sync, mos ops   |
| 23    | ollama weekly restart     | Sun 05:00        | SHELL      | Prevents memory fragmentation         |
| 24    | db-nlm-sync               | 20:30            | NLM        | DB → NotebookLM                       |
| 25    | sync-memory-to-nlm        | Sun 03:40        | NLM        | Memory sync to NotebookLM             |
| 26    | t4-monitor (cron)         | */6h             | NLM        | Social monitor                        |
| 27    | cache-cleanup             | 1st+15th         | SHELL      | npm+pip+brew cleanup                  |

### LaunchAgents (18 plist)

| Label                           | Type      | Model                           | Purpose          |
| ------------------------------- | --------- | ------------------------------- | ---------------- |
| com.cell.organism               | DAEMON    | qwen3.5:9b (now qwen3:4b)       | Cell pulse       |
| ai.openclaw.node                | DAEMON    | Claude Opus → qwen3:4b (TBD)    | OpenClaw node    |
| com.nuzantara.guardian-ragas    | Scheduled | —                               | RAGAS eval       |
| com.nuzantara.guardian-redteam  | Scheduled | —                               | Red team         |
| com.nuzantara.guardian-seo      | Scheduled | —                               | SEO guardian     |
| com.nuzantara.nightly-sync      | Scheduled | —                               | Git sync         |
| com.nuzantara.fly-pg-tunnel     | DAEMON    | —                               | Fly PG tunnel    |
| com.claude-max-api              | DAEMON    | —                               | Claude MAX proxy |
| homebrew.mxcl.ollama            | DAEMON    | —                               | Ollama serve     |
| homebrew.mxcl.postgresql@17     | DAEMON    | —                               | PostgreSQL       |
| homebrew.mxcl.redis             | DAEMON    | —                               | Redis            |

---

## Backend & CI

### Backend-RAG On-Demand (Fly.io + local)

| Role               | Model                  | Where          | Warm?     |
| ------------------ | ---------------------- | -------------- | --------- |
| RAG primary        | gemini-3-flash-preview | Fly.io (cloud) | —         |
| RAG fallback       | gemini-2.5-flash       | Fly.io (cloud) | —         |
| FAST (local)       | qwen3.5:9b             | Pro Ollama     | WARM      |
| HEAVY (local)      | deepseek-r1:32b        | Pro Ollama     | On-demand |
| KG / JSON (local)  | gemma4:26b             | Pro Ollama     | On-demand |
| VISION (local)     | qwen2.5vl:7b           | Pro Ollama     | On-demand |

### Backend Event-Driven (16 entries)

| #   | Name                              | Type           | Trigger                     | System     |
| --- | --------------------------------- | -------------- | --------------------------- | ---------- |
| 1   | event_bus_client_changed          | PG NOTIFY      | clients INSERT/UPDATE       | CRM        |
| 2   | event_bus_practice_status_changed | PG NOTIFY      | practices status change     | CRM        |
| 3   | event_bus_compliance_alert        | PG NOTIFY      | compliance threshold breach | Compliance |
| 4   | redis_reconnect_loop              | backend-loop   | on disconnect               | Ops        |
| 5   | article_composer_cache_startup    | startup-hook   | once at boot                | Content    |
| 6   | bali_intel_task_queue             | backend-loop   | while scraper running       | Intel      |
| 7   | bali_intel_proxy_health_check     | backend-loop   | while scraper running       | Intel      |
| 8   | bali_intel_browser_pool_cleanup   | backend-loop   | while scraper running       | Intel      |
| 9   | bali_intel_ai_batch_flush         | backend-loop   | batch threshold/delay       | Intel      |
| 10  | bali_intel_webhook_receiver       | webhook        | incoming POST               | Intel      |
| 11  | bg_crm_practice_email             | BackgroundTask | practice update             | CRM        |
| 12  | bg_crm_client_welcome             | BackgroundTask | client creation             | CRM        |
| 13  | bg_whatsapp_async_processing      | BackgroundTask | incoming WA message         | Channels   |
| 14  | bg_document_ocr                   | BackgroundTask | document upload             | CRM        |

### GitHub Actions (8 workflows)

| #   | Workflow           | Trigger             | Schedule      | Purpose                           |
| --- | ------------------ | ------------------- | ------------- | --------------------------------- |
| 1   | docs-sync          | push/PR             | —             | Checks docs in sync               |
| 2   | fly-deploy         | push to main        | —             | lint → test → deploy (rolling)    |
| 3   | fly-secrets-check  | scheduled + manual  | Mon 09:00 UTC | Verifies FLY_API_TOKEN + TG alert |
| 4   | intel-router-tests | push/PR             | —             | bali-intel-scraper API tests      |
| 5   | security-scanning  | scheduled + manual  | Sun 00:00 UTC | Snyk Python + Node                |
| 6   | semgrep-sast       | push/PR             | —             | Bandit + ESLint, blocks on HIGH   |
| 7   | sonarqube          | push/PR             | —             | Code quality gates                |
| 8   | tests              | push/PR             | —             | pytest + coverage gate            |

### Claude Code Hooks (12 hooks)

| #   | Event            | Matcher    | Purpose                          |
| --- | ---------------- | ---------- | -------------------------------- |
| 1-3 | PostToolUse      | Edit/Write | Post-processors on file edits    |
| 4   | PostToolUse      | Bash       | Post-processor on shell commands |
| 5   | PostToolUse      | *          | Global post-processor            |
| 6   | Notification     | *          | Notification handler             |
| 7   | PreToolUse       | Edit/Write | Pre-validation on file edits     |
| 8   | PreToolUse       | Bash       | Pre-validation on shell          |
| 9   | Stop             | *          | Session cleanup                  |
| 10  | SessionStart     | compact    | Context loading                  |
| 11  | SessionStart     | *          | Global init                      |
| 12  | UserPromptSubmit | *          | Prompt pre-processing            |

---

## CRM Flows (reference snapshot)

These 15 automations run inside the backend-rag Fly.io app. Source: `ACTIVE_AUTOMATIONS.md`
(archived Feb 2026). For current status, see `docs/AUTOMATIONS_REFERENCE.md`.

### Real-Time Triggers (7)

**Invoice Automation** — fires when practice status → `sending_invoice`
(`services/invoicing/invoice_service.py`). Generates PDF, emails client with invoice
attached, notifies Asya, uploads to Google Drive (Individual_CRM or Company_CRM folder).
Email via Zoho Mail API, SMTP fallback.

**Process Start Notification** — fires on status → `on_process`
(`services/crm/process_automation_service.py`). Sends warm email to client ("payment
received, starting your process") and notification to assigned team leader.

**Process Completion** — fires on status → `completed`
(`services/crm/completed_process_service.py`). Uploads final documents to client's Drive
"Final Documents" folder, sends congratulatory email with document links, notifies team
leader, and creates a renewal alert 60 days before expiry.

**Drive Folder Creation** — fires on new client creation (`app/routers/crm_clients.py`).
Creates standardized Google Drive folder structure:
`{ID}_{ClientName}/00_Profile/ 01_Immigration/ 02_Company/ 03_Tax/ 04_Family/ 99_Misc/`.

**Auto-CRM Extraction** — fires at end of chat conversation (`services/crm/ai_crm_extractor.py`). AI extracts client data; creates client if confidence >= 0.7, updates if >= 0.5, creates practice if intent detected (KITAS, PT PMA, etc.).

**Lead Assignment** — fires on new client creation (`services/crm/lead_assignment_agent.py`). Deduplicates by email/phone/Telegram/WhatsApp, assigns by department + load balancing, sends Telegram notification with Accept/Reassign buttons.

**Document Upload Notification v2.0** — fires on client portal upload
(`/api/portal/documents/upload`, `services/portal/portal_service.py`). Virus scan →
Drive upload to `Zantara Portal Uploads/{client_id}_{name}/{doc_type}/{timestamp}_{file}`
→ OCR via Gemini Vision → expiry date detection → DB save → timeline event → email to
assigned lead with file details, Drive link, detected expiry, client workspace link.

### Scheduled (5)

**Self-Healing Monitor** — every 5 minutes. Monitors Qdrant, PostgreSQL, AI Router;
attempts auto-fix for common issues; logs all actions.

**Conversation Trainer** — every 6 hours. Analyzes last 7 days of high-rated
conversations, identifies winning patterns, generates improved prompts, opens PR if
changes are significant.

**Renewal Alerts Checker** — every 12 hours. Checks practices expiring in 90/60/30 days,
creates `renewal_alerts` records if not already present; picked up by notification system.

**Birthday Notifier** — every 24h (~08:00 Bali time, `services/crm/birthday_notifier_service.py`). Sends personalized email in client's language (IT/EN/ID/UK/RU). Via Zoho Mail.

**Conversation Cleanup** — every 24h. Anonymizes data older than 7 days, deletes conversations older than 30 days (GDPR compliance).

**Golden Routes Seeder** — one-time at application startup. Seeds common query patterns to `golden_routes` for faster routing.

### Background Services (2)

**Health Monitor** — every 60 seconds. Checks all external services (Qdrant, PostgreSQL, AI
Router, Tools); sends Telegram alerts on issues.

**Auto-Logout Monitor** — continuous. Monitors team member activity, auto-logs out inactive
members after timeout.

---

## Ollama Model Requirements

### Pro — Required Models

| Model               | RAM (warm)       | Warm H24?      | Consumers                                              |
| ------------------- | ---------------- | -------------- | ------------------------------------------------------ |
| qwen3.5:9b          | ~9GB (32K ctx)   | YES            | OpenClaw 15 cron + Cell Tier 0 + backend-rag FAST      |
| gemma4:26b          | ~23GB (256K ctx) | No (on-demand) | translate-articles (→ e4b), backend-rag KG/JSON, Cell  |
| gemma4:e4b          | ~10GB            | No (on-demand) | translate-articles (new default)                       |
| qwen2.5vl:7b        | ~5GB             | No (on-demand) | backend-rag VISION                                     |
| deepseek-r1:32b     | ~20GB            | No (on-demand) | backend-rag HEAVY                                      |
| ~~qwen2.5-coder~~   | —                | —              | DEAD — not installed, LaunchAgent not loaded           |

### Air — Required Models

| Model           | RAM (warm)      | Warm H24? | Consumers                         |
| --------------- | --------------- | --------- | --------------------------------- |
| qwen3:4b        | ~3.2GB (4K ctx) | YES       | OpenClaw 12 cron + Cell sentry    |
| ~~qwen3.5:27b~~ | —               | —         | NEVER INSTALLED — remove from cfg |
| ~~qwen3.5:9b~~  | —               | —         | NEVER INSTALLED — remove from cfg |

### Cloud / CLI (zero local RAM)

| Model / Interface      | How                 | Consumers                          |
| ---------------------- | ------------------- | ---------------------------------- |
| claude CLI (OAuth)     | Subprocess          | Sentinel classifier, DLQ Autopilot |
| gemini CLI             | Subprocess          | Gap scanner remediate, dispatch    |
| gemini-3-flash-preview | Gemini API (Fly.io) | backend-rag RAG primary            |
| text-embedding-3-small | OpenAI API          | RAG canary, embedding              |
| NLM notebooks          | nlm CLI (cloud)     | 18+ NLM pipeline cron jobs         |

---

## 24h Timing (Zero RAM Conflict)

### Pro — Timeline 24h (WITA)

```
00:00 ┌─ qwen3.5:9b WARM H24 (9GB) ──────────────────────────────────────────┐
      │ nightlies: NLM pipelines (cloud, 0 RAM local)                         │
01:00 │ nlm-deep-research (skipped)                                           │
02:00 │ conversation-cleanup, NLM nb2-nb10 (cloud)                            │
03:00 │ fly-backup (SHELL), weekly-dep-audit (Mon), t4-monitor                │
04:00 │ mos-maintenance (SHELL), nlm-nb1-refresh                              │
05:00 │ kb-ingest (SHELL)                                                     │
06:00 │                                                                       │
07:00 │ cert-monitor (SHELL)                                                  │
08:00 │ daily-ops, expiry-alerter, sync-ruslana                               │
      │ ┌── gemma4:e4b LOAD (translate :30) ~10GB ─── UNLOAD 10min idle ──┐  │
09:00 │ │ indexing-daily, seo-guardian-weekly (Mon), weekly-review (Mon)    │  │
10:00 │ │                                                                   │  │
      │ └──────────────────────────────────────────────────────────────────┘  │
      │ (translate every hour :30 → e4b load/unload, ~5s cold, OK)            │
14:00 │ client-health-monitor                                                 │
      │ seo-guardian-observe every 40min (warm model, instant)                │
      │ system-doctor every 4h (warm model)                                   │
      │ tech-orchestrator every 4h (warm model)                               │
      │ compliance-ops every 6h (warm model)                                  │
19:00 │ bali-zero-akta overnight (SHELL, 0 RAM)                              │
20:00 │ NLM nb1-refresh (cloud), NLM gap scanner (cloud)                     │
21:00 │ NLM freshness monitor (cloud)                                         │
22:00 │ NLM multimodal (cloud)                                                │
23:00 │ learning-pipeline (Sun), automations-reference                        │
00:00 └──────────────────────────────────────────────────────────────────────┘

Max RAM simultaneous: 9GB (warm) + 10GB (translate e4b) = 19GB of 48GB. OK.
Worst case: 9GB + 23GB (KG query during translate) = 32GB of 48GB. Still OK.
```

### Air — Timeline 24h (WITA)

```
00:00 ┌─ qwen3:4b WARM H24 (3.2GB) ────────────────────────────────────────┐
      │ notifiers (API, 0 RAM), welcome-pending */15min (API)                │
01:00 │ ollama-cron-window start (loads qwen2.5 for auto_test 02:15)        │
02:00 │ auto_test.sh (Ollama qwen2.5 + qwen3:4b coexist: 3.2+3=6.2GB)      │
03:00 │ auto_sentinel (SHELL), fly-pg-backup (SHELL)                         │
04:00 │ qdrant-snapshot (Sun, SHELL)                                         │
05:00 │ kb-ingest (SHELL)                                                    │
06:00 │ ollama-cron-window stop (unloads qwen2.5, qwen3:4b stays warm)      │
      │ ragas_eval (Sat, Python)                                             │
07:00 │                                                                      │
08:00 │ system_doctor (no direct LLM), drive_watchdog                        │
09:00 │ job_health (SHELL)                                                   │
      │ OpenClaw: fly-health every 30min, ecosystem every 6h                 │
      │ OpenClaw: intel-pipeline, normativa-daily, codebase-audit            │
16:00 │ auto_judgement_day (Sun, RAGAS)                                      │
20:00 │ db-nlm-sync (NLM cloud)                                             │
23:00 │ crm-automation (API), lkpm-notifier (API)                           │
00:00 └────────────────────────────────────────────────────────────────────┘

Max RAM simultaneous: 3.2GB (warm) + 3GB (qwen2.5 test window 01-06) = 6.2GB of 16GB.
Outside test window: 3.2GB only. 12.8GB free for OS+PG+Redis+services.
```

---

## Scars & Notes

### Ollama Operational Scars

1. **qwen3.5:9b tool-calling in Ollama is broken** ([#14493](https://github.com/ollama/ollama/issues/14493)) — but OpenClaw cron jobs do NOT use the `tools` parameter; they use text messages. No impact.
2. **gemma4:12b does not exist** — Gemma 4 only has e2b/e4b/26b/31b variants.
3. **Ollama MLX** on Pro (48GB >= 32GB): ~65-80 tok/s. Air (16GB): does not qualify, stays Metal.
4. **Ollama memory fragmentation** after 3-7 days — weekly restart scheduled Sun 05:00 on Air (and Pro via cron).
5. **Air Python `urllib` Connection Refused** on `localhost:11434` — always use `127.0.0.1` or subprocess curl.

### Critical Ollama Config

| Parameter                   | Value          | Reason                                                             |
| --------------------------- | -------------- | ------------------------------------------------------------------ |
| Pro qwen3.5:9b `keep_alive` | -1 (forever)   | Never unloaded, 0s cold start                                      |
| Air qwen3:4b `keep_alive`   | -1 (forever)   | Never unloaded, 0s cold start                                      |
| Pro gemma4:e4b `keep_alive` | 10m            | Unloads after translate, 5s cold start acceptable                  |
| Pro gemma4:26b `keep_alive` | 10m            | On-demand for KG, 15s cold start acceptable                        |
| All Ollama consumers        | `think: false` | qwen3/3.5 produces thinking tags, content empty without this flag  |
| All Ollama consumers        | `format: json` | Forces valid JSON output where needed                              |
| All Ollama API calls        | `keep_alive: -1` in every request | Prevents timer-reset bug (#5272)              |
| Air Python scripts          | `http://127.0.0.1:11434`          | IPv4/IPv6 issue: Python fails to connect via `localhost` |

### CRM Operational Notes

**Email sending:** All CRM automated emails go via Zoho Mail API (`zero@balizero.com`),
SMTP fallback (`smtppro.zoho.com:587`). Note: global system email rule uses
`zantara@balizero.com` (Brevo) — CRM flows above predate that rule and have not
been migrated. Verify before changing.

**Drive folders:** Individual clients → `Individual_CRM` folder
(`1mNi2FkhZqP9inJH2Y1taXLCgS95UkYk4`). Companies → `Company_CRM` folder
(`1rLlr2G7TdNUmmvQ_xN9pZQLbPrDFjUsW`).

**Telegram notifications:** Sent via Telegram Bot to assigned team members for new leads
and to clients for urgent deadlines (<=7 days).

---

## References

- `scripts/automation_catalog.json` — machine-readable source of truth for all jobs
- `docs/AUTOMATIONS_REFERENCE.md` — live system health snapshot (auto-generated nightly 23:15 WITA by `scripts/generate_automations_reference.py`; do not edit or archive)
- Archived predecessors: `docs/archive/ACTIVE_AUTOMATIONS.md`, `docs/archive/AUTOMATION_MODEL_MAP.md`
