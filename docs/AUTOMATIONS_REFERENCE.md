# NUZANTARA — AUTOMATIONS REFERENCE

> **Auto-generated from live system state** — do not edit manually.
> Generated: 2026-05-10 15:15 UTC
> Source: `crontab -l` (Pro+Mini) + `launchctl list` (Pro+Mini) + log health + `job_registry.json` + `sentinel_status.json` + `circuit_breakers.json`

---

## System Health Summary

| Metric                | Value   |
| --------------------- | ------- |
| Total jobs            | **155** |
| ✅ Healthy            | **90**  |
| 🔄 Running (daemons)  | **31**  |
| ⚠️ Warning/Skip/NoLog | **3**   |
| ❌ Failed             | **15**  |

---

## Sentinel Overview

> Ultimo aggiornamento sentinel: `2026-05-10T14:29:57Z`

| Metrica                   | Valore                       |
| ------------------------- | ---------------------------- |
| Circuit OPEN              | **8**                        |
| Circuit TERMINAL          | **34**                       |
| DLQ entries totali        | **63**                       |
| DLQ phase distribution    | `T3=1 · T4=28 · TERMINAL=34` |
| Job critici (in registry) | **2**                        |

---

## Pro (nuzantara@Nuzantara — M4 Pro 48GB)

### LaunchAgents

| Label                                          | Status                 | Autonomy   | Exit | Circuit | Scope | Critical |
| ---------------------------------------------- | ---------------------- | ---------- | ---- | ------- | ----- | -------- |
| `ai.openclaw.gateway`                          | 🔄 Running (PID=23103) | —          | 0    | —       | —     |          |
| `com.balizero.bz-daily-visual-pipeline`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.client-value-predictor`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.codex-spalla-calibrate`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.competitor-monitor.monthly`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.competitor-signal-router.weekly` | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.cron-log-sentinel`               | 🔄 Running (PID=46078) | —          | -15  | —       | —     |          |
| `com.balizero.domain-mesh.foundations.daily`   | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.indexing-sweep.daily`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-dedup-gateway`             | 🔄 Running (PID=46057) | —          | -15  | —       | —     |          |
| `com.balizero.intel-radar-daily-digest`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel.nightly`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.meta-dispatcher`                 | 🔄 Running (PID=46099) | —          | -15  | —       | —     |          |
| `com.balizero.nlm-bridge`                      | 🔄 Running (PID=2389)  | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara-drive-sync`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.observatory`                     | 🔄 Running (PID=48876) | —          | -15  | —       | —     |          |
| `com.balizero.observatory-export`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.observatory-server`              | 🔄 Running (PID=2663)  | —          | -15  | —       | —     |          |
| `com.balizero.post-publish-poller`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.post-publish-webhook`            | 🔄 Running (PID=2402)  | —          | 0    | —       | —     |          |
| `com.balizero.regulatory-watcher.daily`        | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.renewal-alerts`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.research-sentinel`               | 🔄 Running (PID=46069) | —          | -15  | —       | —     |          |
| `com.balizero.seo-cell.28d-check`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.seo-cell.daily`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.setup-team.daily`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-checkpoint`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-collect`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-monthly`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-weekly`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.translate.hourly`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.canva-apply`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.canva-gc.weekly`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.canva-oauth-watchdog`        | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.canva-renderer`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.connector`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.daily-metrics`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.deploy-puller`               | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.dossier-compiler`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.draft-generator`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.fact-checker`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.fact-extractor`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.hardening`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.ig-metrics-analyst.weekly`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.ig-scraper.daily`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.image-generator`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.learner-nightly`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.measurer`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.newsletter`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.oracle`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.pg-proxy`                    | 🔄 Running (PID=2424)  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.plist-watchdog`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.queue-server`                | 🔄 Running (PID=2379)  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.reflexion.weekly`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.sla-worker`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.strategos`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.supervisor`                  | 🔄 Running (PID=18014) | —          | 74   | —       | —     |          |
| `com.balizero.wr2.supervisor-watchdog`         | 🔄 Running (PID=12721) | —          | 74   | —       | —     |          |
| `com.balizero.wr2.topic-selector`              | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.trend-hunter`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.voyager.weekly`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.yield-optimizer.weekly`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.cell.metabolic-rollup`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.cell.organism`                            | 🔄 Running (PID=2393)  | —          | 0    | —       | —     |          |
| `com.claude-max-api`                           | 🔄 Running (PID=2403)  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-server`                 | 🔄 Running (PID=2371)  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-telegram`               | 🔄 Running (PID=2385)  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-watchdog`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.automations-reference`          | 🔄 Running (PID=70586) | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory`               | 🔄 Running (PID=2397)  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory-prune`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory-selfcheck`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.claude-config-sync`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.claude-max-usage-watcher`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-autofix-ci`               | ✅ OK                  | ⚠️ SKIPPED | 0    | —       | —     |          |
| `com.nuzantara.codex-coverage-improver`        | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.codex-openclaw-analysis`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-overnight-feeder`         | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.codex-overnight-runner`         | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.codex-research-actor`           | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-daily-cap`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-weekly`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cpu-monitor`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.disk-monitor`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.dlq-autopilot`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.federation-alert-dispatcher`    | 🔄 Running (PID=9704)  | —          | 1    | —       | —     |          |
| `com.nuzantara.fly-restart-loop-detector`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.heartbeat-bridge`               | 🔄 Running (PID=2369)  | —          | 0    | —       | —     |          |
| `com.nuzantara.launchagent-state-bridge`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.launchd-env-loader`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.login-healthcheck`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.memory-sync-bidirectional`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.nb-intel-delta-watcher.hourly`  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.nb-mitochondrial-monitor.daily` | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-children-watchdog`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-logrotate`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.control-panel`         | 🔄 Running (PID=2404)  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.scheduled-tick`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.supervisor`            | 🔄 Running (PID=55907) | —          | 0    | —       | —     |          |
| `com.nuzantara.outbox-prune.daily`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.pg-organism-bridge`             | 🔄 Running (PID=58591) | —          | 0    | —       | —     |          |
| `com.nuzantara.prime-tunnel`                   | 🔄 Running (PID=2370)  | —          | 0    | —       | —     |          |
| `com.nuzantara.secrets-sync-mini`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel`                       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel-aggregate`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel-meta-watchdog`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.supervisor-liveness-watchdog`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.vector-reindex-check`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.zombie-hunter`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.ollama`                         | 🔄 Running (PID=14783) | —          | 0    | —       | —     |          |
| `homebrew.mxcl.postgresql@17`                  | 🔄 Running (PID=2414)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                          | 🔄 Running (PID=2391)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.syncthing`                      | 🔄 Running (PID=2413)  | —          | 0    | —       | —     |          |

### Cron Jobs

| Job                     | Schedule                  | Last Run         | Status    | Circuit      | Scope        | Critical | Notes                                               |
| ----------------------- | ------------------------- | ---------------- | --------- | ------------ | ------------ | -------- | --------------------------------------------------- |
| `audit_trail_cleanup`   | Sun 2:00 UTC              | 2026-05-10 02:00 | ? check   | —            | —            |          | 2026-05-09 18:00:06,046 Deleted: 0 rows \| Oldest:  |
| `auto_judgement_day`    | Sun 8:00 UTC              | 2026-04-26 08:00 | ? check   | —            | —            |          | /Users/nuzantara/Desktop/nuzantara/scripts/auto_ju  |
| `auto_sentinel`         | daily 19:00 UTC           | 2026-04-29 19:00 | ❌ FAIL   | —            | —            |          | /bin/bash: /Users/nuzantara/Desktop/nuzantara/scri  |
| `auto_test`             | daily 18:15 UTC           | 2026-05-10 18:15 | ❌ FAIL   | —            | —            |          | [2026-05-10 18:15:00] ❌ Test failures: agentic llm |
| `backups`               | Sun 5:00 UTC              |                  |           | —            | —            |          |                                                     |
| `cache_cleanup`         | 1st+15th 3:30 UTC         | 2026-05-01 03:30 | ❌ FAIL   | —            | —            |          | npm error A complete log of this run can be found   |
| `cert_monitor`          | daily 7:00 UTC            |                  |           | —            | OBSERVE_ONLY | 🔴       |                                                     |
| `coverage_trend`        | daily 4:30 UTC            | 2026-05-10 04:30 | ? check   | —            | LOCAL        |          | /Users/nuzantara/Desktop/nuzantara/apps/backend-ra  |
| `cron_agent`            | daily 1:10 UTC (+8 more)  | 2026-05-09 01:14 | ✅ OK     | —            | —            |          | [2026-05-09T01:14:30] [nlm-deep-research] OK durat  |
| `cron_runner`           | every 5m (+23 more)       | 2026-05-10 02:00 | ❌ FAIL   | —            | —            |          | [2026-05-10 02:00:04] ✅ KG builder completed: {"ex |
| `cron_wrapper`          | daily 21:00 UTC (+6 more) |                  |           | —            | —            |          |                                                     |
| `curiosity_loop`        | daily 20:30 UTC           | 2026-05-10 20:30 | ❌ FAIL   | —            | —            |          | 2026-05-10 20:30:02,759 INFO nuzantara_graph.curio  |
| `docs_guardian`         | Sun 5:00 UTC              | 2026-04-26 05:00 | ❌ FAIL   | —            | —            |          | /bin/bash: /Users/nuzantara/Desktop/nuzantara/scri  |
| `fly_backup`            | daily 3:00 UTC            | 2026-05-10 03:00 | ? check   | —            | EXTERNAL     | 🔴       | /Users/nuzantara/scripts/fly-pg-backup.sh: line 20  |
| `fly_cost_alert`        | Mon 9:00 UTC              |                  | ⚠️ NO LOG | ✅ CLOSED/T4 | —            |          |                                                     |
| `genome_decay`          | daily 18:30 UTC           | 2026-04-29 18:30 | ❌ FAIL   | —            | —            |          | /bin/bash: /Users/nuzantara/Desktop/nuzantara/scri  |
| `job_health`            | daily 9:00 UTC            | 2026-05-10 09:00 | ❌ FAIL   | —            | —            |          | ❌ t4-monitor failing 2026-05-10 06:00              |
| `legal_radar`           | Sun 0:00 UTC              | 2026-05-10 00:00 | ? check   | —            | —            |          | Legal Radar summary sent to Telegram                |
| `memory`                | daily 4:00 UTC (+1 more)  |                  |           | —            | —            |          |                                                     |
| `mos_maintenance`       | daily 4:00 UTC            |                  |           | —            | LOCAL        |          |                                                     |
| `ollama_cron_window`    | daily 17:10 UTC (+1 more) | 2026-05-10 22:05 | ? check   | —            | —            |          | [2026-05-10 22:05:00] All models unloaded — Ollama  |
| `ollama_warm_pin`       | Sun 5:00 UTC              | 2026-05-10 05:00 | ✅ OK     | —            | —            |          | [2026-05-10T05:00:29] Warm-pin complete on Nuzanta  |
| `openclaw_state_bridge` | every 5m                  | 2026-05-10 23:15 | ? check   | —            | —            |          | [openclaw-bridge] Written 24/24 state files         |
| `overnight`             | Sun-Fri 19:00 UTC         |                  | ⚠️ NO LOG | —            | —            |          |                                                     |
| `pro_heartbeat`         | 0 \* \* \* \*             |                  |           | —            | —            |          |                                                     |
| `ragas_eval`            | 5 22:30 UTC               | 2026-05-08 22:30 | ? check   | —            | —            |          | [ragas-eval] 2026-05-08 22:30 WITA — similarity=0.  |
| `run`                   | every 15m (+14 more)      | 2026-05-10 23:15 | ❌ FAIL   | —            | —            |          | 2026-05-10 23:15:03 [info ] check_now_done          |
| `sentry_quota_check`    | daily 9:00 UTC            | 2026-05-10 09:00 | ✅ OK     | —            | —            |          | [sentry-quota-check] OK                             |
| `sync_damar`            | 0 \* \* \* \*             |                  |           | —            | —            |          |                                                     |
| `sync_memory_ruslana`   | daily 8:00 UTC            | 2026-05-10 08:00 | ⚠️ WARN   | —            | —            |          | [2026-05-10 08:00] Ruslana host unreachable — skip  |
| `sync_memory_to_nlm`    | Sun 3:00 UTC              | 2026-05-10 03:00 | ✅ OK     | —            | —            |          | ✅ Sync complete                                    |
| `warmup_vision`         | Mon-Sat 9-17:\*/4 UTC     |                  |           | —            | —            |          |                                                     |

---

## Mini (nuzantara@mini-pro2 — M4 Pro 24GB, H24)

### LaunchAgents

| Label                                    | Status                | Autonomy | Exit | Circuit | Scope | Critical |
| ---------------------------------------- | --------------------- | -------- | ---- | ------- | ----- | -------- |
| `com.nuzantara.fly-pg-tunnel`            | 🔄 Running (PID=1093) | —        | 1    | —       | —     |          |
| `com.nuzantara.git-pull-main.5min`       | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.heartbeat-watchdog.daily` | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.log-prune.daily`          | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.ollama-warm-pin`          | ❌ FAILED (exit=52)   | —        | 52   | —       | —     |          |
| `com.nuzantara.overlap-detector.daily`   | ✅ OK                 | —        | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                    | 🔄 Running (PID=1097) | —        | 1    | —       | —     |          |

### Cron Jobs

| Job                      | Schedule       | Last Run         | Status | Circuit | Scope | Critical | Notes                                               |
| ------------------------ | -------------- | ---------------- | ------ | ------- | ----- | -------- | --------------------------------------------------- |
| `crm_kg_build_mediated`  | every 6h (:0)  | 2026-05-10 22:54 | ✅ OK  | —       | —     |          | [2026-05-10 22:54:39] ✅ build-mediated OK: {"statu |
| `crm_kg_garbage_collect` | daily 3:00 UTC | 2026-05-10 22:54 | ✅ OK  | —       | —     |          | [2026-05-10 22:54:39] ✅ garbage-collect OK: {"stat |
| `drive_poll`             | every 5m       | 2026-05-10 23:15 | ✅ OK  | —       | —     |          | [2026-05-10 23:15:02] ✅ Drive poll OK: 0 new files |

---

_Generated by `scripts/generate_automations_reference.py` — 2026-05-10 15:15 UTC_
