# NUZANTARA — AUTOMATIONS REFERENCE

> **Auto-generated from live system state** — do not edit manually.
> Generated: 2026-05-30 15:15 UTC
> Source: `crontab -l` (Pro+Mini) + `launchctl list` (Pro+Mini) + log health + `job_registry.json` + `sentinel_status.json` + `circuit_breakers.json`

---

## System Health Summary

| Metric                | Value   |
| --------------------- | ------- |
| Total jobs            | **206** |
| ✅ Healthy            | **113** |
| 🔄 Running (daemons)  | **38**  |
| ⚠️ Warning/Skip/NoLog | **6**   |
| ❌ Failed             | **34**  |

---

## Sentinel Overview

> Ultimo aggiornamento sentinel: `2026-05-30T14:46:07Z`

| Metrica                   | Valore        |
| ------------------------- | ------------- |
| Circuit OPEN              | **0**         |
| Circuit TERMINAL          | **13**        |
| DLQ entries totali        | **13**        |
| DLQ phase distribution    | `TERMINAL=13` |
| Job critici (in registry) | **0**         |

---

## Pro (nuzantara@Nuzantara — M4 Pro 48GB)

### LaunchAgents

| Label                                                | Status                 | Autonomy   | Exit | Circuit | Scope | Critical |
| ---------------------------------------------------- | ---------------------- | ---------- | ---- | ------- | ----- | -------- |
| `ai.openclaw.gateway`                                | 🔄 Running (PID=7053)  | —          | 0    | —       | —     |          |
| `ai.openclaw.node`                                   | 🔄 Running (PID=7037)  | —          | -15  | —       | —     |          |
| `com.balizero.agent-library-evolver.weekly`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.audit-launchd.daily`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.bz-daily-visual-pipeline`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.cicatrix-rotation.monthly`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.claude-settings-watcher`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.client-value-predictor`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.codex-spalla-calibrate`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.competitor-monitor.monthly`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.competitor-signal-router.weekly`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.crm-guardian-cli-worker`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.cron-log-sentinel`                     | 🔄 Running (PID=977)   | —          | 0    | —       | —     |          |
| `com.balizero.curiosity.weekly`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.domain-mesh.foundations.daily`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.fly-cost-alert.weekly`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.guardrails-daemon`                     | 🔄 Running (PID=1035)  | —          | 0    | —       | —     |          |
| `com.balizero.indexing-sweep.daily`                  | 🔄 Running (PID=24740) | —          | 0    | —       | —     |          |
| `com.balizero.intel-dedup-gateway`                   | 🔄 Running (PID=1039)  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake-nb-pusher.15min`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake-router.5min`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake.e2e-probe.6h`               | ❌ FAILED (exit=2)     | —          | 2    | —       | —     |          |
| `com.balizero.intel-lake.outbox-drain.minute`        | ❌ FAILED (exit=2)     | —          | 2    | —       | —     |          |
| `com.balizero.intel-lake.shadow-validate.6h`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-radar-daily-digest`              | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.intel.nightly`                         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.l5-2-phase2b-trigger`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.meta-dispatcher`                       | 🔄 Running (PID=966)   | —          | 0    | —       | —     |          |
| `com.balizero.mos-plus.compression`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.mos-plus.qdrant-indexer`               | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.nb-curator.daily`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nlm-bridge`                            | 🔄 Running (PID=997)   | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara-drive-sync`                  | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.nuzantara.disk-watchdog`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara.log-size-watchdog`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.observatory`                           | 🔄 Running (PID=1046)  | —          | 0    | —       | —     |          |
| `com.balizero.observatory-export`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.observatory-server`                    | 🔄 Running (PID=1022)  | —          | 0    | —       | —     |          |
| `com.balizero.post-publish-poller`                   | ❌ FAILED (exit=78)    | —          | 78   | —       | —     |          |
| `com.balizero.post-publish-webhook`                  | 🔄 Running (PID=1010)  | —          | 0    | —       | —     |          |
| `com.balizero.profile-monitor-wrapper`               | 🔄 Running (PID=1028)  | —          | 0    | —       | —     |          |
| `com.balizero.qdrant.daemon`                         | ❌ FAILED (exit=101)   | —          | 101  | —       | —     |          |
| `com.balizero.regulatory-watcher.daily`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.regulatory-watcher.fix-b-verify`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.renewal-alerts`                        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.research-sentinel`                     | 🔄 Running (PID=1050)  | —          | 0    | —       | —     |          |
| `com.balizero.seo-cell.28d-check`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.seo-cell.daily`                        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.setup-team.daily`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-checkpoint`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-collect`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-monthly`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-weekly`                       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.translate.hourly`                      | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wa-dashboard-m1`                       | 🔄 Running (PID=1024)  | —          | 0    | —       | —     |          |
| `com.balizero.wa-lid-refresh`                        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror`                             | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.wa-mirror-attention-classifier`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-attention-digest`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-attention-realtime`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-auto-promote`                | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wa-mirror-launcher`                    | 🔄 Running (PID=24509) | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-strategic-recap`             | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wa-viewer`                             | 🔄 Running (PID=1023)  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.canva-apply`                       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.canva-gc.weekly`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.canva-lease-watchdog.10min`        | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.wr2.canva-oauth-watchdog`              | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.canva-renderer`                    | ❌ FAILED (exit=78)    | —          | 78   | —       | —     |          |
| `com.balizero.wr2.canva-token-watchdog.daily`        | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.wr2.carousel-dispatcher`               | 🔄 Running (PID=17324) | —          | 75   | —       | —     |          |
| `com.balizero.wr2.connector`                         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.daily-metrics`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.deploy-puller`                     | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.dossier-compiler`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.draft-generator`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.e2e-probe.daily`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.external-bench.monthly`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.fact-checker`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.fact-extractor`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.hardening`                         | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.ig-metrics-analyst.weekly`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.ig-scraper.daily`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.image-generator`                   | ❌ FAILED (exit=2)     | —          | 2    | —       | —     |          |
| `com.balizero.wr2.learner-nightly`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.measurer`                          | ❌ FAILED (exit=2)     | —          | 2    | —       | —     |          |
| `com.balizero.wr2.newsletter`                        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.oracle`                            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.pg-proxy`                          | 🔄 Running (PID=1044)  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.pg-queue-sync`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.plist-watchdog`                    | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.queue-server`                      | 🔄 Running (PID=984)   | —          | 0    | —       | —     |          |
| `com.balizero.wr2.reflexion.weekly`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.sla-worker`                        | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.strategos`                         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.supervisor`                        | 🔄 Running (PID=17298) | —          | 74   | —       | —     |          |
| `com.balizero.wr2.supervisor-watchdog`               | 🔄 Running (PID=8749)  | —          | 74   | —       | —     |          |
| `com.balizero.wr2.telegram-gate`                     | 🔄 Running (PID=34461) | —          | 1    | —       | —     |          |
| `com.balizero.wr2.topic-selector`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.trend-hunter`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.voyager.weekly`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.worktree-gc.daily`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.editorial-bench.monthly`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.reflexion.weekly`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.supervisor`                        | ❌ FAILED (exit=78)    | —          | 78   | —       | —     |          |
| `com.balizero.wr3.yt-metrics.weekly`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.yield-optimizer.weekly`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.cell.metabolic-rollup`                          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.cell.organism`                                  | 🔄 Running (PID=9380)  | —          | 1    | —       | —     |          |
| `com.claude-max-api`                                 | ❌ FAILED (exit=78)    | —          | 78   | —       | —     |          |
| `com.nuzantara.archive-empty-sessions.daily`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-server`                       | 🔄 Running (PID=970)   | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-telegram`                     | 🔄 Running (PID=993)   | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-watchdog`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.automations-reference`                | 🔄 Running (PID=24762) | —          | 0    | —       | —     |          |
| `com.nuzantara.branch-cleanup.weekly`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory`                     | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.cell-observatory-prune`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory-selfcheck`           | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.claude-config-sync`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cleanup-2026-05-16-ttl-sentinel`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-autofix-ci`                     | 🔄 Running (PID=24763) | ⚠️ SKIPPED | 0    | —       | —     |          |
| `com.nuzantara.codex-coverage-improver`              | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.codex-openclaw-analysis`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-overnight-feeder`               | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.codex-overnight-runner`               | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.codex-research-actor`                 | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.codex-spark-alarm`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-spark-harvester`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-spark-loop`                     | 🔄 Running (PID=1018)  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-daily-cap`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-weekly`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cpu-monitor`                          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.disk-monitor`                         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.dlq-autopilot`                        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.federation-alert-dispatcher`          | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.fly-restart-loop-detector`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.gh-auth-healthcheck.weekly`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.heartbeat-bridge`                     | 🔄 Running (PID=967)   | —          | 0    | —       | —     |          |
| `com.nuzantara.launchagent-state-bridge`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.launchd-env-loader`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.login-healthcheck`                    | ❌ FAILED (exit=78)    | —          | 78   | —       | —     |          |
| `com.nuzantara.memory-sync-bidirectional`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.nb-intel-delta-watcher.hourly`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.nb-mitochondrial-monitor.daily`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-children-watchdog`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-logrotate`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-whatsapp-bridge`             | 🔄 Running (PID=4899)  | —          | -15  | —       | —     |          |
| `com.nuzantara.openclaw-whatsapp-tunnel`             | 🔄 Running (PID=66618) | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw.guardian-board`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.control-panel`               | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.organism.scheduled-tick`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.supervisor`                  | 🔄 Running (PID=1016)  | —          | 0    | —       | —     |          |
| `com.nuzantara.outbox-prune.daily`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.outbox-prune.weekly`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.pg-organism-bridge`                   | 🔄 Running (PID=1004)  | —          | 0    | —       | —     |          |
| `com.nuzantara.pg-organism-bridge-watchdog`          | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.nuzantara.pg-proxy-cluster-recheck-oneshot`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.prime-tunnel`                         | 🔄 Running (PID=968)   | —          | 0    | —       | —     |          |
| `com.nuzantara.repomap.15min`                        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.secrets-sync-mini`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel`                             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel-aggregate`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel-meta-watchdog`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.skills-bridge-consumer`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.supervisor-liveness-watchdog`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.vector-reindex-check`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.workspace-event-bridge-sheets-import` | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.worktree-gc-universal.daily`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.zombie-hunter`                        | ✅ OK                  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.ollama`                               | 🔄 Running (PID=1009)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.postgresql@17`                        | 🔄 Running (PID=1030)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                                | 🔄 Running (PID=999)   | —          | 0    | —       | —     |          |
| `homebrew.mxcl.syncthing`                            | 🔄 Running (PID=1029)  | —          | 0    | —       | —     |          |

### Cron Jobs

| Job                     | Schedule                  | Last Run         | Status    | Circuit | Scope | Critical | Notes                                               |
| ----------------------- | ------------------------- | ---------------- | --------- | ------- | ----- | -------- | --------------------------------------------------- |
| `audit_trail_cleanup`   | Sun 2:00 UTC              | 2026-05-24 02:00 | ❌ FAIL   | —       | —     |          | Error: no access token available. Please login wit  |
| `auto_judgement_day`    | Sun 8:00 UTC              | 2026-04-26 08:00 | ? check   | —       | —     |          | /Users/nuzantara/Desktop/nuzantara/scripts/auto_ju  |
| `auto_sentinel`         | daily 19:00 UTC           | 2026-04-29 19:00 | ❌ FAIL   | —       | —     |          | /bin/bash: /Users/nuzantara/Desktop/nuzantara/scri  |
| `auto_test`             | daily 18:15 UTC           | 2026-05-30 18:15 | ❌ FAIL   | —       | —     |          | [2026-05-30 18:15:00] ❌ Test failures: agentic llm |
| `backups`               | Sun 5:00 UTC              |                  |           | —       | —     |          |                                                     |
| `cache_cleanup`         | 1st+15th 3:30 UTC         | 2026-05-01 03:30 | ❌ FAIL   | —       | —     |          | npm error A complete log of this run can be found   |
| `cert_monitor`          | daily 7:00 UTC            |                  |           | —       | —     |          |                                                     |
| `coverage_trend`        | daily 4:30 UTC            | 2026-05-30 04:30 | ? check   | —       | —     |          | /Users/nuzantara/Desktop/nuzantara/apps/backend-ra  |
| `cron_agent`            | daily 1:10 UTC (+8 more)  | 2026-05-30 01:11 | ✅ OK     | —       | —     |          | [2026-05-30T01:11:36] [nlm-deep-research] OK durat  |
| `cron_runner`           | every 5m (+23 more)       | 2026-05-24 02:00 | ❌ FAIL   | —       | —     |          | [2026-05-24 02:00:35] ✅ KG builder completed: {"ex |
| `cron_wrapper`          | daily 21:00 UTC (+5 more) |                  |           | —       | —     |          |                                                     |
| `curiosity_loop`        | daily 20:42 UTC           | 2026-05-24 20:42 | ❌ FAIL   | —       | —     |          | 2026-05-24 20:42:01,208 INFO nuzantara_graph.curio  |
| `docs_guardian`         | Sun 5:00 UTC              | 2026-04-26 05:00 | ❌ FAIL   | —       | —     |          | /bin/bash: /Users/nuzantara/Desktop/nuzantara/scri  |
| `fly_backup`            | daily 3:00 UTC            | 2026-05-30 03:21 | ✅ OK     | —       | —     |          | [03:21:44] === Backup complete: PG ✅ Qdrant ✅ === |
| `fly_cost_alert`        | Mon 9:00 UTC              | 2026-05-25 09:00 | ? check   | —       | —     |          | [2026-05-25 09:00:02] Cost within budget ✅         |
| `genome_decay`          | daily 18:30 UTC           | 2026-04-29 18:30 | ❌ FAIL   | —       | —     |          | /bin/bash: /Users/nuzantara/Desktop/nuzantara/scri  |
| `job_health`            | daily 9:00 UTC            | 2026-05-29 09:00 | ✅ OK     | —       | —     |          | ✅ t4-monitor healthy 2026-05-29 06:00              |
| `memory`                | daily 4:00 UTC (+1 more)  |                  |           | —       | —     |          |                                                     |
| `mos_maintenance`       | daily 4:00 UTC            |                  |           | —       | —     |          |                                                     |
| `nb_agents_daily_dr`    | daily 7:30 UTC            |                  | ⚠️ NO LOG | —       | —     |          |                                                     |
| `nextdns_weekly_digest` | Mon 0:55 UTC              | 2026-05-25 00:55 | ? check   | —       | —     |          | /Users/nuzantara/Desktop/nuzantara/scripts/nextdns  |
| `ollama_cron_window`    | daily 17:10 UTC (+1 more) | 2026-05-30 22:05 | ? check   | —       | —     |          | [2026-05-30 22:05:00] No models loaded — nothing t  |
| `ollama_warm_pin`       | Sun 5:00 UTC              | 2026-05-24 05:00 | ✅ OK     | —       | —     |          | [2026-05-24T05:00:28] Warm-pin complete on Nuzanta  |
| `openclaw_state_bridge` | every 5m                  | 2026-05-30 23:15 | ? check   | —       | —     |          | [openclaw-bridge] Written 4/4 state files           |
| `pro_heartbeat`         | 0 \* \* \* \*             |                  |           | —       | —     |          |                                                     |
| `ragas_eval`            | 5 22:30 UTC               | 2026-05-29 22:30 | ? check   | —       | —     |          | [ragas-eval] 2026-05-29 22:30 WITA — similarity=0.  |
| `run`                   | every 15m (+14 more)      | 2026-05-30 23:15 | ❌ FAIL   | —       | —     |          | 2026-05-30 23:15:03 [info ] check_now_done          |
| `sentry_quota_check`    | daily 9:00 UTC            | 2026-05-29 09:00 | ✅ OK     | —       | —     |          | [sentry-quota-check] OK                             |
| `sync_damar`            | 0 \* \* \* \*             |                  |           | —       | —     |          |                                                     |
| `sync_memory_ruslana`   | daily 8:00 UTC            | 2026-05-29 08:00 | ⚠️ WARN   | —       | —     |          | [2026-05-29 08:00] Ruslana host unreachable — skip  |
| `sync_memory_to_nlm`    | Sun 3:00 UTC              | 2026-05-24 03:00 | ✅ OK     | —       | —     |          | ✅ Sync complete                                    |
| `warmup_vision`         | Mon-Sat 9-17:\*/4 UTC     |                  |           | —       | —     |          |                                                     |

---

_Generated by `scripts/generate_automations_reference.py` — 2026-05-30 15:15 UTC_
