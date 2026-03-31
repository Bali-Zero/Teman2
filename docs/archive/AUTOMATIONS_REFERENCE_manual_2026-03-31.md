# NUZANTARA — AUTOMATIONS REFERENCE

**Documento di riferimento definitivo per tutte le automazioni di sistema**

> **Versione:** 2.1
> **Data:** 2026-03-31 (v2.1 — audit accurato Pro/Air: PID reali, schedule corretti, ComfyUI broken, ai.openclaw.tunnel aggiunto)
> **Macchine:** Air (antonellosiano@Nuzantara-9) + Pro (nuzantara@Nuzantara)
> **Fonti:** crontab Pro+Air + plutil plist + codice sorgente + Explore agent + **Codex GPT-5.4** + **DeepSeek R1 671b**

---

## INDICE

1. [Topologia Oraria](#1-topologia-oraria)
2. [LaunchD — Air (Always-On)](#2-launchd-macos-air--always-on)
3. [LaunchD — Pro (Always-On)](#3-launchd-macos-pro--always-on)
4. [Cron Jobs (Air)](#4-cron-jobs-air)
5. [Cron Jobs (Pro)](#5-cron-jobs-pro)
6. [Intel Scraper + War Room Pipeline](#6-intel-scraper--war-room-pipeline)
7. [Core Guardian V3](#7-core-guardian-v3)
8. [FastAPI Autonomous Scheduler (Fly.io)](#8-fastapi-autonomous-scheduler-flyio)
9. [APScheduler — Notification Scheduler (Fly.io)](#9-apscheduler--notification-scheduler-flyio)
10. [GitHub Actions (CI/CD)](#10-github-actions-cicd)
11. [OpenClaw Agents](#11-openclaw-agents)
12. [MCP Workflow Chains](#12-mcp-workflow-chains)
13. [PostgreSQL Triggers (Fly.io DB)](#13-postgresql-triggers-flyio-db)
14. [Webhook Handlers (Event-Driven)](#14-webhook-handlers-event-driven)
15. [Script Locali (Manuali / On-Demand)](#15-script-locali-manuali--on-demand)
16. [Anomalie e Fix](#16-anomalie-e-fix)
17. [Criticità e Rischi](#17-criticità-e-rischi)
18. [Mappa di Priorità](#18-mappa-di-priorità)

---

## 1. TOPOLOGIA ORARIA

Visualizzazione consolidata di TUTTI i job schedulati (Air + Pro + Fly.io), per ora WITA (UTC+8):

```
WITA     UTC      MACCHINA  JOB
------   ------   --------  -------------------------------------------------------
00:30    16:30    Air       RAG Canary #1 (embedding drift)
01:00    17:00    Air       [CRON] Ollama Start
01:00    17:00    Pro       [LAUNCHD] Intel Scraper + War Room nightly (com.balizero.intel.nightly)
02:00    18:00    Air       [LAUNCHD] Nightly Git Sync (Air→Pro)
02:15    18:15    Air       [CRON] Auto Test Suite
02:20    18:20    Pro       [CRON] NLM NB4 Pipeline (Lun-Sab)
02:30    18:30    Air       RAG Canary #2
02:30    18:30    Pro       [CRON] NLM NB6 Pipeline (Lun-Sab)
02:40    18:40    Pro       [CRON] NLM NB8 Pipeline (Lun-Sab)
02:50    18:50    Pro       [CRON] NLM NB10 Pipeline (Lun-Sab)
03:00    19:00    Air       [CRON] Sentinel → Core Guardian Watchdog
03:00    19:00    Pro       [CRON] fly-backup.sh (pg_dump → Tigris)
04:30    20:30    Pro       [CRON] NLM NB-1 Daily Bundle Refresh
05:00    21:00    Air       [CRON] KB Ingest
06:00    22:00    Air       [LAUNCHD] Weekly Cleanup (Dom only)
06:05    22:05    Air       [CRON] Ollama Stop
06:30    22:30    Air       RAG Canary #3
06:30    22:30    Pro       [CRON] YT Monitor (ogni 6h)
07:00    23:00    Air       [CRON] CRM Automation Engine
08:00    00:00    Air       [CRON] System Doctor (daily report)
08:00    00:00    Air       Drive Token Watchdog #3
09:00    01:00    Fly.io    [FASTAPI] Notification Daily Check (APScheduler)
09:00    01:00    Air       [CRON] SEO Guardian (KBLI indexing)
10:00    02:00    Pro       [CRON] KG Builder (settimanale Dom)
10:00    02:00    Pro       [CRON] Conversation Trainer (settimanale Dom)
12:30    04:30    Air       RAG Canary #4
14:00    06:00    Air       Drive Token Watchdog #4
16:00    08:00    Air       [CRON] Judgement Day (Dom only)
18:00    10:00    Pro       [CRON] NLM NB5 T4 Monitor (Mar+Gio)
Dom06:00 Sab22:00 Air       [CRON] RAGAS Eval settimanale
Dom13:30 Dom05:30 Pro       [CRON] Peraturan Ingestion settimanale
*/5min   */5min   Pro       [CRON] Drive Poll + Intel Sentinel Bridge
*/5min   */5min   Fly.io    [FASTAPI] Self-Healing Agent
*/30min  */30min  Air       [LAUNCHD] Docker Health Check
*/1h     */1h     Fly.io    [FASTAPI] Notification Pending Send
*/6h     */6h     Air       NLM T4 Monitor, Drive Watchdog, RAG Canary
*/30m    7-19WITA Pro       [CRON] Fly.io Health Check
On-push  On-push  GitHub    [GH ACTIONS] Tests, Deploy, Security
On-msg   On-msg   Fly.io    [WEBHOOK] WhatsApp, Telegram, Instagram, Web
```

---

## 2. LAUNCHD (macOS Air — Always-On)

Servizi gestiti da macOS launchd. Persistono dopo reboot.
File: `~/Library/LaunchAgents/`

### 2.1 OpenClaw Node Host

| Campo        | Valore                                                                                              |
| ------------ | --------------------------------------------------------------------------------------------------- |
| **ID**       | `ai.openclaw.node`                                                                                  |
| **Schedule** | Always-On (KeepAlive=true)                                                                          |
| **Comando**  | `node ~/.npm-global/lib/node_modules/openclaw/dist/index.js node run --host 127.0.0.1 --port 18789` |
| **Cosa fa**  | Runtime OpenClaw (agent orchestrator). Gateway su `localhost:18789`. 129 MCP tools via mcporter.    |
| **Macchina** | Air                                                                                                 |
| **Stato**    | ✅ ATTIVO                                                                                           |
| **Log**      | `/tmp/openclaw/`                                                                                    |
| **Note**     | v2026.2.25. Se muore: tutti gli agenti AI e MCP tools diventano non disponibili.                    |

### 2.2 CELL Organism (AI Agent Loop)

| Campo        | Valore                                                                  |
| ------------ | ----------------------------------------------------------------------- |
| **ID**       | `com.cell.organism`                                                     |
| **Schedule** | Always-On (KeepAlive=true, RunAtLoad=true)                              |
| **Comando**  | `apps/cell/.venv/bin/python -m cell.main`                               |
| **Cosa fa**  | Agente CELL autonomo — Health RED quando sia Qwen che Gemini falliscono |
| **Macchina** | Air                                                                     |
| **Stato**    | ⚠️ ATTIVO ma Health=RED (segnalato nei messaggi di sistema)             |
| **Log**      | `/tmp/cell.stdout.log`, `/tmp/cell.stderr.log`                          |
| **Env**      | `CELL_BACKEND_HEALTH_URL`, `CELL_TELEGRAM_CHAT_ID=1125336968`           |

### 2.3 Claude Max API

| Campo        | Valore                                     |
| ------------ | ------------------------------------------ |
| **ID**       | `com.claude-max-api`                       |
| **Schedule** | Always-On (KeepAlive=true, RunAtLoad=true) |
| **Comando**  | `~/.npm-global/bin/claude-max-api`         |
| **Cosa fa**  | Bridge API per accesso Claude Max          |
| **Macchina** | Air                                        |
| **Stato**    | ✅ ATTIVO                                  |
| **Log**      | `/tmp/claude-max-api.log`                  |

### 2.4 OpenClaw Monitor Pro

| Campo        | Valore                                                |
| ------------ | ----------------------------------------------------- |
| **ID**       | `com.openclaw.monitor-pro`                            |
| **Schedule** | Ogni 300s (5 min)                                     |
| **Script**   | `~/.openclaw/scripts/monitor-pro.sh`                  |
| **Cosa fa**  | SSH ping a Pro — controlla raggiungibilità e sync git |
| **Macchina** | Air                                                   |
| **Stato**    | ✅ ATTIVO                                             |
| **Log**      | `/tmp/openclaw/monitor-pro-stdout.log`                |

### 2.5 Nightly Git Sync

| Campo        | Valore                                                       |
| ------------ | ------------------------------------------------------------ |
| **ID**       | `com.nuzantara.nightly-sync`                                 |
| **Schedule** | 02:30 WITA (18:30 UTC)                                       |
| **Script**   | `scripts/nz-nightly.sh`                                      |
| **Cosa fa**  | `git pull pro main --ff-only` → sync Air con Pro             |
| **Macchina** | Air                                                          |
| **Stato**    | ✅ ATTIVO (era ERR=127 — script mancante, fixato 2026-03-31) |
| **Log**      | `/tmp/nuzantara-nightly-sync.log`                            |

### 2.6 Docker Health Check

| Campo        | Valore                                                                           |
| ------------ | -------------------------------------------------------------------------------- |
| **ID**       | `com.user.docker-health-check`                                                   |
| **Schedule** | Ogni 1800s (30 min, RunAtLoad=true)                                              |
| **Script**   | `~/scripts/docker-health-check.sh`                                               |
| **Cosa fa**  | Controlla salute homebrew services: PostgreSQL 17, Redis + qdrant via curl :6333 |
| **Macchina** | Air                                                                              |
| **Stato**    | ✅ ATTIVO (era ERR=127 — script mancante, fixato 2026-03-31)                     |
| **Log**      | `~/scripts/docker-health-stderr.log`                                             |

### 2.7 Weekly Cleanup

| Campo        | Valore                                          |
| ------------ | ----------------------------------------------- |
| **ID**       | `com.user.weekly-cleanup`                       |
| **Schedule** | Domenica 02:00 WITA                             |
| **Script**   | `~/scripts/cleanup-weekly.sh`                   |
| **Cosa fa**  | Pulizia directory tmp, log rotation, disk space |
| **Macchina** | Air                                             |
| **Stato**    | ✅ ATTIVO                                       |

### 2.8 Homebrew Services (Infrastruttura)

| ID                            | Servizio                   | Schedule  | Stato |
| ----------------------------- | -------------------------- | --------- | ----- |
| `homebrew.mxcl.postgresql@17` | PostgreSQL 17 (porta 5432) | Always-On | ✅    |
| `homebrew.mxcl.redis`         | Redis (porta 6379)         | Always-On | ✅    |
| `homebrew.mxcl.ollama`        | Ollama LLM server          | Always-On | ✅    |

### 2.9 Fly Postgres Tunnel (Always-On) ← NUOVO 2026-03-31

| Campo        | Valore                                                                                                                                             |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ID**       | `com.nuzantara.fly-pg-tunnel`                                                                                                                      |
| **Schedule** | Always-On (KeepAlive=true, ThrottleInterval=10s)                                                                                                   |
| **Comando**  | `fly proxy 15432:5432 -a nuzantara-postgres --bind-addr 127.0.0.1`                                                                                 |
| **Cosa fa**  | Mantiene `localhost:15432` sempre aperto → consente a `crm_automation_engine.py` e altri script di connettersi a Fly Postgres senza tunnel manuale |
| **Macchina** | Air                                                                                                                                                |
| **Stato**    | ✅ ATTIVO                                                                                                                                          |
| **Log**      | `logs/fly-pg-tunnel.log`                                                                                                                           |
| **Plist**    | `scripts/launchd/com.nuzantara.fly-pg-tunnel.plist`                                                                                                |

---

## 3. LAUNCHD (macOS Pro — Always-On)

Servizi gestiti da macOS launchd su **Pro** (`nuzantara@Nuzantara`).
File: `/Users/nuzantara/Library/LaunchAgents/`

| ID                                    | Cosa fa                                                            | Schedule                   | Stato                                                                      |
| ------------------------------------- | ------------------------------------------------------------------ | -------------------------- | -------------------------------------------------------------------------- |
| `com.balizero.intel.nightly`          | **Intel Scraper + War Room** — pipeline completa nightly (vedi §6) | 01:00 WITA                 | ✅ ATTIVO                                                                  |
| `com.balizero.nlm-bridge`             | NLM Bridge — stato NotebookLM sync                                 | Always-On (KeepAlive=true) | ✅ PID=15346                                                               |
| `com.balizero.post-publish-webhook`   | Post-publish webhook — notifica dopo publish articolo              | Always-On (KeepAlive=true) | ✅ PID=4213                                                                |
| `com.balizero.post-publish-poller`    | Poller articoli pubblicati                                         | Scheduled (ogni ora)       | ⚠️ PID=- (on-demand)                                                       |
| `com.balizero.client-value-predictor` | Predittore valore clienti                                          | 09:00 WITA daily           | ⚠️ PID=- (scheduled)                                                       |
| `com.balizero.comfyui-server`         | ComfyUI image generation server                                    | KeepAlive (cond.)          | ❌ STATUS=78 (app crash loop — `/Applications/ComfyUI.app` non installata) |
| `com.balizero.renewal-alerts`         | Alert rinnovi (visa/passport)                                      | 08:00 WITA daily           | ⚠️ PID=- → script: `openclaw-cron/renewal-alerts.sh`                       |
| `com.balizero.translate.hourly`       | Traduzione automatica articoli                                     | Ogni ora al :30            | ⚠️ PID=- (scheduled)                                                       |
| `com.balizero.backend-prewarm`        | Prewarm Fly.io backend (cold start prevention)                     | Più volte/die a ore fisse  | ⚠️ PID=- → curl a `/api/health`                                            |
| `com.nuzantara.dlq-autopilot`         | Dead Letter Queue autopilot — retry job falliti                    | Ogni 1800s (30min)         | ✅ PID=- (runs + exits, `~/scripts/dlq_autopilot.py`)                      |
| `com.nuzantara.prime-dashboard`       | Prime dashboard server                                             | Always-On                  | ✅ PID=4200                                                                |
| `com.nuzantara.prime-tunnel`          | Prime tunnel (prime.balizero.com backend)                          | Always-On                  | ✅ PID=4199                                                                |
| `com.nuzantara.qwen-code-review`      | Code review automatico con Qwen                                    | 10:00 WITA daily           | ⚠️ PID=- (scheduled)                                                       |
| `com.nuzantara.sentinel`              | Sentinel Pro (`nuzantara-sentinel.py`)                             | Ogni 300s (5min)           | ✅ PID=92155                                                               |
| `com.nuzantara.vector-reindex-check`  | Verifica coerenza indici Qdrant                                    | Scheduled                  | ⚠️ PID=-                                                                   |
| `com.nuzantara.zombie-hunter`         | Elimina processi zombie (`~/.claude/scripts/zombie-hunter.sh`)     | Ogni 60s                   | ✅ PID=- (runs + exits)                                                    |
| `com.cell.organism`                   | CELL Organism AI agent                                             | Always-On                  | ✅ PID=57903                                                               |
| `com.claude-max-api`                  | Claude Max API bridge                                              | Always-On                  | ✅ PID=4214                                                                |
| `ai.openclaw.gateway`                 | OpenClaw gateway Pro                                               | Always-On                  | ✅ ATTIVO                                                                  |
| `ai.openclaw.tunnel`                  | OpenClaw tunnel Pro (KeepAlive=true)                               | Always-On                  | ✅ PID=4220                                                                |
| `ai.openclaw.monitor-air`             | Monitor Air da Pro                                                 | Ogni 5min                  | ✅ ATTIVO                                                                  |
| `homebrew.mxcl.postgresql@17`         | PostgreSQL 17 locale Pro                                           | Always-On                  | ✅                                                                         |
| `homebrew.mxcl.redis`                 | Redis locale Pro                                                   | Always-On                  | ✅                                                                         |
| `homebrew.mxcl.ollama`                | Ollama Pro (qwen3.5:27b ecc.)                                      | Always-On                  | ✅                                                                         |

> **Nota:** PID=- per job scheduled (runs to completion, non KeepAlive) è **normale** — il job gira e poi esce. ❌ STATUS=78 = crash loop (app non installata/broken). KeepAlive=true = si riavvia sempre.

---

## 4. CRON JOBS (Air)

File: `crontab -l` su Air. Log in `~/Projects/nuzantara/logs/`.

### 3.1 Infrastruttura AI (Ollama Window)

| Job              | Cron        | Schedule WITA | Script                                | Cosa fa                                                     |
| ---------------- | ----------- | ------------- | ------------------------------------- | ----------------------------------------------------------- |
| **Ollama Start** | `0 1 * * *` | 01:00         | `scripts/ollama_cron_window.sh start` | Avvia Ollama per batch notturno (test, sentinel, KB ingest) |
| **Ollama Stop**  | `5 6 * * *` | 06:05         | `scripts/ollama_cron_window.sh stop`  | Safety net: ferma Ollama dopo tutti i task notturni         |

**Note:** Ollama gira `localhost:11434`. Durante la window 01:00-06:05 è disponibile per tutti i cron.

### 3.2 Quality & Testing

| Job           | Cron         | Schedule WITA | Script                     | Cosa fa                                                     |
| ------------- | ------------ | ------------- | -------------------------- | ----------------------------------------------------------- |
| **Auto Test** | `15 2 * * *` | 02:15         | `scripts/auto_test.sh`     | Backend pytest, import chain check, report Telegram se fail |
| **Sentinel**  | `0 3 * * *`  | 03:00         | `scripts/auto_sentinel.sh` | Auto-repair broken jobs: detect errori, patch, retry        |

### 3.3 Data Collection

| Job           | Cron        | Schedule WITA | Script                      | Cosa fa                                                   |
| ------------- | ----------- | ------------- | --------------------------- | --------------------------------------------------------- |
| **KB Ingest** | `0 5 * * *` | 05:00         | `scripts/auto_kb_ingest.sh` | Ingest knowledge base: visa + peraturan + putusan spiders |

> **Note:** Unified Scraper (609 fonti) e Visa Agent sono in crontab ma i comandi sono commentati. Runnano su Pro via OpenClaw (03:00 WITA Pro).

### 3.4 CRM Automation

| Job                       | Cron         | Schedule WITA | Script                                              | Cosa fa                                                                           |
| ------------------------- | ------------ | ------------- | --------------------------------------------------- | --------------------------------------------------------------------------------- |
| **CRM Automation Engine** | `0 23 * * *` | 07:00 (+1d)   | `apps/backend-rag/scripts/crm_automation_engine.py` | 4 moduli: quality fixes, doc checklists, renewals, stale detection. ~805 fix/run. |

### 3.5 Monitoring & Reports

| Job                | Cron           | Schedule WITA              | Script                                                       | Cosa fa                                                                                 |
| ------------------ | -------------- | -------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| **RAG Canary**     | `30 */6 * * *` | 00:30, 06:30, 12:30, 18:30 | `scripts/rag_canary.py`                                      | Embedding drift detection + golden query regression. Alert se drift > threshold.        |
| **System Doctor**  | `0 8 * * *`    | 08:00                      | `scripts/system_doctor.py --notify-telegram`                 | Health check completo: backend, frontend, Fly.io, SSL, logs. Report mattutino Telegram. |
| **Drive Watchdog** | `0 */6 * * *`  | 02:00, 08:00, 14:00, 20:00 | `scripts/drive_token_watchdog.py`                            | Monitora scadenza OAuth token Google Drive. Alert Telegram 7gg prima scadenza.          |
| **NLM T4 Monitor** | `0 */6 * * *`  | 02:00, 08:00, 14:00, 20:00 | `apps/evaluator/nlm_deep_research/scripts/run_t4_monitor.sh` | NotebookLM T4 social media monitor.                                                     |
| **SEO Guardian**   | `0 1 * * *`    | 09:00                      | `apps/evaluator/seo_guardian_agent.py --observe-first`       | KBLI indexing submit + SEO/GEO audit. 420/1563 KBLI URL indicizzate.                    |
| **RAGAS Eval**     | `0 6 * * 0`    | Dom 06:00                  | `scripts/ragas_eval.py`                                      | Valutazione qualità RAG settimanale (RAGAS metrics).                                    |
| **Judgement Day**  | `0 16 * * 0`   | Dom 16:00                  | `scripts/auto_judgement_day.sh`                              | Weekly rollup: 7gg di stats, anomalie, report email/Telegram.                           |

---

## 5. CRON JOBS (Pro)

File: `crontab -l` su Pro (`nuzantara@Nuzantara`). Log in `/tmp/cron-*.log` e `~/logs/`.

| Job                        | Cron              | Schedule WITA              | Script                                               | Cosa fa                                                                     |
| -------------------------- | ----------------- | -------------------------- | ---------------------------------------------------- | --------------------------------------------------------------------------- |
| **Fly Health Check**       | `*/30 7-19 * * *` | 07:00-19:00 ogni 30min     | `~/scripts/fly-health-check.sh`                      | Ping Fly.io health, alert Telegram se down                                  |
| **Drive Poll**             | `*/5 * * * *`     | ogni 5min                  | `~/scripts/openclaw-cron/drive-poll.sh`              | Google Drive changes poll, page_token in DB                                 |
| **Intel Sentinel Bridge**  | `*/5 * * * *`     | ogni 5min                  | `~/scripts/intel-scraper-sentinel-bridge.sh`         | Monitora log intel scraper + War Room, scrive heartbeat                     |
| **Pro Heartbeat**          | `0 * * * *`       | ogni ora :00               | inline `touch + ssh air`                             | Pro e Air si pingano reciprocamente                                         |
| **Fly Backup**             | `0 3 * * *`       | 03:00                      | `~/scripts/fly-backup.sh`                            | pg_dump Fly Postgres → Tigris `nuzantara-backups`                           |
| **NLM NB-1 Daily Refresh** | `30 4 * * *`      | 04:30                      | `scripts/nlm_nb1_daily_refresh.py`                   | NotebookLM NB-1 bundle aggiornamento giornaliero                            |
| **Expiry Alerter**         | `0 8 * * *`       | 08:00                      | `scripts/expiry_alerter.py`                          | Alert scadenza passport/visa clienti (ridondante con APScheduler ma su Pro) |
| **Legal Radar**            | `0 0 * * 0`       | Dom 08:00                  | `scripts/legal_radar.py`                             | Monitora nuove leggi indonesiane (UU, PP, Permen)                           |
| **KG Builder**             | `0 2 * * 0`       | Dom 02:00                  | `~/scripts/openclaw-cron/knowledge-graph-builder.sh` | Rebuild Knowledge Graph settimanale (56K nodi, 161K edges)                  |
| **Conversation Trainer**   | `0 3 * * 0`       | Dom 03:00                  | `~/scripts/openclaw-cron/conversation-trainer.sh`    | Fine-tuning conversazionale su dati settimana                               |
| **YT Monitor**             | `30 */6 * * *`    | 06:30, 12:30, 18:30, 00:30 | `run_yt_monitor.sh`                                  | Monitora canali YouTube per immigration content (NLM NB-2)                  |
| **NLM NB4 Pipeline**       | `20 2 * * 1-6`    | 02:20 (Lun-Sab)            | `run_nb4_pipeline.sh`                                | NotebookLM NB-4 research pipeline notturna                                  |
| **NLM NB5 T4 Monitor**     | `0 18 * * 2,4`    | 18:00 (Mar+Gio)            | `run_nb5_t4_monitor.sh`                              | NB-5 gap analysis T4 monitor (Mar e Gio)                                    |
| **NLM NB6 Pipeline**       | `30 2 * * 1-6`    | 02:30 (Lun-Sab)            | `run_nb6_pipeline.sh`                                | NotebookLM NB-6 pipeline                                                    |
| **NLM NB8 Pipeline**       | `40 2 * * 1-6`    | 02:40 (Lun-Sab)            | `run_nb8_pipeline.sh`                                | NotebookLM NB-8 pipeline                                                    |
| **NLM NB10 Pipeline**      | `50 2 * * 1-6`    | 02:50 (Lun-Sab)            | `run_nb10_pipeline.sh`                               | NotebookLM NB-10 pipeline                                                   |
| **Peraturan Ingestion**    | `30 21 * * 0`     | Dom 05:30 (+1d)            | `run_peraturan_ingestion.sh`                         | Ingest peraturan (leggi) in Qdrant settimanale                              |
| **NLM Bridge Heartbeat**   | `*/4 * * * *`     | ogni 4min                  | inline JSON write                                    | Scrive heartbeat JSON per NLM bridge state                                  |
| **OpenClaw State Bridge**  | `*/5 * * * *`     | ogni 5min                  | `~/scripts/openclaw-state-bridge.py`                 | Sincronizza stato agenti OpenClaw                                           |
| **LaunchAgent Bridge**     | `*/5 * * * *`     | ogni 5min                  | `~/scripts/launchagent-state-bridge.py`              | Sincronizza stato LaunchAgents                                              |
| **Cache Cleanup**          | `30 3 1,15 * *`   | 1° e 15 ore 03:30          | inline npm+pip+brew                                  | Pulizia cache npm, pip, brew ogni 2 settimane                               |

---

## 6. INTEL SCRAPER + WAR ROOM PIPELINE

**La pipeline nightly più importante del sistema.** Gestita da `com.balizero.intel.nightly` su Pro.

### Architettura

```
LaunchD 01:00 WITA
    │
    ├── Step 1: Intel Scraper (apps/bali-intel-scraper/)
    │   ├── 609 fonti aggregate (news + gov sites + social)
    │   ├── scripts/run_intel_pipeline.py --mode full --limit 15
    │   ├── AI enrichment (Gemini Flash + sentiment + entità)
    │   └── Push a staging queue (DB) per review umano
    │
    └── Step 2: War Room (apps/war-room/)
        ├── pipeline.sh --auto
        ├── agents: 00_topic_selector → 01_grok_scraper → 01_chatgpt_researcher
        │          → 02_gemini_researcher → 03_gemini_strategist → 04_claude_director
        │          → 05_gemini_images → 06_canva_builder → 07_delivery.sh
        └── Output: Canva design aggiornato + Telegram delivery al gruppo
```

### Intel Scraper (apps/bali-intel-scraper/)

| Campo        | Valore                                                                              |
| ------------ | ----------------------------------------------------------------------------------- |
| **Runtime**  | Pro locale via LaunchD (NON su Fly.io)                                              |
| **Schedule** | 01:00 WITA ogni notte                                                               |
| **Fonti**    | 609 aggregate: news indonesiani, siti governativi imigrasi, business registry       |
| **Pipeline** | Scrape → NLP filter → AI enrichment (Gemini Flash) → staging queue                  |
| **Sentinel** | `~/scripts/intel-scraper-sentinel-bridge.sh` ogni 5min legge log e scrive heartbeat |
| **Log**      | `~/.openclaw/workspace/logs/intel_nightly_YYYYMMDD.log`                             |
| **Env**      | `.env` in `apps/bali-intel-scraper/` (API keys, DB URL)                             |
| **Alert**    | Telegram group `-1003826235564` su failure                                          |

### War Room (apps/war-room/)

| Campo            | Valore                                                          |
| ---------------- | --------------------------------------------------------------- |
| **Trigger**      | Subito dopo Intel Scraper (step 2 dello stesso LaunchD job)     |
| **Agenti**       | 10 agenti in sequenza (AI multi-model pipeline)                 |
| **Output**       | Canva design + Telegram post al gruppo ops                      |
| **Lock**         | `/tmp/warroom_pipeline.lock` (previene doppia istanza)          |
| **Esecuzione**   | `pipeline.sh --auto` oppure `pipeline_v2.py "topic"` (A2A mode) |
| **Canva Design** | `DAHE6lx1lf8` (default, override con `CANVA_DESIGN_ID=`)        |
| **Log**          | `apps/war-room/logs/pipeline_YYYYMMDD_HHMMSS.log`               |

### Post-Publish Flow (Pro LaunchD)

| Componente                                      | Cosa fa                                              |
| ----------------------------------------------- | ---------------------------------------------------- |
| `com.balizero.post-publish-webhook` (Always-On) | Riceve webhook dopo publish articolo → notifica team |
| `com.balizero.post-publish-poller`              | Polling articoli pubblicati per analytics            |

---

## 7. CORE GUARDIAN V3

File: `apps/evaluator/core_guardian/`
**Runtime:** Cron Air (03:00 via `auto_sentinel.sh` → `sentinel` wrapper → `watchdog.py`)

### Architettura 3 livelli

| Livello           | File          | Frequenza                             | Modello          | Cosa fa                                                                                  |
| ----------------- | ------------- | ------------------------------------- | ---------------- | ---------------------------------------------------------------------------------------- |
| **Watchdog (L1)** | `watchdog.py` | ogni 30min (giorno) / ogni 2h (notte) | Python puro — $0 | pytest junitxml, confronto baseline.json, circuit breaker, Telegram alert se regressione |
| **Scout (L2)**    | `scout.py`    | On-demand / triggered da Watchdog     | Nessuno          | AST analysis: cache invalidation audit, unused imports, hardcoded secrets pattern        |
| **Surgeon (L3)**  | `surgeon.py`  | On-demand (worktree isolato)          | Locale (Qwen)    | Fix automatici deterministici: DTZ005, DTZ003, ANN204, ruff --fix                        |

### Componenti ausiliari

| File               | Scopo                                            |
| ------------------ | ------------------------------------------------ |
| `watchdog.py`      | Entry point cron — pytest + baseline tracking    |
| `cron_guardian.py` | Cron job guardian — monitora salute dei cron job |
| `learn.py`         | Apprende pattern dai fix per migliorare Scout    |
| `observe.py`       | Observer pattern — hook pre/post esecuzione      |
| `agent.py`         | Agente Core Guardian autonomo                    |
| `checks/`          | Check deterministici AST-based                   |

### Baseline e Metriche

| Metrica         | Baseline (2026-03-20)            |
| --------------- | -------------------------------- |
| Test passed     | 3,917                            |
| Ruff violations | 2,051                            |
| Baseline file   | `.agent/decisions/baseline.json` |

> **Nota:** Il Surgeon è lo step più aggressivo — opera in worktree isolato (`git worktree`), mai direttamente su `main`. I fix vengono proposti come PR o applicati solo se confidence > 0.95.

---

## 8. FASTAPI AUTONOMOUS SCHEDULER (Fly.io)

File: `apps/backend-rag/backend/services/misc/autonomous_scheduler.py`
Inizializzato in: `backend/app/setup/service_initializer.py`
**Vincolo critico:** `auto_stop=true` su Fly.io → solo task con interval ≤ 5min sopravvivono.

### Task ATTIVI (enabled=True)

| Nome                    | Interval          | Cosa fa                                                                                                                            | Stato                            |
| ----------------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| `self_healing`          | 5 min             | Backend self-healing agent. Detect + fix errori di servizio (DB conn, Redis, cache). Redis leader election (solo 1 worker esegue). | ✅ ATTIVO                        |
| `golden_routes_seeder`  | 1 anno (one-time) | Seed delle rotte golden per warm-up cache al primo avvio.                                                                          | ✅ ATTIVO (one-time)             |
| `birthplace_enrichment` | 24h               | Enrichment dati luogo nascita clienti tramite geocoding.                                                                           | ⚠️ ATTIVO ma a rischio auto_stop |
| `conversation_cleanup`  | 24h               | Pulizia conversazioni vecchie > 90gg.                                                                                              | ⚠️ ATTIVO ma a rischio auto_stop |
| `auto_ingestion`        | 24h               | Auto-ingestion documenti intel.                                                                                                    | ⚠️ ATTIVO ma a rischio auto_stop |

### Task DISABILITATI (enabled=False)

| Nome                   | Motivo disabilitazione                          | Covered by                           |
| ---------------------- | ----------------------------------------------- | ------------------------------------ |
| `conversation_trainer` | Git subprocess non funziona su Fly.io ephemeral | —                                    |
| `renewal_alerts`       | 12h > auto_stop uptime                          | OpenClaw `practice_lifecycle_check`  |
| `birthday_notifier`    | 24h > auto_stop uptime                          | OpenClaw `client_health_monitor`     |
| `daily_ops_autopilot`  | BUG: chiama localhost:8000 = se stesso          | OpenClaw `daily_ops_autopilot` chain |
| `drive_changes_poll`   | Fly.io auto_stop incompatibile con page_token   | Air cron (ogni 5min curl POST)       |

---

## 9. APSCHEDULER — NOTIFICATION SCHEDULER (Fly.io)

File: `apps/backend-rag/backend/app/modules/notifications/scheduler.py`
Classe: `NotificationScheduler`
**Tabella DB:** `notification_alerts` ← **migration_071** (applicata 2026-03-31)

### Job 1: Daily Expiry Check

| Campo          | Valore                                                                                                                           |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **ID**         | `daily_notification_check`                                                                                                       |
| **Schedule**   | 09:00 WITA (CronTrigger, Asia/Makassar)                                                                                          |
| **Cosa fa**    | Scansiona TUTTI i clienti → genera alert (passport/visa expiry, birthday) → salva in `notification_alerts` con dedup ON CONFLICT |
| **Lock**       | `asyncio.Lock()` (single execution per worker)                                                                                   |
| **Dipendenze** | `ExpiryChecker`, `AlertDeduplicator`, `get_clients_from_db`                                                                      |

### Job 2: Hourly Pending Send

| Campo              | Valore                                                                                                            |
| ------------------ | ----------------------------------------------------------------------------------------------------------------- |
| **ID**             | `hourly_pending_send`                                                                                             |
| **Schedule**       | Ogni ora :00 (CronTrigger `minute=0`)                                                                             |
| **Cosa fa**        | Legge tutti gli alert `status=pending` dal DB → invia email via SendGrid/SMTP → aggiorna status a `sent`/`failed` |
| **Lock**           | `asyncio.Lock()`                                                                                                  |
| **Provider email** | Brevo (xkeysib- key, alias `zantara@balizero.com`)                                                                |

---

## 10. GITHUB ACTIONS (CI/CD)

Directory: `.github/workflows/`

### 6.1 Deploy Backend to Fly.io

| Campo                | Valore                                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------------------ |
| **File**             | `fly-deploy.yml`                                                                                       |
| **Trigger**          | `push` → `main` (path: `apps/backend-rag/**`)                                                          |
| **Jobs**             | Pre-deploy gate → Run migrations → Rolling deploy → Post-deploy health (10 retry × 30s, auto-rollback) |
| **Notifiche**        | Telegram (success/failure)                                                                             |
| **Stato**            | ✅ ATTIVO                                                                                              |
| **Secrets required** | `FLY_API_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID`                                        |

### 6.2 Tests & Coverage

| Campo       | Valore                                                   |
| ----------- | -------------------------------------------------------- |
| **File**    | `tests.yml`                                              |
| **Trigger** | `push main/develop`, `pull_request`, `workflow_dispatch` |
| **Jobs**    | Backend pytest, Frontend vitest, E2E Playwright, Summary |
| **Stato**   | ✅ ATTIVO                                                |

### 6.3 Security Scanning

| Campo       | Valore                                                                                |
| ----------- | ------------------------------------------------------------------------------------- |
| **File**    | `security.yml`                                                                        |
| **Trigger** | `push`, `pull_request`, **schedule `0 0 * * 0`** (Dom 00:00 UTC), `workflow_dispatch` |
| **Jobs**    | Snyk Python, Snyk Node, OWASP, Dependency review                                      |
| **Stato**   | ✅ ATTIVO                                                                             |

### 6.4 SonarQube Analysis

| Campo       | Valore                                      |
| ----------- | ------------------------------------------- |
| **File**    | `sonarqube.yml`                             |
| **Trigger** | `push`, `pull_request`, `workflow_dispatch` |
| **Stato**   | ✅ ATTIVO                                   |

### 6.5 Intel Router Tests

| Campo       | Valore                                      |
| ----------- | ------------------------------------------- |
| **File**    | `intel-router-tests.yml`                    |
| **Trigger** | `push`, `pull_request`, `workflow_dispatch` |
| **Stato**   | ✅ ATTIVO                                   |

### 6.6 Docs Sync Check

| Campo       | Valore                                       |
| ----------- | -------------------------------------------- |
| **File**    | `docs-sync.yml`                              |
| **Trigger** | `push`, `pull_request`                       |
| **Cosa fa** | Verifica sincronizzazione docs tra Air e Pro |
| **Stato**   | ✅ ATTIVO                                    |

---

## 11. OPENCLAW AGENTS

Config: `~/.openclaw/openclaw.json`
Gateway: `localhost:18789`

| Agent         | Model                  | Ruolo                                       | Sandbox | Heartbeat | Stato     |
| ------------- | ---------------------- | ------------------------------------------- | ------- | --------- | --------- |
| **main**      | claude-opus-4-6        | Orchestratore principale, Telegram listener | off     | 1h        | ✅ ATTIVO |
| **coder**     | qwen3.5:27b (Ollama)   | Coding tasks locali, zero-cost              | off     | 0         | ✅ ATTIVO |
| **qa-visual** | gemini-3.1-pro-preview | QA visivo, review                           | off     | 0         | ✅ ATTIVO |

**MCP Bridge:** 129 tools via mcporter wrappers in `~/.local/bin/`
**Note critiche:**

- `main` è l'UNICO listener Telegram (@Balizerobot). Air e Fly.io mandano solo.
- Se OpenClaw muore → nessun AI su Telegram → alert tramite Telegram non funziona (paradosso).

---

## 12. MCP WORKFLOW CHAINS

File: `apps/nuzantara-mcp/nuzantara_mcp/workflows/chains.py`
Eseguiti via OpenClaw (mcporter) o manuale.

| Chain                            | Trigger                 | Steps                                                                        | Stato       |
| -------------------------------- | ----------------------- | ---------------------------------------------------------------------------- | ----------- |
| `chain_daily_ops_autopilot`      | OpenClaw cron / manuale | 5: expiry alerts → agent health → intel articles → team hours → email report | ✅ DEFINITA |
| `chain_new_client_onboarding`    | CRM new client          | 8: CRM → KBLI → visa → Drive folder → practice → plan → welcome → log        | ✅ DEFINITA |
| `chain_practice_lifecycle_check` | Ogni 6h (OpenClaw)      | 5: visa renewals, doc reminders, escalations, completion                     | ✅ DEFINITA |
| `chain_compliance_autopilot`     | Manuale / scheduled     | 5: critical alerts, urgent, auto-renewals, summary                           | ✅ DEFINITA |
| `chain_intel_pipeline`           | Post-scraper            | 6: submit → wait → review → approve → compose → report                       | ✅ DEFINITA |
| `chain_client_health_monitor`    | OpenClaw scheduled      | 5: value score, VIP nurture, high-risk, reminders, surveys                   | ✅ DEFINITA |
| `chain_journey_accelerator`      | User action             | 6: journey → pricing → Drive → compliance → welcome → orchestration          | ✅ DEFINITA |
| `chain_weekly_report`            | Dom mattina (OpenClaw)  | 6: CRM stats, revenue, team, intel trends, RAG perf, email                   | ✅ DEFINITA |

---

## 13. POSTGRESQL TRIGGERS (Fly.io DB)

Database: `nuzantara-postgres.flycast:5432/nuzantara_rag`

### 9.1 Client to Memory Sync

| Campo              | Valore                                                                                                         |
| ------------------ | -------------------------------------------------------------------------------------------------------------- |
| **Trigger**        | `AFTER INSERT OR UPDATE ON clients`                                                                            |
| **Cosa fa**        | Copia `assigned_to`, `status`, `tags` da `clients` → `user_stats.preferences` (JSONB) per fast frontend access |
| **File migration** | `migration_050_client_memory_sync.py`                                                                          |
| **Stato**          | ✅ ATTIVO                                                                                                      |

### 9.2 Lead Assignment Agent

| Campo       | Valore                                                                           |
| ----------- | -------------------------------------------------------------------------------- |
| **Trigger** | `asyncio.create_task()` post-INSERT in `AutoCRMService`                          |
| **Cosa fa** | LangGraph workflow: 1) dedup, 2) assign (specialty+workload), 3) notify Telegram |
| **File**    | `backend/services/crm/lead_assignment_agent.py`                                  |
| **Stato**   | ✅ ATTIVO (non-blocking)                                                         |

---

## 14. WEBHOOK HANDLERS (Event-Driven)

Tutti su Fly.io. Richiedono macchina attiva (cold start ~35s).

| Channel       | Endpoint                      | Trigger                     | Adapter                         | Stato                     |
| ------------- | ----------------------------- | --------------------------- | ------------------------------- | ------------------------- |
| **WhatsApp**  | `POST /api/whatsapp/webhook`  | Meta Cloud API incoming msg | `channels/whatsapp/adapter.py`  | ✅ LIVE                   |
| **Telegram**  | `POST /api/telegram/webhook`  | Telegram incoming (POST)    | `channels/telegram/adapter.py`  | ✅ LIVE (Air polls)       |
| **Instagram** | `POST /api/webhook/instagram` | Meta Instagram incoming     | `channels/instagram/adapter.py` | ✅ LIVE                   |
| **Web Chat**  | `POST /api/webhook/chat`      | Web chat submission         | `channels/web/adapter.py`       | ✅ LIVE                   |
| **X/Twitter** | `POST /api/webhook/twitter`   | Twitter incoming            | `channels/twitter/adapter.py`   | ❌ BROKEN (CRC auth fail) |

---

## 15. SCRIPT LOCALI (Manuali / On-Demand)

Scripts non schedulati, usati manualmente o da ai-dispatch.

| Script                       | Tipo          | Scopo                                                               |
| ---------------------------- | ------------- | ------------------------------------------------------------------- |
| `ai-dispatch.sh`             | Bash (56KB)   | Orchestratore AI: dispatch a Gemini, Codex, Claude, DeepSeek, Aider |
| `federation_orchestrator.py` | Python        | Orchestrazione multi-agent per task complessi                       |
| `nuzantara-sentinel.py`      | Python (23KB) | Sentinel avanzato: detect + fix pattern specifici                   |
| `dlq_autopilot.py`           | Python (20KB) | Dead Letter Queue autopilot: retry job falliti                      |
| `expiry_alerter.py`          | Python (16KB) | Expiry alerts manuale (test/debug del notification scheduler)       |
| `fly-pg-backup.sh`           | Bash          | pg_dump → Tigris `nuzantara-backups`. Schedulato su Pro.            |
| `fly-qdrant-backup.sh`       | Bash          | Qdrant snapshot backup. Schedulato su Pro.                          |
| `nlm_nb1_daily_refresh.py`   | Python (14KB) | NotebookLM NB-1 refresh (orario variabile)                          |
| `nlm_pipeline_run.sh`        | Bash          | Lancia NLM research pipeline completo                               |
| `preflight.sh`               | Bash          | Preflight SDD check (L1/L2/L3) prima di task non-triviali           |
| `ragas_eval.py`              | Python        | RAG evaluation con framework RAGAS (schedulato Dom)                 |
| `coverage_trend.py`          | Python        | Tracking trend test coverage nel tempo                              |
| `dep_audit.py`               | Python        | Audit dipendenze Python/Node                                        |
| `ux-audit.sh`                | Bash          | Audit UX su frontend                                                |
| `vector-reindex-check.py`    | Python        | Verifica coerenza indici vettoriali Qdrant                          |

---

## 16. ANOMALIE RILEVATE DA CODEX (verifica log reali — 2026-03-31)

> Codex GPT-5.4 ha letto i log effettivi in `logs/`. Questi sono problemi **confermati in produzione**.

### Job rotti / degradati (confermato da log)

> **Stato 2026-03-31:** 7 di 8 job fixati nel commit `8e9bce647f`. Rimane aperto: `crm_automation_engine.py` (tunnel DB).

| Job                          | Problema                                                           | Stato     | Fix applicato                                                                                                   |
| ---------------------------- | ------------------------------------------------------------------ | --------- | --------------------------------------------------------------------------------------------------------------- |
| **auto_sentinel.sh**         | Punta a `apps/core/sentinel.py` che non esiste                     | ✅ FIXATO | `sentinel` wrapper ora punta a `apps/evaluator/core_guardian/watchdog.py`                                       |
| **auto_kb_ingest.sh**        | Script Python target non presenti                                  | ✅ FIXATO | `run_if_exists()` wrapper — skip graceful con log se script mancante                                            |
| **auto_judgement_day.sh**    | `ragas` non installato nel venv Air                                | ✅ FIXATO | Check dipendenza prima del run, skip con messaggio di istruzioni                                                |
| **crm_automation_engine.py** | Usa `localhost:15432` (tunnel DB) invece del DB reale              | ✅ FIXATO | LaunchAgent `com.nuzantara.fly-pg-tunnel` mantiene `fly proxy 15432:5432` sempre attivo su Air (KeepAlive=true) |
| **system_doctor.py** (cron)  | Cron usa `--notify-telegram` ma il flag non esiste nel parser      | ✅ FIXATO | Aggiunto `--notify-telegram` all'argparse                                                                       |
| **T4 monitor**               | OpenAI API key assente nel contesto di esecuzione cron             | ✅ FIXATO | `run_t4_monitor.sh` ora fa `source backend/.env` prima dell'esecuzione                                          |
| **seo_guardian_agent.py**    | `npx` non trovato nel PATH del cron                                | ✅ FIXATO | Usa `/opt/homebrew/bin/npx` path assoluto con fallback                                                          |
| **auto_test.sh**             | Test `agentic` rossi → job esce con codice non-zero senza notifica | ✅ FIXATO | Aggiunto Telegram alert su failure + rimosso `set -e` in favore di `set -uo pipefail`                           |

### Drift documentazione vs realtà

| Claim doc                                                                                       | Realtà (Codex)                                                                                                     |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| "auto_stop vincolo 5min"                                                                        | `fly.toml` ha `min_machines_running = 1` → macchina non si spegne                                                  |
| "drive_changes_poll coperto da cron Air ogni 5min"                                              | Entry cron non presente nel dump, `drive_poll_cron.sh` non trovato                                                 |
| Task `birthplace_enrichment`, `conversation_cleanup`, `auto_ingestion` "abilitati ma a rischio" | Codex conferma: in production sono tutti **disabilitati** da flag env (`ENVIRONMENT=production`) o default `False` |

### Autonomous Scheduler (realtà)

Con `min_machines_running=1` la macchina Fly non si spegne → i task 24h sono **tecnicamente** viabili. Ma in pratica sono quasi tutti condizionati a `False` in production. L'unico task 24h realmente attivo è `golden_routes_seeder` (one-time, ~1 anno).

---

### 16b. ANALISI RISCHI DA DEEPSEEK R1 (chain-of-thought — 2026-03-31)

### Rischi collision (confermati)

- **Notifiche duplicate potenziali:** `notification_scheduler` APScheduler + eventuali cron Air che chiamano lo stesso endpoint → verificare assenza overlap
- **OpenClaw agent overlap:** 3 agent scraping potenzialmente sugli stessi siti governativi indonesiani

### Gap critici identificati da DeepSeek

1. **Backup Qdrant mancante:** `fly-qdrant-backup.sh` esiste ma non schedulato su Air (solo Pro). 82K+ vettori non protetti su Air.
2. **SSL cert expiry monitoring:** Nessun alert 30gg prima scadenza su `balizero.com`, `kita.balizero.com`
3. **Redis cache cleaning:** Attualmente manuale
4. **Fly.io cost alerts:** Nessun monitor se supera soglia mensile

### Mitigazione Notification Scheduler (auto_stop)

Con `min_machines_running=1` il rischio è ridotto. Ma DeepSeek suggerisce comunque un **warmup cron** su Air:

```bash
# Aggiungere in crontab Air — wakeup 5min prima del daily check
55 0 * * * curl -s https://nuzantara-rag.fly.dev/health > /dev/null
```

Costo: 0. Garantisce che la macchina sia calda alle 09:00 WITA.

---

## 17. CRITICITÀ E RISCHI

### Rischi di Collision/Overlap

| Rischio                             | Dettaglio                                                                                              | Mitigazione                                                                  |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| **Drive Watchdog vs RAG Canary**    | Entrambi a `*/6h :00`. Stessa fascia.                                                                  | Indipendenti. Nessun shared state. OK.                                       |
| **System Doctor vs SEO Guardian**   | Entrambi verso le 08:00-09:00 WITA.                                                                    | SEO è `0 1 UTC` = 09:00 WITA. Doctor è `0 8 WITA`. ≠ orari. OK.              |
| **Autonomous Scheduler 24h tasks**  | `birthplace_enrichment`, `conversation_cleanup`, `auto_ingestion` abilitati ma Fly.io si spegne prima. | Tasks a rischio. Vanno monitorati.                                           |
| **Notification Scheduler solo Fly** | Se Fly.io è fermo (auto_stop), il job delle 09:00 non gira.                                            | Fly si risveglia su richiesta ma solo se c'è traffico. Aggiungere heartbeat. |

### Single Points of Failure

| Componente             | Impatto se down                                    | Recovery                                          |
| ---------------------- | -------------------------------------------------- | ------------------------------------------------- |
| **OpenClaw (Air)**     | Tutti i MCP tools, Telegram listener, agenti AI    | `launchctl start ai.openclaw.node`                |
| **Redis (Air)**        | Leader election scheduler Fly, cache, rate limiter | `brew services restart redis`                     |
| **PostgreSQL (Fly)**   | Tutto il backend                                   | `fly postgres restart -a nuzantara-postgres`      |
| **OAuth Google Drive** | Polling Drive, OCR, documenti clienti              | `https://kita.balizero.com/settings/integrations` |
| **CELL Organism**      | Auto-healing, monitoring CELL                      | Riavvio `launchctl`                               |

### Gap Identificati

1. **Notification Scheduler senza heartbeat:** Se Fly.io è idle alle 09:00, il job non parte. Soluzione: cron Air che fa warmup request 5min prima.
2. **Backup manuali:** `fly-pg-backup.sh` e `fly-qdrant-backup.sh` esistono ma non sono nel crontab Air (sono su Pro).
3. **X/Twitter broken:** Nessun monitor attivo che segnali il CRC failure ripetuto (X API 403 già in TECH Orchestrator report).
4. **CELL Health RED:** CELL organism attivo ma in stato RED da almeno un report. Nessun auto-recovery visibile.

---

## 18. MAPPA DI PRIORITÀ

Ordinata per **impatto se smette di funzionare**:

### CRITICO (impatto immediato su clienti)

| #   | Automazione                         | Impatto                                  |
| --- | ----------------------------------- | ---------------------------------------- |
| 1   | Webhook WhatsApp/Telegram/Instagram | Nessuna risposta AI ai clienti           |
| 2   | PostgreSQL (Fly.io)                 | Backend non funziona                     |
| 3   | OpenClaw Node Host                  | MCP tools, Telegram AI agent             |
| 4   | Notification Scheduler              | Alert scadenza visa/passport non inviati |
| 5   | Lead Assignment Agent               | Nuovi clienti non assegnati al team      |

### ALTO (impatto entro 24h)

| #   | Automazione           | Impatto                                              |
| --- | --------------------- | ---------------------------------------------------- |
| 6   | Intel Scraper nightly | Nessun contenuto fresco → War Room vuota → no report |
| 7   | Drive Token Watchdog  | OAuth scade silenziosamente → no documenti clienti   |
| 8   | Self-Healing Agent    | Errori backend si accumulano senza auto-fix          |
| 9   | System Doctor         | Nessun alert mattutino → problemi non rilevati       |
| 10  | CRM Automation Engine | Quality decay CRM: dati errati, no renewals          |

### MEDIO (impatto operativo)

| #   | Automazione                  | Impatto                          |
| --- | ---------------------------- | -------------------------------- |
| 11  | GitHub Actions Deploy        | Deploy manuali richiesti         |
| 12  | RAG Canary                   | Drift embedding non rilevato     |
| 13  | SEO Guardian                 | KBLI indexing arretrato          |
| 14  | KB Ingest                    | Knowledge base outdated          |
| 15  | Auto Test                    | Regressioni non rilevate         |
| 16  | Core Guardian V3             | Code quality decay non rilevato  |
| 17  | NLM Pipeline (NB-1/4/6/8/10) | Research knowledge base outdated |
| 18  | War Room                     | Nessun Canva report automatico   |

### BASSO (impatto a lungo termine)

| #   | Automazione       | Impatto                                 |
| --- | ----------------- | --------------------------------------- |
| 19  | RAGAS Eval        | Nessun tracking qualità RAG settimanale |
| 20  | Judgement Day     | Nessun report settimanale               |
| 21  | NLM T4/YT Monitor | Social media + YouTube monitoring gap   |
| 22  | MCP Chains        | Workflow manuali invece di automatici   |
| 23  | KG Builder        | Knowledge Graph non aggiornato (Dom)    |
| 24  | Legal Radar       | Nuove leggi non rilevate                |

---

## RIEPILOGO NUMERICO (v2.0 — completo Air + Pro)

| Categoria                    | Totale       | Attivi       | Disabilitati/Broken          |
| ---------------------------- | ------------ | ------------ | ---------------------------- |
| LaunchD Air                  | 12           | 11           | 1 (CELL Health RED)          |
| LaunchD Pro                  | 21           | 8 always-on  | 13 scheduled/on-demand       |
| Cron Jobs Air                | 11           | 11           | 0 (tutti fixati 2026-03-31)  |
| Cron Jobs Pro                | 21           | 21           | 0                            |
| Intel Scraper + War Room     | 2 (pipeline) | 2            | 0                            |
| Core Guardian V3             | 3 livelli    | 2 attivi     | 1 (Surgeon: bridge mancante) |
| FastAPI Autonomous Scheduler | 8            | 5            | 3 (disabled in prod)         |
| APScheduler Notification     | 2            | 2            | 0                            |
| GitHub Actions               | 6            | 6            | 0                            |
| OpenClaw Agents Air+Pro      | 6            | 6            | 0                            |
| MCP Chains                   | 8            | 8 (definite) | 0                            |
| PostgreSQL Triggers          | 2            | 2            | 0                            |
| Webhook Handlers             | 5            | 4            | 1 (X/Twitter CRC)            |
| **TOTALE AUTOMAZIONI**       | **~107**     | **~86**      | **~17 disabled/broken**      |

---

_Documento v2.0 — 2026-03-31. Include Air + Pro + Intel Scraper + War Room + Core Guardian._
_Fonti: `crontab Air+Pro`, `plutil plist Air+Pro`, codice sorgente, Explore agent, Codex, DeepSeek R1._
