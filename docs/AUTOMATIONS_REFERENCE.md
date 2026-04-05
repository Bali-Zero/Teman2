# NUZANTARA — AUTOMATIONS REFERENCE

> **Auto-generated from live system state** — do not edit manually.
> Generated: 2026-04-05 15:50 UTC
> Source: `crontab -l` (Pro+Air) + `launchctl list` (Pro+Air) + log file health

---

## System Health Summary

| Metric | Value |
|--------|-------|
| Total jobs | **99** |
| ✅ Healthy | **18** |
| 🔄 Running (daemons) | **14** |
| ⚠️ Warning/Skip | **22** |
| ❌ Failed | **25** |

---

## Pro (nuzantara@Nuzantara — M4 Pro 48GB)

### LaunchAgents

| Label | Status | Exit |
|-------|--------|------|
| `ai.openclaw.gateway` | 🔄 Running (PID=99074) | 0 |
| `ai.openclaw.monitor-air` | ✅ OK | 0 |
| `ai.openclaw.tunnel` | 🔄 Running (PID=3720) | 1 |
| `com.balizero.backend-prewarm` | ✅ OK | 0 |
| `com.balizero.client-value-predictor` | ✅ OK | 0 |
| `com.balizero.intel.nightly` | ✅ OK | 0 |
| `com.balizero.nlm-bridge` | 🔄 Running (PID=51145) | 1 |
| `com.balizero.post-publish-poller` | ✅ OK | 0 |
| `com.balizero.post-publish-webhook` | 🔄 Running (PID=1998) | 0 |
| `com.balizero.renewal-alerts` | ✅ OK | 0 |
| `com.balizero.translate.hourly` | ✅ OK | 0 |
| `com.cell.organism` | 🔄 Running (PID=1993) | 0 |
| `com.claude-max-api` | 🔄 Running (PID=2000) | 0 |
| `com.nuzantara.dlq-autopilot` | ✅ OK | 0 |
| `com.nuzantara.prime-dashboard` | ⚠️ NOT LOADED | ? |
| `com.nuzantara.prime-tunnel` | 🔄 Running (PID=3718) | 1 |
| `com.nuzantara.qwen-code-review` | ⚠️ NOT LOADED | ? |
| `com.nuzantara.sentinel` | ✅ OK | 0 |
| `com.nuzantara.vector-reindex-check` | ✅ OK | 0 |
| `com.nuzantara.zombie-hunter` | ✅ OK | 0 |

### Cron Jobs

| Job | Schedule | Last Run | Status | Notes |
|-----|----------|----------|--------|-------|
| `.pro_heartbeat` | 0 * * * * |  |  |  |
| `backups` | Sun 5:00 UTC |  |  |  |
| `conversation_trainer` | Sun 3:00 UTC |  | ⚠️ NO LOG |  |
| `cron_cache_cleanup` | 1st+15th 3:30 UTC |  | ⚠️ NO LOG |  |
| `drive_poll` | every 5m | 2026-04-05 23:50 | ✅ OK | [2026-04-05 23:50:12] ✅ Drive poll OK: 0 new files processed |
| `expiry_alerter` | daily 8:00 UTC | 2026-04-04 08:00 | ❌ FAIL | /Applications/Xcode.app/Contents/Developer/usr/bin/python3:  |
| `fly_backup` | daily 3:00 UTC | 2026-04-04 03:01 | ❌ FAIL | [2026-04-04 03:01:11] ERROR: pg_dump failed after 3 attempts |
| `fly_health_check` | daily 7-19:*/30 UTC | 2026-04-05 19:30 | ✅ OK | [2026-04-05 19:30:05] ✅ All services healthy |
| `freshness_monitor` | daily 22:00 UTC | 2026-04-05 22:00 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |
| `gap_scanner` | daily 21:30 UTC | 2026-04-05 21:30 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |
| `gap_scanner` | Sun 19:00 UTC | 2026-04-05 21:30 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |
| `gap_scanner` | Sun 20:30 UTC | 2026-04-05 21:30 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |
| `heartbeat_check` | every 6h (:30) | 2026-04-05 18:30 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |
| `heartbeat_check` | daily 0:00 UTC | 2026-04-05 18:30 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |
| `intel_scraper_sentinel_bridge` | every 5m |  |  |  |
| `knowledge_graph_builder` | Sun 2:00 UTC |  | ⚠️ NO LOG |  |
| `legal_radar` | Sun 0:00 UTC |  | ⚠️ NO LOG |  |
| `memory` | daily 4:00 UTC |  |  |  |
| `memory` | daily 5:00 UTC |  |  |  |
| `multimodal` | Sun 22:00 UTC | 2026-04-05 22:00 | ❌ FAIL | /bin/bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator |
| `multimodal` | Mon 22:00 UTC | 2026-04-05 22:00 | ❌ FAIL | /bin/bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator |
| `multimodal` | 0 22 * * 2 | 2026-04-05 22:00 | ❌ FAIL | /bin/bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator |
| `multimodal` | 0 22 * * 3 | 2026-04-05 22:00 | ❌ FAIL | /bin/bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator |
| `multimodal` | 0 22 * * 4 | 2026-04-05 22:00 | ❌ FAIL | /bin/bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator |
| `multimodal` | 0 22 * * 6 | 2026-04-05 22:00 | ❌ FAIL | /bin/bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator |
| `nb10_pipeline` | Mon-Sat 2:50 UTC |  | ⚠️ NO LOG |  |
| `nb1_refresh` | daily 20:30 UTC | 2026-04-05 20:30 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |
| `nb2_pipeline` | Sun-Fri 18:10 UTC | 2026-04-05 18:10 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |
| `nb3_pipeline` | Mon-Sat 2:45 UTC |  | ⚠️ NO LOG |  |
| `nb4_pipeline` | Mon-Sat 2:20 UTC |  | ⚠️ NO LOG |  |
| `nb5_pipeline` | Mon-Sat 2:25 UTC |  | ⚠️ NO LOG |  |
| `nb5_t4_monitor` | Tue,Thu 18:00 UTC |  | ⚠️ NO LOG |  |
| `nb6_pipeline` | Mon-Sat 2:30 UTC |  | ⚠️ NO LOG |  |
| `nb7_pipeline` | Mon-Sat 2:35 UTC |  | ⚠️ NO LOG |  |
| `nb8_pipeline` | Mon-Sat 2:40 UTC |  | ⚠️ NO LOG |  |
| `nlm_bridge.last` | every 4m |  |  |  |
| `openclaw_state_bridge` | every 5m | 2026-04-05 23:50 | ? unknown | [openclaw-bridge] Written 24/24 state files |
| `ops_briefing` | Mon 0:00 UTC |  | ⚠️ NO LOG |  |
| `peraturan_ingestion` | Sun 21:30 UTC | 2026-04-05 21:30 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |
| `persona_validate` | Sun 1:00 UTC |  | ⚠️ NO LOG |  |
| `pipeline` | daily 11:52 UTC |  | ⚠️ NO LOG |  |
| `sync_damar` | 0 * * * * |  |  |  |
| `sync_memory_to_nlm` | Sun 3:00 UTC |  | ⚠️ NO LOG |  |
| `yt_monitor` | every 6h (:30) | 2026-04-05 18:30 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |

---

## Air (antonellosiano@Nuzantara-9 — M4 16GB, H24)

### LaunchAgents

| Label | Status | Exit |
|-------|--------|------|
| `ai.openclaw.node` | 🔄 Running (PID=5908) | 0 |
| `com.cell.organism` | 🔄 Running (PID=994) | 0 |
| `com.claude-max-api` | 🔄 Running (PID=999) | 0 |
| `com.nuzantara.fly-pg-tunnel` | 🔄 Running (PID=58795) | 1 |
| `com.nuzantara.nightly-sync` | ✅ OK | 0 |
| `com.openclaw.monitor-pro` | ✅ OK | 0 |
| `com.user.docker-health-check` | ✅ OK | 0 |
| `com.user.weekly-cleanup` | ⚠️ NOT LOADED | ? |
| `homebrew.mxcl.ollama` | 🔄 Running (PID=998) | 0 |
| `homebrew.mxcl.postgresql@17` | 🔄 Running (PID=40852) | 0 |
| `homebrew.mxcl.redis` | 🔄 Running (PID=993) | 0 |

### Cron Jobs

| Job | Schedule | Last Run | Status | Notes |
|-----|----------|----------|--------|-------|
| `all` | daily 0:00 UTC | 2026-04-04 00:05 | ❌ FAIL | {"visa_expiry":{"total_alerts":4},"unpaid_invoices":{"overdu |
| `auto_judgement_day` | Sun 16:00 UTC | 2026-04-05 16:00 | ⚠️ WARN | [2026-04-05 16:00:01] ⚠️  SKIP: ragas not installed in venv. |
| `auto_kb_ingest` | daily 5:00 UTC | 2026-04-05 05:00 | ✅ OK | [2026-04-05 05:00:01] ✅ KB Ingestion Cycle Complete. |
| `auto_sentinel` | daily 3:00 UTC | 2026-04-05 03:00 | ✅ OK | [Watchdog 03:00:00] INFO: === Watchdog Complete === |
| `auto_test` | daily 2:15 UTC | 2026-04-05 02:16 | ❌ FAIL | [2026-04-05 02:15:00] ❌ Test failures: agentic llm |
| `backups` | Sun 5:00 UTC |  |  |  |
| `birthday` | daily 0:05 UTC | 2026-04-04 00:05 | ❌ FAIL | {"visa_expiry":{"total_alerts":4},"unpaid_invoices":{"overdu |
| `crm_automation_engine` | daily 23:00 UTC | 2026-04-05 23:00 |  |  |
| `cron_cache_cleanup` | 1st+15th 3:30 UTC |  | ⚠️ NO LOG |  |
| `db_nlm_sync` | daily 20:30 UTC | 2026-04-05 20:30:01,456 [WARNING] __main__: DB→NLM sync already running (PID 19399). Exiting. |  |  |
| `drive_token_watchdog` | every 6h (:0) | 2026-04-05 18:00 |  |  |
| `fly_pg_backup` | daily 3:00 UTC | 2026-04-05 03:00 | ❌ FAIL | [03:00:22] ALERT: Proxy not ready after 20s — aborting |
| `memory` | daily 4:00 UTC |  |  |  |
| `memory` | daily 5:00 UTC |  |  |  |
| `ollama_cron_window` | daily 1:00 UTC | 2026-04-05 06:05 |  |  |
| `ollama_cron_window` | daily 6:05 UTC |  |  |  |
| `rag_canary` | every 6h (:30) | 2026-04-05 18:30 |  |  |
| `ragas_eval` | Sun 6:00 UTC | 2026-04-05 06:00 |  |  |
| `seo_guardian_agent` | daily 1:00 UTC | 2026-04-05 01:00 | ⚠️ WARN |     "skipped": [] |
| `sync_damar` | 0 * * * * |  |  |  |
| `sync_memory_to_nlm` | Sun 3:00 UTC | 2026-04-05 03:00 | ❌ FAIL | Error: in prepare, no such table: sessions |
| `system_doctor` | daily 8:00 UTC | 2026-04-05 08:00 | ❌ FAIL |   "telegram_summary": "\ud83c\udfe5 System Doctor \u2014 202 |
| `t4_monitor` | every 6h (:0) | 2026-04-05T10:00:11Z [DONE] T4 monitor completed |  |  |
| `welcome_pending` | every 15m | 2026-04-05 23:45 | ❌ FAIL | {"detail":"Not Found","correlation_id":"d4666afd-6d6f-4eda-9 |

---

*Generated by `scripts/generate_automations_reference.py` — 2026-04-05 15:50 UTC*
