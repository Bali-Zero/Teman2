# NUZANTARA — AUTOMATIONS REFERENCE

> **Auto-generated from live system state** — do not edit manually.
> Generated: 2026-07-13 15:15 UTC
> Source: `crontab -l` (Pro+Mini) + `launchctl list` (Pro+Mini) + log health + `job_registry.json` + `sentinel_status.json` + `circuit_breakers.json`

---

## System Health Summary

| Metric                | Value   |
| --------------------- | ------- |
| Total jobs            | **224** |
| ✅ Healthy            | **137** |
| 🔄 Running (daemons)  | **55**  |
| ⚠️ Warning/Skip/NoLog | **7**   |
| ❌ Failed             | **19**  |

---

## Sentinel Overview

> Ultimo aggiornamento sentinel: `2026-07-13T15:05:47Z`

| Metrica                   | Valore        |
| ------------------------- | ------------- |
| Circuit OPEN              | **0**         |
| Circuit TERMINAL          | **11**        |
| DLQ entries totali        | **11**        |
| DLQ phase distribution    | `TERMINAL=11` |
| Job critici (in registry) | **0**         |

---

## Pro (nuzantara@Nuzantara — M4 Pro 48GB)

### LaunchAgents

| Label                                          | Status                 | Autonomy   | Exit | Circuit | Scope | Critical |
| ---------------------------------------------- | ---------------------- | ---------- | ---- | ------- | ----- | -------- |
| `ai.openclaw.gateway`                          | 🔄 Running (PID=17800) | —          | 0    | —       | —     |          |
| `ai.openclaw.node`                             | 🔄 Running (PID=17771) | —          | -15  | —       | —     |          |
| `com.balizero.agent-library-evolver.daily`     | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.agent-library-evolver.weekly`    | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.audit-launchd.daily`             | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.bz-daily-visual-pipeline`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.cicatrix-rotation.monthly`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.claude-settings-watcher`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.client-value-predictor`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.codex-spalla-calibrate`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.competitor-monitor.monthly`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.competitor-signal-router.weekly` | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.crm-guardian-cli-worker`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.cron-log-sentinel`               | 🔄 Running (PID=1752)  | —          | 0    | —       | —     |          |
| `com.balizero.curiosity.weekly`                | ❌ FAILED (exit=127)   | —          | 127  | —       | —     |          |
| `com.balizero.domain-mesh.foundations.daily`   | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.drive-intake-drain`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.dropbox-intake`                  | 🔄 Running (PID=95716) | —          | 0    | —       | —     |          |
| `com.balizero.fly-cost-alert.weekly`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.guardrails-daemon`               | 🔄 Running (PID=1829)  | —          | 0    | —       | —     |          |
| `com.balizero.intel-dedup-gateway`             | 🔄 Running (PID=1832)  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake-nb-pusher.15min`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake-router.5min`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake.e2e-probe.6h`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake.outbox-drain.minute`  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake.shadow-validate.6h`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-radar-daily-digest`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel.nightly`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.l5-2-phase2b-trigger`            | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.meta-dispatcher`                 | 🔄 Running (PID=11546) | —          | 1    | —       | —     |          |
| `com.balizero.mlx-server`                      | 🔄 Running (PID=1768)  | —          | 0    | —       | —     |          |
| `com.balizero.modus.autoloop.nightly`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.mos-plus.compression`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.mos-plus.qdrant-indexer`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nb-curator.daily`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nextdns-tamper-detect.weekly`    | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.nlm-bridge`                      | 🔄 Running (PID=1774)  | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara-drive-sync`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara.disk-watchdog`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara.log-size-watchdog`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.observatory`                     | 🔄 Running (PID=11497) | —          | 1    | —       | —     |          |
| `com.balizero.observatory-export`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.observatory-server`              | 🔄 Running (PID=1812)  | —          | 0    | —       | —     |          |
| `com.balizero.post-publish-poller`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.post-publish-webhook`            | 🔄 Running (PID=1794)  | —          | 0    | —       | —     |          |
| `com.balizero.profile-monitor-wrapper`         | 🔄 Running (PID=1817)  | —          | 0    | —       | —     |          |
| `com.balizero.qdrant.daemon`                   | 🔄 Running (PID=1755)  | —          | 0    | —       | —     |          |
| `com.balizero.regulatory-watcher.daily`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.renewal-alerts`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.research-sentinel`               | 🔄 Running (PID=1845)  | —          | 0    | —       | —     |          |
| `com.balizero.seo-cell.28d-check`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.seo-cell.daily`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.setup-team.daily`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-checkpoint`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-collect`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-monthly`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-weekly`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.translate.hourly`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-dashboard-m1`                 | 🔄 Running (PID=1814)  | —          | 0    | —       | —     |          |
| `com.balizero.wa-lid-refresh`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-meta-inbox`                   | 🔄 Running (PID=1788)  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-attention-classifier`  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-attention-digest`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-attention-realtime`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-auto-promote`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-auto-promote-selfheal` | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-launcher`              | 🔄 Running (PID=1756)  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-strategic-recap`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-team-metrics-rollup`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.connector`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.daily-metrics`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.daily-reconciler`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.deploy-puller`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.dossier-compiler`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.draft-generator`             | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.wr2.e2e-probe.daily`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.external-bench.monthly`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.fact-checker`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.fact-extractor`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.hardening`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.html-apply`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.ig-metrics-analyst.weekly`   | 🔄 Running (PID=72413) | —          | 0    | —       | —     |          |
| `com.balizero.wr2.ig-metrics-scrape.daily`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.ig-scraper.daily`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.image-generator`             | ❌ FAILED (exit=2)     | —          | 2    | —       | —     |          |
| `com.balizero.wr2.learner-nightly`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.measurer`                    | ❌ FAILED (exit=2)     | —          | 2    | —       | —     |          |
| `com.balizero.wr2.newsletter`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.oracle`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.pg-proxy`                    | 🔄 Running (PID=1837)  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.pg-queue-sync`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.plist-watchdog`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.queue-server`                | 🔄 Running (PID=1759)  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.reflexion.weekly`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.sla-worker`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.strategos`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.supervisor`                  | 🔄 Running (PID=93857) | —          | 0    | —       | —     |          |
| `com.balizero.wr2.supervisor-watchdog`         | 🔄 Running (PID=93981) | —          | 0    | —       | —     |          |
| `com.balizero.wr2.topic-selector`              | ❌ FAILED (exit=2)     | —          | 2    | —       | —     |          |
| `com.balizero.wr2.trend-hunter`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.voyager.weekly`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.worktree-gc.daily`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2control`                      | 🔄 Running (PID=1784)  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.editorial-bench.monthly`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.reflexion.weekly`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.supervisor`                  | 🔄 Running (PID=11560) | —          | 74   | —       | —     |          |
| `com.balizero.yield-optimizer.weekly`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.cell.metabolic-rollup`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.cell.organism`                            | 🔄 Running (PID=7462)  | —          | 1    | —       | —     |          |
| `com.nuzantara.agent-worktree-cleanup.daily`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.archive-empty-sessions.daily`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-server`                 | 🔄 Running (PID=1744)  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-telegram`               | 🔄 Running (PID=1769)  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-watchdog`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.automations-reference`          | 🔄 Running (PID=56459) | —          | 0    | —       | —     |          |
| `com.nuzantara.branch-cleanup.weekly`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory`               | 🔄 Running (PID=1787)  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory-prune`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory-selfcheck`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.chronic-failure-digest.weekly`  | ❌ FAILED (exit=127)   | —          | 127  | —       | —     |          |
| `com.nuzantara.claude-config-sync`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.claude-max-usage-watcher`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cloudflared-intake-review`      | 🔄 Running (PID=1820)  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-autofix-ci`               | 🔄 Running (PID=56458) | ⚠️ SKIPPED | 0    | —       | —     |          |
| `com.nuzantara.codex-coverage-improver`        | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.codex-openclaw-analysis`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-research-actor`           | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-daily-cap`         | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.cost-advisor-weekly`            | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.cost-breaker`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-breaker-deadman`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-ledger-export`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cpu-monitor`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.curiosity-loop.daily`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.daily-indexing-sweep`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.disk-monitor`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.dlq-autopilot`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.federation-alert-dispatcher`    | 🔄 Running (PID=11556) | —          | 1    | —       | —     |          |
| `com.nuzantara.fly-restart-loop-detector`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.gh-auth-healthcheck.weekly`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.healer-pro.6h`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.heartbeat-bridge`               | 🔄 Running (PID=1740)  | —          | 0    | —       | —     |          |
| `com.nuzantara.intake-blob-retention`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.intake-gate-count-pusher`       | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.intake-review-reader`           | 🔄 Running (PID=1790)  | —          | 0    | —       | —     |          |
| `com.nuzantara.intake-review-reader-liveness`  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.intake-worker`                  | 🔄 Running (PID=6016)  | —          | -11  | —       | —     |          |
| `com.nuzantara.launchagent-state-bridge`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.launchd-env-loader`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.lead-intent-matcher`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.local-livekit-server`           | 🔄 Running (PID=1773)  | —          | 0    | —       | —     |          |
| `com.nuzantara.local-livekit-worker`           | 🔄 Running (PID=1813)  | —          | 0    | —       | —     |          |
| `com.nuzantara.login-healthcheck`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.mcp-integrity`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.memory-sync-bidirectional`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.merge-train`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.nb-intel-delta-watcher.hourly`  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.nb-mitochondrial-monitor.daily` | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-children-watchdog`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-logrotate`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-whatsapp-bridge`       | 🔄 Running (PID=17787) | —          | -15  | —       | —     |          |
| `com.nuzantara.openclaw-whatsapp-tunnel`       | 🔄 Running (PID=17775) | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw.guardian-board`        | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.organism.control-panel`         | 🔄 Running (PID=1801)  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.scheduled-tick`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.supervisor`            | 🔄 Running (PID=1802)  | —          | 0    | —       | —     |          |
| `com.nuzantara.outbox-prune.daily`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.outbox-prune.weekly`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.pg-organism-bridge`             | 🔄 Running (PID=1782)  | —          | 0    | —       | —     |          |
| `com.nuzantara.pg-organism-bridge-watchdog`    | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.nuzantara.plist-snapshot.daily`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.prime-tunnel`                   | 🔄 Running (PID=1741)  | —          | 0    | —       | —     |          |
| `com.nuzantara.repomap.15min`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.review-gate`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.runtime-reconcile`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.secrets-sync-mini`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel`                       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel-aggregate`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel-meta-watchdog`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.skills-bridge-consumer`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.supervisor-liveness-watchdog`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.tg-digest-flush`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.vector-reindex-check`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.verify-connectome`              | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.verify-the-verifiers`           | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.wa-media-pull`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.wa-mirror-intake-sweeper`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.wa-mirror-session-janitor`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.worktree-gc-universal.daily`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.zombie-hunter`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.ollama`                         | 🔄 Running (PID=1793)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.postgresql@17`                  | 🔄 Running (PID=1819)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                          | 🔄 Running (PID=1776)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.syncthing`                      | 🔄 Running (PID=1818)  | —          | 0    | —       | —     |          |

### Cron Jobs

| Job               | Schedule                  | Last Run         | Status    | Circuit           | Scope | Critical | Notes                                               |
| ----------------- | ------------------------- | ---------------- | --------- | ----------------- | ----- | -------- | --------------------------------------------------- |
| `cache_cleanup`   | 1st+15th 3:30 UTC         |                  | ⚠️ NO LOG | ✅ HALF_OPEN/None | LOCAL |          |                                                     |
| `cron_agent`      | daily 1:10 UTC (+7 more)  | 2026-07-13 01:14 | ✅ OK     | —                 | —     |          | [2026-07-13T01:14:23] [nlm-deep-research] OK durat  |
| `cron_runner`     | every 5m (+23 more)       | 2026-07-12 02:00 | ❌ FAIL   | —                 | —     |          | [2026-07-12 02:00:05] ✅ KG builder completed: {"ex |
| `cron_state`      | every 5m (+21 more)       | 2026-07-13 23:15 | ? check   | —                 | —     |          | [openclaw-bridge] Cannot read jobs.json: [Errno 2]  |
| `cron_wrapper`    | daily 21:00 UTC (+5 more) |                  |           | —                 | —     |          |                                                     |
| `fly_cost_alert`  | Mon 9:00 UTC              | 2026-07-13 09:00 | ? check   | ✅ CLOSED/T0      | LOCAL |          | [2026-07-13 09:00:01] Cost within budget ✅         |
| `ollama_warm_pin` | Sun 5:00 UTC              | 2026-07-12 05:00 | ✅ OK     | —                 | —     |          | [2026-07-12T05:00:27] Warm-pin complete on Nuzanta  |
| `pro_heartbeat`   | 0 \* \* \* \*             |                  |           | ✅ CLOSED/T0      | LOCAL |          |                                                     |
| `run`             | every 15m (+14 more)      | 2026-07-13 23:15 | ❌ FAIL   | —                 | —     |          | 2026-07-13 23:15:06 [info ] telegram_alert          |

---

## Mini (nuzantara@mini-pro2 — M4 Pro 24GB, H24)

### LaunchAgents

| Label                                    | Status                 | Autonomy | Exit | Circuit | Scope | Critical |
| ---------------------------------------- | ---------------------- | -------- | ---- | ------- | ----- | -------- |
| `com.balizero.mlx-server`                | 🔄 Running (PID=92776) | —        | -15  | —       | —     |          |
| `com.balizero.wa-mirror`                 | ⚠️ NOT LOADED          | —        | ?    | —       | —     |          |
| `com.balizero.wr2.warroom-sync`          | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.balizero.wr2control`                | 🔄 Running (PID=36483) | —        | -9   | —       | —     |          |
| `com.balizero.zerodesign.studio`         | 🔄 Running (PID=1478)  | —        | 0    | —       | —     |          |
| `com.nuzantara.daily-gsc-indexing-sweep` | ⚠️ NOT LOADED          | —        | ?    | —       | —     |          |
| `com.nuzantara.fleet-watch`              | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.git-pull-main.5min`       | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.healer.4h`                | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.heartbeat-watchdog.daily` | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.local-livekit-server`     | 🔄 Running (PID=59125) | —        | -15  | —       | —     |          |
| `com.nuzantara.local-livekit-worker`     | 🔄 Running (PID=59134) | —        | 0    | —       | —     |          |
| `com.nuzantara.log-prune.daily`          | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.mini.tg-digest-flush`     | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.ollama-warm-pin`          | ✅ OK                  | —        | 0    | —       | —     |          |
| `com.nuzantara.overlap-detector.daily`   | ❌ FAILED (exit=1)     | —        | 1    | —       | —     |          |
| `homebrew.mxcl.postgresql@18`            | 🔄 Running (PID=1480)  | —        | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                    | 🔄 Running (PID=2299)  | —        | 1    | —       | —     |          |

### Cron Jobs

| Job                      | Schedule       | Last Run         | Status  | Circuit | Scope | Critical | Notes                                              |
| ------------------------ | -------------- | ---------------- | ------- | ------- | ----- | -------- | -------------------------------------------------- |
| `crm_kg_build_mediated`  | every 6h (:0)  | 2026-07-13 18:00 |         | —       | —     |          |                                                    |
| `crm_kg_garbage_collect` | daily 3:00 UTC | 2026-07-13 03:00 |         | —       | —     |          |                                                    |
| `drive_poll`             | every 5m       | 2026-07-13 23:15 | ❌ FAIL | —       | —     |          | [2026-07-13 23:15:00] ⚠️ Drive poll failed (HTTP 4 |

---

_Generated by `scripts/generate_automations_reference.py` — 2026-07-13 15:15 UTC_
