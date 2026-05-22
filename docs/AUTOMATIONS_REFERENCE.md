# NUZANTARA — AUTOMATIONS REFERENCE

> **Auto-generated from live system state** — do not edit manually.
> Generated: 2026-05-22 15:15 UTC
> Source: `crontab -l` (Pro+Mini) + `launchctl list` (Pro+Mini) + log health + `job_registry.json` + `sentinel_status.json` + `circuit_breakers.json`

---

## System Health Summary

| Metric                | Value   |
| --------------------- | ------- |
| Total jobs            | **195** |
| ✅ Healthy            | **115** |
| 🔄 Running (daemons)  | **41**  |
| ⚠️ Warning/Skip/NoLog | **7**   |
| ❌ Failed             | **15**  |

---

## Sentinel Overview

> Ultimo aggiornamento sentinel: `2026-05-22T14:42:30Z`

| Metrica                   | Valore        |
| ------------------------- | ------------- |
| Circuit OPEN              | **6**         |
| Circuit TERMINAL          | **63**        |
| DLQ entries totali        | **63**        |
| DLQ phase distribution    | `TERMINAL=63` |
| Job critici (in registry) | **2**         |

---

## Pro (nuzantara@Nuzantara — M4 Pro 48GB)

### LaunchAgents

| Label                                            | Status                 | Autonomy   | Exit | Circuit | Scope | Critical |
| ------------------------------------------------ | ---------------------- | ---------- | ---- | ------- | ----- | -------- |
| `ai.openclaw.gateway`                            | 🔄 Running (PID=171)   | —          | 1    | —       | —     |          |
| `com.balizero.agent-library-evolver.weekly`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.bz-daily-visual-pipeline`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.client-value-predictor`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.codex-spalla-calibrate`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.competitor-monitor.monthly`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.competitor-signal-router.weekly`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.crm-guardian-cli-worker`           | 🔄 Running (PID=29072) | —          | 1    | —       | —     |          |
| `com.balizero.cron-log-sentinel`                 | 🔄 Running (PID=4229)  | —          | 0    | —       | —     |          |
| `com.balizero.curiosity.weekly`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.domain-mesh.foundations.daily`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.guardrails-daemon`                 | 🔄 Running (PID=4284)  | —          | 0    | —       | —     |          |
| `com.balizero.indexing-sweep.daily`              | 🔄 Running (PID=69773) | —          | 0    | —       | —     |          |
| `com.balizero.intel-dedup-gateway`               | 🔄 Running (PID=4287)  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake-nb-pusher.15min`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake-router.5min`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake.e2e-probe.6h`           | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.intel-lake.outbox-drain.minute`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake.shadow-validate.6h`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-radar-daily-digest`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel.nightly`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.meta-dispatcher`                   | 🔄 Running (PID=4220)  | —          | 0    | —       | —     |          |
| `com.balizero.nb-curator.weekly`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nlm-bridge`                        | 🔄 Running (PID=4249)  | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara-drive-sync`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara.disk-watchdog`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara.log-size-watchdog`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.observatory`                       | 🔄 Running (PID=4294)  | —          | 0    | —       | —     |          |
| `com.balizero.observatory-export`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.observatory-server`                | 🔄 Running (PID=4272)  | —          | 0    | —       | —     |          |
| `com.balizero.post-publish-poller`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.post-publish-webhook`              | 🔄 Running (PID=4261)  | —          | 0    | —       | —     |          |
| `com.balizero.profile-monitor-wrapper`           | 🔄 Running (PID=4277)  | —          | 0    | —       | —     |          |
| `com.balizero.regulatory-watcher.daily`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.regulatory-watcher.fix-b-verify`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.renewal-alerts`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.research-sentinel`                 | 🔄 Running (PID=4297)  | —          | 0    | —       | —     |          |
| `com.balizero.seo-cell.28d-check`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.seo-cell.daily`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.setup-team.daily`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-checkpoint`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-collect`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-monthly`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-weekly`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.translate.hourly`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror`                         | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.wa-mirror-attention-classifier`    | 🔄 Running (PID=69719) | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-attention-digest`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-attention-realtime`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-auto-promote`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-launcher`                | 🔄 Running (PID=67135) | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-strategic-recap`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-viewer`                         | 🔄 Running (PID=4274)  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.canva-apply`                   | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.canva-gc.weekly`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.canva-lease-watchdog.10min`    | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.wr2.canva-oauth-watchdog`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.canva-renderer`                | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.canva-token-watchdog.daily`    | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.wr2.connector`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.daily-metrics`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.deploy-puller`                 | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.dossier-compiler`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.draft-generator`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.e2e-probe.daily`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.external-bench.monthly`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.fact-checker`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.fact-extractor`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.hardening`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.ig-metrics-analyst.weekly`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.ig-scraper.daily`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.image-generator`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.learner-nightly`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.measurer`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.newsletter`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.oracle`                        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.pg-proxy`                      | 🔄 Running (PID=13602) | —          | 126  | —       | —     |          |
| `com.balizero.wr2.pg-queue-sync`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.plist-watchdog`                | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.queue-server`                  | 🔄 Running (PID=4235)  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.reflexion.weekly`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.sla-worker`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.strategos`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.supervisor`                    | 🔄 Running (PID=25650) | —          | 74   | —       | —     |          |
| `com.balizero.wr2.supervisor-watchdog`           | 🔄 Running (PID=27004) | —          | 74   | —       | —     |          |
| `com.balizero.wr2.topic-selector`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.trend-hunter`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.voyager.weekly`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.editorial-bench.monthly`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.reflexion.weekly`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.supervisor`                    | 🔄 Running (PID=25315) | —          | 75   | —       | —     |          |
| `com.balizero.wr3.yt-metrics.weekly`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.yield-optimizer.weekly`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.cell.metabolic-rollup`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.cell.organism`                              | 🔄 Running (PID=30151) | —          | 1    | —       | —     |          |
| `com.claude-max-api`                             | 🔄 Running (PID=4264)  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-server`                   | 🔄 Running (PID=4224)  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-telegram`                 | 🔄 Running (PID=4244)  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-watchdog`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.automations-reference`            | 🔄 Running (PID=69946) | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory`                 | 🔄 Running (PID=4257)  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory-prune`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory-selfcheck`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.claude-config-sync`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cleanup-2026-05-16-ttl-sentinel`  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-autofix-ci`                 | 🔄 Running (PID=69945) | ⚠️ SKIPPED | 0    | —       | —     |          |
| `com.nuzantara.codex-coverage-improver`          | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.codex-openclaw-analysis`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-overnight-feeder`           | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.codex-overnight-runner`           | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.codex-research-actor`             | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.codex-spark-alarm`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-spark-harvester`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-spark-loop`                 | 🔄 Running (PID=4268)  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-daily-cap`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-weekly`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cpu-monitor`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.disk-monitor`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.dlq-autopilot`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.federation-alert-dispatcher`      | 🔄 Running (PID=36614) | —          | 1    | —       | —     |          |
| `com.nuzantara.fly-restart-loop-detector`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.heartbeat-bridge`                 | 🔄 Running (PID=4221)  | —          | 0    | —       | —     |          |
| `com.nuzantara.launchagent-state-bridge`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.launchd-env-loader`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.login-healthcheck`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.memory-sync-bidirectional`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.nb-intel-delta-watcher.hourly`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.nb-mitochondrial-monitor.daily`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-children-watchdog`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-logrotate`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.control-panel`           | 🔄 Running (PID=4265)  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.scheduled-tick`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.supervisor`              | 🔄 Running (PID=5303)  | —          | -15  | —       | —     |          |
| `com.nuzantara.outbox-prune.daily`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.outbox-prune.weekly`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.pg-organism-bridge`               | 🔄 Running (PID=4256)  | —          | 0    | —       | —     |          |
| `com.nuzantara.pg-organism-bridge-watchdog`      | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.nuzantara.pg-proxy-cluster-recheck-oneshot` | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.prime-tunnel`                     | 🔄 Running (PID=4222)  | —          | 0    | —       | —     |          |
| `com.nuzantara.secrets-sync-mini`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel`                         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel-aggregate`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel-meta-watchdog`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.skills-bridge-consumer`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.supervisor-liveness-watchdog`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.vector-reindex-check`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.zombie-hunter`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.ollama`                           | 🔄 Running (PID=4260)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.postgresql@17`                    | 🔄 Running (PID=4279)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                            | 🔄 Running (PID=4251)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.syncthing`                        | 🔄 Running (PID=4278)  | —          | 0    | —       | —     |          |

### Cron Jobs

| Job                     | Schedule                  | Last Run         | Status  | Circuit      | Scope        | Critical | Notes                                               |
| ----------------------- | ------------------------- | ---------------- | ------- | ------------ | ------------ | -------- | --------------------------------------------------- |
| `audit_trail_cleanup`   | Sun 2:00 UTC              | 2026-05-17 02:00 | ❌ FAIL | —            | —            |          | Error: no access token available. Please login wit  |
| `auto_judgement_day`    | Sun 8:00 UTC              | 2026-04-26 08:00 | ? check | —            | —            |          | /Users/nuzantara/Desktop/nuzantara/scripts/auto_ju  |
| `auto_sentinel`         | daily 19:00 UTC           | 2026-04-29 19:00 | ❌ FAIL | —            | —            |          | /bin/bash: /Users/nuzantara/Desktop/nuzantara/scri  |
| `auto_test`             | daily 18:15 UTC           | 2026-05-22 18:15 | ❌ FAIL | —            | —            |          | [2026-05-22 18:15:00] ❌ Test failures: agentic llm |
| `backups`               | Sun 5:00 UTC              |                  |         | —            | —            |          |                                                     |
| `cache_cleanup`         | 1st+15th 3:30 UTC         | 2026-05-01 03:30 | ❌ FAIL | —            | —            |          | npm error A complete log of this run can be found   |
| `cert_monitor`          | daily 7:00 UTC            |                  |         | —            | OBSERVE_ONLY | 🔴       |                                                     |
| `coverage_trend`        | daily 4:30 UTC            | 2026-05-22 04:30 | ? check | —            | LOCAL        |          | /Users/nuzantara/Desktop/nuzantara/apps/backend-ra  |
| `cron_agent`            | daily 1:10 UTC (+8 more)  | 2026-05-22 01:11 | ✅ OK   | —            | —            |          | [2026-05-22T01:11:40] [nlm-deep-research] OK durat  |
| `cron_runner`           | every 5m (+23 more)       | 2026-05-17 02:00 | ❌ FAIL | —            | —            |          | [2026-05-17 02:00:04] ✅ KG builder completed: {"ex |
| `cron_wrapper`          | daily 21:00 UTC (+5 more) |                  |         | —            | —            |          |                                                     |
| `curiosity_loop`        | daily 20:42 UTC           | 2026-05-22 20:42 | ❌ FAIL | —            | —            |          | 2026-05-22 20:42:00,939 INFO nuzantara_graph.curio  |
| `docs_guardian`         | Sun 5:00 UTC              | 2026-04-26 05:00 | ❌ FAIL | —            | —            |          | /bin/bash: /Users/nuzantara/Desktop/nuzantara/scri  |
| `fly_backup`            | daily 3:00 UTC            | 2026-05-22 03:05 | ✅ OK   | —            | EXTERNAL     | 🔴       | Completed 1.0 MiB/325.8 MiB (420.7 KiB/s) with 1 f  |
| `fly_cost_alert`        | Mon 9:00 UTC              | 2026-05-18 09:00 | ? check | ✅ CLOSED/T4 | —            |          | [2026-05-18 09:00:01] Cost within budget ✅         |
| `genome_decay`          | daily 18:30 UTC           | 2026-04-29 18:30 | ❌ FAIL | —            | —            |          | /bin/bash: /Users/nuzantara/Desktop/nuzantara/scri  |
| `job_health`            | daily 9:00 UTC            | 2026-05-22 09:00 | ✅ OK   | —            | —            |          | ✅ t4-monitor healthy 2026-05-22 06:00              |
| `memory`                | daily 4:00 UTC (+1 more)  |                  |         | —            | —            |          |                                                     |
| `mos_maintenance`       | daily 4:00 UTC            |                  |         | —            | LOCAL        |          |                                                     |
| `nb_agents_daily_dr`    | daily 7:30 UTC            | 2026-05-14 07:30 |         | —            | —            |          |                                                     |
| `nextdns_weekly_digest` | Mon 0:55 UTC              | 2026-05-18 00:55 | ? check | —            | —            |          | [nextdns-digest] Inviato digest settimana 11/05–18  |
| `ollama_cron_window`    | daily 17:10 UTC (+1 more) | 2026-05-22 22:05 | ? check | —            | —            |          | [2026-05-22 22:05:00] All models unloaded — Ollama  |
| `ollama_warm_pin`       | Sun 5:00 UTC              | 2026-05-17 05:00 | ✅ OK   | —            | —            |          | [2026-05-17T05:00:29] Warm-pin complete on Nuzanta  |
| `openclaw_state_bridge` | every 5m                  | 2026-05-22 23:15 | ? check | —            | —            |          | [openclaw-bridge] Written 24/24 state files         |
| `pro_heartbeat`         | 0 \* \* \* \*             |                  |         | —            | —            |          |                                                     |
| `ragas_eval`            | 5 22:30 UTC               | 2026-05-22 22:30 | ? check | —            | —            |          | [ragas-eval] 2026-05-22 22:30 WITA — similarity=0.  |
| `run`                   | every 15m (+14 more)      | 2026-05-22 23:15 | ❌ FAIL | —            | —            |          | 2026-05-22 23:15:02 [info ] check_now_done          |
| `sentry_quota_check`    | daily 9:00 UTC            | 2026-05-22 09:00 | ✅ OK   | —            | —            |          | [sentry-quota-check] OK                             |
| `sync_damar`            | 0 \* \* \* \*             |                  |         | —            | —            |          |                                                     |
| `sync_memory_ruslana`   | daily 8:00 UTC            | 2026-05-22 08:00 | ⚠️ WARN | —            | —            |          | [2026-05-22 08:00] Ruslana host unreachable — skip  |
| `sync_memory_to_nlm`    | Sun 3:00 UTC              | 2026-05-17 03:00 | ✅ OK   | —            | —            |          | ✅ Sync complete                                    |
| `warmup_vision`         | Mon-Sat 9-17:\*/4 UTC     |                  |         | —            | —            |          |                                                     |

---

## Mini (nuzantara@mini-pro2 — M4 Pro 24GB, H24)

### LaunchAgents

| Label                                    | Status                 | Autonomy | Exit | Circuit | Scope | Critical |
| ---------------------------------------- | ---------------------- | -------- | ---- | ------- | ----- | -------- |
| `com.balizero.wa-mirror`                 | ⚠️ NOT LOADED          | —        | ?    | —       | —     |          |
| `com.nuzantara.fly-pg-tunnel`            | ⚠️ NOT LOADED          | —        | ?    | —       | —     |          |
| `com.nuzantara.fly-pg-tunnel.local`      | 🔄 Running (PID=47845) | —        | -15  | —       | —     |          |
| `com.nuzantara.git-pull-main.5min`       | ❌ FAILED (exit=1)     | —        | 1    | —       | —     |          |
| `com.nuzantara.heartbeat-watchdog.daily` | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.log-prune.daily`          | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.ollama-warm-pin`          | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.overlap-detector.daily`   | ✅ OK                  | —        | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                    | 🔄 Running (PID=1464)  | —        | 0    | —       | —     |          |

### Cron Jobs

| Job                      | Schedule       | Last Run         | Status | Circuit | Scope | Critical | Notes                                               |
| ------------------------ | -------------- | ---------------- | ------ | ------- | ----- | -------- | --------------------------------------------------- |
| `crm_kg_build_mediated`  | every 6h (:0)  | 2026-05-22 18:00 | ✅ OK  | —       | —     |          | [2026-05-22 18:00:01] ✅ build-mediated OK: {"statu |
| `crm_kg_garbage_collect` | daily 3:00 UTC | 2026-05-22 03:00 | ✅ OK  | —       | —     |          | [2026-05-22 03:00:01] ✅ garbage-collect OK: {"stat |
| `drive_poll`             | every 5m       | 2026-05-22 23:15 |        | —       | —     |          |                                                     |

---

_Generated by `scripts/generate_automations_reference.py` — 2026-05-22 15:15 UTC_
