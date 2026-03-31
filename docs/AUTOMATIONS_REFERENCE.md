# NUZANTARA — AUTOMATIONS REFERENCE

> **Auto-generated** — do not edit manually.
> Source: `job_registry.json` (checksum `—…`) + `sentinel_status.json`
> Generated: 2026-03-31 02:49 UTC

---

## Pro Jobs (31)

| Job                      | Type        | Schedule | repair_scope | idempotent | critical | Circuit      | DLQ                        |
| ------------------------ | ----------- | -------- | ------------ | ---------- | -------- | ------------ | -------------------------- |
| `client_health_monitor`  | openclaw    | 1d       | —            | ✅         | —        | 🔴 OPEN (T0) | 🟠 DLQ (abandoned)         |
| `client_value_predictor` | launchagent | 1d       | —            | ✅         | —        | ✅ CLOSED    |                            |
| `comfyui_server`         | launchagent | 1d       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `compliance_ops`         | openclaw    | 6h       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `conversation_cleanup`   | openclaw    | 1d       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `core_guardian`          | openclaw    | 3h       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `coverage_trend`         | shell       | 1d       | —            | ✅         | —        | ✅ CLOSED    |                            |
| `daily_ops`              | openclaw    | 1d       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `dlq_autopilot`          | launchagent | 30m      | —            | ✅         | —        | ✅ CLOSED    |                            |
| `expiry_alerter`         | launchagent | 1d       | —            | ✅         | —        | ✅ CLOSED    |                            |
| `fly_backup`             | shell       | 1d       | —            | ✅         | —        | ✅ CLOSED    |                            |
| `fly_health_check`       | cron        | 30m      | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `indexing_daily`         | openclaw    | 1d       | —            | ✅         | —        | 🔴 OPEN (T0) | 🟠 DLQ (abandoned)         |
| `intel_scraper`          | launchagent | 1d       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `learning_pipeline`      | openclaw    | 7d       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `nlm_bridge`             | launchagent | 1m       | —            | ✅         | —        | 🔴 OPEN (T0) | 🟠 DLQ (skipped_preflight) |
| `nlm_nb1_daily_refresh`  | shell       | 1d       | —            | ✅         | —        | 🔴 OPEN (T0) | 🟠 DLQ (skipped_preflight) |
| `post_publish_poller`    | launchagent | 5m       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `post_publish_webhook`   | launchagent | 5m       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `prime_dashboard`        | launchagent | 1d       | —            | ✅         | —        | ✅ CLOSED    |                            |
| `prime_tunnel`           | launchagent | 1h       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `rag_canary_pro`         | shell       | 6h       | —            | ✅         | —        | ✅ CLOSED    |                            |
| `seo_guardian_observe`   | openclaw    | 40m      | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `seo_guardian_weekly`    | openclaw    | 7d       | —            | ✅         | —        | ✅ CLOSED    |                            |
| `system_doctor`          | openclaw    | 4h       | —            | ✅         | —        | 🔴 OPEN (T0) | 🟠 DLQ (escalated)         |
| `tech_orchestrator`      | openclaw    | 4h       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `translate_hourly`       | launchagent | 1h       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `war_room`               | launchagent | 1d       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `weekly_dep_audit`       | shell       | 7d       | —            | ✅         | —        | ✅ CLOSED    |                            |
| `weekly_review`          | openclaw    | 7d       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |
| `zombie_hunter`          | launchagent | 1m       | —            | ✅         | —        | ✅ CLOSED    | 🟠 DLQ (abandoned)         |

---

## Dead Letter Queue

### Active Entries

| Job                        | Status            | Attempts | Error                                            |
| -------------------------- | ----------------- | -------- | ------------------------------------------------ |
| `weekly_report`            | skipped_preflight | 1        |                                                  |
| `nlm_nb1_daily_refresh`    | skipped_preflight | 1        |                                                  |
| `conversation_trainer`     | skipped_preflight | 1        |                                                  |
| `nlm_bridge`               | skipped_preflight | 1        |                                                  |
| `seo_guardian_measure`     | skipped_preflight | 1        |                                                  |
| `biz_orchestrator`         | skipped_preflight | 1        |                                                  |
| `compliance_autopilot`     | skipped_preflight | 1        |                                                  |
| `kbli_indexing_daily`      | skipped_preflight | 1        |                                                  |
| `fly_pg_backup`            | skipped_preflight | 1        |                                                  |
| `health_check`             | skipped_preflight | 1        |                                                  |
| `quality_orchestrator`     | skipped_preflight | 1        |                                                  |
| `daily_ops_autopilot`      | skipped_preflight | 1        |                                                  |
| `knowledge_graph_builder`  | skipped_preflight | 1        |                                                  |
| `cell_weekly_report`       | skipped_preflight | 1        | OpenClaw consecutiveErrors=0, lastStatus=skipped |
| `articles_indexing_daily`  | skipped_preflight | 1        |                                                  |
| `fly_qdrant_backup`        | skipped_preflight | 1        |                                                  |
| `vector_reindex_check`     | skipped_preflight | 1        |                                                  |
| `practice_lifecycle_check` | skipped_preflight | 1        |                                                  |
| `system_doctor`            | escalated         | 1        | OpenClaw consecutiveErrors=3, lastStatus=error   |
| `client_health_monitor`    | abandoned         | 4        | OpenClaw consecutiveErrors=5, lastStatus=error   |
| `indexing_daily`           | abandoned         | 4        | OpenClaw consecutiveErrors=6, lastStatus=error   |
| `zombie_hunter`            | abandoned         | 6        |                                                  |
| `post_publish_webhook`     | abandoned         | 6        |                                                  |
| `post_publish_poller`      | abandoned         | 6        |                                                  |
| `war_room`                 | abandoned         | 6        |                                                  |
| `conversation_cleanup`     | abandoned         | 8        |                                                  |
| `fly_health_check`         | abandoned         | 8        |                                                  |
| `nlm_deep_research`        | abandoned         | 8        |                                                  |
| `tech_orchestrator`        | abandoned         | 8        |                                                  |
| `seo_guardian_observe`     | abandoned         | 8        |                                                  |
| `intel_scraper`            | abandoned         | 9        |                                                  |
| `prime_tunnel`             | abandoned         | 9        |                                                  |
| `translate_hourly`         | abandoned         | 9        |                                                  |
| `core_guardian`            | abandoned         | 9        |                                                  |
| `weekly_review`            | abandoned         | 36       | OpenClaw consecutiveErrors=0, lastStatus=unknown |
| `learning_pipeline`        | abandoned         | 52       | OpenClaw consecutiveErrors=0, lastStatus=unknown |
| `compliance_ops`           | abandoned         | 139      |                                                  |
| `daily_ops`                | abandoned         | 160      | OpenClaw consecutiveErrors=0, lastStatus=unknown |
| `nightly_code_quality`     | abandoned         | 164      | OpenClaw consecutiveErrors=1, lastStatus=error   |
| `seo_auto_fixer`           | abandoned         | 164      | OpenClaw consecutiveErrors=1, lastStatus=error   |
| `comfyui_server`           | abandoned         | 164      | Daemon not running (no PID)                      |

---

_Generated by `scripts/generate_automations_reference.py` — 2026-03-31 02:49 UTC_
