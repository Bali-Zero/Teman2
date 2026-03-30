# NUZANTARA — AUTOMATIONS REFERENCE
**Documento di riferimento definitivo per tutte le automazioni di sistema**

> **Versione:** 1.1
> **Data:** 2026-03-31
> **Macchina origine:** Air (antonellosiano@Nuzantara-9)
> **Fonti:** crontab -l + plutil plist + codice sorgente + Explore agent + **Codex GPT-5.4** (verifica log reali) + **DeepSeek R1 671b** (analisi rischi)
> **Gemini:** rate limit 429 — non disponibile questa sessione

---

## INDICE

1. [Topologia Oraria](#1-topologia-oraria)
2. [LaunchD (macOS Air — Always-On)](#2-launchd-macos-air--always-on)
3. [Cron Jobs (Air)](#3-cron-jobs-air)
4. [FastAPI Autonomous Scheduler (Fly.io)](#4-fastapi-autonomous-scheduler-flyio)
5. [APScheduler — Notification Scheduler (Fly.io)](#5-apscheduler--notification-scheduler-flyio)
6. [GitHub Actions (CI/CD)](#6-github-actions-cicd)
7. [OpenClaw Agents (Air)](#7-openclaw-agents-air)
8. [MCP Workflow Chains](#8-mcp-workflow-chains)
9. [PostgreSQL Triggers (Fly.io DB)](#9-postgresql-triggers-flyio-db)
10. [Webhook Handlers (Event-Driven)](#10-webhook-handlers-event-driven)
11. [Script Locali (Manuali / On-Demand)](#11-script-locali-manuali--on-demand)
12. [Criticità e Rischi](#12-criticità-e-rischi)
13. [Mappa di Priorità](#13-mappa-di-priorità)

---

## 1. TOPOLOGIA ORARIA

Visualizzazione consolidata di tutti i job schedulati per ora WITA (UTC+8):

```
WITA     UTC      JOB
------   ------   -------------------------------------------------------
00:30    16:30    RAG Canary #1 (embedding drift)
01:00    17:00    [CRON] Ollama Start
02:00    18:00    [LAUNCHD] Nightly Git Sync (Air↔Pro)
02:15    18:15    [CRON] Auto Test Suite
02:30    18:30    RAG Canary #2
03:00    19:00    [CRON] Sentinel (auto-repair)
05:00    21:00    [CRON] KB Ingest
06:00    22:00    [LAUNCHD] Weekly Cleanup (Dom only)
06:05    22:05    [CRON] Ollama Stop
06:30    22:30    RAG Canary #3
07:00    23:00    [CRON] CRM Automation Engine
08:00    00:00    [CRON] System Doctor (daily report)
08:00    00:00    Drive Token Watchdog #3
09:00    01:00    [FASTAPI] Notification Daily Check
09:00    01:00    [CRON] SEO Guardian (KBLI indexing)
12:30    04:30    RAG Canary #4
14:00    06:00    Drive Token Watchdog #4
*/5min   */5min   [FASTAPI] Self-Healing Agent + [LAUNCHD] Docker Health (*/30m)
*/1h     */1h     [FASTAPI] Notification Pending Send
*/6h     */6h     [CRON] NLM T4 Monitor, Drive Watchdog, RAG Canary
16:00    08:00    [CRON] Judgement Day (Dom only)
Dom 06:00 Sab22:00 [CRON] RAGAS Eval settimanale
On-push  On-push  [GH ACTIONS] Tests, Deploy, Security
On-msg   On-msg   [WEBHOOK] WhatsApp, Telegram, Instagram, Web
```

---

## 2. LAUNCHD (macOS Air — Always-On)

Servizi gestiti da macOS launchd. Persistono dopo reboot.
File: `~/Library/LaunchAgents/`

### 2.1 OpenClaw Node Host
| Campo | Valore |
|-------|--------|
| **ID** | `ai.openclaw.node` |
| **Schedule** | Always-On (KeepAlive=true) |
| **Comando** | `node ~/.npm-global/lib/node_modules/openclaw/dist/index.js node run --host 127.0.0.1 --port 18789` |
| **Cosa fa** | Runtime OpenClaw (agent orchestrator). Gateway su `localhost:18789`. 129 MCP tools via mcporter. |
| **Macchina** | Air |
| **Stato** | ✅ ATTIVO |
| **Log** | `/tmp/openclaw/` |
| **Note** | v2026.2.25. Se muore: tutti gli agenti AI e MCP tools diventano non disponibili. |

### 2.2 CELL Organism (AI Agent Loop)
| Campo | Valore |
|-------|--------|
| **ID** | `com.cell.organism` |
| **Schedule** | Always-On (KeepAlive=true, RunAtLoad=true) |
| **Comando** | `apps/cell/.venv/bin/python -m cell.main` |
| **Cosa fa** | Agente CELL autonomo — Health RED quando sia Qwen che Gemini falliscono |
| **Macchina** | Air |
| **Stato** | ⚠️ ATTIVO ma Health=RED (segnalato nei messaggi di sistema) |
| **Log** | `/tmp/cell.stdout.log`, `/tmp/cell.stderr.log` |
| **Env** | `CELL_BACKEND_HEALTH_URL`, `CELL_TELEGRAM_CHAT_ID=1125336968` |

### 2.3 Claude Max API
| Campo | Valore |
|-------|--------|
| **ID** | `com.claude-max-api` |
| **Schedule** | Always-On (KeepAlive=true, RunAtLoad=true) |
| **Comando** | `~/.npm-global/bin/claude-max-api` |
| **Cosa fa** | Bridge API per accesso Claude Max |
| **Macchina** | Air |
| **Stato** | ✅ ATTIVO |
| **Log** | `/tmp/claude-max-api.log` |

### 2.4 OpenClaw Monitor Pro
| Campo | Valore |
|-------|--------|
| **ID** | `com.openclaw.monitor-pro` |
| **Schedule** | Ogni 300s (5 min) |
| **Script** | `~/.openclaw/scripts/monitor-pro.sh` |
| **Cosa fa** | SSH ping a Pro — controlla raggiungibilità e sync git |
| **Macchina** | Air |
| **Stato** | ✅ ATTIVO |
| **Log** | `/tmp/openclaw/monitor-pro-stdout.log` |

### 2.5 Nightly Git Sync
| Campo | Valore |
|-------|--------|
| **ID** | `com.nuzantara.nightly-sync` |
| **Schedule** | 02:30 WITA (18:30 UTC) |
| **Script** | `scripts/nz-nightly.sh` |
| **Cosa fa** | `git pull pro main --ff-only` → sync Air con Pro |
| **Macchina** | Air |
| **Stato** | ✅ ATTIVO |
| **Log** | `/tmp/nuzantara-nightly-sync.log` |

### 2.6 Docker Health Check
| Campo | Valore |
|-------|--------|
| **ID** | `com.user.docker-health-check` |
| **Schedule** | Ogni 1800s (30 min, RunAtLoad=true) |
| **Script** | `~/scripts/docker-health-check.sh` |
| **Cosa fa** | Controlla salute Docker containers: PostgreSQL 17, Qdrant, Redis |
| **Macchina** | Air |
| **Stato** | ✅ ATTIVO |
| **Log** | `~/scripts/docker-health-stderr.log` |

### 2.7 Weekly Cleanup
| Campo | Valore |
|-------|--------|
| **ID** | `com.user.weekly-cleanup` |
| **Schedule** | Domenica 02:00 WITA |
| **Script** | `~/scripts/cleanup-weekly.sh` |
| **Cosa fa** | Pulizia directory tmp, log rotation, disk space |
| **Macchina** | Air |
| **Stato** | ✅ ATTIVO |

### 2.8 Homebrew Services (Infrastruttura)
| ID | Servizio | Schedule | Stato |
|----|---------|---------|-------|
| `homebrew.mxcl.postgresql@17` | PostgreSQL 17 (porta 5432) | Always-On | ✅ |
| `homebrew.mxcl.redis` | Redis (porta 6379) | Always-On | ✅ |
| `homebrew.mxcl.ollama` | Ollama LLM server | Always-On | ✅ |

---

## 3. CRON JOBS (Air)

File: `crontab -l` su Air. Log in `~/Projects/nuzantara/logs/`.

### 3.1 Infrastruttura AI (Ollama Window)

| Job | Cron | Schedule WITA | Script | Cosa fa |
|-----|------|---------------|--------|---------|
| **Ollama Start** | `0 1 * * *` | 01:00 | `scripts/ollama_cron_window.sh start` | Avvia Ollama per batch notturno (test, sentinel, KB ingest) |
| **Ollama Stop** | `5 6 * * *` | 06:05 | `scripts/ollama_cron_window.sh stop` | Safety net: ferma Ollama dopo tutti i task notturni |

**Note:** Ollama gira `localhost:11434`. Durante la window 01:00-06:05 è disponibile per tutti i cron.

### 3.2 Quality & Testing

| Job | Cron | Schedule WITA | Script | Cosa fa |
|-----|------|---------------|--------|---------|
| **Auto Test** | `15 2 * * *` | 02:15 | `scripts/auto_test.sh` | Backend pytest, import chain check, report Telegram se fail |
| **Sentinel** | `0 3 * * *` | 03:00 | `scripts/auto_sentinel.sh` | Auto-repair broken jobs: detect errori, patch, retry |

### 3.3 Data Collection

| Job | Cron | Schedule WITA | Script | Cosa fa |
|-----|------|---------------|--------|---------|
| **KB Ingest** | `0 5 * * *` | 05:00 | `scripts/auto_kb_ingest.sh` | Ingest knowledge base: visa + peraturan + putusan spiders |

> **Note:** Unified Scraper (609 fonti) e Visa Agent sono in crontab ma i comandi sono commentati. Runnano su Pro via OpenClaw (03:00 WITA Pro).

### 3.4 CRM Automation

| Job | Cron | Schedule WITA | Script | Cosa fa |
|-----|------|---------------|--------|---------|
| **CRM Automation Engine** | `0 23 * * *` | 07:00 (+1d) | `apps/backend-rag/scripts/crm_automation_engine.py` | 4 moduli: quality fixes, doc checklists, renewals, stale detection. ~805 fix/run. |

### 3.5 Monitoring & Reports

| Job | Cron | Schedule WITA | Script | Cosa fa |
|-----|------|---------------|--------|---------|
| **RAG Canary** | `30 */6 * * *` | 00:30, 06:30, 12:30, 18:30 | `scripts/rag_canary.py` | Embedding drift detection + golden query regression. Alert se drift > threshold. |
| **System Doctor** | `0 8 * * *` | 08:00 | `scripts/system_doctor.py --notify-telegram` | Health check completo: backend, frontend, Fly.io, SSL, logs. Report mattutino Telegram. |
| **Drive Watchdog** | `0 */6 * * *` | 02:00, 08:00, 14:00, 20:00 | `scripts/drive_token_watchdog.py` | Monitora scadenza OAuth token Google Drive. Alert Telegram 7gg prima scadenza. |
| **NLM T4 Monitor** | `0 */6 * * *` | 02:00, 08:00, 14:00, 20:00 | `apps/evaluator/nlm_deep_research/scripts/run_t4_monitor.sh` | NotebookLM T4 social media monitor. |
| **SEO Guardian** | `0 1 * * *` | 09:00 | `apps/evaluator/seo_guardian_agent.py --observe-first` | KBLI indexing submit + SEO/GEO audit. 420/1563 KBLI URL indicizzate. |
| **RAGAS Eval** | `0 6 * * 0` | Dom 06:00 | `scripts/ragas_eval.py` | Valutazione qualità RAG settimanale (RAGAS metrics). |
| **Judgement Day** | `0 16 * * 0` | Dom 16:00 | `scripts/auto_judgement_day.sh` | Weekly rollup: 7gg di stats, anomalie, report email/Telegram. |

---

## 4. FASTAPI AUTONOMOUS SCHEDULER (Fly.io)

File: `apps/backend-rag/backend/services/misc/autonomous_scheduler.py`
Inizializzato in: `backend/app/setup/service_initializer.py`
**Vincolo critico:** `auto_stop=true` su Fly.io → solo task con interval ≤ 5min sopravvivono.

### Task ATTIVI (enabled=True)

| Nome | Interval | Cosa fa | Stato |
|------|----------|---------|-------|
| `self_healing` | 5 min | Backend self-healing agent. Detect + fix errori di servizio (DB conn, Redis, cache). Redis leader election (solo 1 worker esegue). | ✅ ATTIVO |
| `golden_routes_seeder` | 1 anno (one-time) | Seed delle rotte golden per warm-up cache al primo avvio. | ✅ ATTIVO (one-time) |
| `birthplace_enrichment` | 24h | Enrichment dati luogo nascita clienti tramite geocoding. | ⚠️ ATTIVO ma a rischio auto_stop |
| `conversation_cleanup` | 24h | Pulizia conversazioni vecchie > 90gg. | ⚠️ ATTIVO ma a rischio auto_stop |
| `auto_ingestion` | 24h | Auto-ingestion documenti intel. | ⚠️ ATTIVO ma a rischio auto_stop |

### Task DISABILITATI (enabled=False)

| Nome | Motivo disabilitazione | Covered by |
|------|----------------------|------------|
| `conversation_trainer` | Git subprocess non funziona su Fly.io ephemeral | — |
| `renewal_alerts` | 12h > auto_stop uptime | OpenClaw `practice_lifecycle_check` |
| `birthday_notifier` | 24h > auto_stop uptime | OpenClaw `client_health_monitor` |
| `daily_ops_autopilot` | BUG: chiama localhost:8000 = se stesso | OpenClaw `daily_ops_autopilot` chain |
| `drive_changes_poll` | Fly.io auto_stop incompatibile con page_token | Air cron (ogni 5min curl POST) |

---

## 5. APSCHEDULER — NOTIFICATION SCHEDULER (Fly.io)

File: `apps/backend-rag/backend/app/modules/notifications/scheduler.py`
Classe: `NotificationScheduler`
**Tabella DB:** `notification_alerts` ← **migration_071** (applicata 2026-03-31)

### Job 1: Daily Expiry Check
| Campo | Valore |
|-------|--------|
| **ID** | `daily_notification_check` |
| **Schedule** | 09:00 WITA (CronTrigger, Asia/Makassar) |
| **Cosa fa** | Scansiona TUTTI i clienti → genera alert (passport/visa expiry, birthday) → salva in `notification_alerts` con dedup ON CONFLICT |
| **Lock** | `asyncio.Lock()` (single execution per worker) |
| **Dipendenze** | `ExpiryChecker`, `AlertDeduplicator`, `get_clients_from_db` |

### Job 2: Hourly Pending Send
| Campo | Valore |
|-------|--------|
| **ID** | `hourly_pending_send` |
| **Schedule** | Ogni ora :00 (CronTrigger `minute=0`) |
| **Cosa fa** | Legge tutti gli alert `status=pending` dal DB → invia email via SendGrid/SMTP → aggiorna status a `sent`/`failed` |
| **Lock** | `asyncio.Lock()` |
| **Provider email** | Brevo (xkeysib- key, alias `zantara@balizero.com`) |

---

## 6. GITHUB ACTIONS (CI/CD)

Directory: `.github/workflows/`

### 6.1 Deploy Backend to Fly.io
| Campo | Valore |
|-------|--------|
| **File** | `fly-deploy.yml` |
| **Trigger** | `push` → `main` (path: `apps/backend-rag/**`) |
| **Jobs** | Pre-deploy gate → Run migrations → Rolling deploy → Post-deploy health (10 retry × 30s, auto-rollback) |
| **Notifiche** | Telegram (success/failure) |
| **Stato** | ✅ ATTIVO |
| **Secrets required** | `FLY_API_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID` |

### 6.2 Tests & Coverage
| Campo | Valore |
|-------|--------|
| **File** | `tests.yml` |
| **Trigger** | `push main/develop`, `pull_request`, `workflow_dispatch` |
| **Jobs** | Backend pytest, Frontend vitest, E2E Playwright, Summary |
| **Stato** | ✅ ATTIVO |

### 6.3 Security Scanning
| Campo | Valore |
|-------|--------|
| **File** | `security.yml` |
| **Trigger** | `push`, `pull_request`, **schedule `0 0 * * 0`** (Dom 00:00 UTC), `workflow_dispatch` |
| **Jobs** | Snyk Python, Snyk Node, OWASP, Dependency review |
| **Stato** | ✅ ATTIVO |

### 6.4 SonarQube Analysis
| Campo | Valore |
|-------|--------|
| **File** | `sonarqube.yml` |
| **Trigger** | `push`, `pull_request`, `workflow_dispatch` |
| **Stato** | ✅ ATTIVO |

### 6.5 Intel Router Tests
| Campo | Valore |
|-------|--------|
| **File** | `intel-router-tests.yml` |
| **Trigger** | `push`, `pull_request`, `workflow_dispatch` |
| **Stato** | ✅ ATTIVO |

### 6.6 Docs Sync Check
| Campo | Valore |
|-------|--------|
| **File** | `docs-sync.yml` |
| **Trigger** | `push`, `pull_request` |
| **Cosa fa** | Verifica sincronizzazione docs tra Air e Pro |
| **Stato** | ✅ ATTIVO |

---

## 7. OPENCLAW AGENTS (Air)

Config: `~/.openclaw/openclaw.json`
Gateway: `localhost:18789`

| Agent | Model | Ruolo | Sandbox | Heartbeat | Stato |
|-------|-------|-------|---------|-----------|-------|
| **main** | claude-opus-4-6 | Orchestratore principale, Telegram listener | off | 1h | ✅ ATTIVO |
| **coder** | qwen3.5:27b (Ollama) | Coding tasks locali, zero-cost | off | 0 | ✅ ATTIVO |
| **qa-visual** | gemini-3.1-pro-preview | QA visivo, review | off | 0 | ✅ ATTIVO |

**MCP Bridge:** 129 tools via mcporter wrappers in `~/.local/bin/`
**Note critiche:**
- `main` è l'UNICO listener Telegram (@Balizerobot). Air e Fly.io mandano solo.
- Se OpenClaw muore → nessun AI su Telegram → alert tramite Telegram non funziona (paradosso).

---

## 8. MCP WORKFLOW CHAINS

File: `apps/nuzantara-mcp/nuzantara_mcp/workflows/chains.py`
Eseguiti via OpenClaw (mcporter) o manuale.

| Chain | Trigger | Steps | Stato |
|-------|---------|-------|-------|
| `chain_daily_ops_autopilot` | OpenClaw cron / manuale | 5: expiry alerts → agent health → intel articles → team hours → email report | ✅ DEFINITA |
| `chain_new_client_onboarding` | CRM new client | 8: CRM → KBLI → visa → Drive folder → practice → plan → welcome → log | ✅ DEFINITA |
| `chain_practice_lifecycle_check` | Ogni 6h (OpenClaw) | 5: visa renewals, doc reminders, escalations, completion | ✅ DEFINITA |
| `chain_compliance_autopilot` | Manuale / scheduled | 5: critical alerts, urgent, auto-renewals, summary | ✅ DEFINITA |
| `chain_intel_pipeline` | Post-scraper | 6: submit → wait → review → approve → compose → report | ✅ DEFINITA |
| `chain_client_health_monitor` | OpenClaw scheduled | 5: value score, VIP nurture, high-risk, reminders, surveys | ✅ DEFINITA |
| `chain_journey_accelerator` | User action | 6: journey → pricing → Drive → compliance → welcome → orchestration | ✅ DEFINITA |
| `chain_weekly_report` | Dom mattina (OpenClaw) | 6: CRM stats, revenue, team, intel trends, RAG perf, email | ✅ DEFINITA |

---

## 9. POSTGRESQL TRIGGERS (Fly.io DB)

Database: `nuzantara-postgres.flycast:5432/nuzantara_rag`

### 9.1 Client to Memory Sync
| Campo | Valore |
|-------|--------|
| **Trigger** | `AFTER INSERT OR UPDATE ON clients` |
| **Cosa fa** | Copia `assigned_to`, `status`, `tags` da `clients` → `user_stats.preferences` (JSONB) per fast frontend access |
| **File migration** | `migration_050_client_memory_sync.py` |
| **Stato** | ✅ ATTIVO |

### 9.2 Lead Assignment Agent
| Campo | Valore |
|-------|--------|
| **Trigger** | `asyncio.create_task()` post-INSERT in `AutoCRMService` |
| **Cosa fa** | LangGraph workflow: 1) dedup, 2) assign (specialty+workload), 3) notify Telegram |
| **File** | `backend/services/crm/lead_assignment_agent.py` |
| **Stato** | ✅ ATTIVO (non-blocking) |

---

## 10. WEBHOOK HANDLERS (Event-Driven)

Tutti su Fly.io. Richiedono macchina attiva (cold start ~35s).

| Channel | Endpoint | Trigger | Adapter | Stato |
|---------|---------|---------|---------|-------|
| **WhatsApp** | `POST /api/whatsapp/webhook` | Meta Cloud API incoming msg | `channels/whatsapp/adapter.py` | ✅ LIVE |
| **Telegram** | `POST /api/telegram/webhook` | Telegram incoming (POST) | `channels/telegram/adapter.py` | ✅ LIVE (Air polls) |
| **Instagram** | `POST /api/webhook/instagram` | Meta Instagram incoming | `channels/instagram/adapter.py` | ✅ LIVE |
| **Web Chat** | `POST /api/webhook/chat` | Web chat submission | `channels/web/adapter.py` | ✅ LIVE |
| **X/Twitter** | `POST /api/webhook/twitter` | Twitter incoming | `channels/twitter/adapter.py` | ❌ BROKEN (CRC auth fail) |

---

## 11. SCRIPT LOCALI (Manuali / On-Demand)

Scripts non schedulati, usati manualmente o da ai-dispatch.

| Script | Tipo | Scopo |
|--------|------|-------|
| `ai-dispatch.sh` | Bash (56KB) | Orchestratore AI: dispatch a Gemini, Codex, Claude, DeepSeek, Aider |
| `federation_orchestrator.py` | Python | Orchestrazione multi-agent per task complessi |
| `nuzantara-sentinel.py` | Python (23KB) | Sentinel avanzato: detect + fix pattern specifici |
| `dlq_autopilot.py` | Python (20KB) | Dead Letter Queue autopilot: retry job falliti |
| `expiry_alerter.py` | Python (16KB) | Expiry alerts manuale (test/debug del notification scheduler) |
| `fly-pg-backup.sh` | Bash | pg_dump → Tigris `nuzantara-backups`. Schedulato su Pro. |
| `fly-qdrant-backup.sh` | Bash | Qdrant snapshot backup. Schedulato su Pro. |
| `nlm_nb1_daily_refresh.py` | Python (14KB) | NotebookLM NB-1 refresh (orario variabile) |
| `nlm_pipeline_run.sh` | Bash | Lancia NLM research pipeline completo |
| `preflight.sh` | Bash | Preflight SDD check (L1/L2/L3) prima di task non-triviali |
| `ragas_eval.py` | Python | RAG evaluation con framework RAGAS (schedulato Dom) |
| `coverage_trend.py` | Python | Tracking trend test coverage nel tempo |
| `dep_audit.py` | Python | Audit dipendenze Python/Node |
| `ux-audit.sh` | Bash | Audit UX su frontend |
| `vector-reindex-check.py` | Python | Verifica coerenza indici vettoriali Qdrant |

---

## 11b. ANOMALIE RILEVATE DA CODEX (verifica log reali — 2026-03-31)

> Codex GPT-5.4 ha letto i log effettivi in `logs/`. Questi sono problemi **confermati in produzione**.

### Job rotti / degradati (confermato da log)

> **Stato 2026-03-31:** 7 di 8 job fixati nel commit `8e9bce647f`. Rimane aperto: `crm_automation_engine.py` (tunnel DB).

| Job | Problema | Stato | Fix applicato |
|-----|---------|-------|---------------|
| **auto_sentinel.sh** | Punta a `apps/core/sentinel.py` che non esiste | ✅ FIXATO | `sentinel` wrapper ora punta a `apps/evaluator/core_guardian/watchdog.py` |
| **auto_kb_ingest.sh** | Script Python target non presenti | ✅ FIXATO | `run_if_exists()` wrapper — skip graceful con log se script mancante |
| **auto_judgement_day.sh** | `ragas` non installato nel venv Air | ✅ FIXATO | Check dipendenza prima del run, skip con messaggio di istruzioni |
| **crm_automation_engine.py** | Usa `localhost:15432` (tunnel DB) invece del DB reale | ✅ FIXATO | LaunchAgent `com.nuzantara.fly-pg-tunnel` mantiene `fly proxy 15432:5432` sempre attivo su Air (KeepAlive=true) |
| **system_doctor.py** (cron) | Cron usa `--notify-telegram` ma il flag non esiste nel parser | ✅ FIXATO | Aggiunto `--notify-telegram` all'argparse |
| **T4 monitor** | OpenAI API key assente nel contesto di esecuzione cron | ✅ FIXATO | `run_t4_monitor.sh` ora fa `source backend/.env` prima dell'esecuzione |
| **seo_guardian_agent.py** | `npx` non trovato nel PATH del cron | ✅ FIXATO | Usa `/opt/homebrew/bin/npx` path assoluto con fallback |
| **auto_test.sh** | Test `agentic` rossi → job esce con codice non-zero senza notifica | ✅ FIXATO | Aggiunto Telegram alert su failure + rimosso `set -e` in favore di `set -uo pipefail` |

### Drift documentazione vs realtà

| Claim doc | Realtà (Codex) |
|-----------|----------------|
| "auto_stop vincolo 5min" | `fly.toml` ha `min_machines_running = 1` → macchina non si spegne |
| "drive_changes_poll coperto da cron Air ogni 5min" | Entry cron non presente nel dump, `drive_poll_cron.sh` non trovato |
| Task `birthplace_enrichment`, `conversation_cleanup`, `auto_ingestion` "abilitati ma a rischio" | Codex conferma: in production sono tutti **disabilitati** da flag env (`ENVIRONMENT=production`) o default `False` |

### Autonomous Scheduler (realtà)
Con `min_machines_running=1` la macchina Fly non si spegne → i task 24h sono **tecnicamente** viabili. Ma in pratica sono quasi tutti condizionati a `False` in production. L'unico task 24h realmente attivo è `golden_routes_seeder` (one-time, ~1 anno).

---

## 11c. ANALISI RISCHI DA DEEPSEEK R1 (chain-of-thought — 2026-03-31)

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

## 12. CRITICITÀ E RISCHI

### Rischi di Collision/Overlap

| Rischio | Dettaglio | Mitigazione |
|---------|-----------|-------------|
| **Drive Watchdog vs RAG Canary** | Entrambi a `*/6h :00`. Stessa fascia. | Indipendenti. Nessun shared state. OK. |
| **System Doctor vs SEO Guardian** | Entrambi verso le 08:00-09:00 WITA. | SEO è `0 1 UTC` = 09:00 WITA. Doctor è `0 8 WITA`. ≠ orari. OK. |
| **Autonomous Scheduler 24h tasks** | `birthplace_enrichment`, `conversation_cleanup`, `auto_ingestion` abilitati ma Fly.io si spegne prima. | Tasks a rischio. Vanno monitorati. |
| **Notification Scheduler solo Fly** | Se Fly.io è fermo (auto_stop), il job delle 09:00 non gira. | Fly si risveglia su richiesta ma solo se c'è traffico. Aggiungere heartbeat. |

### Single Points of Failure

| Componente | Impatto se down | Recovery |
|------------|----------------|---------|
| **OpenClaw (Air)** | Tutti i MCP tools, Telegram listener, agenti AI | `launchctl start ai.openclaw.node` |
| **Redis (Air)** | Leader election scheduler Fly, cache, rate limiter | `brew services restart redis` |
| **PostgreSQL (Fly)** | Tutto il backend | `fly postgres restart -a nuzantara-postgres` |
| **OAuth Google Drive** | Polling Drive, OCR, documenti clienti | `https://kita.balizero.com/settings/integrations` |
| **CELL Organism** | Auto-healing, monitoring CELL | Riavvio `launchctl` |

### Gap Identificati

1. **Notification Scheduler senza heartbeat:** Se Fly.io è idle alle 09:00, il job non parte. Soluzione: cron Air che fa warmup request 5min prima.
2. **Backup manuali:** `fly-pg-backup.sh` e `fly-qdrant-backup.sh` esistono ma non sono nel crontab Air (sono su Pro).
3. **X/Twitter broken:** Nessun monitor attivo che segnali il CRC failure ripetuto (X API 403 già in TECH Orchestrator report).
4. **CELL Health RED:** CELL organism attivo ma in stato RED da almeno un report. Nessun auto-recovery visibile.

---

## 13. MAPPA DI PRIORITÀ

Ordinata per **impatto se smette di funzionare**:

### CRITICO (impatto immediato su clienti)
| # | Automazione | Impatto |
|---|------------|---------|
| 1 | Webhook WhatsApp/Telegram/Instagram | Nessuna risposta AI ai clienti |
| 2 | PostgreSQL (Fly.io) | Backend non funziona |
| 3 | OpenClaw Node Host | MCP tools, Telegram AI agent |
| 4 | Notification Scheduler | Alert scadenza visa/passport non inviati |
| 5 | Lead Assignment Agent | Nuovi clienti non assegnati al team |

### ALTO (impatto entro 24h)
| # | Automazione | Impatto |
|---|------------|---------|
| 6 | Drive Token Watchdog | OAuth scade silenziosamente → no documenti clienti |
| 7 | Self-Healing Agent | Errori backend si accumulano senza auto-fix |
| 8 | System Doctor | Nessun alert mattutino → problemi non rilevati |
| 9 | CRM Automation Engine | Quality decay CRM: dati errati, no renewals |

### MEDIO (impatto operativo)
| # | Automazione | Impatto |
|---|------------|---------|
| 10 | GitHub Actions Deploy | Deploy manuali richiesti |
| 11 | RAG Canary | Drift embedding non rilevato |
| 12 | SEO Guardian | KBLI indexing arretrato |
| 13 | KB Ingest | Knowledge base outdated |
| 14 | Auto Test | Regressioni non rilevate |

### BASSO (impatto a lungo termine)
| # | Automazione | Impatto |
|---|------------|---------|
| 15 | RAGAS Eval | Nessun tracking qualità RAG settimanale |
| 16 | Judgement Day | Nessun report settimanale |
| 17 | NLM T4 Monitor | Social media monitoring gap |
| 18 | MCP Chains | Workflow manuali invece di automatici |

---

## RIEPILOGO NUMERICO

| Categoria | Totale | Attivi | Disabilitati/Broken |
|-----------|--------|--------|---------------------|
| LaunchD (macOS Air) | 11 | 10 | 1 (CELL Health RED) |
| Cron Jobs (Air) | 11 | 11 | 0 |
| FastAPI Autonomous Scheduler | 8 | 5 | 3 (disabled) |
| APScheduler Notification | 2 | 2 | 0 |
| GitHub Actions | 6 | 6 | 0 |
| OpenClaw Agents | 3 | 3 | 0 |
| MCP Chains | 8 | 8 (definite) | 0 |
| PostgreSQL Triggers | 2 | 2 | 0 |
| Webhook Handlers | 5 | 4 | 1 (X/Twitter CRC) |
| **TOTALE** | **56** | **51** | **4 + 3 disabled** |

---

*Documento generato il 2026-03-31. Aggiornare dopo ogni modifica significativa al sistema di automazioni.*
*Fonti: `crontab -l`, `plutil plist`, codice sorgente backend, Explore agent.*
