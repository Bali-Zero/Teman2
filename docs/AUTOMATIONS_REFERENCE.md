# NUZANTARA — AUTOMATIONS REFERENCE

> **Auto-generated from live system state** — do not edit manually.
> Generated: 2026-09-12 15:15 UTC
> Source: `crontab -l` (Pro+Mini) + `launchctl list` (Pro+Mini) + log health + `job_registry.json` + `sentinel_status.json` + `circuit_breakers.json`

---

## Repo-canon additions pending live snapshot

These entries are committed as repo-canon LaunchAgents but are not counted in
the generated live totals above until installed on the target host and included
in the next automation snapshot. Derived from `infra/launchagents/**/*.plist`
headers, the target script's own header and `infra/home-fork/declared-pairs.json`
on every run — never hand-edit this table, edit the plist (or its target
script) instead.

| Label                                                                       | Host | Schedule                                                               | Purpose                                                                                                                                                          |
| --------------------------------------------------------------------------- | ---- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `com.balizero.auth-sentinel.daily`                                          | M5   | every 6h                                                               | Cron puro: StartInterval, NO KeepAlive (scar #7 daemon-vs-cron).                                                                                                 |
| `com.balizero.domain-mesh.foundations.daily`                                | Pro  | daily 04:00 WITA                                                       | runs `domain-mesh-foundations-cron.sh`                                                                                                                           |
| `com.balizero.indexing-sweep.daily`                                         | Pro  | daily 00:30 WITA                                                       | Daily Google Search Console Indexing Sweep (Pro) Phase 1: Articles (max 200/day) Phase 2: KBLI (max 600/day via 3 SAs × 200 each) Submits unindexed URLs to G... |
| `com.balizero.l5-2-phase2b-trigger`                                         | Pro  | daily 09:00 WITA                                                       | L5.2 Phase 2b trigger — one-shot LaunchAgent.                                                                                                                    |
| `com.balizero.magazine.breaking`                                            | Pro  | every 10m                                                              | Pro-only LaunchAgent: drains qualified Breaking candidates every 10 minutes or less.                                                                             |
| `com.balizero.magazine.morning`                                             | Pro  | daily 08:15 WITA                                                       | Pro-only LaunchAgent: morning magazine compose at 08:15 WITA, after collectors, target publish by 08:30.                                                         |
| `com.balizero.wa-codex-broker`                                              | Pro  | —                                                                      | LaunchDAEMON, not LaunchAgent (deliberate, spec §4.1): zantara-codex is a login-less user, and a LaunchAgent for a user who never logs in never runs (scar fa... |
| `com.balizero.wa-codex-seat-probe`                                          | Pro  | every 6h                                                               | LaunchDAEMON, not LaunchAgent (deliberate, spec §4.1, same reasoning as com.balizero.wa-codex-broker): zantara-codex is a login-less user, and a LaunchAgent...  |
| `com.matagaruda.kita-feed` (`com.matagaruda.kita-feed.daily.plist`)         | Pro  | daily 05:00 WITA                                                       | Mata Garuda — Kita Feed Generator runner.                                                                                                                        |
| `com.nuzantara.chore-dispatch.daily`                                        | Mini | daily 05:30 WITA                                                       | com.nuzantara.chore-dispatch.daily — receptor-live PART B, chore queue for cheap seats (2026-08-27).                                                             |
| `com.nuzantara.kb-probe-history.6h`                                         | Pro  | daily 00:05 WITA; daily 06:05 WITA; daily 12:05 WITA; daily 18:05 WITA | pro.kb_probe_history — kb-current-live campaign (2026-08-25/26).                                                                                                 |
| `com.nuzantara.nlm-drive-backup.daily`                                      | Mini | daily 03:00 WITA                                                       | com.nuzantara.nlm-drive-backup.daily Daily NLM → Drive 30TB backup, fires at 03:00 local time (WITA on Pro).                                                     |
| `com.nuzantara.queue-shepherd` (`com.nuzantara.queue-shepherd.10min.plist`) | Pro  | every 10m                                                              | queue_shepherd.py — Merge-OS v3 Codex F7 disposition: budgeted auto-rearm + stale-run janitor.                                                                   |
| `com.nuzantara.seat-mix.daily`                                              | Pro  | daily 06:30 WITA                                                       | A7/R12 daily seat-mix telemetry.                                                                                                                                 |
| `com.nuzantara.wa-mirror-freshness-liveness`                                | Mini | every 15m                                                              | com.nuzantara.wa-mirror-freshness-liveness — W0 read-only freshness guardian for the WhatsApp mirror (2026-08-15).                                               |
| `com.nuzantara.wal-continuity-probe.daily`                                  | Pro  | daily 05:00 WITA                                                       | Nightly WAL-continuity probe (Pro).                                                                                                                              |
| `com.nuzantara.wr2-damar-publish-consumer`                                  | Pro  | every 5m                                                               | Poll every 5 min.                                                                                                                                                |
| `com.nuzantara.fw-guard`                                                    | Mini | every 5m                                                               | runs `nuzantara-fw-guard.sh`                                                                                                                                     |

---

### GitHub Actions scheduled workflows (repo-canon)

The workflows below carry a `schedule:` trigger in `.github/workflows/`;
cron times are UTC (WITA = UTC+8). Derived from `.github/workflows/*.yml`
on every run — never hand-edit this table, edit the workflow instead.

| Workflow                                 | Name                                                    | Cron (UTC)            | Purpose                                                                                                                                                          |
| ---------------------------------------- | ------------------------------------------------------- | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `codex-autofix-reaper.yml`               | cron - codex autofix reaper (autonomous reap every 48h) | 0 22 */2 * *          | Garbage-collects the Codex auto-fix backlog (superscar #2: the nightly autofix generator opens a PR + branch per failing CI run and never reaps them — they a... |
| `craft-instruments-daily.yml`            | Craft instruments (advisory)                            | 17 21 * * *           | Arms two advisory instruments that previously had no executor anywhere in the fleet: `scripts/council_yield_report.py` and `scripts/correction_tax.py`.          |
| `cron-cert-monitor.yml`                  | cron - cert monitor (daily 07:00 WITA)                  | 0 23 * * *            | Migrated from Pro crontab `0 7 * * * cert-monitor.sh` (2026-04-26).                                                                                              |
| `cron-drive-poll.yml`                    | cron - drive poll monitor                               | */15 * * * *          | The Drive poll itself is owned by the Fly `drive` process group.                                                                                                 |
| `cron-fly-cost-alert.yml`                | cron - fly cost alert (weekly Mon 09:00 WITA)           | 0 1 * * 1             | Migrated from Pro crontab `0 9 * * 1 fly-cost-alert.sh` (2026-04-26).                                                                                            |
| `cron-fly-restart-detector.yml`          | cron - fly restart loop detector (every 15 min)         | */15 * * * *          | Migrated from Pro crontab `*/15 * * * * fly-restart-loop-detector.sh` (2026-04-26).                                                                              |
| `cron-fly-watcher.yml`                   | cron - fly watcher (every 15 min)                       | */15 * * * *          | Migrated from Pro crontab `*/15 * * * * cron-agent-python/run.sh fly-watcher` (2026-04-26).                                                                      |
| `cron-kg-staging-promotion.yml`          | Cron — KG staging promotion                             | 23 5,11,17,23 * * *   | Campaign S5 (2026-07-18): arms the second half of the KG quarantine pattern (migration_077 staging tables).                                                      |
| `cron-llm-credit-sentinel.yml`           | cron - LLM credit sentinel (every 20 min)               | */20 * * * *          | Born from the 2026-07-28 outage: the Gemini prepay hit zero and the bot was mute for ~34 hours before a human noticed, with the whole team testing against it.   |
| `cron-notifiers-all.yml`                 | cron - notifiers all (daily 00:00 WITA)                 | 0 16 * * *            | cron - notifiers all (daily 00:00 WITA)                                                                                                                          |
| `cron-notifiers-compliance-forecast.yml` | cron - notifiers compliance-forecast (daily 06:30 WITA) | 30 22 * * *           | cron - notifiers compliance-forecast (daily 06:30 WITA)                                                                                                          |
| `cron-notifiers-e33-guarantee-scan.yml`  | cron - notifiers e33-guarantee-scan (daily 07:10 WITA)  | 10 23 * * *           | cron - notifiers e33-guarantee-scan (daily 07:10 WITA)                                                                                                           |
| `cron-notifiers-email-health.yml`        | cron - notifiers email-health (every 30 min)            | */30 * * * *          | cron - notifiers email-health (every 30 min)                                                                                                                     |
| `cron-notifiers-lkpm-deadlines.yml`      | cron - notifiers lkpm-deadlines (daily 23:00 WITA)      | 0 15 * * *            | cron - notifiers lkpm-deadlines (daily 23:00 WITA)                                                                                                               |
| `cron-notifiers-welcome-pending.yml`     | cron - notifiers welcome-pending (every 15 min)         | */15 * * * *          | cron - notifiers welcome-pending (every 15 min)                                                                                                                  |
| `cron-practice-auto-create.yml`          | cron - practice auto-create (daily 07:30 WITA)          | 30 23 * * *           | cron - practice auto-create (daily 07:30 WITA)                                                                                                                   |
| `cron-sentry-quota-check.yml`            | cron - sentry quota check (daily 09:00 WITA)            | 0 1 * * *             | Migrated from Pro LaunchAgent / sentry-quota-check.sh (2026-04-26).                                                                                              |
| `docs-inventory-refresh-liveness.yml`    | cron - docs-inventory-refresh liveness (every 6h)       | 17 */6 * * *          | Out-of-band check for the scheduled artifact publisher.                                                                                                          |
| `docs-inventory-refresh.yml`             | Docs Inventory Refresh                                  | 0 19 * * *;0 7 * * *  | Scheduled publication of volatile documentation state.                                                                                                           |
| `fly-secrets-check.yml`                  | Fly.io Secrets Health Check                             | 0 9 * * 1             | Weekly check that FLY_API_TOKEN is still valid (#2 S06 self-healing) Deadman's switch: if THIS workflow fails (token expired), GitHub sends failure email to...  |
| `frontend-live-sentinel.yml`             | Frontend Live Sentinel                                  | */30 * * * *          | 2026-07-27: balizero.com served 13-hour-old code while 25 commits landed on main.                                                                                |
| `main-push-failure-watch.yml`            | Main-push Failure Watch                                 | */15 * * * *          | Task #23 (superscar #2, "Esiste ≠ Armato" — cicatrix-superscar.md #2).                                                                                           |
| `merge-queue-watch.yml`                  | merge-queue-watch                                       | */10 * * * *          | poll-based watcher for merge-queue ejections and automerge-armed-but-stuck PRs.                                                                                  |
| `pr-size-taxonomy.yml`                   | PR size taxonomy (advisory)                             | 0 20 * * *            | L04-PR3 — report-only, prints to the job summary.                                                                                                                |
| `restore-drill.yml`                      | Monthly PG Restore Drill                                | 0 4 1 * *             | Proves that the daily pg_dump → Tigris pipeline is actually restorable.                                                                                          |
| `scripts-tests-sweep.yml`                | scripts/tests/ sweep (report-only)                      | 15 2 * * *            | STAGE 1 of the fix in task #16 / cicatrix superscar #2 (exists != armed) applied to the immune system's own test suite.                                          |
| `security.yml`                           | Security Scanning                                       | 17 19 * * *;0 0 * * 0 | Daily backstop, 19:17 UTC = 03:17 WITA next day.                                                                                                                 |
| `tests.yml`                              | Tests & Coverage                                        | 17 */2 * * *          | Task #37 (2026-07-26).                                                                                                                                           |

---

## System Health Summary

| Metric                | Value   |
| --------------------- | ------- |
| Total jobs            | **268** |
| ✅ Healthy            | **175** |
| 🔄 Running (daemons)  | **56**  |
| ⚠️ Warning/Skip/NoLog | **13**  |
| ❌ Failed             | **16**  |

---

## Sentinel Overview

> Ultimo aggiornamento sentinel: `2026-09-12T15:06:08Z`

| Metrica                   | Valore         |
| ------------------------- | -------------- |
| Circuit OPEN              | **0**          |
| Circuit TERMINAL          | **147**        |
| DLQ entries totali        | **0**          |
| DLQ phase distribution    | `TERMINAL=147` |
| Job critici (in registry) | **0**          |

---

## Pro (nuzantara@Nuzantara — M4 Pro 48GB)

### LaunchAgents

| Label                                           | Status                 | Autonomy   | Exit | Circuit | Scope | Critical |
| ----------------------------------------------- | ---------------------- | ---------- | ---- | ------- | ----- | -------- |
| `ai.openclaw.gateway`                           | 🔄 Running (PID=51065) | —          | 0    | —       | —     |          |
| `ai.openclaw.node`                              | 🔄 Running (PID=50966) | —          | -15  | —       | —     |          |
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
| `com.balizero.cron-log-sentinel`                | 🔄 Running (PID=1410)  | —          | 0    | —       | —     |          |
| `com.balizero.curiosity.weekly`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.drive-intake-drain`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.dropbox-intake`                   | 🔄 Running (PID=85437) | —          | 0    | —       | —     |          |
| `com.balizero.fly-cost-alert.weekly`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.guardrails-daemon`                | 🔄 Running (PID=82832) | —          | -15  | —       | —     |          |
| `com.balizero.intel-dedup-gateway`              | 🔄 Running (PID=9964)  | —          | 1    | —       | —     |          |
| `com.balizero.intel-lake-nb-pusher.15min`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake-router.5min`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake.e2e-probe.6h`          | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.balizero.intel-lake.outbox-drain.minute`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-lake.shadow-validate.6h`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel-radar-daily-digest`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.intel.nightly`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.meta-dispatcher`                  | 🔄 Running (PID=9950)  | —          | 1    | —       | —     |          |
| `com.balizero.modus.autoloop.nightly`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.mos-plus.compression`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.mos-plus.qdrant-indexer`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nb-curator.daily`                 | ❌ FAILED (exit=2)     | —          | 2    | —       | —     |          |
| `com.balizero.nexus-session-retention.daily`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nlm-bridge`                       | 🔄 Running (PID=1429)  | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara-drive-sync`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara.disk-watchdog`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.nuzantara.log-size-watchdog`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.observatory`                      | 🔄 Running (PID=9963)  | —          | 1    | —       | —     |          |
| `com.balizero.observatory-export`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.observatory-server`               | 🔄 Running (PID=1470)  | —          | 0    | —       | —     |          |
| `com.balizero.post-publish-poller`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.post-publish-webhook`             | 🔄 Running (PID=1449)  | —          | 0    | —       | —     |          |
| `com.balizero.profile-monitor-wrapper`          | 🔄 Running (PID=1476)  | —          | 0    | —       | —     |          |
| `com.balizero.qdrant.daemon`                    | 🔄 Running (PID=1413)  | —          | 0    | —       | —     |          |
| `com.balizero.regulatory-watcher.daily`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.renewal-alerts`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.research-sentinel`                | 🔄 Running (PID=9967)  | —          | 1    | —       | —     |          |
| `com.balizero.s7-yield.weekly`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.seo-cell.28d-check`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.seo-cell.daily`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.setup-team.daily`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.sota.m13-checkpoint`              | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.sota.m13-collect`                 | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.sota.m13-monthly`                 | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.sota.m13-weekly`                  | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.translate.hourly`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-dashboard-m1`                  | 🔄 Running (PID=1473)  | —          | 0    | —       | —     |          |
| `com.balizero.wa-lid-refresh`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-meta-inbox`                    | 🔄 Running (PID=17263) | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-attention-classifier`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-attention-digest`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-attention-realtime`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-auto-promote`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-auto-promote-selfheal`  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-launcher`               | 🔄 Running (PID=1414)  | —          | 0    | —       | —     |          |
| `com.balizero.wa-mirror-strategic-recap`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wa-team-metrics-rollup`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr2.pg-proxy`                     | 🔄 Running (PID=1493)  | —          | 0    | —       | —     |          |
| `com.balizero.wr2control`                       | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.balizero.wr3.editorial-bench.monthly`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.reflexion.weekly`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.balizero.wr3.supervisor`                   | 🔄 Running (PID=85542) | —          | 0    | —       | —     |          |
| `com.balizero.zoho-mail-loop.daily`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.cell.metabolic-rollup`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.cell.organism`                             | 🔄 Running (PID=3137)  | —          | 1    | —       | —     |          |
| `com.matagaruda.archiver.hourly`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.bridge.adaptive`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.classifier.adaptive`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.consumer-lag.check`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.daily-briefing`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.gap.consumer`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.intel-bridge.daily`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.invalidation-sweep`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.kg-linker`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.kg-query-api`                   | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.matagaruda.kita-feed.daily`                | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.matagaruda.ner.adaptive`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.nlm-expander.weekly`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.nlm-feeder-stream.hourly`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.nlm-rollup.daily`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.pel-cleaner.weekly`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.pipeline-health.hourly`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.plist-watchdog.hourly`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.public-channel`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.reg-alert.30min`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.sentinel.hourly`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.unmapped-audit.daily`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.watcher.daily`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.weekly-digest`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.matagaruda.wr-topic`                       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.agent-worktree-cleanup.daily`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.anti-stall-caffeinate`           | 🔄 Running (PID=1441)  | —          | 0    | —       | —     |          |
| `com.nuzantara.archive-empty-sessions.daily`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.army-jules-dispatch`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.army-jules-harvest`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.army-spark`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-server`                  | 🔄 Running (PID=1403)  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-telegram`                | 🔄 Running (PID=1424)  | —          | 0    | —       | —     |          |
| `com.nuzantara.automap-watchdog`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.automations-reference`           | 🔄 Running (PID=5281)  | —          | 0    | —       | —     |          |
| `com.nuzantara.branch-cleanup.weekly`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory`                | 🔄 Running (PID=1442)  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory-prune`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cell-observatory-selfcheck`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.chatgpt-marketing-tunnel`        | 🔄 Running (PID=21082) | —          | 0    | —       | —     |          |
| `com.nuzantara.chronic-failure-digest.weekly`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.claude-config-sync`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.claude-max-usage-watcher`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cloudflared-intake-review`       | 🔄 Running (PID=1479)  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-autofix-ci`                | ✅ OK                  | ⚠️ SKIPPED | 0    | —       | —     |          |
| `com.nuzantara.codex-coverage-improver`         | ❌ FAILED (exit=1)     | ⛔ BLOCKED | 1    | —       | —     |          |
| `com.nuzantara.codex-openclaw-analysis`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.codex-research-actor`            | ✅ OK                  | ✅ OK/idle | 0    | —       | —     |          |
| `com.nuzantara.cost-advisor-daily-cap`          | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.nuzantara.cost-advisor-weekly`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-breaker`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-breaker-deadman`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cost-ledger-export`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.cpu-monitor`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.curiosity-loop.daily`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.daily-indexing-sweep`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.disk-monitor`                    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.dlq-autopilot`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.federation-alert-dispatcher`     | 🔄 Running (PID=9952)  | —          | 1    | —       | —     |          |
| `com.nuzantara.fly-logs-accumulator`            | 🔄 Running (PID=1495)  | —          | 0    | —       | —     |          |
| `com.nuzantara.fly-restart-loop-detector`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.gh-auth-healthcheck.weekly`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.git-pull-main.15min`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.healer-pro.6h`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.heartbeat-bridge`                | 🔄 Running (PID=1399)  | —          | 0    | —       | —     |          |
| `com.nuzantara.intake-blob-retention`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.intake-gate-count-pusher`        | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.intake-health-report`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.intake-review-reader`            | 🔄 Running (PID=1445)  | —          | 0    | —       | —     |          |
| `com.nuzantara.intake-review-reader-liveness`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.intake-worker`                   | 🔄 Running (PID=18151) | —          | 0    | —       | —     |          |
| `com.nuzantara.iqoo-radar-relay`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.kbli-surface-conformance.daily`  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.launchagent-state-bridge`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.launchd-env-loader`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.launchd-liveness-detector.daily` | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.lead-intent-matcher`             | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.llm-burn-alarm`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.local-livekit-server`            | 🔄 Running (PID=1428)  | —          | 0    | —       | —     |          |
| `com.nuzantara.local-livekit-worker`            | 🔄 Running (PID=1471)  | —          | 0    | —       | —     |          |
| `com.nuzantara.log-rotate.daily`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.login-healthcheck`               | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.machine-boot-report`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.mcp-integrity`                   | ❌ FAILED (exit=2)     | —          | 2    | —       | —     |          |
| `com.nuzantara.memory-sync-bidirectional`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.merge-train`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.nb-intel-delta-watcher.hourly`   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.nb-mitochondrial-monitor.daily`  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.ollama`                          | 🔄 Running (PID=1432)  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-children-watchdog`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-logrotate`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw-whatsapp-bridge`        | 🔄 Running (PID=50976) | —          | -15  | —       | —     |          |
| `com.nuzantara.openclaw-whatsapp-tunnel`        | 🔄 Running (PID=50977) | —          | 0    | —       | —     |          |
| `com.nuzantara.openclaw.guardian-board`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.control-panel`          | 🔄 Running (PID=1458)  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.scheduled-tick`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.organism.supervisor`             | 🔄 Running (PID=82308) | —          | 0    | —       | —     |          |
| `com.nuzantara.outbox-prune.daily`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.outbox-prune.weekly`             | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.pg-organism-bridge`              | 🔄 Running (PID=1438)  | —          | 0    | —       | —     |          |
| `com.nuzantara.pg-organism-bridge-watchdog`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.plist-snapshot.daily`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.price-review-sentinel`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.prime-tunnel`                    | 🔄 Running (PID=1400)  | —          | 0    | —       | —     |          |
| `com.nuzantara.pro-fleet-watch`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.queue-baseline`                  | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.queue-shepherd.10min`            | ⚠️ NOT LOADED          | —          | ?    | —       | —     |          |
| `com.nuzantara.redis-liveness`                  | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.repomap.15min`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.restic-backup-pro`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.restic-prune-pro`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.review-gate`                     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.runtime-reconcile`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.seat-usage`                      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.secrets-permissions-audit`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.secrets-sync-mini`               | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel`                        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel-aggregate`              | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.sentinel-meta-watchdog`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.session-orphan-reaper`           | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.skills-bridge-consumer`          | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.suite-growth-probe`              | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.supervisor-liveness-watchdog`    | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.tg-digest-flush`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.tokenaudit.daily`                | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.vector-reindex-check`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.verify-connectome`               | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.verify-the-verifiers`            | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.visa-freshness-sentinel`         | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.vision-cinema`                   | 🔄 Running (PID=1420)  | —          | 0    | —       | —     |          |
| `com.nuzantara.vision-deck`                     | 🔄 Running (PID=1457)  | —          | 0    | —       | —     |          |
| `com.nuzantara.vision-term`                     | 🔄 Running (PID=1480)  | —          | 0    | —       | —     |          |
| `com.nuzantara.wa-bot-throughput-sentinel`      | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.wa-media-pull`                   | ❌ FAILED (exit=1)     | —          | 1    | —       | —     |          |
| `com.nuzantara.wa-mirror-intake-sweeper`        | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.wa-mirror-session-janitor`       | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.web-lead-funnel`                 | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.worktree-gc-universal.daily`     | ✅ OK                  | —          | 0    | —       | —     |          |
| `com.nuzantara.zombie-hunter`                   | ✅ OK                  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.colima`                          | 🔄 Running (PID=1472)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.postgresql@17`                   | 🔄 Running (PID=1478)  | —          | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                           | 🔄 Running (PID=3113)  | —          | 1    | —       | —     |          |
| `homebrew.mxcl.syncthing`                       | 🔄 Running (PID=1477)  | —          | 0    | —       | —     |          |

### Cron Jobs

| Job                   | Schedule                  | Last Run         | Status    | Circuit      | Scope | Critical | Notes                                              |
| --------------------- | ------------------------- | ---------------- | --------- | ------------ | ----- | -------- | -------------------------------------------------- |
| `cache_cleanup`       | 1st+15th 3:30 UTC         | 2026-09-01 03:30 | ✅ OK     | ✅ CLOSED/T0 | LOCAL |          | Tue Sep 1 03:30:50 WITA 2026: cache cleanup done   |
| `cron_agent`          | Sun 8:00 UTC (+5 more)    | 2026-09-06 08:00 | ✅ OK     | —            | —     |          | [2026-09-06T08:00:02] [cell-weekly-report] OK dura |
| `cron_runner`         | every 5m (+22 more)       | 2026-09-06 02:00 | ❌ FAIL   | —            | —     |          | [2026-09-06 02:00:01] ⚠️ KG builder failed (HTTP 4 |
| `cron_state`          | every 5m (+22 more)       | 2026-09-12 23:15 | ? check   | —            | —     |          | [openclaw-bridge] Cannot read jobs.json: [Errno 2] |
| `cron_wrapper`        | daily 21:00 UTC (+5 more) |                  |           | —            | —     |          |                                                    |
| `fly_cost_alert`      | Mon 9:00 UTC              | 2026-09-07 09:00 | ? check   | ✅ CLOSED/T0 | LOCAL |          | [2026-09-07 09:00:01] Cost within budget ✅        |
| `ollama_warm_pin`     | Sun 5:00 UTC              | 2026-09-06 05:00 | ✅ OK     | —            | —     |          | [2026-09-06T05:00:21] Warm-pin complete on Nuzanta |
| `peraturan_ingestion` | 6 21:30 UTC               |                  | ⚠️ NO LOG | —            | —     |          |                                                    |
| `pro_heartbeat`       | 0 * * * *                 |                  |           | ✅ CLOSED/T0 | LOCAL |          |                                                    |
| `run`                 | every 15m (+14 more)      | 2026-09-12 23:15 | ❌ FAIL   | —            | —     |          | 2026-09-12 23:15:01 [info ] check_now_done         |

---

## Mini (nuzantara@mini-pro2 — M4 Pro 24GB, H24)

### LaunchAgents

| Label                                        | Status                | Autonomy | Exit | Circuit | Scope | Critical |
| -------------------------------------------- | --------------------- | -------- | ---- | ------- | ----- | -------- |
| `com.balizero.mlx-server`                    | 🔄 Running (PID=1415) | —        | 0    | —       | —     |          |
| `com.balizero.wa-mirror`                     | ⚠️ NOT LOADED         | —        | ?    | —       | —     |          |
| `com.balizero.wr2.warroom-sync`              | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.balizero.wr2control`                    | 🔄 Running (PID=1419) | —        | 0    | —       | —     |          |
| `com.balizero.zerodesign.studio`             | 🔄 Running (PID=1429) | —        | 0    | —       | —     |          |
| `com.matagaruda.intel-bridge.daily`          | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.matagaruda.kg-query-api`                | 🔄 Running (PID=1423) | —        | 0    | —       | —     |          |
| `com.matagaruda.normalizer.hourly`           | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.matagaruda.sentinel.daily`              | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.agent-worktree-cleanup.daily` | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.fleet-watch`                  | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.git-pull-main.5min`           | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.healer.4h`                    | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.heartbeat-watchdog.daily`     | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.imigrasi-mirror.daily`        | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.imigrasi-mirror.healthcheck`  | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.imigrasi-mirror.weekly`       | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.journey-sentinel`             | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.kc-watchdog`                  | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.local-livekit-server`         | 🔄 Running (PID=1416) | —        | 0    | —       | —     |          |
| `com.nuzantara.local-livekit-worker`         | 🔄 Running (PID=1427) | —        | 0    | —       | —     |          |
| `com.nuzantara.log-prune.daily`              | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.mini-iqoo-radar-relay`        | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.mini.tg-digest-flush`         | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.ollama-warm-pin`              | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.overlap-detector.daily`       | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.seat-usage`                   | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.secrets-perms-sweep`          | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.vercel-autopromote`           | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.visa-oracle-retention.15min`  | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.voa-deadman`                  | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.voa-probe`                    | ✅ OK                 | —        | 0    | —       | —     |          |
| `com.nuzantara.worktree-gc-universal.daily`  | ✅ OK                 | —        | 0    | —       | —     |          |
| `homebrew.mxcl.postgresql@17`                | 🔄 Running (PID=1430) | —        | 0    | —       | —     |          |
| `homebrew.mxcl.redis`                        | 🔄 Running (PID=1417) | —        | 0    | —       | —     |          |

### Cron Jobs

| Job                      | Schedule                 | Last Run         | Status  | Circuit | Scope | Critical | Notes                                              |
| ------------------------ | ------------------------ | ---------------- | ------- | ------- | ----- | -------- | -------------------------------------------------- |
| `Tailscale`              | * * * * *                |                  |         | —       | —     |          |                                                    |
| `crm_kg_build_mediated`  | every 6h (:0)            | 2026-09-12 18:00 |         | —       | —     |          |                                                    |
| `crm_kg_garbage_collect` | daily 3:00 UTC           | 2026-09-12 03:00 |         | —       | —     |          |                                                    |
| `cron_runner`            | daily 9:15 UTC (+2 more) | 2026-09-12 09:15 |         | —       | —     |          |                                                    |
| `drive_poll`             | every 5m                 | 2026-09-12 23:15 | ❌ FAIL | —       | —     |          | [2026-09-12 23:15:02] ⚠️ Drive poll failed (HTTP 4 |

---

_Generated by `scripts/generate_automations_reference.py` — 2026-09-12 15:15 UTC_
