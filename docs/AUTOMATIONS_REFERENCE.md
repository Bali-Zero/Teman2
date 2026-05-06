# NUZANTARA — AUTOMATIONS REFERENCE

> **Auto-generated from live system state** — do not edit manually.
> Generated: 2026-05-06 07:02 UTC
> Source: `crontab -l` (Pro+Mini) + `launchctl list` (Pro+Mini) + log health + `job_registry.json` + `sentinel_status.json` + `circuit_breakers.json`

---

## System Health Summary

| Metric                | Value   |
| --------------------- | ------- |
| Total jobs            | **123** |
| ✅ Healthy            | **65**  |
| 🔄 Running (daemons)  | **26**  |
| ⚠️ Warning/Skip/NoLog | **4**   |
| ❌ Failed             | **11**  |

---

## Sentinel Overview

> Ultimo aggiornamento sentinel: `2026-05-06T06:17:11Z`

| Metrica                   | Valore               |
| ------------------------- | -------------------- |
| Circuit OPEN              | **22**               |
| Circuit TERMINAL          | **3**                |
| DLQ entries totali        | **63**               |
| DLQ phase distribution    | `T4=60 · TERMINAL=3` |
| Job critici (in registry) | **2**                |

---

## Pro (nuzantara@Nuzantara — M4 Pro 48GB)

### LaunchAgents

| Label                                         | Status                 | Exit | Circuit | Scope | Critical |
| --------------------------------------------- | ---------------------- | ---- | ------- | ----- | -------- |
| `ai.openclaw.gateway`                         | 🔄 Running (PID=89977) | 1    | —       | —     |          |
| `com.balizero.bz-daily-visual-pipeline`       | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.client-value-predictor`         | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.codex-spalla-calibrate`         | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.indexing-sweep.daily`           | ⚠️ NOT LOADED          | ?    | —       | —     |          |
| `com.balizero.intel-radar-daily-digest`       | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.intel.nightly`                  | 🔄 Running (PID=63391) | 0    | —       | —     |          |
| `com.balizero.nlm-bridge`                     | 🔄 Running (PID=3908)  | 0    | —       | —     |          |
| `com.balizero.post-publish-poller`            | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.post-publish-webhook`           | 🔄 Running (PID=3955)  | 0    | —       | —     |          |
| `com.balizero.renewal-alerts`                 | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.seo-cell.28d-check`             | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.seo-cell.daily`                 | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.sota.m13-checkpoint`            | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.sota.m13-collect`               | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.sota.m13-monthly`               | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.sota.m13-weekly`                | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.translate.hourly`               | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.wr2.canva-apply`                | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.wr2.connector`                  | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.wr2.dossier-compiler`           | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.wr2.draft-generator`            | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.wr2.hardening`                  | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.wr2.image-generator`            | ❌ FAILED (exit=2)     | 2    | —       | —     |          |
| `com.balizero.wr2.learner-nightly`            | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.wr2.measurer`                   | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.wr2.newsletter`                 | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.wr2.oracle`                     | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.wr2.pg-proxy`                   | 🔄 Running (PID=18341) | 0    | —       | —     |          |
| `com.balizero.wr2.sla-worker`                 | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.wr2.strategos`                  | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.wr2.supervisor`                 | 🔄 Running (PID=27449) | 0    | —       | —     |          |
| `com.balizero.wr2.topic-selector`             | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.wr2.trend-hunter`               | ✅ OK                  | 0    | —       | —     |          |
| `com.cell.metabolic-rollup`                   | ✅ OK                  | 0    | —       | —     |          |
| `com.cell.organism`                           | 🔄 Running (PID=30047) | 1    | —       | —     |          |
| `com.claude-max-api`                          | 🔄 Running (PID=3956)  | 0    | —       | —     |          |
| `com.nuzantara.automap-server`                | 🔄 Running (PID=3899)  | 0    | —       | —     |          |
| `com.nuzantara.automap-telegram`              | 🔄 Running (PID=3906)  | 0    | —       | —     |          |
| `com.nuzantara.automap-watchdog`              | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.automations-reference`         | 🔄 Running (PID=67634) | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory`              | 🔄 Running (PID=3914)  | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory-prune`        | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory-selfcheck`    | ❌ FAILED (exit=1)     | 1    | —       | —     |          |
| `com.nuzantara.claude-config-sync`            | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.claude-max-usage-watcher`      | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.codex-autofix-ci`              | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.codex-coverage-improver`       | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.codex-overnight-feeder`        | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.codex-overnight-runner`        | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.codex-research-actor`          | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-daily-cap`        | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-weekly`           | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.cpu-monitor`                   | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.disk-monitor`                  | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.dlq-autopilot`                 | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.federation-alert-dispatcher`   | 🔄 Running (PID=30082) | 1    | —       | —     |          |
| `com.nuzantara.fly-restart-loop-detector`     | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.heartbeat-bridge`              | 🔄 Running (PID=3896)  | 0    | —       | —     |          |
| `com.nuzantara.launchagent-state-bridge`      | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.login-healthcheck`             | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.memory-sync-bidirectional`     | 🔄 Running (PID=66925) | 0    | —       | —     |          |
| `com.nuzantara.nb-intel-delta-watcher.hourly` | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.ollama-warm-pin`               | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.openclaw-children-watchdog`    | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.openclaw-logrotate`            | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.organism.control-panel`        | 🔄 Running (PID=3957)  | 0    | —       | —     |          |
| `com.nuzantara.organism.scheduled-tick`       | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.organism.supervisor`           | 🔄 Running (PID=3958)  | 0    | —       | —     |          |
| `com.nuzantara.prime-tunnel`                  | 🔄 Running (PID=3897)  | 0    | —       | —     |          |
| `com.nuzantara.secrets-sync-mini`             | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.sentinel`                      | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.sentinel-meta-watchdog`        | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.vector-reindex-check`          | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.zombie-hunter`                 | ✅ OK                  | 0    | —       | —     |          |
| `homebrew.mxcl.ollama`                        | 🔄 Running (PID=3951)  | 0    | —       | —     |          |
| `homebrew.mxcl.postgresql@17`                 | 🔄 Running (PID=3964)  | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                         | 🔄 Running (PID=3909)  | 0    | —       | —     |          |
| `homebrew.mxcl.syncthing`                     | 🔄 Running (PID=3963)  | 0    | —       | —     |          |

### Cron Jobs

| Job                     | Schedule                  | Last Run         | Status    | Circuit      | Scope        | Critical | Notes                                               |
| ----------------------- | ------------------------- | ---------------- | --------- | ------------ | ------------ | -------- | --------------------------------------------------- |
| `audit_trail_cleanup`   | Sun 2:00 UTC              | 2026-05-03 02:00 | ? check   | —            | —            |          | 2026-05-02 18:00:14,577 Deleted: 0 rows \| Oldest:  |
| `auto_judgement_day`    | Sun 8:00 UTC              | 2026-04-26 08:00 | ? check   | —            | —            |          | /Users/nuzantara/Desktop/nuzantara/scripts/auto_ju  |
| `auto_sentinel`         | daily 19:00 UTC           | 2026-04-29 19:00 | ❌ FAIL   | —            | —            |          | /bin/bash: /Users/nuzantara/Desktop/nuzantara/scri  |
| `auto_test`             | daily 18:15 UTC           | 2026-05-05 18:15 | ❌ FAIL   | —            | —            |          | [2026-05-05 18:15:00] ❌ Test failures: agentic llm |
| `backups`               | Sun 5:00 UTC              |                  |           | —            | —            |          |                                                     |
| `cache_cleanup`         | 1st+15th 3:30 UTC         | 2026-05-01 03:30 | ❌ FAIL   | —            | —            |          | npm error A complete log of this run can be found   |
| `cert_monitor`          | daily 7:00 UTC            |                  |           | —            | OBSERVE_ONLY | 🔴       |                                                     |
| `coverage_trend`        | daily 4:30 UTC            | 2026-05-06 04:30 | ? check   | —            | LOCAL        |          | /Users/nuzantara/Desktop/nuzantara/apps/backend-ra  |
| `cron_agent`            | daily 1:10 UTC (+8 more)  | 2026-05-06 01:13 | ✅ OK     | —            | —            |          | [2026-05-06T01:13:51] [nlm-deep-research] OK durat  |
| `cron_runner`           | every 5m (+23 more)       | 2026-05-03 02:00 | ❌ FAIL   | —            | —            |          | [2026-05-03 02:00:05] ✅ KG builder completed: {"ex |
| `cron_wrapper`          | daily 21:00 UTC (+6 more) |                  |           | —            | —            |          |                                                     |
| `curiosity_loop`        | daily 20:30 UTC           | 2026-05-05 20:30 | ❌ FAIL   | —            | —            |          | 2026-05-05 20:30:02,783 INFO nuzantara_graph.curio  |
| `docs_guardian`         | Sun 5:00 UTC              | 2026-04-26 05:00 | ❌ FAIL   | —            | —            |          | /bin/bash: /Users/nuzantara/Desktop/nuzantara/scri  |
| `fly_backup`            | daily 3:00 UTC            | 2026-05-06 03:00 | ? check   | —            | EXTERNAL     | 🔴       | [03:00:01] === Fly Backup start ===                 |
| `fly_cost_alert`        | Mon 9:00 UTC              |                  | ⚠️ NO LOG | ✅ CLOSED/T4 | —            |          |                                                     |
| `genome_decay`          | daily 18:30 UTC           | 2026-04-29 18:30 | ❌ FAIL   | —            | —            |          | /bin/bash: /Users/nuzantara/Desktop/nuzantara/scri  |
| `job_health`            | daily 9:00 UTC            | 2026-05-06 09:00 | ❌ FAIL   | —            | —            |          | ❌ t4-monitor failing 2026-05-06 00:00              |
| `legal_radar`           | Sun 0:00 UTC              | 2026-05-03 00:00 | ? check   | —            | —            |          | Legal Radar summary sent to Telegram                |
| `memory`                | daily 4:00 UTC (+1 more)  |                  |           | —            | —            |          |                                                     |
| `mos_maintenance`       | daily 4:00 UTC            |                  |           | —            | LOCAL        |          |                                                     |
| `ollama_cron_window`    | daily 17:10 UTC (+1 more) | 2026-05-05 22:05 | ? check   | —            | —            |          | [2026-05-05 22:05:00] All models unloaded — Ollama  |
| `ollama_warm_pin`       | Sun 5:00 UTC              | 2026-05-06 14:58 | ✅ OK     | —            | —            |          | [2026-05-06T14:58:15] Warm-pin complete on Nuzanta  |
| `openclaw_state_bridge` | every 5m                  | 2026-05-06 15:00 | ? check   | —            | —            |          | [openclaw-bridge] Written 24/24 state files         |
| `overnight`             | Sun-Fri 19:00 UTC         |                  | ⚠️ NO LOG | —            | —            |          |                                                     |
| `pro_heartbeat`         | 0 \* \* \* \*             |                  |           | —            | —            |          |                                                     |
| `ragas_eval`            | 5 22:30 UTC               | 2026-05-01 22:30 | ? check   | —            | —            |          | [ragas-eval] 2026-05-01 22:30 WITA — similarity=0.  |
| `run`                   | every 15m (+14 more)      | 2026-05-06 15:00 | ❌ FAIL   | —            | —            |          | 2026-05-06 15:00:03 [info ] check_now_done          |
| `sentry_quota_check`    | daily 9:00 UTC            | 2026-05-06 09:00 | ✅ OK     | —            | —            |          | [sentry-quota-check] OK                             |
| `sync_damar`            | 0 \* \* \* \*             |                  |           | —            | —            |          |                                                     |
| `sync_memory_ruslana`   | daily 8:00 UTC            | 2026-05-05 14:48 | ? check   | —            | —            |          | [2026-05-05 14:48] Synced 91 memory files to Rusla  |
| `sync_memory_to_nlm`    | Sun 3:00 UTC              | 2026-05-03 03:00 | ✅ OK     | —            | —            |          | ✅ Sync complete                                    |
| `warmup_vision`         | Mon-Sat 9-17:\*/4 UTC     |                  |           | —            | —            |          |                                                     |

---

## Mini (nuzantara@mini-pro2 — M4 Pro 24GB, H24)

### LaunchAgents

| Label                                     | Status                 | Exit | Circuit | Scope | Critical |
| ----------------------------------------- | ---------------------- | ---- | ------- | ----- | -------- |
| `com.balizero.indexing-sweep.daily`       | ⚠️ NOT LOADED          | ?    | —       | —     |          |
| `com.balizero.intel-radar-daily-digest`   | ✅ OK                  | 0    | —       | —     |          |
| `com.balizero.nlm-bridge`                 | 🔄 Running (PID=755)   | 0    | —       | —     |          |
| `com.balizero.renewal-alerts`             | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-daily-cap`    | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-weekly`       | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.fly-pg-tunnel`             | 🔄 Running (PID=1102)  | 1    | —       | —     |          |
| `com.nuzantara.fly-restart-loop-detector` | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.git-pull-main.5min`        | 🔄 Running (PID=86402) | 0    | —       | —     |          |
| `com.nuzantara.login-healthcheck`         | ✅ OK                  | 0    | —       | —     |          |
| `com.nuzantara.ollama-warm-pin`           | ✅ OK                  | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                     | 🔄 Running (PID=757)   | 0    | —       | —     |          |

---

_Generated by `scripts/generate_automations_reference.py` — 2026-05-06 07:02 UTC_
