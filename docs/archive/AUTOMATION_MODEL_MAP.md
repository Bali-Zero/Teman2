# Nuzantara — Mappa Completa Automazioni x Modelli LLM

> **Auto-reference** — mantenuto manualmente. Aggiornare quando si aggiunge/modifica un'automazione.
> Ultimo aggiornamento: 2026-04-14

---

## Legenda

- **LLM**: usa un modello linguistico (locale o cloud)
- **NLM**: usa NotebookLM (cloud, via nlm CLI)
- **API**: chiama API backend Fly.io (nessun LLM locale)
- **SHELL**: puro bash/python, nessun LLM
- **DAEMON**: processo long-running

---

## PRO (nuzantara@Nuzantara — M4 Pro 48GB)

### OpenClaw Cron Jobs (24)

| #   | Job                    | Schedule (WITA) | Agent | LLM?           | Modello               | Note                        |
| --- | ---------------------- | --------------- | ----- | -------------- | --------------------- | --------------------------- |
| 1   | core-guardian          | \*/3h           | coder | LLM (OpenClaw) | **qwen3.5:9b** (warm) | Esegue python cron_guardian |
| 2   | seo-guardian-observe   | ogni 40min      | main  | LLM (OpenClaw) | **qwen3.5:9b** (warm) | curl + parse SEO            |
| 3   | system-doctor          | \*/4h           | main  | LLM (OpenClaw) | **qwen3.5:9b** (warm) | Diagnose + auto-fix         |
| 4   | tech-orchestrator      | ogni 4h         | main  | LLM (OpenClaw) | **qwen3.5:9b** (warm) | Guard + orchestrate         |
| 5   | compliance-ops         | ogni 6h         | main  | LLM (OpenClaw) | **qwen3.5:9b** (warm) | Compliance check            |
| 6   | daily-ops              | 08:00           | main  | LLM (OpenClaw) | **qwen3.5:9b** (warm) | Morning sweep               |
| 7   | client-health-monitor  | 14:00           | main  | LLM (OpenClaw) | **qwen3.5:9b** (warm) | mcporter chain              |
| 8   | conversation-cleanup   | 02:00           | coder | LLM (OpenClaw) | **qwen3.5:9b** (warm) | curl API + parse            |
| 9   | indexing-daily         | 09:00           | coder | LLM (OpenClaw) | **qwen3.5:9b** (warm) | GSC indexing                |
| 10  | seo-guardian-weekly    | Lun 08:00       | main  | LLM (OpenClaw) | **qwen3.5:9b** (warm) | SEO analysis                |
| 11  | weekly-review          | Lun 09:00       | main  | LLM (OpenClaw) | **qwen3.5:9b** (warm) | KPI review                  |
| 12  | weekly-dep-audit       | Lun 03:30       | main  | LLM (OpenClaw) | **qwen3.5:9b** (warm) | pip-audit                   |
| 13  | learning-pipeline      | Dom 23:00       | main  | LLM (OpenClaw) | **qwen3.5:9b** (warm) | Training pipeline           |
| 14  | t4-monitor-daily       | 03:35           | main  | LLM (OpenClaw) | **qwen3.5:9b** (warm) | bash script exec            |
| 15  | nlm-nb1-daily-refresh  | 04:30           | main  | LLM (OpenClaw) | **qwen3.5:9b** (warm) | python3 exec                |
| 16  | nlm-nb3-company-setup  | 02:45 Lun-Sab   | main  | —              | Skipped (empty task)  |                             |
| 17  | nlm-nb4-tax-fiscal     | 02:20 Lun-Sab   | main  | —              | Skipped (empty task)  |                             |
| 18  | nlm-nb5-property       | 02:35 Lun-Sab   | main  | —              | Skipped (empty task)  |                             |
| 19  | nlm-nb6-ops-compliance | 02:30 Lun-Sab   | main  | —              | Skipped (empty task)  |                             |
| 20  | nlm-nb7-editorial      | 02:40 Lun-Sab   | main  | —              | Skipped (empty task)  |                             |
| 21  | nlm-nb8-expat-life     | 02:47 Lun-Sab   | main  | —              | Skipped (empty task)  |                             |
| 22  | nlm-nb10-team-guides   | 02:50 Lun-Sab   | main  | —              | Skipped (empty task)  |                             |
| 23  | nlm-deep-research      | 01:10           | main  | —              | Skipped (empty task)  |                             |
| 24  | cell-weekly-report     | Dom 08:00       | main  | —              | Skipped (empty task)  |                             |

### Crontab Jobs (47 entries)

| #     | Job                                 | Schedule (WITA)     | LLM?  | Modello                           | Note                                             |
| ----- | ----------------------------------- | ------------------- | ----- | --------------------------------- | ------------------------------------------------ |
| 1     | **translate-articles.py**           | ogni ora :30        | LLM   | **gemma4:26b** → gemma4:e4b       | Traduzione IT/ID/RU/FR via Ollama API            |
| 2     | **qwen-code-review.sh**             | 10:00 (NOT LOADED)  | LLM   | qwen2.5-coder:32b (NOT INSTALLED) | **MORTO** — da riassegnare a qwen3:8b o ritirare |
| 3     | **legal_radar.py**                  | Dom 08:00           | SHELL | —                                 | Python puro, nessun LLM                          |
| 4     | fly-health-check.sh                 | \*/30min            | SHELL | —                                 | curl check                                       |
| 5     | drive-poll.sh                       | \*/5min             | SHELL | —                                 | Google Drive poll                                |
| 6     | intel-scraper-sentinel-bridge.sh    | \*/5min             | SHELL | —                                 | State bridge                                     |
| 7     | pro_heartbeat                       | ogni ora            | SHELL | —                                 | `touch ~/.pro_heartbeat`                         |
| 8     | fly-backup.sh                       | 03:00               | SHELL | —                                 | pg_dump + qdrant backup                          |
| 9     | expiry_alerter.py                   | 08:00               | SHELL | —                                 | Alerting, no LLM                                 |
| 10    | openclaw-state-bridge.py            | \*/5min             | SHELL | —                                 | State sync                                       |
| 11    | nlm_bridge state                    | \*/4min             | SHELL | —                                 | JSON write                                       |
| 12    | mos-maintenance.sh                  | 04:00               | SHELL | —                                 | SQLite vacuum                                    |
| 13    | sync-memory-to-nlm.sh               | Dom 03:00           | NLM   | —                                 | NLM CLI (cloud)                                  |
| 14    | sync-memory-ruslana.sh              | 08:00               | SHELL | —                                 | SCP files                                        |
| 15    | cert-monitor.sh                     | 07:00               | SHELL | —                                 | SSL check                                        |
| 16    | fly-restart-loop-detector.sh        | \*/15min            | SHELL | —                                 | Fly.io monitor                                   |
| 17    | fly-cost-alert.sh                   | Lun 09:00           | SHELL | —                                 | Cost report                                      |
| 18    | sync-damar.sh                       | ogni ora            | SHELL | —                                 | SCP sync                                         |
| 19    | cache-cleanup                       | 1o+15o 03:30        | SHELL | —                                 | npm+pip+brew cleanup                             |
| 20    | warmup-vision.sh                    | \*/4 9-17 Lun-Sab   | SHELL | —                                 | Ollama vision warmup                             |
| 21    | **bali-zero-akta overnight**        | 19:00 Dom-Ven       | SHELL | —                                 | Bulk processor, no LLM diretto                   |
| 22-28 | **NLM nb2-nb10 pipelines** (7 jobs) | 02:10-02:50 Lun-Sab | NLM   | —                                 | `nlm` CLI → NotebookLM cloud                     |
| 29    | NLM nb1 refresh (cron)              | 20:30               | NLM   | —                                 | `nlm` CLI                                        |
| 30    | NLM peraturan ingestion             | Dom 21:30           | NLM   | —                                 | `nlm` CLI                                        |
| 31-36 | **NLM multimodal** (6 jobs)         | 22:00 Lun-Sab       | NLM   | —                                 | `nlm` CLI                                        |
| 37    | NLM gap scanner layer-a             | 21:30               | NLM   | —                                 | `nlm` CLI + Gemini search (cloud)                |
| 38    | NLM gap scanner layer-b             | Dom 19:00           | NLM   | —                                 | `nlm` CLI                                        |
| 39    | NLM gap scanner remediate           | Dom 20:30           | NLM   | —                                 | `nlm` CLI                                        |
| 40    | NLM freshness monitor               | 22:00               | NLM   | —                                 | `nlm` CLI                                        |
| 41    | NLM heartbeat check                 | \*/6h               | NLM   | —                                 | `nlm` CLI                                        |
| 42    | NLM heartbeat digest                | 00:00               | NLM   | —                                 | `nlm` CLI                                        |
| 43    | NLM ops briefing                    | Lun 00:00           | NLM   | —                                 | `nlm` CLI                                        |
| 44    | NLM persona validate                | Dom 01:00           | NLM   | —                                 | `nlm` CLI                                        |
| 45    | NLM yt monitor                      | \*/6h               | NLM   | —                                 | `nlm` CLI                                        |
| 46    | NLM nb5 t4 monitor (cron)           | Mar,Gio 18:00       | NLM   | —                                 | `nlm` CLI                                        |
| 47    | NLM db-nlm-sync (Air)               | 20:30               | NLM   | —                                 | `nlm` CLI                                        |

### LaunchAgents (38 plist)

| #     | Label                                  | LLM? | Modello                   | Tipo                   | Note                   |
| ----- | -------------------------------------- | ---- | ------------------------- | ---------------------- | ---------------------- |
| 1     | **com.balizero.translate.hourly**      | LLM  | gemma4:26b → e4b          | Scheduled              | Traduzione articoli    |
| 2     | **com.nuzantara.qwen-code-review**     | LLM  | qwen2.5-coder:32b (MORTO) | Scheduled (NOT LOADED) | Da fixare              |
| 3     | **com.nuzantara.dlq-autopilot**        | LLM  | claude --print (CLI)      | Scheduled 30min        | DLQ reasoning          |
| 4     | **com.nuzantara.sentinel**             | LLM  | claude --print (CLI)      | Scheduled 5min         | Classifier fallback    |
| 5     | **com.cell.organism**                  | LLM  | qwen3.5:9b / gemma4:26b   | DAEMON                 | Cell reasoner Tier 0/1 |
| 6     | **com.matagaruda.sentinel.daily**      | LLM  | — (check)                 | Scheduled              | Mata Garuda sentinel   |
| 7     | com.balizero.nlm-bridge                | —    | —                         | DAEMON (port 18790)    | HTTP bridge per NLM    |
| 8     | com.balizero.post-publish-webhook      | —    | —                         | DAEMON (port 7788)     | Webhook server         |
| 9     | com.balizero.post-publish-poller       | —    | —                         | Scheduled              | Intel poller           |
| 10    | com.balizero.intel.nightly             | —    | —                         | Scheduled              | Intel scraper          |
| 11    | com.balizero.renewal-alerts            | —    | —                         | Scheduled              | Expiry alerts          |
| 12    | com.balizero.client-value-predictor    | —    | —                         | Scheduled              | Client scoring         |
| 13    | com.nuzantara.automap-server           | —    | —                         | DAEMON                 | Automap server         |
| 14    | com.nuzantara.automap-telegram         | —    | —                         | DAEMON                 | Automap Telegram       |
| 15    | com.nuzantara.automap-watchdog         | —    | —                         | Scheduled              | Automap health         |
| 16    | com.nuzantara.automations-reference    | —    | —                         | Scheduled 23:15        | Doc generator          |
| 17    | com.nuzantara.disk-monitor             | —    | —                         | Scheduled 30min        | Disk health            |
| 18    | com.nuzantara.launchagent-state-bridge | —    | —                         | Scheduled              | State sync             |
| 19    | com.nuzantara.nuz-sync                 | —    | —                         | Scheduled              | Git sync               |
| 20    | com.nuzantara.nuz-sync-watchdog        | —    | —                         | Scheduled              | Sync health            |
| 21    | com.nuzantara.prime-tunnel             | —    | —                         | DAEMON                 | Cloudflared tunnel     |
| 22    | com.nuzantara.vector-reindex-check     | —    | —                         | Scheduled              | Qdrant check           |
| 23    | com.nuzantara.zombie-hunter            | —    | —                         | Scheduled 1min         | Process cleanup        |
| 24    | ai.openclaw.gateway                    | —    | —                         | DAEMON                 | OpenClaw gateway       |
| 25    | ai.openclaw.monitor-air                | —    | —                         | Scheduled              | Air monitor            |
| 26    | ai.openclaw.tunnel                     | —    | —                         | DAEMON                 | AutoSSH tunnel         |
| 27    | com.garuda.consumer.daily              | —    | —                         | Scheduled              | KG consumer            |
| 28    | com.garuda.gap-detector.twice-daily    | —    | —                         | Scheduled              | KG gap detect          |
| 29    | com.matagaruda.watcher.daily           | —    | —                         | Scheduled              | Garuda watch           |
| 30    | com.claude-max-api                     | —    | —                         | DAEMON                 | Claude MAX proxy       |
| 31    | homebrew.mxcl.ollama                   | —    | —                         | DAEMON                 | Ollama serve           |
| 32    | homebrew.mxcl.postgresql@17            | —    | —                         | DAEMON                 | PostgreSQL             |
| 33    | homebrew.mxcl.redis                    | —    | —                         | DAEMON                 | Redis                  |
| 34    | homebrew.mxcl.syncthing                | —    | —                         | DAEMON                 | File sync              |
| 35-38 | Google/OpenAI updaters                 | —    | —                         | DAEMON                 | System updaters        |

### Backend-RAG (on demand, Fly.io + locale)

| Ruolo              | Modello                | Dove gira      | Warm?     |
| ------------------ | ---------------------- | -------------- | --------- |
| RAG primary        | gemini-3-flash-preview | Fly.io (cloud) | —         |
| RAG fallback       | gemini-2.5-flash       | Fly.io (cloud) | —         |
| FAST (locale)      | qwen3.5:9b             | Pro Ollama     | WARM      |
| HEAVY (locale)     | deepseek-r1:32b        | Pro Ollama     | On-demand |
| KG / JSON (locale) | gemma4:26b             | Pro Ollama     | On-demand |
| VISION (locale)    | qwen2.5vl:7b           | Pro Ollama     | On-demand |

---

## AIR (antonellosiano@Nuzantara-9 — M4 16GB)

### OpenClaw Cron Jobs (12)

| #   | Job                      | Schedule   | Agent | LLM?           | Modello             | Note                  |
| --- | ------------------------ | ---------- | ----- | -------------- | ------------------- | --------------------- |
| 1   | ecosystem-healthcheck    | ogni 6h    | main  | LLM (OpenClaw) | **qwen3:4b** (warm) | Health ping           |
| 2   | fly-health-30m           | ogni 30min | main  | LLM (OpenClaw) | **qwen3:4b** (warm) | MCP check             |
| 3   | system-doctor            | —          | main  | LLM (OpenClaw) | **qwen3:4b** (warm) | System diag           |
| 4   | pg-sync                  | 03:00      | main  | SHELL          | —                   | pg_dump, no LLM       |
| 5   | pg-sync-verify           | 05:00      | main  | LLM (OpenClaw) | **qwen3:4b** (warm) | Verify dump           |
| 6   | intel-pipeline           | 06:00      | main  | LLM (OpenClaw) | **qwen3:4b** (warm) | Scraper orchestration |
| 7   | intel-retry              | 08:00      | main  | LLM (OpenClaw) | **qwen3:4b** (warm) | Failed scrape retry   |
| 8   | source-enrichment-weekly | Dom 03:00  | main  | LLM (OpenClaw) | **qwen3:4b** (warm) | Source enrichment     |
| 9   | nuz-intel-radar          | —          | main  | LLM (OpenClaw) | **qwen3:4b** (warm) | Intel monitor         |
| 10  | nuz-normativa-daily      | —          | main  | LLM (OpenClaw) | **qwen3:4b** (warm) | Regulation check      |
| 11  | nuz-codebase-audit       | —          | main  | LLM (OpenClaw) | **qwen3:4b** (warm) | Code audit            |
| 12  | nuz-weekly-report        | —          | main  | LLM (OpenClaw) | **qwen3:4b** (warm) | Weekly report         |

### Crontab Jobs (29 entries)

| #   | Job                       | Schedule (WITA) | LLM?  | Modello                     | Note                                                |
| --- | ------------------------- | --------------- | ----- | --------------------------- | --------------------------------------------------- |
| 1   | **auto_test.sh**          | 02:15           | LLM   | qwen2.5:latest (via Ollama) | Test con Ollama finestra 01-06                      |
| 3   | **system_doctor.py**      | 08:00           | —     | No LLM diretto              | Parsa log, non genera                               |
| 4   | auto_sentinel.sh          | 03:00           | SHELL | —                           | Wrapper sentinel                                    |
| 5   | auto_kb_ingest.sh         | 05:00           | SHELL | —                           | Spider pipeline                                     |
| 6   | auto_judgement_day.sh     | Dom 16:00       | SHELL | —                           | RAGAS eval (Python, no LLM diretto)                 |
| 7   | rag_canary.py             | \*/6h :30       | SHELL | —                           | Embedding check (OpenAI API per embedding, non LLM) |
| 8   | drive_token_watchdog.py   | \*/6h           | SHELL | —                           | Token check                                         |
| 9   | ragas_eval.py             | Sab 06:00       | SHELL | —                           | RAGAS framework                                     |
| 10  | job_health.py             | 09:00           | SHELL | —                           | Dashboard                                           |
| 11  | crm_automation_engine.py  | 23:00           | API   | —                           | Chiama Fly.io API                                   |
| 12  | ollama_cron_window start  | 01:00           | SHELL | —                           | Avvia Ollama per finestra test                      |
| 13  | ollama_cron_window stop   | 06:05           | SHELL | —                           | Ferma modelli                                       |
| 14  | notifiers/all             | 00:00           | API   | —                           | curl Fly.io                                         |
| 15  | notifiers/birthday        | 00:05           | API   | —                           | curl Fly.io                                         |
| 16  | notifiers/welcome-pending | \*/15min        | API   | —                           | curl Fly.io                                         |
| 17  | fly-pg-backup.sh          | 03:20           | SHELL | —                           | pg_dump                                             |
| 18  | qdrant-snapshot.sh        | Dom 04:00       | SHELL | —                           | Qdrant backup                                       |
| 19  | lkpm-notifier             | 23:00           | API   | —                           | curl Fly.io                                         |
| 20  | auto-practice-creator     | 07:30           | API   | —                           | curl Fly.io                                         |
| 21  | owner-cashout-sync        | Lun 01:00       | SHELL | —                           | Fly sync                                            |
| 22  | db-nlm-sync               | 20:30           | NLM   | —                           | NLM CLI                                             |
| 23  | t4-monitor (cron)         | \*/6h           | NLM   | —                           | NLM CLI                                             |
| 24  | sync-damar.sh             | ogni ora        | SHELL | —                           | SCP                                                 |
| 25  | mos backup                | 04:00           | SHELL | —                           | SQLite cp                                           |
| 26  | mos prune backups         | Dom 05:00       | SHELL | —                           | find + delete                                       |
| 27  | mos ttl cleanup           | 05:00           | SHELL | —                           | SQLite delete                                       |
| 28  | sync-memory-to-nlm        | Dom 03:40       | NLM   | —                           | NLM CLI                                             |
| 29  | cache-cleanup             | 1o+15o          | SHELL | —                           | npm+pip+brew                                        |

### LaunchAgents (18 plist)

| #   | Label                           | LLM? | Modello                                   | Tipo      | Note             |
| --- | ------------------------------- | ---- | ----------------------------------------- | --------- | ---------------- |
| 1   | **com.cell.organism**           | LLM  | qwen3.5:9b (default, ora qwen3:4b)        | DAEMON    | Cell pulse       |
| 2   | **ai.openclaw.node**            | LLM  | Claude Opus → qwen3:4b (da riconfigurare) | DAEMON    | OpenClaw node    |
| 3   | com.nuzantara.guardian-ragas    | —    | —                                         | Scheduled | RAGAS eval       |
| 4   | com.nuzantara.guardian-redteam  | —    | —                                         | Scheduled | Red team         |
| 5   | com.nuzantara.guardian-seo      | —    | —                                         | Scheduled | SEO guardian     |
| 6   | com.nuzantara.nightly-sync      | —    | —                                         | Scheduled | Git sync         |
| 7   | com.nuzantara.nuz-sync          | —    | —                                         | Scheduled | nuz-sync         |
| 8   | com.nuzantara.nuz-sync-watchdog | —    | —                                         | Scheduled | Sync health      |
| 9   | com.nuzantara.fly-pg-tunnel     | —    | —                                         | DAEMON    | Fly PG tunnel    |
| 10  | com.openclaw.monitor-pro        | —    | —                                         | Scheduled | Pro monitor      |
| 11  | com.user.docker-health-check    | —    | —                                         | Scheduled | Docker check     |
| 12  | com.user.weekly-cleanup         | —    | —                                         | Scheduled | Cleanup          |
| 13  | com.claude-max-api              | —    | —                                         | DAEMON    | Claude MAX proxy |
| 14  | homebrew.mxcl.ollama            | —    | —                                         | DAEMON    | Ollama serve     |
| 15  | homebrew.mxcl.postgresql@17     | —    | —                                         | DAEMON    | PostgreSQL       |
| 16  | homebrew.mxcl.redis             | —    | —                                         | DAEMON    | Redis            |
| 17  | homebrew.mxcl.syncthing         | —    | —                                         | DAEMON    | File sync        |
| 18  | com.adobe.ccxprocess            | —    | —                                         | DAEMON    | Adobe (sistema)  |

---

## Riepilogo Modelli Necessari

### PRO — Modelli Ollama richiesti

| Modello               | RAM (warm)       | Warm H24?      | Consumer                                                     |
| --------------------- | ---------------- | -------------- | ------------------------------------------------------------ |
| **qwen3.5:9b**        | ~9GB (32K ctx)   | **SI**         | OpenClaw 15 cron job + Cell Tier 0 + backend-rag FAST        |
| **gemma4:26b**        | ~23GB (256K ctx) | NO (on demand) | translate-articles (→ e4b), backend-rag KG/JSON, Cell Tier 1 |
| **gemma4:e4b**        | ~10GB            | NO (on demand) | translate-articles (nuovo default)                           |
| **qwen2.5vl:7b**      | ~5GB             | NO (on demand) | backend-rag VISION                                           |
| **deepseek-r1:32b**   | ~20GB            | NO (on demand) | backend-rag HEAVY                                            |
| ~~qwen2.5-coder:32b~~ | —                | —              | **MORTO** — non installato, LaunchAgent non loaded           |

### AIR — Modelli Ollama richiesti

| Modello         | RAM (warm)      | Warm H24? | Consumer                                 |
| --------------- | --------------- | --------- | ---------------------------------------- |
| **qwen3:4b**    | ~3.2GB (4K ctx) | **SI**    | OpenClaw 12 cron + Cell sentry           |
| ~~qwen3.5:27b~~ | —               | —         | **MAI INSTALLATO** — rimuovere da config |
| ~~qwen3.5:9b~~  | —               | —         | **MAI INSTALLATO** — rimuovere da config |

### Cloud/CLI (zero RAM locale)

| Modello                | Interfaccia         | Consumer                           |
| ---------------------- | ------------------- | ---------------------------------- |
| claude --print (CLI)   | Subprocess          | Sentinel classifier, DLQ Autopilot |
| gemini --print (CLI)   | Subprocess          | Gap scanner remediate, dispatch    |
| gemini-3-flash-preview | Gemini API (Fly.io) | backend-rag RAG primary            |
| text-embedding-3-small | OpenAI API          | RAG canary, embedding              |
| NLM notebooks          | nlm CLI (cloud)     | 18+ NLM pipeline cron job          |

---

## Timing — Nessun Conflitto RAM

### Pro — Timeline 24h (WITA)

```
00:00 ┌─ qwen3.5:9b WARM H24 (9GB) ──────────────────────────────────────────┐
      │ nightlies: NLM pipelines (cloud, 0 RAM locale)                        │
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
      │ (translate ogni ora :30 → e4b load/unload, ~5s cold, OK)              │
14:00 │ client-health-monitor                                                 │
      │ seo-guardian-observe ogni 40min (warm model, instant)                  │
      │ system-doctor ogni 4h (warm model)                                    │
      │ tech-orchestrator ogni 4h (warm model)                                │
      │ compliance-ops ogni 6h (warm model)                                   │
19:00 │ bali-zero-akta overnight (SHELL, 0 RAM)                              │
20:00 │ NLM nb1-refresh (cloud), NLM gap scanner (cloud)                     │
21:00 │ NLM freshness monitor (cloud)                                         │
22:00 │ NLM multimodal (cloud)                                                │
23:00 │ learning-pipeline (Dom), automations-reference                        │
00:00 └──────────────────────────────────────────────────────────────────────┘

Max RAM simultaneo: 9GB (warm) + 10GB (translate e4b) = 19GB di 48GB. OK.
Worst case: 9GB + 23GB (se KG query durante translate) = 32GB di 48GB. Ancora OK.
```

### Air — Timeline 24h (WITA)

```
00:00 ┌─ qwen3:4b WARM H24 (3.2GB) ────────────────────────────────────────┐
      │ notifiers (API, 0 RAM), welcome-pending */15min (API)                │
01:00 │ ollama-cron-window start (carica qwen2.5 per auto_test 02:15)        │
02:00 │ auto_test.sh (Ollama qwen2.5 + qwen3:4b coesistono: 3.2+3=6.2GB)   │
03:00 │ auto_sentinel (SHELL), fly-pg-backup (SHELL)                         │
04:00 │ qdrant-snapshot (Dom, SHELL)                                         │
05:00 │ kb-ingest (SHELL)                                                    │
06:00 │ ollama-cron-window stop (scarica qwen2.5, qwen3:4b resta warm)       │
      │ ragas_eval (Sab, Python)                                             │
07:00 │                                                                       │
08:00 │ system_doctor (no LLM diretto), drive_watchdog                       │
09:00 │ job_health (SHELL)                                                    │
      │ OpenClaw: fly-health ogni 30min, ecosystem ogni 6h                    │
      │ OpenClaw: intel-pipeline, normativa-daily, codebase-audit             │
16:00 │ auto_judgement_day (Dom, RAGAS)                                       │
20:00 │ db-nlm-sync (NLM cloud)                                              │
23:00 │ crm-automation (API), lkpm-notifier (API)                            │
00:00 └────────────────────────────────────────────────────────────────────────┘

Max RAM simultaneo: 3.2GB (warm) + 3GB (qwen2.5 test window 01-06) = 6.2GB di 16GB.
Fuori finestra test: solo 3.2GB. 12.8GB liberi per OS+PG+Redis+servizi.
```

---

## Configurazioni Critiche per Zero Timeout

| Parametro                   | Valore                                   | Perche'                                                                  |
| --------------------------- | ---------------------------------------- | ------------------------------------------------------------------------ |
| Pro qwen3.5:9b `keep_alive` | `-1` (forever)                           | Mai scaricato, 0s cold load                                              |
| Air qwen3:4b `keep_alive`   | `-1` (forever)                           | Mai scaricato, 0s cold load                                              |
| Pro gemma4:e4b `keep_alive` | `10m`                                    | Si scarica dopo translate, cold load 5s (accettabile su job da 10-30min) |
| Pro gemma4:26b `keep_alive` | `10m`                                    | On-demand per KG, cold load 15s (accettabile su query batch)             |
| Tutti i consumer Ollama     | `think: false`                           | qwen3/3.5 produce thinking tag, content vuoto senza questo flag          |
| Tutti i consumer Ollama     | `format: json`                           | Forza output JSON valido (dove serve JSON)                               |
| Tutti i consumer Ollama API | `keep_alive: -1` in ogni request         | Previene bug reset timer (#5272)                                         |
| Air Python scripts          | `http://127.0.0.1:11434` non `localhost` | IPv4/IPv6 issue: Python non connette a Ollama via `localhost`            |

---

## Note e Scar

1. **qwen3.5:9b tool calling in Ollama e' rotto** ([#14493](https://github.com/ollama/ollama/issues/14493)) — ma i nostri cron OpenClaw NON usano il parametro `tools`, usano messaggi testuali → non ci impatta
2. **gemma4:12b non esiste** — Gemma 4 ha solo e2b/e4b/26b/31b
3. **Ollama MLX** su Pro (48GB >= 32GB): ~65-80 tok/s. Air (16GB): NON qualifica, resta Metal
4. **Ollama memory fragmentation** dopo 3-7 giorni → weekly restart schedulato Dom 05:00
5. **Air Python urllib Connection Refused** su `localhost:11434` — usare `127.0.0.1` o subprocess curl

---

## GitHub Actions (8 workflow)

| #   | Workflow           | Trigger         | Schedule      | LLM? | Note                              |
| --- | ------------------ | --------------- | ------------- | ---- | --------------------------------- |
| 1   | docs-sync          | push/PR         | —             | —    | Checks docs in sync               |
| 2   | fly-deploy         | push to main    | —             | —    | Multi-stage: lint→test→deploy     |
| 3   | fly-secrets-check  | scheduled + man | Lun 09:00 UTC | —    | Verifica FLY_API_TOKEN + TG alert |
| 4   | intel-router-tests | push/PR         | —             | —    | bali-intel-scraper API tests      |
| 5   | security-scanning  | scheduled + man | Dom 00:00 UTC | —    | Snyk Python + Node                |
| 6   | semgrep-sast       | push/PR         | —             | —    | Bandit + ESLint, blocks on HIGH   |
| 7   | sonarqube          | push/PR         | —             | —    | Code quality gates                |
| 8   | tests              | push/PR         | —             | —    | pytest + coverage gate            |

---

## Claude Code Hooks (12 hooks)

| #   | Event            | Matcher    | LLM? | Note                             |
| --- | ---------------- | ---------- | ---- | -------------------------------- |
| 1-3 | PostToolUse      | Edit/Write | —    | 3 post-processors on file edits  |
| 4   | PostToolUse      | Bash       | —    | Post-processor on shell commands |
| 5   | PostToolUse      | \*         | —    | Global post-processor            |
| 6   | Notification     | \*         | —    | Notification handler             |
| 7   | PreToolUse       | Edit/Write | —    | Pre-validation on file edits     |
| 8   | PreToolUse       | Bash       | —    | Pre-validation on shell          |
| 9   | Stop             | \*         | —    | Session cleanup                  |
| 10  | SessionStart     | compact    | —    | Context loading                  |
| 11  | SessionStart     | \*         | —    | Global init                      |
| 12  | UserPromptSubmit | \*         | —    | Prompt pre-processing            |

---

## Backend Event-Driven (16 entries)

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

---

## Home Scripts (~/scripts/ — non in repo, 13 entries)

| #   | Script                      | Type         | System  | Note                           |
| --- | --------------------------- | ------------ | ------- | ------------------------------ |
| 1   | ai-intel-sentinel.sh        | TCC bridge   | Intel   | LaunchAgent→venv bypass        |
| 2   | cron-runner.sh              | wrapper      | Ops     | macOS provenance bypass        |
| 3   | deadman-heartbeat.sh        | monitor      | Ops     | Pro→Air ogni 30s               |
| 4   | comfyui-server.sh           | manual       | AI      | Image gen (non schedulato)     |
| 5   | gdrive-backup-all.sh        | orchestrator | Backup  | PG+Qdrant+Intel→GDrive         |
| 6   | gdrive-intel-archive.sh     | backup       | Backup  | Intel data→GDrive 30TB         |
| 7   | gdrive-pg-backup.sh         | backup       | Backup  | PG→GDrive secondary DR         |
| 8   | gdrive-qdrant-backup.sh     | backup       | Backup  | Qdrant→GDrive                  |
| 9   | generate-automations-all.sh | generator    | Ops     | MD+Excel via LaunchAgent 23:15 |
| 10  | mata-garuda-watcher.sh      | TCC bridge   | Garuda  | LaunchAgent→repo bridge        |
| 11  | warroom-wrapper.sh          | TCC bridge   | Content | LaunchAgent→War Room bridge    |
| 12  | setup-grafana-cloud.sh      | setup        | Ops     | One-time Grafana setup         |
| 13  | setup-log-drain.sh          | setup        | Ops     | One-time log drain setup       |

---

## Air Cron Extras (5 entries non nel blocco principale)

| #   | Job                    | Schedule         | System     | Note                          |
| --- | ---------------------- | ---------------- | ---------- | ----------------------------- |
| 1   | LKPM deadline notifier | 07:00 WITA daily | Compliance | API call a Fly.io             |
| 2   | db-nlm-sync            | 20:30 UTC daily  | NLM        | DB→NotebookLM                 |
| 3   | T4 monitor             | ogni 6h          | Content    | Social monitor                |
| 4   | Ollama restart weekly  | Dom 05:00        | AI         | Previene memory fragmentation |
| 5   | Auto practice creator  | 07:30 WITA daily | CRM        | Crea pratiche rinnovo T-60    |

---

_Compilata da: Claude Opus 4.6, verificata su dati live 2026-04-14_
_Deep scan sessione 2: +52 automazioni (179→231 totali)_
