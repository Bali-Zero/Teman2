# NUZANTARA — AUTOMATIONS REFERENCE

> **Auto-generated from live system state** — do not edit manually.
> Repo-canon additions below are maintained by hand (2026-09-11 bonifica) and are excluded from the generated totals.
> Generated: 2026-07-25 15:15 UTC
> Source: `crontab -l` (Pro+Mini) + `launchctl list` (Pro+Mini) + log health + `job_registry.json` + `sentinel_status.json` + `circuit_breakers.json`

---

## Repo-canon additions pending live snapshot

These entries are committed as repo-canon LaunchAgents but are not counted in
the generated live totals above until installed on Pro and included in the next
automation snapshot.

| Label                                          | Host            | Schedule                                                             | Purpose                                                                                                                                                                                                                                               |
| ---------------------------------------------- | --------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `com.balizero.magazine.morning`                | Pro             | 08:15 WITA                                                           | Compose/publish the internal Bali Zero Magazine morning issue after the Regulatory Watcher window; target readable by 08:30 WITA.                                                                                                                     |
| `com.balizero.magazine.breaking`               | Pro             | 600s                                                                 | Drain qualified Breaking magazine candidates within the 10-minute objective.                                                                                                                                                                          |
| `com.balizero.auth-sentinel.daily`             | M5              | every 21600s                                                         | TO VERIFY — runs /Users/balizero/.nuzantara-cron/auth_sentinel_cron.sh                                                                                                                                                                                |
| `com.balizero.indexing-sweep.daily`            | Pro/Mini        | 00:30 daily (WITA, unverified TZ)                                    | Daily Indexing Sweep Cron Wrapper — submits unindexed articles + KBLI pages to Google Indexing API (daily quota-based).                                                                                                                               |
| `com.balizero.wa-codex-broker`                 | TO VERIFY       | keepalive daemon                                                     | TO VERIFY — runs /usr/local/libexec/wa-codex-broker-wrapper.sh                                                                                                                                                                                        |
| `com.balizero.wa-codex-seat-probe`             | TO VERIFY       | every 21600s                                                         | TO VERIFY — runs /usr/local/libexec/wa-codex-seat-probe-wrapper.sh                                                                                                                                                                                    |
| `com.balizero.zoho-mail-loop.daily`            | Pro/Mini        | 07:30 daily (WITA, unverified TZ)                                    | zoho-mail-loop.sh — daily wrapper for the Zoho mail loop.                                                                                                                                                                                             |
| `com.matagaruda.archiver.hourly`               | Pro/Mini        | every 3600s                                                          | Mata Garuda — Archiver Worker.                                                                                                                                                                                                                        |
| `com.matagaruda.classifier.adaptive`           | Pro/Mini        | every 300s                                                           | Mata Garuda — Classifier Worker runner (Layer 2 enrichment).                                                                                                                                                                                          |
| `com.matagaruda.consumer-lag.check`            | Pro/Mini        | every 1800s                                                          | TO VERIFY — runs /Users/nuzantara/scripts/matagaruda-consumer-lag-run.sh                                                                                                                                                                              |
| `com.matagaruda.council-weekly`                | TO VERIFY       | 10:00 Sun daily (WITA, unverified TZ)                                | Council Weekly — SYMBIOSIS Pillar 4 deliberation cron wrapper.                                                                                                                                                                                        |
| `com.matagaruda.daily-briefing`                | Pro/Mini        | 07:00 daily (WITA, unverified TZ)                                    | Mata Garuda — Daily Briefing runner (LaunchAgent-invoked).                                                                                                                                                                                            |
| `com.matagaruda.intel-bridge.daily`            | Pro/Mini        | 06:30 daily (WITA, unverified TZ)                                    | Mata Garuda — Intel Scraper Bridge runner.                                                                                                                                                                                                            |
| `com.matagaruda.invalidation-sweep`            | Pro/Mini        | 04:13 daily (WITA, unverified TZ)                                    | TO VERIFY — runs /Users/nuzantara/scripts/mata_garuda/mata_garuda_invalidation_sweep_wrapper.sh                                                                                                                                                       |
| `com.matagaruda.kg-linker`                     | Pro/Mini        | every 3600s                                                          | Mata Garuda — KG Linker runner (Layer 3 Nexus).                                                                                                                                                                                                       |
| `com.matagaruda.kg-query-api`                  | Pro/Mini        | keepalive daemon                                                     | TO VERIFY — runs /Users/nuzantara/scripts/mini-infra/kg-query-api-wrapper.sh                                                                                                                                                                          |
| `com.matagaruda.kita-feed`                     | Pro/Mini        | 05:00 daily (WITA, unverified TZ)                                    | Mata Garuda — Kita Feed Generator runner.                                                                                                                                                                                                             |
| `com.matagaruda.ner.adaptive`                  | Pro/Mini        | every 300s                                                           | Mata Garuda — NER Worker runner (Layer 2.5 Pre-KG).                                                                                                                                                                                                   |
| `com.matagaruda.nlm-expander.weekly`           | Pro/Mini        | 09:00 Sun daily (WITA, unverified TZ)                                | Mata Garuda — NLM Expander runner (LaunchAgent-invoked, Sun 09:00 WITA).                                                                                                                                                                              |
| `com.matagaruda.nlm-feeder-stream.hourly`      | Pro/Mini        | every 3600s                                                          | Mata Garuda — NLM Feeder Stream runner (alerts + enriched).                                                                                                                                                                                           |
| `com.matagaruda.nlm-rollup.daily`              | Pro/Mini        | 23:30 daily (WITA, unverified TZ)                                    | Mata Garuda — NLM Daily Rollup (summarize-then-store, council fix #5).                                                                                                                                                                                |
| `com.matagaruda.pel-cleaner.weekly`            | Pro/Mini        | 04:00 Sun daily (WITA, unverified TZ)                                | W12+W13 PEL-cleaner: systematic recovery from PEL accumulation pattern.                                                                                                                                                                               |
| `com.matagaruda.pipeline-health.hourly`        | Pro/Mini        | every 3600s                                                          | Mata Garuda — pipeline health monitor (real operativity, not exit-0).                                                                                                                                                                                 |
| `com.matagaruda.plist-watchdog.hourly`         | Pro/Mini        | every 3600s                                                          | Mata Garuda plist auto-heal watchdog — reinstalls a VANISHED launchd job.                                                                                                                                                                             |
| `com.matagaruda.public-channel`                | Pro/Mini        | 02:15, 06:15, 10:15, 14:15, 18:15, 22:15 daily (WITA, unverified TZ) | Mata Garuda — Public Channel runner.                                                                                                                                                                                                                  |
| `com.matagaruda.reg-alert.30min`               | Pro/Mini        | every 1800s                                                          | Mata Garuda — Regulation Alert runner (LaunchAgent-invoked, every 30m).                                                                                                                                                                               |
| `com.matagaruda.sentinel.hourly`               | Pro/Mini        | every 3600s                                                          | Sentinel Cell hourly runner — single-pulse driver for cron / LaunchAgent.                                                                                                                                                                             |
| `com.matagaruda.unmapped-audit.daily`          | Pro/Mini        | 09:00 daily (WITA, unverified TZ)                                    | Mata-Garuda C.2 — Daily unmapped gap audit.                                                                                                                                                                                                           |
| `com.matagaruda.weekly-digest`                 | Pro/Mini        | 08:00 Sun daily (WITA, unverified TZ)                                | Mata Garuda — Weekly Digest runner (LaunchAgent-invoked, Sun 08:00 WITA).                                                                                                                                                                             |
| `com.matagaruda.wr-topic`                      | Pro/Mini        | 08:00 Wed, 08:00 Sat daily (WITA, unverified TZ)                     | Mata Garuda — WR Topic Agent runner (Wed/Sat 08:00 WITA).                                                                                                                                                                                             |
| `com.nuzantara.army-jules-dispatch`            | Pro/Mini        | 09:00 daily (WITA, unverified TZ)                                    | jules_lane_dispatch_wrapper.sh — thin bash shim so cron-runner.sh (execs `/bin/bash "$SCRIPT"`) can invoke the Python lane (jules_lane.py).                                                                                                           |
| `com.nuzantara.army-jules-harvest`             | Pro/Mini        | every 10800s                                                         | jules_lane_harvest_wrapper.sh — thin bash shim so cron-runner.sh (execs `/bin/bash "$SCRIPT"`) can invoke the Python lane (jules_lane.py).                                                                                                            |
| `com.nuzantara.army-spark`                     | Pro/Mini        | every 7200s                                                          | army.spark_lane — Armata H24 lane 1: standing read-only analysis on the gpt-5.3-codex-spark weekly bucket (measured idle 2026-08-14, separate bucket from the primary codex quota — see research/operations/2026-08-14-armata-h24-standing-lanes.md). |
| `com.nuzantara.chore-dispatch.daily`           | Pro/Mini        | 05:30 daily (WITA, unverified TZ)                                    | chore_dispatch_wrapper.sh — thin bash shim so cron-runner.sh (execs `/bin/bash "$SCRIPT"`) can invoke the Python chore dispatcher (scripts/chore_dispatch.py).                                                                                        |
| `com.nuzantara.escalations-digest.weekly`      | Pro/Mini        | 09:07 Sun daily (WITA, unverified TZ)                                | S3 / W55: weekly cron wrapper for the suppressed-alerts digest.                                                                                                                                                                                       |
| `com.nuzantara.escalations-prune`              | Pro/Mini        | 03:00 daily (WITA, unverified TZ)                                    | P1-8: daily cron wrapper for escalations SQLite mirror.                                                                                                                                                                                               |
| `com.nuzantara.fw-guard`                       | Mini (dir hint) | every 300s                                                           | TO VERIFY — runs /usr/local/bin/nuzantara-fw-guard.sh                                                                                                                                                                                                 |
| `com.nuzantara.intake-health-report`           | Pro/Mini        | 07:30 daily (WITA, unverified TZ)                                    | intake_health_report_run.sh — venv-python launcher for scripts/intake_health_report.py.                                                                                                                                                               |
| `com.nuzantara.iqoo-radar-relay`               | Pro/Mini        | every 60s                                                            | TO VERIFY — runs /Users/nuzantara/scripts/pro-iqoo-radar-relay.sh                                                                                                                                                                                     |
| `com.nuzantara.journey-sentinel`               | TO VERIFY       | every 3600s                                                          | journey_sentinel.sh — cron wrapper for the L11 production journey sentinels (apps/mouth/e2e/production/*.spec.ts, run via apps/mouth/playwright.production.config.ts against REAL production).                                                        |
| `com.nuzantara.kb-probe-history.6h`            | Pro/Mini        | 00:05, 06:05, 12:05, 18:05 daily (WITA, unverified TZ)               | TO VERIFY — runs /Users/nuzantara/scripts/pro-kb-probe-history.sh                                                                                                                                                                                     |
| `com.nuzantara.kbli-surface-conformance.daily` | Pro/Mini        | 08:20 daily (WITA, unverified TZ)                                    | Read-only semantic adapter for scripts/kbli_filiera/kbli_surface_conformance.py.                                                                                                                                                                      |
| `com.nuzantara.kc-watchdog`                    | Pro/Mini        | every 15s                                                            | TO VERIFY — runs /Users/nuzantara/scripts/kc-watchdog.sh                                                                                                                                                                                              |
| `com.nuzantara.llm-burn-alarm`                 | Pro/Mini        | every 3600s                                                          | TO VERIFY — runs /Users/nuzantara/scripts/pro-llm-burn-alarm.sh                                                                                                                                                                                       |
| `com.nuzantara.mini-iqoo-radar-relay`          | Pro/Mini        | every 60s                                                            | TO VERIFY — runs /Users/nuzantara/scripts/mini-iqoo-radar-relay.sh                                                                                                                                                                                    |
| `com.nuzantara.nlm-drive-backup.daily`         | Pro/Mini        | 03:00 daily (WITA, unverified TZ)                                    | Daily NLM → Drive backup — Week 0 Phase D foundation.                                                                                                                                                                                                 |
| `com.nuzantara.price-review-sentinel`          | Pro/Mini        | every 86400s                                                         | TO VERIFY — runs /Users/nuzantara/scripts/pro-price-review-sentinel.sh                                                                                                                                                                                |
| `com.nuzantara.pro-fleet-watch`                | Pro/Mini        | every 900s                                                           | TO VERIFY — runs /Users/nuzantara/scripts/pro-fleet-watch.sh                                                                                                                                                                                          |
| `com.nuzantara.queue-shepherd`                 | Pro/Mini        | every 600s                                                           | queue_shepherd.py — Merge-OS v3 Codex F7 disposition: budgeted auto-rearm + stale-run janitor.                                                                                                                                                        |
| `com.nuzantara.seat-mix.daily`                 | Pro/Mini        | 06:30 daily (WITA, unverified TZ)                                    | seat_mix_report.py -- A7/R12 daily seat-mix telemetry, joined to PRs.                                                                                                                                                                                 |
| `com.nuzantara.secrets-perms-sweep`            | Pro/Mini        | every 21600s                                                         | TO VERIFY — runs /Users/nuzantara/scripts/mini-secrets-perms-sweep.sh                                                                                                                                                                                 |
| `com.nuzantara.vercel-autopromote`             | Pro/Mini        | every 120s                                                           | TO VERIFY — runs /Users/nuzantara/scripts/mini-vercel-autopromote.sh                                                                                                                                                                                  |
| `com.nuzantara.visa-freshness-sentinel`        | Pro/Mini        | every 21600s                                                         | TO VERIFY — runs /Users/nuzantara/scripts/pro-visa-freshness-sentinel.sh                                                                                                                                                                              |
| `com.nuzantara.voa-deadman`                    | TO VERIFY       | every 300s                                                           | voa-deadman-wrapper.sh — cron wrapper for scripts/probes/voa_deadman.py.                                                                                                                                                                              |
| `com.nuzantara.voa-probe`                      | TO VERIFY       | every 900s                                                           | voa-probe-wrapper.sh — cron wrapper for scripts/probes/voa_journey_probe.mjs.                                                                                                                                                                         |
| `com.nuzantara.wa-bot-throughput-sentinel`     | Pro/Mini        | every 900s                                                           | wa_bot_throughput_sentinel_run.sh — venv-python launcher for scripts/wa_bot_throughput_sentinel.py.                                                                                                                                                   |
| `com.nuzantara.wa-mirror-freshness-liveness`   | Pro/Mini        | every 900s                                                           | wa_mirror_freshness_liveness_run.sh — venv-python launcher for scripts/wa_mirror_freshness_liveness.py.                                                                                                                                               |
| `com.nuzantara.wal-continuity-probe.daily`     | Pro/Mini        | 05:00 daily (WITA, unverified TZ)                                    | TO VERIFY — runs /Users/nuzantara/.nuzantara-cron/wal-continuity-probe.sh                                                                                                                                                                             |
| `com.nuzantara.web-lead-funnel`                | Pro/Mini        | 09:00 Mon daily (WITA, unverified TZ)                                | Web-lead funnel report cron wrapper.                                                                                                                                                                                                                  |
| `com.nuzantara.wr2-damar-publish-consumer`     | Pro/Mini        | every 300s                                                           | WR2 Damar publish consumer — LaunchAgent wrapper (STRATO 2).                                                                                                                                                                                          |

---

### GitHub Actions scheduled workflows (repo-canon)

The workflows below carry a `schedule:` trigger in `.github/workflows/` but were not yet listed in this reference or in `scripts/automation_catalog.json`; cron times are UTC (WITA = UTC+8).

| Workflow                                 | Name                                                    | Cron (UTC)           | Purpose                                                                                                                                                                                                                                        |
| ---------------------------------------- | ------------------------------------------------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `codex-autofix-reaper.yml`               | cron - codex autofix reaper (autonomous reap every 48h) | 0 22 */2 * *         | Garbage-collects the Codex auto-fix backlog (superscar #2): the nightly autofix generator opens a PR + branch per failing CI run and never reaps them, so this reaps eligible PRs/branches autonomously every 48h with a Telegram audit trail. |
| `craft-instruments-daily.yml`            | Craft instruments (advisory)                            | 17 21 * * *          | Arms two previously-unscheduled advisory instruments (`scripts/council_yield_report.py`, `scripts/correction_tax.py`) — schedules them and makes their output readable in the Actions run summary; report-only, not acted upon automatically.  |
| `cron-cert-monitor.yml`                  | cron - cert monitor (daily 07:00 WITA)                  | 0 23 * * *           | Checks SSL cert expiry on 7 balizero.com subdomains + nuzantara-rag.fly.dev; alerts Telegram when a cert is under 30 days from expiry or unreachable.                                                                                          |
| `cron-drive-poll.yml`                    | cron - drive poll monitor                               | */15 * * * *         | Lightweight monitor for the Drive poll owned by the Fly `drive` process group; never runs the poll itself in the HTTP request path.                                                                                                            |
| `cron-fly-cost-alert.yml`                | cron - fly cost alert (weekly Mon 09:00 WITA)           | 0 1 * * 1            | Weekly resource-inventory guard, since Fly.io exposes no billing alert/API; must never report a fabricated $0 when billing data is unavailable.                                                                                                |
| `cron-fly-restart-detector.yml`          | cron - fly restart loop detector (every 15 min)         | */15 * * * *         | Detects Fly machines not in expected state or with unhealthy checks across critical apps; force-starts a machine stuck crashed-stopped and alerts on OOM/restart events.                                                                       |
| `cron-fly-watcher.yml`                   | cron - fly watcher (every 15 min)                       | */15 * * * *         | Snapshot of Fly status for runtime apps still on Fly; alerts if any app has machines not in expected state or with unhealthy checks (vm-pressure check is warning-only).                                                                       |
| `cron-kg-staging-promotion.yml`          | Cron — KG staging promotion                             | 23 5,11,17,23 * * *  | Promotes the KG quarantine's staging tables (migration_077); shadow-first (dry-run by default), chunked short transactions with an advisory-lock singleton.                                                                                    |
| `cron-llm-credit-sentinel.yml`           | cron - LLM credit sentinel (every 20 min)               | */20 * * * *         | Detects a depleted Gemini prepay balance (born from the 2026-07-28 outage where the bot was mute ~34h before anyone noticed); one 9-token check every 20 minutes.                                                                              |
| `cron-notifiers-all.yml`                 | cron - notifiers all (daily 00:00 WITA)                 | 0 16 * * *           | Triggers the backend's `/api/cron/notifiers/all` endpoint daily (00:00 WITA).                                                                                                                                                                  |
| `cron-notifiers-compliance-forecast.yml` | cron - notifiers compliance-forecast (daily 06:30 WITA) | 30 22 * * *          | Inert until `system_settings.compliance_forecast_enabled = "true"` (the endpoint returns `{"status":"disabled"}` otherwise) — the kill switch is the deliberate go-live gesture, not the schedule.                                             |
| `cron-notifiers-e33-guarantee-scan.yml`  | cron - notifiers e33-guarantee-scan (daily 07:10 WITA)  | 10 23 * * *          | The E33 Day-90 guarantee gate: builds the Day 30/60/75 escalation toward the 90-day evidence deadline and annual-maintenance recurrence for every open Second Home case, then hands them to the AlertsEngine.                                  |
| `cron-notifiers-email-health.yml`        | cron - notifiers email-health (every 30 min)            | */30 * * * *         | Triggers the backend's `/api/cron/notifiers/email-health` endpoint every 30 minutes.                                                                                                                                                           |
| `cron-notifiers-lkpm-deadlines.yml`      | cron - notifiers lkpm-deadlines (daily 23:00 WITA)      | 0 15 * * *           | Triggers the backend's `/api/cron/notifiers/lkpm-deadlines` endpoint daily (23:00 WITA).                                                                                                                                                       |
| `cron-notifiers-welcome-pending.yml`     | cron - notifiers welcome-pending (every 15 min)         | */15 * * * *         | Triggers the backend's `/api/cron/notifiers/welcome-pending` endpoint every 15 minutes.                                                                                                                                                        |
| `cron-practice-auto-create.yml`          | cron - practice auto-create (daily 07:30 WITA)          | 30 23 * * *          | Triggers the backend's `/api/admin/practice/auto-create` endpoint daily (07:30 WITA).                                                                                                                                                          |
| `cron-sentry-quota-check.yml`            | cron - sentry quota check (daily 09:00 WITA)            | 0 1 * * *            | Reads Sentry config from the nuzantara-rag runtime env via `flyctl ssh console`; alerts Telegram if `SENTRY_TRACES_SAMPLE_RATE` > 0.02 in production or `SENTRY_SEND_DEFAULT_PII` is truthy.                                                   |
| `docs-inventory-refresh-liveness.yml`    | cron - docs-inventory-refresh liveness (every 6h)       | 17 */6 * * *         | Out-of-band check for the scheduled artifact publisher: the organ no longer opens a PR, so liveness is exactly "a successful run within 2x cadence".                                                                                           |
| `docs-inventory-refresh.yml`             | Docs Inventory Refresh                                  | 0 19 * * *;0 7 * * * | Scheduled publication of volatile documentation state; the result is an artifact, never a commit or pull request, so global drift cannot blame a PR.                                                                                           |
| `fly-secrets-check.yml`                  | Fly.io Secrets Health Check                             | 0 9 * * 1            | Weekly check that `FLY_API_TOKEN` is still valid; a deadman's switch — if this workflow itself fails (token expired), GitHub emails the repo owner even if the Telegram alert can't be sent.                                                   |
| `frontend-live-sentinel.yml`             | Frontend Live Sentinel                                  | */30 * * * *         | Verifies production is actually RUNNING the latest commit (not just that a deploy was announced) across balizero.com and its subdomains; born from a 2026-07-27 incident where stale code served for 13 hours undetected.                      |
| `main-push-failure-watch.yml`            | Main-push Failure Watch                                 | */15 * * * *         | One generic watcher for every scheduled- or push-triggered workflow's completion on `main`, replacing three independently-reinvented hand-rolled alert mechanisms; does not alert on `pull_request` or `workflow_dispatch` runs.               |
| `merge-queue-watch.yml`                  | merge-queue-watch                                       | */10 * * * *         | Poll-based watcher for merge-queue ejections and automerge-armed-but-stuck PRs (GraphQL polling, since the `merge_group` webhook does not deliver queue-ejection events to Actions).                                                           |
| `pr-size-taxonomy.yml`                   | PR size taxonomy (advisory)                             | 0 20 * * *           | Report-only PR size taxonomy that prints to the job summary; NEVER gates a merge (no `--check` flag, not a required check).                                                                                                                    |
| `restore-drill.yml`                      | Monthly PG Restore Drill                                | 0 4 1 * *            | Proves the daily pg_dump → Tigris backup pipeline is actually restorable; runs monthly (1st, 04:00 UTC / 12:00 WITA), also triggerable on-demand.                                                                                              |
| `scripts-tests-sweep.yml`                | scripts/tests/ sweep (report-only)                      | 15 2 * * *           | Report-only sweep of `scripts/tests/` surfacing test files named by no workflow (174 orphans measured 2026-07-26); does not gate anything.                                                                                                     |

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
