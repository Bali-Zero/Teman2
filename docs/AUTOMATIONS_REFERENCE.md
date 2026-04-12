# NUZANTARA — AUTOMATIONS REFERENCE

> **Auto-generated from live system state** — do not edit manually.
> Generated: 2026-04-12 18:50 UTC
> Source: `crontab -l` (Pro+Air) + `launchctl list` (Pro+Air) + log health + `job_registry.json` + `sentinel_status.json` + `circuit_breakers.json`

---

## System Health Summary

| Metric                | Value  |
| --------------------- | ------ |
| Total jobs            | **83** |
| ✅ Healthy            | **26** |
| 🔄 Running (daemons)  | **20** |
| ⚠️ Warning/Skip/NoLog | **10** |
| ❌ Failed             | **9**  |

---

## Sentinel Overview

> Ultimo aggiornamento sentinel: `2026-04-12T18:50:24Z`

| Metrica                   | Valore                               |
| ------------------------- | ------------------------------------ |
| Circuit OPEN              | **9**                                |
| Circuit TERMINAL          | **19**                               |
| DLQ entries totali        | **59**                               |
| DLQ phase distribution    | `T0=4 · T3=19 · T4=17 · TERMINAL=19` |
| Job critici (in registry) | **4**                                |

---

## Pro (nuzantara@Nuzantara — M4 Pro 48GB)

### LaunchAgents

| Label                                    | Status                 | Exit | Circuit | Scope | Critical |
| ---------------------------------------- | ---------------------- | ---- | ------- | ----- | -------- |
| `ai.openclaw.gateway`                    | 🔄 Running (PID=42111) | 0    | —       | —     |          |
| `ai.openclaw.monitor-air`                | ✅ OK                  | 0    | —       | —     |          |
| `ai.openclaw.tunnel`                     | 🔄 Running (PID=8455)  | 1    | —       | —     |          |
| `com.balizero.client-value-predictor`    | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.intel.nightly`             | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.nlm-bridge`                | 🔄 Running (PID=64504) | 1    | —       | —     |          |
| `com.balizero.post-publish-poller`       | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.post-publish-webhook`      | 🔄 Running (PID=3395)  | 0    | —       | —     |          |
| `com.balizero.renewal-alerts`            | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.translate.hourly`          | ❌ FAILED (exit=1)     | 1    | —       | —     |          |
| `com.cell.organism`                      | 🔄 Running (PID=3389)  | 0    | —       | —     |          |
| `com.claude-max-api`                     | 🔄 Running (PID=3397)  | 0    | —       | —     |          |
| `com.nuzantara.automap-server`           | 🔄 Running (PID=3376)  | 0    | —       | —     |          |
| `com.nuzantara.automap-telegram`         | 🔄 Running (PID=3382)  | 0    | —       | —     |          |
| `com.nuzantara.automap-watchdog`         | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.automations-reference`    | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.disk-monitor`             | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.dlq-autopilot`            | 🔄 Running (PID=76544) | 0    | —       | —     |          |
| `com.nuzantara.launchagent-state-bridge` | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.nuz-sync`                 | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.nuz-sync-watchdog`        | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.prime-tunnel`             | 🔄 Running (PID=3374)  | 0    | —       | —     |          |
| `com.nuzantara.qwen-code-review`         | ⚠️ NOT LOADED          | ?    | —       | —     |          |
| `com.nuzantara.sentinel`                 | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.vector-reindex-check`     | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.zombie-hunter`            | ✅ OK                  | 0    | —       | —     |          |
| `homebrew.mxcl.postgresql@17`            | 🔄 Running (PID=3404)  | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                    | 🔄 Running (PID=3386)  | 0    | —       | —     |          |
| `homebrew.mxcl.syncthing`                | 🔄 Running (PID=3403)  | 0    | —       | —     |          |

### Cron Jobs

| Job                         | Schedule              | Last Run         | Status    | Circuit      | Scope        | Critical | Notes                                               |
| --------------------------- | --------------------- | ---------------- | --------- | ------------ | ------------ | -------- | --------------------------------------------------- |
| `cache_cleanup`             | 1st+15th 3:30 UTC     |                  | ⚠️ NO LOG | —            | —            |          |                                                     |
| `cert_monitor`              | daily 7:00 UTC        |                  |           | —            | OBSERVE_ONLY | 🔴       |                                                     |
| `cron_runner`               | every 5m (+27 more)   |                  | ⚠️ NO LOG | —            | —            |          |                                                     |
| `drive_poll`                | every 5m              | 2026-04-13 02:50 | ✅ OK     | —            | —            |          | [2026-04-13 02:50:01] ✅ Drive poll OK: 0 new files |
| `expiry_alerter`            | daily 8:00 UTC        | 2026-04-12 08:00 | ? check   | ✅ CLOSED/T0 | LOCAL        | 🔴       | No expiries found.                                  |
| `fly_backup`                | daily 3:00 UTC        | 2026-04-12 03:02 | ❌ FAIL   | —            | EXTERNAL     | 🔴       | [2026-04-12 03:02:05] ERROR: pg_dump failed after   |
| `fly_cost_alert`            | Mon 9:00 UTC          |                  | ⚠️ NO LOG | —            | —            |          |                                                     |
| `fly_health_check`          | every 30m             | 2026-04-13 02:30 | ✅ OK     | ✅ CLOSED/T0 | EXTERNAL     | 🔴       | [2026-04-13 02:30:02] ✅ All services healthy       |
| `fly_restart_loop_detector` | every 15m             |                  |           | —            | —            |          |                                                     |
| `legal_radar`               | Sun 0:00 UTC          |                  | ⚠️ NO LOG | —            | —            |          |                                                     |
| `mos_maintenance`           | daily 4:00 UTC        |                  |           | —            | LOCAL        |          |                                                     |
| `nlm_bridge_state`          | every 4m              |                  |           | —            | —            |          |                                                     |
| `openclaw_state_bridge`     | every 5m              | 2026-04-13 02:50 | ? check   | —            | —            |          | [openclaw-bridge] Written 24/24 state files         |
| `overnight`                 | Sun-Fri 19:00 UTC     |                  | ⚠️ NO LOG | —            | —            |          |                                                     |
| `pro_heartbeat`             | 0 \* \* \* \*         |                  |           | —            | —            |          |                                                     |
| `sync_damar`                | 0 \* \* \* \*         |                  |           | —            | —            |          |                                                     |
| `sync_memory_ruslana`       | daily 8:00 UTC        | 2026-04-12 09:29 | ? check   | —            | —            |          | [2026-04-12 09:29] Synced 0 memory files to Ruslan  |
| `sync_memory_to_nlm`        | Sun 3:00 UTC          |                  | ⚠️ NO LOG | —            | —            |          |                                                     |
| `warmup_vision`             | Mon-Sat 9-17:\*/4 UTC |                  |           | —            | —            |          |                                                     |

---

## Air (antonellosiano@Nuzantara-9 — M4 16GB, H24)

### LaunchAgents

| Label                             | Status                | Exit | Circuit | Scope | Critical |
| --------------------------------- | --------------------- | ---- | ------- | ----- | -------- |
| `ai.openclaw.node`                | 🔄 Running (PID=4493) | 0    | —       | —     |          |
| `com.cell.organism`               | ❌ FAILED (exit=1)    | 1    | —       | —     |          |
| `com.claude-max-api`              | 🔄 Running (PID=1316) | 0    | —       | —     |          |
| `com.nuzantara.fly-pg-tunnel`     | 🔄 Running (PID=1748) | 126  | —       | —     |          |
| `com.nuzantara.guardian-ragas`    | ✅ OK                 | 0    | —       | —     |          |
| `com.nuzantara.guardian-redteam`  | ✅ OK                 | 0    | —       | —     |          |
| `com.nuzantara.guardian-seo`      | ✅ OK                 | 0    | —       | —     |          |
| `com.nuzantara.nightly-sync`      | ✅ OK                 | 0    | —       | —     |          |
| `com.nuzantara.nuz-sync`          | ✅ OK                 | 0    | —       | —     |          |
| `com.nuzantara.nuz-sync-watchdog` | ✅ OK                 | 0    | —       | —     |          |
| `com.openclaw.monitor-pro`        | ✅ OK                 | 0    | —       | —     |          |
| `com.user.docker-health-check`    | ✅ OK                 | 0    | —       | —     |          |
| `com.user.weekly-cleanup`         | ✅ OK                 | 0    | —       | —     |          |
| `homebrew.mxcl.ollama`            | 🔄 Running (PID=1314) | 0    | —       | —     |          |
| `homebrew.mxcl.postgresql@17`     | 🔄 Running (PID=1322) | 0    | —       | —     |          |
| `homebrew.mxcl.redis`             | 🔄 Running (PID=1308) | 0    | —       | —     |          |
| `homebrew.mxcl.syncthing`         | 🔄 Running (PID=1321) | 0    | —       | —     |          |

### Cron Jobs

| Job                   | Schedule                 | Last Run         | Status    | Circuit | Scope | Critical | Notes                                               |
| --------------------- | ------------------------ | ---------------- | --------- | ------- | ----- | -------- | --------------------------------------------------- |
| `audit_trail_cleanup` | Sun 2:00 UTC             |                  | ⚠️ NO LOG | —       | —     |          |                                                     |
| `auto_create`         | daily 7:30 UTC           | 2026-04-12 07:30 | ❌ FAIL   | —       | —     |          | {"visas_checked":0,"practices_created":0,"practice  |
| `auto_judgement_day`  | Sun 16:00 UTC            | 2026-04-12 16:00 | ❌ FAIL   | —       | —     |          | [2026-04-12 16:00:01] ❌ Evaluation FAILED with exi |
| `auto_sentinel`       | daily 3:00 UTC           | 2026-04-12 03:00 | ✅ OK     | —       | —     |          | [Watchdog 03:00:02] INFO: === Watchdog Complete ==  |
| `auto_test`           | daily 2:15 UTC           | 2026-04-13 02:15 | ❌ FAIL   | —       | —     |          | [2026-04-13 02:15:00] Agent tests — Passed: 2 \| F  |
| `cache_cleanup`       | 1st+15th 3:30 UTC        |                  | ⚠️ NO LOG | —       | —     |          |                                                     |
| `cron_wrapper`        | daily 5:00 UTC (+8 more) |                  |           | —       | —     |          |                                                     |
| `job_health`          | daily 9:00 UTC           | 2026-04-11 09:00 |           | —       | —     |          |                                                     |
| `mos_backup`          | daily 4:00 UTC           |                  |           | —       | —     |          |                                                     |
| `mos_prune_backups`   | Sun 5:00 UTC             |                  |           | —       | —     |          |                                                     |
| `mos_ttl_cleanup`     | daily 5:00 UTC           |                  |           | —       | —     |          |                                                     |
| `notifiers_all`       | daily 0:00 UTC           | 2026-04-13 00:05 | ❌ FAIL   | —       | —     |          | {"visa_expiry":{"total_alerts":4},"unpaid_invoices  |
| `notifiers_birthday`  | daily 0:05 UTC           | 2026-04-13 00:05 | ❌ FAIL   | —       | —     |          | {"visa_expiry":{"total_alerts":4},"unpaid_invoices  |
| `notifiers_welcome`   | every 15m                | 2026-04-13 02:45 | ❌ FAIL   | —       | —     |          | {"detail":"Not Found","correlation_id":"d4666afd-6  |
| `ollama_cron_window`  | daily 1:00 UTC (+1 more) | 2026-04-13 01:00 |           | —       | —     |          |                                                     |
| `ragas_eval`          | 6 6:00 UTC               | 2026-04-11 06:00 |           | —       | —     |          |                                                     |
| `sync_damar`          | 0 \* \* \* \*            |                  |           | —       | —     |          |                                                     |
| `sync_memory_to_nlm`  | Sun 3:40 UTC             |                  | ⚠️ NO LOG | —       | —     |          |                                                     |

---

_Generated by `scripts/generate_automations_reference.py` — 2026-04-12 18:50 UTC_
