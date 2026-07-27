# NUZANTARA — AUTOMATIONS REFERENCE

> **Auto-generated from live system state** — do not edit manually.
> Generated: 2026-07-25 15:15 UTC
> Source: `crontab -l` (Pro+Mini) + `launchctl list` (Pro+Mini) + log health + `job_registry.json` + `sentinel_status.json` + `circuit_breakers.json`

---

## Repo-canon additions pending live snapshot

These entries are committed as repo-canon LaunchAgents but are not counted in
the generated live totals above until installed on Pro and included in the next
automation snapshot.

| Label                            | Host | Schedule   | Purpose                                                                                                                           |
| -------------------------------- | ---- | ---------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `com.balizero.magazine.morning`  | Pro  | 08:15 WITA | Compose/publish the internal Bali Zero Magazine morning issue after the Regulatory Watcher window; target readable by 08:30 WITA. |
| `com.balizero.magazine.breaking` | Pro  | 600s       | Drain qualified Breaking magazine candidates within the 10-minute objective.                                                      |

---

## System Health Summary

| Metric                | Value   |
| --------------------- | ------- |
| Total jobs            | **235** |
| ✅ Healthy            | **157** |
| 🔄 Running (daemons)  | **55**  |
| ⚠️ Warning/Skip/NoLog | **6**   |
| ❌ Failed             | **11**  |

---

## Sentinel Overview

> Ultimo aggiornamento sentinel: `2026-07-25T15:06:37Z`

| Metrica                   | Valore               |
| ------------------------- | -------------------- |
| Circuit OPEN              | **0**                |
| Circuit TERMINAL          | **17**               |
| DLQ entries totali        | **18**               |
| DLQ phase distribution    | `T0=1 · TERMINAL=17` |
| Job critici (in registry) | **0**                |

---

## Pro (nuzantara@Nuzantara — M4 Pro 48GB)

### LaunchAgents

| Label                                           | Status                 | Autonomy   | Exit | Circuit | Scope | Critical |
| ----------------------------------------------- | ---------------------- | ---------- | ---- | ------- | ----- | -------- |
| `ai.openclaw.gateway`                           | 🔄 Running (PID=53403) | —          | 0    | —       | —     |          |
| `ai.openclaw.node`                              | 🔄 Running (PID=19639) | —          | -15  | —       | —     |          |
| `com.balizero.agent-library-evolver.daily`      | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.agent-library-evolver.weekly`     | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.audit-launchd.daily`              | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.bz-daily-visual-pipeline`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.cicatrix-rotation.monthly`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.claude-settings-watcher`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.client-value-predictor`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.codex-spalla-calibrate`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.competitor-monitor.monthly`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.competitor-signal-router.weekly`  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.crm-guardian-cli-worker`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.cron-log-sentinel`                | 🔄 Running (PID=1328)  | —          | 0    | —       | —     |          |
| `com.balizero.curiosity.weekly`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.domain-mesh.foundations.daily`    | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.drive-intake-drain`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.dropbox-intake`                   | 🔄 Running (PID=57275) | —          | 0    | —       | —     |          |
| `com.balizero.fly-cost-alert.weekly`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.guardrails-daemon`                | 🔄 Running (PID=1408)  | —          | 0    | —       | —     |          |
| `com.balizero.intel-dedup-gateway`              | 🔄 Running (PID=1412)  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake-nb-pusher.15min`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake-router.5min`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake.e2e-probe.6h`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake.outbox-drain.minute`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake.shadow-validate.6h`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-radar-daily-digest`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel.nightly`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.l5-2-phase2b-trigger`             | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.meta-dispatcher`                  | 🔄 Running (PID=1315)  | —          | 0    | —       | —     |          |
| `com.balizero.mlx-server`                       | 🔄 Running (PID=1344)  | —          | 0    | —       | —     |          |
| `com.balizero.modus.autoloop.nightly`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.mos-plus.compression`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.mos-plus.qdrant-indexer`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nb-curator.daily`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nextdns-tamper-detect.weekly`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nexus-session-retention.daily`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nlm-bridge`                       | 🔄 Running (PID=1350)  | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara-drive-sync`             | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.nuzantara.disk-watchdog`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara.log-size-watchdog`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.observatory`                      | 🔄 Running (PID=1419)  | —          | 0    | —       | —     |          |
| `com.balizero.observatory-export`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.observatory-server`               | 🔄 Running (PID=1390)  | —          | 0    | —       | —     |          |
| `com.balizero.post-publish-poller`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.post-publish-webhook`             | 🔄 Running (PID=1371)  | —          | 0    | —       | —     |          |
| `com.balizero.profile-monitor-wrapper`          | 🔄 Running (PID=1396)  | —          | 0    | —       | —     |          |
| `com.balizero.qdrant.daemon`                    | 🔄 Running (PID=1331)  | —          | 0    | —       | —     |          |
| `com.balizero.regulatory-watcher.daily`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.renewal-alerts`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.research-sentinel`                | 🔄 Running (PID=1426)  | —          | 0    | —       | —     |          |
| `com.balizero.seo-cell.28d-check`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.seo-cell.daily`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.setup-team.daily`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-checkpoint`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-collect`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-monthly`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-weekly`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.translate.hourly`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-dashboard-m1`                  | 🔄 Running (PID=1393)  | —          | 0    | —       | —     |          |
| `com.balizero.wa-lid-refresh`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-meta-inbox`                    | 🔄 Running (PID=1364)  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-attention-classifier`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-attention-digest`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-attention-realtime`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-auto-promote`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-auto-promote-selfheal`  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-launcher`               | 🔄 Running (PID=1332)  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-strategic-recap`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-team-metrics-rollup`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.connector`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.daily-metrics`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.daily-reconciler`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.deploy-puller`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.dossier-compiler`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.draft-generator`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.e2e-probe.daily`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.external-bench.monthly`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.fact-checker`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.fact-extractor`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.hardening`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.html-apply`                   | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.ig-metrics-analyst.weekly`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.ig-metrics-scrape.daily`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.ig-scraper.daily`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.image-generator`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.learner-nightly`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.measurer`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.newsletter`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.oracle`                       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.pg-proxy`                     | 🔄 Running (PID=1416)  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.pg-queue-sync`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.plist-watchdog`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.queue-server`                 | 🔄 Running (PID=1335)  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.reflexion.weekly`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.sla-worker`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.strategos`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.supervisor`                   | 🔄 Running (PID=67146) | —          | 0    | —       | —     |          |
| `com.balizero.wr2.supervisor-watchdog`          | 🔄 Running (PID=67179) | —          | 0    | —       | —     |          |
| `com.balizero.wr2.topic-selector`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.trend-hunter`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.voyager.weekly`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.worktree-gc.daily`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2control`                       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.editorial-bench.monthly`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.reflexion.weekly`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.supervisor`                   | 🔄 Running (PID=17953) | —          | 74   | —       | —     |          |
| `com.balizero.yield-optimizer.weekly`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.cell.metabolic-rollup`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.cell.organism`                             | 🔄 Running (PID=6677)  | —          | 1    | —       | —     |          |
| `com.nuzantara.agent-worktree-cleanup.daily`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.anti-stall-caffeinate`           | 🔄 Running (PID=1362)  | —          | 0    | —       | —     |          |
| `com.nuzantara.archive-empty-sessions.daily`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-server`                  | 🔄 Running (PID=1321)  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-telegram`                | 🔄 Running (PID=1345)  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-watchdog`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.automations-reference`           | 🔄 Running (PID=36777) | —          | 0    | —       | —     |          |
| `com.nuzantara.branch-cleanup.weekly`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory`                | 🔄 Running (PID=1363)  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory-prune`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory-selfcheck`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.chronic-failure-digest.weekly`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.claude-config-sync`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.claude-max-usage-watcher`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cloudflared-intake-review`       | 🔄 Running (PID=1399)  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-autofix-ci`                | 🔄 Running (PID=36776) | ⚠️ SKIPPED | 0    | —       | —     |          |
| `com.nuzantara.codex-coverage-improver`         | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.codex-openclaw-analysis`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-research-actor`            | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-daily-cap`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-weekly`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-breaker`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-breaker-deadman`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-ledger-export`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cpu-monitor`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.curiosity-loop.daily`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.daily-indexing-sweep`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.disk-monitor`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.dlq-autopilot`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.federation-alert-dispatcher`     | 🔄 Running (PID=18011) | —          | 1    | —       | —     |          |
| `com.nuzantara.fly-logs-accumulator`            | 🔄 Running (PID=1418)  | —          | 0    | —       | —     |          |
| `com.nuzantara.fly-restart-loop-detector`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.gh-auth-healthcheck.weekly`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.git-pull-main.15min`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.healer-pro.6h`                   | 🔄 Running (PID=80008) | —          | 0    | —       | —     |          |
| `com.nuzantara.heartbeat-bridge`                | 🔄 Running (PID=1316)  | —          | 0    | —       | —     |          |
| `com.nuzantara.intake-blob-retention`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.intake-gate-count-pusher`        | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.intake-review-reader`            | 🔄 Running (PID=1366)  | —          | 0    | —       | —     |          |
| `com.nuzantara.intake-review-reader-liveness`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.intake-worker`                   | 🔄 Running (PID=1354)  | —          | 0    | —       | —     |          |
| `com.nuzantara.launchagent-state-bridge`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.launchd-env-loader`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.launchd-liveness-detector.daily` | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.lead-intent-matcher`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.local-livekit-server`            | 🔄 Running (PID=1349)  | —          | 0    | —       | —     |          |
| `com.nuzantara.local-livekit-worker`            | 🔄 Running (PID=1391)  | —          | 0    | —       | —     |          |
| `com.nuzantara.log-rotate.daily`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.login-healthcheck`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.machine-boot-report`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.mcp-integrity`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.memory-sync-bidirectional`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.merge-train`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.nb-intel-delta-watcher.hourly`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.nb-mitochondrial-monitor.daily`  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-children-watchdog`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-logrotate`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-whatsapp-bridge`        | 🔄 Running (PID=19655) | —          | -15  | —       | —     |          |
| `com.nuzantara.openclaw-whatsapp-tunnel`        | 🔄 Running (PID=19643) | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw.guardian-board`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.control-panel`          | 🔄 Running (PID=1379)  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.scheduled-tick`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.supervisor`             | 🔄 Running (PID=1381)  | —          | 0    | —       | —     |          |
| `com.nuzantara.outbox-prune.daily`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.outbox-prune.weekly`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.pg-organism-bridge`              | 🔄 Running (PID=1358)  | —          | 0    | —       | —     |          |
| `com.nuzantara.pg-organism-bridge-watchdog`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.plist-snapshot.daily`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.prime-tunnel`                    | 🔄 Running (PID=1317)  | —          | 0    | —       | —     |          |
| `com.nuzantara.redis-liveness`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.repomap.15min`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.review-gate`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.runtime-reconcile`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.secrets-sync-mini`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel`                        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel-aggregate`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel-meta-watchdog`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.skills-bridge-consumer`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.supervisor-liveness-watchdog`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.tg-digest-flush`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.vector-reindex-check`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.verify-connectome`               | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.verify-the-verifiers`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.wa-media-pull`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.wa-mirror-intake-sweeper`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.wa-mirror-session-janitor`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.worktree-gc-universal.daily`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.zombie-hunter`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.colima`                          | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `homebrew.mxcl.ollama`                          | 🔄 Running (PID=1370)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.postgresql@17`                   | 🔄 Running (PID=1398)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                           | 🔄 Running (PID=1352)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.syncthing`                       | 🔄 Running (PID=1397)  | —          | 0    | —       | —     |          |

### Cron Jobs

| Job                   | Schedule                  | Last Run         | Status    | Circuit      | Scope | Critical | Notes                                              |
| --------------------- | ------------------------- | ---------------- | --------- | ------------ | ----- | -------- | -------------------------------------------------- |
| `cache_cleanup`       | 1st+15th 3:30 UTC         | 2026-07-15 03:30 | ✅ OK     | ✅ CLOSED/T0 | LOCAL |          | Wed Jul 15 03:30:50 WITA 2026: cache cleanup done  |
| `cron_agent`          | daily 1:10 UTC (+7 more)  | 2026-07-25 01:14 | ✅ OK     | —            | —     |          | [2026-07-25T01:14:52] [nlm-deep-research] OK durat |
| `cron_runner`         | every 5m (+22 more)       | 2026-07-19 02:00 | ❌ FAIL   | —            | —     |          | [2026-07-19 02:00:02] ⚠️ KG builder failed (HTTP 4 |
| `cron_state`          | every 5m (+21 more)       | 2026-07-25 23:15 | ? check   | —            | —     |          | [openclaw-bridge] Cannot read jobs.json: [Errno 2] |
| `cron_wrapper`        | daily 21:00 UTC (+5 more) |                  |           | —            | —     |          |                                                    |
| `fly_cost_alert`      | Mon 9:00 UTC              | 2026-07-20 09:00 | ? check   | ✅ CLOSED/T0 | LOCAL |          | [2026-07-20 09:00:14] Cost within budget ✅        |
| `ollama_warm_pin`     | Sun 5:00 UTC              | 2026-07-19 05:01 | ✅ OK     | —            | —     |          | [2026-07-19T05:01:23] Warm-pin complete on Nuzanta |
| `peraturan_ingestion` | 6 21:30 UTC               |                  | ⚠️ NO LOG | —            | —     |          |                                                    |
| `pro_heartbeat`       | 0 \* \* \* \*             |                  |           | ✅ CLOSED/T0 | LOCAL |          |                                                    |
| `run`                 | every 15m (+14 more)      | 2026-07-25 23:15 | ❌ FAIL   | —            | —     |          | 2026-07-25 23:15:02 [info ] check_now_done         |

---

## Mini (nuzantara@mini-pro2 — M4 Pro 24GB, H24)

### LaunchAgents

| Label                                       | Status                 | Autonomy | Exit | Circuit | Scope | Critical |
| ------------------------------------------- | ---------------------- | -------- | ---- | ------- | ----- | -------- |
| `com.balizero.mlx-server`                   | 🔄 Running (PID=92776) | —        | -15  | —       | —     |          |
| `com.balizero.wa-mirror`                    | ⚠️ NOT LOADED          | —        | ?    | —       | —     |          |
| `com.balizero.wr2.warroom-sync`             | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.balizero.wr2control`                   | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.balizero.zerodesign.studio`            | 🔄 Running (PID=1478)  | —        | 0    | —       | —     |          |
| `com.nuzantara.fleet-watch`                 | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.git-pull-main.5min`          | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.healer.4h`                   | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.heartbeat-watchdog.daily`    | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.local-livekit-server`        | 🔄 Running (PID=59125) | —        | -15  | —       | —     |          |
| `com.nuzantara.local-livekit-worker`        | 🔄 Running (PID=59134) | —        | 0    | —       | —     |          |
| `com.nuzantara.log-prune.daily`             | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.mini.tg-digest-flush`        | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.ollama-warm-pin`             | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.overlap-detector.daily`      | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.regie-resume`                | ⚠️ NOT LOADED          | —        | ?    | —       | —     |          |
| `com.nuzantara.worktree-gc-universal.daily` | ✅ OK                  | —        | 0    | —       | —     |          |
| `homebrew.mxcl.postgresql@18`               | 🔄 Running (PID=1480)  | —        | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                       | 🔄 Running (PID=2299)  | —        | 1    | —       | —     |          |

### Cron Jobs

| Job                      | Schedule       | Last Run         | Status  | Circuit | Scope | Critical | Notes                                              |
| ------------------------ | -------------- | ---------------- | ------- | ------- | ----- | -------- | -------------------------------------------------- |
| `crm_kg_build_mediated`  | every 6h (:0)  | 2026-07-25 18:00 |         | —       | —     |          |                                                    |
| `crm_kg_garbage_collect` | daily 3:00 UTC | 2026-07-25 03:00 |         | —       | —     |          |                                                    |
| `drive_poll`             | every 5m       | 2026-07-25 23:15 | ❌ FAIL | —       | —     |          | [2026-07-25 23:15:00] ⚠️ Drive poll failed (HTTP 4 |

---

_Generated by `scripts/generate_automations_reference.py` — 2026-07-25 15:15 UTC_
