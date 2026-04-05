# NUZANTARA — AUTOMATIONS REFERENCE

> **Auto-generated from live system state** — do not edit manually.
> Generated: 2026-04-05 15:54 UTC
> Source: `crontab -l` (Pro+Air) + `launchctl list` (Pro+Air) + log health

---

## System Health Summary

| Metric | Value |
|--------|-------|
| Total jobs | **94** |
| ✅ Healthy | **16** |
| 🔄 Running (daemons) | **18** |
| ⚠️ Warning/Skip/NoLog | **19** |
| ❌ Failed | **10** |

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
| `homebrew.mxcl.ollama` | 🔄 Running (PID=1997) | 0 |
| `homebrew.mxcl.postgresql@17` | 🔄 Running (PID=2006) | 0 |
| `homebrew.mxcl.redis` | 🔄 Running (PID=1992) | 0 |
| `homebrew.mxcl.syncthing` | 🔄 Running (PID=2005) | 0 |

### Cron Jobs

| Job | Schedule | Last Run | Status | Notes |
|-----|----------|----------|--------|-------|
| `cache_cleanup` | 1st+15th 3:30 UTC |  | ⚠️ NO LOG |  |
| `conversation_trainer` | Sun 3:00 UTC |  | ⚠️ NO LOG |  |
| `drive_poll` | every 5m | 2026-04-05 23:50 | ✅ OK | [2026-04-05 23:50:12] ✅ Drive poll OK: 0 new files processed |
| `expiry_alerter` | daily 8:00 UTC | 2026-04-04 08:00 | ❌ FAIL | /Applications/Xcode.app/Contents/Developer/usr/bin/python3:  |
| `fly_backup` | daily 3:00 UTC | 2026-04-04 03:01 | ❌ FAIL | [2026-04-04 03:01:11] ERROR: pg_dump failed after 3 attempts |
| `fly_health_check` | daily 7-19:*/30 UTC | 2026-04-05 19:30 | ✅ OK | [2026-04-05 19:30:05] ✅ All services healthy |
| `freshness_monitor` | daily 22:00 UTC | 2026-04-05 22:00 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |
| `gap_scanner` | daily 21:30 UTC (+2 more) | 2026-04-05 21:30 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |
| `heartbeat_check` | every 6h (:30) (+1 more) | 2026-04-05 18:30 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |
| `intel_scraper_sentinel_bridge` | every 5m |  |  |  |
| `knowledge_graph_builder` | Sun 2:00 UTC |  | ⚠️ NO LOG |  |
| `legal_radar` | Sun 0:00 UTC |  | ⚠️ NO LOG |  |
| `mos_backup` | daily 4:00 UTC |  |  |  |
| `mos_prune_backups` | Sun 5:00 UTC |  |  |  |
| `mos_ttl_cleanup` | daily 5:00 UTC |  |  |  |
| `multimodal` | Sun 22:00 UTC (+5 more) | 2026-04-05 22:00 | ❌ FAIL | /bin/bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator |
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
| `nlm_bridge_state` | every 4m |  |  |  |
| `openclaw_state_bridge` | every 5m | 2026-04-05 23:50 | ? check | [openclaw-bridge] Written 24/24 state files |
| `ops_briefing` | Mon 0:00 UTC |  | ⚠️ NO LOG |  |
| `peraturan_ingestion` | Sun 21:30 UTC | 2026-04-05 21:30 | ❌ FAIL | bash: /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_ |
| `persona_validate` | Sun 1:00 UTC |  | ⚠️ NO LOG |  |
| `pro_heartbeat` | 0 * * * * |  |  |  |
| `sync_damar` | 0 * * * * |  |  |  |
| `sync_memory_to_nlm` | Sun 3:00 UTC |  | ⚠️ NO LOG |  |
| `war_room_oneshot` | daily 11:52 UTC |  | ⚠️ NO LOG |  |
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
| `auto_judgement_day` | Sun 16:00 UTC |  |  |  |
| `auto_kb_ingest` | daily 5:00 UTC |  |  |  |
| `auto_sentinel` | daily 3:00 UTC |  |  |  |
| `auto_test` | daily 2:15 UTC |  |  |  |
| `cache_cleanup` | 1st+15th 3:30 UTC |  |  |  |
| `crm_automation_engine` | daily 23:00 UTC |  |  |  |
| `db_nlm_sync` | daily 20:30 UTC |  |  |  |
| `drive_token_watchdog` | every 6h (:0) |  |  |  |
| `fly_pg_backup` | daily 3:00 UTC |  |  |  |
| `mos_backup` | daily 4:00 UTC |  |  |  |
| `mos_prune_backups` | Sun 5:00 UTC |  |  |  |
| `mos_ttl_cleanup` | daily 5:00 UTC |  |  |  |
| `notifiers_all` | daily 0:00 UTC |  |  |  |
| `notifiers_birthday` | daily 0:05 UTC |  |  |  |
| `notifiers_welcome` | every 15m |  |  |  |
| `ollama_cron_window` | daily 1:00 UTC (+1 more) |  |  |  |
| `rag_canary` | every 6h (:30) |  |  |  |
| `ragas_eval` | Sun 6:00 UTC |  |  |  |
| `seo_guardian_agent` | daily 1:00 UTC |  |  |  |
| `sync_damar` | 0 * * * * |  |  |  |
| `sync_memory_to_nlm` | Sun 3:00 UTC |  |  |  |
| `system_doctor` | daily 8:00 UTC |  |  |  |
| `t4_monitor` | every 6h (:0) |  |  |  |

---

*Generated by `scripts/generate_automations_reference.py` — 2026-04-05 15:54 UTC*
