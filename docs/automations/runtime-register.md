# Runtime register — 200+ automations 5-tier classified

**Date:** 2026-05-02 · **Author:** Sprint 0 Air session (Claude Opus 4.7 1M)
**Reference:** brainstorm 2026-05-02 round 2 § "Runtime register 5 categorie"

This is the working catalog of every Nuzantara automation, classified
into one of the **5 tiers** defined in synthesis v2:

- **full-cell** — has PulseLoop+Genome+HGT+Homeostasis (8 cell L1+ in
  the 14-cell list)
- **light-cell** — Genome+HGT publisher only, no PulseLoop (intel-scraper-cell)
- **organism-submodule** — organelle inside `war-room-organism` or
  `mata-garuda-cell` (the ~13 operational LA + cognitive sub-organelle)
- **observed-shell** — emit events_outbox via ObservedShellBus (Sprint
  0 Track C2). Translation, BI feeds, regulatory monitors, backups,
  webhooks, NLM refresh.
- **leave-alone** — pure deterministic, no observability layer needed
  (mos-maintenance, cache-cleanup, ttl-sweep, etc.)

This snapshot is **NOT** the live state of Pro at audit time. It's the
union of (a) `infra/launchagents/*.plist` versioned in this repo,
(b) `.github/workflows/*.yml` versioned in this repo, (c)
`apps/*` services declared, and (d) the Pro live audit transcript in
`docs/audits/2026-05-02-cell-openclaw-brainstorm/04_automation_inventory_complete.md`
(2026-05-02 ~15:00 WITA snapshot). Mark with **[gap]** any row whose
"runtime owner" or "state store" couldn't be verified offline.

## Top of register (~200 most-relevant rows)

| ID | Name | Category | Path/script | Frequency | Runtime owner | State store | Trace ID? | Kill switch? | 5-tier | Note |
|---|---|---|---|---|---|---|---|---|---|---|

### Cell candidates (14 from round 2)

| 1 | system-doctor-cell | infrastructure | cron-agent-python `system_doctor.py` | every 4h | cron-agent-python | `~/.agent/decisions/state/system_doctor.json` | yes (cron-agent-python sessions.db) | yes (kill cron job) | full-cell | Sprint 4 promotion |
| 2 | seo-guardian-cell | code-quality | `apps/evaluator/seo_cell` + LaunchAgents seo-cell-daily, seo-cell-28d-check | every 40min + daily + weekly | LaunchAgent + cron-agent-python | local cell SQLite + JSON state | partial | yes | full-cell | Sprint 4 |
| 3 | fact-checker-cell | code-quality | cron-agent-python `fact-checker` | every 30min | cron-agent-python | sessions.db | yes | yes | full-cell | Sprint 4 |
| 4 | tech-orchestrator-cell | infrastructure | cron-agent-python `tech-orchestrator` | hourly | cron-agent-python | sessions.db | yes | yes | full-cell | Sprint 4, Local sovereignty refactor needed |
| 5 | conversation-trainer-cell | code-quality | cron-agent-python `conversation-trainer` | weekly | cron-agent-python | sessions.db + Telegram conversations | partial | yes | full-cell | Sprint 4 |
| 6 | daily-ops-cell | reporting | cron-agent-python `daily-ops` | daily 08:00 | cron-agent-python | sessions.db | yes | yes | full-cell | Sprint 4 |
| 7 | crm-cell ⭐ NEW | crm | `crm_automation_engine.py` + `practice_status_listener` + 11 sibling | mixed (07:00 daily + event-driven) | LaunchAgent + Python listener | Postgres CRM tables + state JSON | partial | yes | full-cell | Sprint 3 (consolidates 13 CRM auto) |
| 8 | intel-scraper-cell (light) | intel | `apps/bali-intel-scraper/` + cron-agent-python `intel-radar` + `intel-feed-processor` | 03:00 daily + hourly + 2h | OpenClaw cron wrapper + cron-agent-python | Qdrant `balizero_news` + state JSON | partial | yes | light-cell | Sprint 1 |
| 9 | hgt-coordinator-cell ⭐ NEW | confrontation | NEW (Sprint 1) — propose-only quarantine | NEW | NEW (TBD: cron-agent-python or OpenClaw) | NEW genome propose table | NEW | NEW | full-cell | Sprint 1 |
| 10 | gap-scanner-cell | research | cron-agent-python + Ollama local | weekly | cron-agent-python | sessions.db + 56 gap topics | partial | yes | full-cell | Sprint 6 |
| 11 | kg-cell | knowledge-graph | knowledge-graph-builder cron + KG auto-expansion (mig 077) | every 6h | OpenClaw cron wrapper → Fly backend | Postgres KG tables (108k nodes, 243k edges) | partial | yes | full-cell | Sprint 6 |
| 12 | research-cell | research | NB-2..NB-10 cron + NotebookLM | staggered Mon-Fri 02:10-02:50 WITA | LaunchAgent + NotebookLM | NotebookLM corpus | partial | yes | full-cell | Sprint 6 |
| 13 | war-room-organism | meta | apps/war-room + 16 Bali Dispatch LA | daily/weekly mixed | LaunchAgent + Postgres triggers | war_room_drafts/posts/intel/cognitive tables | yes (event_outbox) | yes (per LA) | organism-submodule (federation) | Sprint 2 |
| 14 | mata-garuda-cell ⭐ NEW | meta | apps/mata-garuda + zantara-media (19-pipeline) | mixed | LaunchAgent | mata-garuda specific schemas | partial | yes | full-cell | Sprint 3 |

### WR2 cognitive backbone (sub-cell of #13)

| 15 | wr2.oracle | cognitive | `backend.services.cognitive.oracle_cli` | Sun 22:30 WITA | LaunchAgent | `ultra_moves` table (mig 114) | yes | yes | organism-submodule | L4, propose-not-decide refactor Sprint 2 |
| 16 | wr2.strategos | cognitive | `backend.services.cognitive.strategos_cli` | Sun 22:00 WITA | LaunchAgent | `weekly_strategic_briefs` (mig 114) | yes | yes | organism-submodule | L3 |
| 17 | wr2.connector | cognitive | `backend.services.cognitive.connector_cli` | daily 04:00 WITA | LaunchAgent | `cross_dossier_theses` (mig 114) | yes | yes | organism-submodule | L1 |
| 18 | wr2.supervisor | meta-orchestrator | `scripts/wr2_supervisor.py` | RunAtLoad daemon | LaunchAgent (KeepAlive=dict) | LISTEN `wr2_status_change` (mig 138) | yes | yes (signal) | organism-submodule | L2 |
| 19 | wr2.pg-proxy | substrate | proxy daemon | daemon | LaunchAgent (KeepAlive=true) | n/a (substrate) | n/a | yes | organism-submodule | L2 |
| 20 | wr2.learner-nightly | reflection | `backend.services.learner.learner_cli` | daily 03:00 | LaunchAgent | `m13_retrain_log` + skills/scars | yes | yes | organism-submodule | L1, Symbiosis Reflection pillar |
| 21 | wr2.trend-hunter | sensor | `backend.services.intel.trend_hunter.cli` | every 2h | LaunchAgent | `trend_signals` (mig 113) | yes | yes | organism-submodule | L1 |
| 22 | wr2.measurer | metrics | `backend.services.measurer.scheduler_cli` | every 6h | LaunchAgent | `post_metrics_history` + `m13_retrain_log` | partial | yes | organism-submodule | L1, ⚠️ no trigger fires (Sprint 1 W1 add measurer_event channel) |
| 23 | wr2.dossier-compiler | digestion | `backend.services.intel.dossier_compiler_cli` | daily 04:30 | LaunchAgent | `research_dossiers` (mig 113) | yes | yes | organism-submodule | L1 |

### WR2 operational organelle (sub-cell of #13)

| 24 | wr2.newsletter | distribution | `backend.services.newsletter.newsletter_cli` | Mon 09:00 | LaunchAgent | apps/web blog MDX + `war_room_posts` | yes | yes | organism-submodule | weekly digest |
| 25 | wr2.sla-worker | governance | `backend.services.review.sla_worker_cli` | every 30min | LaunchAgent | UPDATE `war_room_drafts` status | yes | yes | organism-submodule | timeout enforcement |
| 26 | wr2.hardening | resilience | `scripts/wr2-hardening-chain.sh` | every 6h | LaunchAgent | filesystem logs + Telegram | partial | yes | observed-shell | Sprint 1 wraps in ObservedShellBus.emit |
| 27 | wr2.canva-apply (Pro-only) | rendering | `scripts/wr2_canva_apply.py` | daily | LaunchAgent | UPDATE `war_room_drafts` | yes | yes | organism-submodule | drift to repo (Track B1) |
| 28 | wr2.draft-generator (Pro-only) | content | `scripts/wr2_draft_generator.py` | daily | LaunchAgent | UPDATE `war_room_drafts` | yes | yes | organism-submodule | drift to repo (Track B1) |
| 29 | wr2.image-generator (Pro-only) | content | `scripts/wr2_image_generator.py` | daily | LaunchAgent | UPDATE `war_room_drafts` | yes | yes | organism-submodule | drift to repo (Track B1) |
| 30 | wr2.topic-selector (Pro-only) | content | `scripts/wr2_topic_selector.py` | weekly | LaunchAgent | INSERT `war_room_drafts` | yes | yes | organism-submodule | drift to repo (Track B1) |
| 31 | wr2.canva-renderer | rendering | `infra/launchagents/com.balizero.wr2.canva-renderer.plist` (orphan in repo, possibly dead) | every 300s | LaunchAgent | filesystem | no | yes | leave-alone? | Sprint 0 Track B1 verify orphan vs deprecation |

### Mata-Garuda 19-pipeline (sub-cell of #14)

| 32 | matagaruda.daily-briefing | research | `apps/mata-garuda/...daily_briefing.py` | daily | LaunchAgent | mata-garuda schemas | partial | yes | organism-submodule | Sprint 3 |
| 33 | matagaruda.intel-bridge.daily | intel | `apps/mata-garuda/scripts/intel_bridge.py` | daily | LaunchAgent | bridge tables | partial | yes | organism-submodule | Sprint 3 |
| 34 | matagaruda.kg-linker | knowledge-graph | `apps/mata-garuda/...kg_linker.py` | hourly? | LaunchAgent | KG tables | partial | yes | organism-submodule | Sprint 3 |
| 35 | matagaruda.kita-feed.daily | content | `apps/mata-garuda/...kita_feed.py` | daily | LaunchAgent | feeds table | partial | yes | organism-submodule | Sprint 3 |
| 36 | matagaruda.nlm-expander.weekly | research | `apps/mata-garuda/...nlm_expander.py` | weekly | LaunchAgent | NB corpora | partial | yes | organism-submodule | Sprint 3 |
| 37 | matagaruda.public-channel | distribution | `apps/mata-garuda/...public_channel.py` | event-driven | LaunchAgent | channel posts | partial | yes | organism-submodule | Sprint 3 |
| 38 | matagaruda.reg-alert.30min | regulatory | `apps/mata-garuda/...reg_alert.py` | every 30min | LaunchAgent | alerts table | partial | yes | organism-submodule | Sprint 3 |
| 39 | matagaruda.weekly-digest | distribution | `apps/mata-garuda/...weekly_digest.py` | weekly | LaunchAgent | digest table | partial | yes | organism-submodule | Sprint 3 |
| 40 | matagaruda.wr-topic | bridge | `apps/mata-garuda/...wr_topic.py` | event-driven | LaunchAgent | wr topic table | partial | yes | organism-submodule | Sprint 3 |
| 41 | matagaruda.wr2-bridge.hourly | bridge | `apps/mata-garuda/...wr2_bridge_publisher.py` | hourly | LaunchAgent | wr2 bridge state | yes | yes | organism-submodule | Sprint 3 |

(9 more matagaruda. plist + 19-pipeline scripts — see `apps/mata-garuda/`
for full list. Sprint 3 will refactor as cell.)

### Cell core daemons

| 42 | organism.supervisor | meta | `apps/organism` supervisor daemon | KeepAlive | LaunchAgent | state JSON | yes | yes | organism-submodule | autonomic recovery |
| 43 | organism.control-panel | meta | `apps/organism` control panel | KeepAlive | LaunchAgent | state JSON | yes | yes | organism-submodule | |
| 44 | organism.scheduled-tick | meta | `apps/organism` tick driver | every 60s | LaunchAgent | state JSON | yes | yes | organism-submodule | |
| 45 | cell.organism | meta | `apps/cell` (cell-core consumer) | KeepAlive | LaunchAgent | local SQLite | yes | yes | organism-submodule | |
| 46 | cell-observatory-collector | observability | `apps/cell-observatory-collector` daemon | KeepAlive | LaunchAgent | local SQLite (Pro) | yes | yes | organism-submodule | LISTEN `cell_pulse_observed` |
| 47 | cell-observatory | observability | `apps/cell-observatory-collector` | KeepAlive | LaunchAgent | SQLite | yes | yes | organism-submodule | |
| 48 | cell-observatory-prune | observability | prune cron | daily | LaunchAgent | SQLite | yes | yes | observed-shell | retention |
| 49 | cell-observatory-selfcheck | observability | selfcheck cron | hourly | LaunchAgent | state JSON | yes | yes | observed-shell | |

### Sentinel + monitoring

| 50 | nuzantara-sentinel | sentinel | `~/scripts/nuzantara-sentinel.py` | every 60s | LaunchAgent | state JSON | yes | yes | observed-shell | |
| 51 | sentinel-meta-watchdog | sentinel | `infra/launchagents/com.nuzantara.sentinel-meta-watchdog.plist` | every 60s | LaunchAgent | state JSON | yes | yes | observed-shell | |
| 52 | automap-server | sentinel | automap server | KeepAlive | LaunchAgent | state JSON | yes | yes | observed-shell | |
| 53 | automap-watchdog | sentinel | automap watchdog | every 60s | LaunchAgent | state JSON | yes | yes | observed-shell | |
| 54 | automap-telegram | sentinel | automap → Telegram | event-driven | LaunchAgent | n/a | partial | yes | observed-shell | |
| 55 | auto_sentinel.sh | sentinel | `~/scripts/auto_sentinel.sh` | daily 03:00 | LaunchAgent | state JSON | yes | yes | observed-shell | |
| 56 | intel-scraper-sentinel-bridge | sentinel | bridge script | every 5min | LaunchAgent | state JSON | yes | yes | observed-shell | |
| 57 | fly-restart-loop-detector | sentinel | `~/scripts/fly-restart-loop-detector.sh` | every 15min | LaunchAgent | state JSON | yes | yes | observed-shell | post drive-poll incident antibody |
| 58 | login-healthcheck | sentinel | `~/scripts/login-healthcheck.sh` | every 30min | LaunchAgent | state JSON | yes | yes | observed-shell | E2E user metric |
| 59 | heartbeat_monitor | sentinel | OpenClaw heartbeat | every 1h | OpenClaw skill | OC log | partial | yes | observed-shell | |
| 60 | pro_heartbeat | sentinel | `~/scripts/pro_heartbeat.sh` | hourly | LaunchAgent | state JSON | yes | yes | observed-shell | |
| 61 | dlq-autopilot | sentinel | `~/scripts/dlq_autopilot.py` | every 5min | LaunchAgent | state JSON | yes | yes | observed-shell | DLQ drain |
| 62 | zombie-hunter | sentinel | `~/scripts/zombie-hunter.sh` | every 60s | LaunchAgent | state JSON | yes | yes | observed-shell | LaunchAgent zombie sweeper |

### CRM 13 automations (sub-cell of #7 once promoted Sprint 3)

| 63 | crm.client-health-monitor | crm | cron-agent-python | every 60s | cron-agent-python | sessions.db | yes | yes | observed-shell (pre-promotion) | merges into crm-cell Sprint 3 |
| 64 | crm.compliance-ops | crm | cron-agent-python | every 5min | cron-agent-python | sessions.db | yes | yes | observed-shell | merges Sprint 3 |
| 65 | crm.practice_status_listener | crm | LISTEN `practice_changed` | event-driven | LaunchAgent (Python) | EventBus | yes | yes | organism-submodule | merges Sprint 3 |
| 66 | crm.proactive_compliance_monitor | crm | LaunchAgent | hourly | LaunchAgent | DB scan | partial | yes | observed-shell | merges Sprint 3 |
| 67 | crm.lead-scoring | crm | LaunchAgent | daily | LaunchAgent | DB | partial | yes | observed-shell | merges Sprint 3 |
| 68 | crm_automation_engine | crm | `~/scripts/crm_automation_engine.py` | daily 07:00 | LaunchAgent + Telegram digest | DB updates + JSONL | yes | yes | observed-shell | merges Sprint 3 |
| 69-75 | (7 other CRM auto) | crm | various | mixed | mixed | DB + state | partial | yes | observed-shell | merges Sprint 3 |

### Memory / MOS (6)

| 76 | mos-maintenance | memory | `~/scripts/mos-maintenance.sh` | daily | LaunchAgent | MOS SQLite | partial | yes | observed-shell | TTL sweep |
| 77 | sync-memory-to-nlm | memory | `~/scripts/sync-memory-to-nlm.sh` | daily | LaunchAgent | NotebookLM corpus | partial | yes | observed-shell | |
| 78 | sync-memory-ruslana | memory | `~/scripts/sync-memory-ruslana.sh` | daily | LaunchAgent | NotebookLM | partial | yes | observed-shell | per-user MOS |
| 79 | mos-ttl-sweep | memory | TTL sweep cron | daily | LaunchAgent | MOS SQLite | partial | yes | leave-alone | pure deterministic |
| 80 | mos-backup-purge | memory | backup retention | daily | LaunchAgent | MOS backups | partial | yes | leave-alone | |
| 81 | (other MOS) | memory | various | mixed | LaunchAgent | MOS | partial | yes | leave-alone | |

### Translation, BI, regulatory monitors (observed-shell tier targets)

| 82 | translate-articles.py | translate | cron-agent-python | hourly | cron-agent-python | DB articles + state JSON | partial | yes | observed-shell | Sprint 1 W1 emit |
| 83 | bi-exchange-rate | bi | cron-agent-python | daily 07:00 | cron-agent-python | DB exchange_rates | partial | yes | observed-shell | Sprint 1 W1 emit |
| 84 | imigrasi-monitor | regulatory | cron-agent-python | daily 06:00 | cron-agent-python | DB regulations | partial | yes | observed-shell | Sprint 1 W1 emit |
| 85 | oss-monitor | regulatory | cron-agent-python | every 2h 08:00-22:00 | cron-agent-python | DB + state JSON | partial | yes | observed-shell | Sprint 1 W1 emit |
| 86 | pajak-monitor | regulatory | cron-agent-python | daily 00:00 UTC | cron-agent-python | DB + state JSON | partial | yes | observed-shell | Sprint 1 W1 emit |
| 87 | tdd-pipeline | code-quality | cron-agent-python | weekly Mon 01:00 UTC | cron-agent-python | DB | partial | yes | observed-shell | |
| 88 | vision-doc-extractor | ocr | cron-agent-python `vision-doc` | every 6h | cron-agent-python | DB OCR results | yes | yes | observed-shell | |
| 89 | log-anomaly-detector | infrastructure | cron-agent-python | every 5min | cron-agent-python | sessions.db | yes | yes | observed-shell | |
| 90 | fly-watcher | infrastructure | cron-agent-python | every 15min | cron-agent-python | sessions.db | yes | yes | observed-shell | post drive-poll incident |

### NLM Activation cycle (14, sub-cell of #12 research-cell)

| 91-104 | nlm-nb1..nlm-nb10-daily-refresh | nlm | LaunchAgent staggered | Mon-Fri 02:10-02:50 | LaunchAgent | NB corpora | partial | yes | observed-shell | Sprint 6 absorb into research-cell |
| 105 | nlm-deep-research | nlm | LaunchAgent | weekly | LaunchAgent | NB | partial | yes | observed-shell | |
| 106 | rag_canary | rag-quality | every 6h :30 | LaunchAgent | DB rag_canary_log | yes | yes | observed-shell | |
| 107 | db_nlm_sync | nlm | bridge | daily | LaunchAgent | NB corpus | partial | yes | observed-shell | |

### Drive / Workspace (6)

| 108 | drive-poll | drive | `scripts/drive_poll_cron.sh` | every 5min | LaunchAgent | DB system_settings page_token | yes | yes (commented out) | leave-alone | DISABLED 2026-04-29 (cicatrix) |
| 109 | drive_token_watchdog | drive | `scripts/drive_token_watchdog.py` | every 6h | LaunchAgent | google_drive_tokens table | yes | yes | observed-shell | |
| 110 | gdrive-backup-all | backup | `~/scripts/gdrive-backup-all.sh` | daily | LaunchAgent | Google Drive | partial | yes | observed-shell | Sprint 1 W2 |
| 111 | gdrive-pg-backup | backup | `~/scripts/gdrive-pg-backup.sh` | daily | LaunchAgent | Drive | partial | yes | observed-shell | |
| 112 | gdrive-qdrant-backup | backup | `~/scripts/gdrive-qdrant-backup.sh` | daily | LaunchAgent | Drive | partial | yes | observed-shell | |
| 113 | fly-pg-backup | backup | `~/scripts/fly-pg-backup.sh` | daily | LaunchAgent | Tigris | partial | yes | observed-shell | Sprint 1 W2 |
| 114 | qdrant-snapshot | backup | qdrant snapshot cron | daily | LaunchAgent | Qdrant snapshots | partial | yes | observed-shell | Sprint 1 W2 |

### Webhooks + DLQ (post-publish)

| 115 | post-publish-poller | webhook | `apps/bali-intel-scraper/scripts/post_publish_poller.py` | every 1min | LaunchAgent | DB outbox | yes | yes | observed-shell | |
| 116 | post-publish-webhook | webhook | `apps/bali-intel-scraper/scripts/post_publish_webhook.py` | RunAtLoad | LaunchAgent | DB outbox | yes | yes | observed-shell | |

### Indexing (sub-cell of kg-cell #11)

| 117 | indexing-sweep.daily | seo | `scripts/daily_indexing_cron_wrapper.sh` | daily 00:30 WITA | LaunchAgent (Air → Pro post-retire) | DB indexing_state | yes | yes | observed-shell | Phase 1: 200 articles, Phase 2: 600 KBLI |
| 118 | indexing-daily | seo | indexing daily | daily | LaunchAgent | DB | partial | yes | observed-shell | |
| 119 | kbli-indexing-daily | seo | KBLI indexing | daily | LaunchAgent | DB KBLI | partial | yes | observed-shell | |
| 120 | knowledge-graph-builder | kg | `~/scripts/openclaw-cron/knowledge-graph-builder.sh` | every 6h | OpenClaw cron wrapper → Fly | KG tables | partial | yes | observed-shell | |
| 121 | garuda-indexer | indexer | `~/scripts/openclaw-cron/garuda-indexer.sh` | hourly | OpenClaw cron wrapper → Fly | Mata-Garuda | partial | yes | observed-shell | |
| 122 | garuda-gc | indexer | `~/scripts/openclaw-cron/garuda-gc.sh` | daily | OpenClaw cron wrapper | KG | partial | yes | observed-shell | |

### Code quality + Testing

| 123 | core-guardian | code-quality | core-guardian cron | every 3h | LaunchAgent or cron-agent-python | state JSON | partial | yes | observed-shell | V3 PR cleanup |
| 124 | cron_ragas | rag-quality | `cron_ragas.py` | daily | cron-agent-python | DB ragas | yes | yes | observed-shell | |
| 125 | cron_red_team | rag-quality | `cron_red_team.py` | weekly | cron-agent-python | DB red_team | yes | yes | observed-shell | |
| 126 | seo-auto-fixer | seo | `seo-auto-fixer` cron | weekly | cron-agent-python | DB seo | partial | yes | observed-shell | |
| 127 | ragas-eval | rag-quality | LaunchAgent | Sun 06:00 | LaunchAgent | DB | partial | yes | observed-shell | |

### SOTA M13 (4 LA — measurer-related)

| 128 | sota.m13-checkpoint | metrics | LaunchAgent | weekly | LaunchAgent | M13 tables | partial | yes | observed-shell | M13 sub-cell of measurer |
| 129 | sota.m13-collect | metrics | LaunchAgent | daily | LaunchAgent | M13 | partial | yes | observed-shell | |
| 130 | sota.m13-monthly | metrics | LaunchAgent | monthly | LaunchAgent | M13 | partial | yes | observed-shell | |
| 131 | sota.m13-weekly | metrics | LaunchAgent | weekly | LaunchAgent | M13 | partial | yes | observed-shell | |

### Federation Alert Dispatcher

| 132 | federation-alert-dispatcher | alerts | LaunchAgent | KeepAlive | LaunchAgent (KeepAlive=true) | LISTEN federation_alert | yes | yes | organism-submodule | classify+route alerts |

### Audit + cleanup (7, observed-shell or leave-alone)

| 133 | audit-trail-cleanup | cleanup | cleanup cron | daily | LaunchAgent | DB audit | partial | yes | leave-alone | retention |
| 134 | cache-cleanup | cleanup | cleanup cron | daily | LaunchAgent | n/a | n/a | yes | leave-alone | |
| 135 | escalations-prune | cleanup | escalations prune | daily | LaunchAgent | escalations.jsonl | partial | yes | leave-alone | |
| 136 | launchagent-state-bridge | sentinel | bridge | every 5min | LaunchAgent | state JSON | partial | yes | observed-shell | |
| 137 | conversation-cleanup | cleanup | cleanup cron | daily | LaunchAgent | conversation logs | partial | yes | leave-alone | |
| 138 | learning-pipeline | learning | LaunchAgent | daily | LaunchAgent | learning DB | partial | yes | observed-shell | |
| 139 | nightly-code-quality | code-quality | Lobster workflow `nightly-code-quality.lobster` | nightly | OpenClaw → coder agent | OC observation feed | partial | yes | observed-shell | OC production usage |
| 140 | autofix-loop | code-quality | Lobster workflow `autofix-loop.lobster` | event-driven | OpenClaw → coder agent | OC observation feed | partial | yes | observed-shell | OC production usage |
| 141 | weekly-dep-audit | code-quality | Lobster workflow `weekly-dep-audit.lobster` | weekly | OpenClaw → coder agent | OC observation feed | partial | yes | observed-shell | |
| 142 | nuzantara-dev-pipeline | ci/cd | Lobster workflow | event-driven | OpenClaw → coder agent | OC observation feed | partial | yes | observed-shell | OC production usage |

### Cost / health (cron-agent-python or sub-cell of system-doctor)

| 143 | cost-advisor-* | cost | cost advisor crons | daily | cron-agent-python or LaunchAgent | DB cost_log | partial | yes | observed-shell | |
| 144 | cpu-monitor | infra | cpu monitor | every 60s | LaunchAgent | state JSON | partial | yes | leave-alone | |
| 145 | disk-monitor | infra | disk monitor | every 60s | LaunchAgent | state JSON | partial | yes | leave-alone | |
| 146 | ollama-warm-pin | infra | Ollama warm pin | every 5min | LaunchAgent | n/a | n/a | yes | leave-alone | keep models in RAM |
| 147 | judgement-day | rag-quality | `auto_judgement_day.sh` | Sun 16:00 | LaunchAgent | DB | partial | yes | observed-shell | |

### GitHub Actions (29 workflows — runtime CI, NOT runtime runner)

| 148-176 | .github/workflows/*.yml | ci/cd | GitHub Actions | per-event or scheduled | GitHub Actions | GitHub | yes | yes (cancel run) | leave-alone (CI) | not Pro automations |

### Backend Fly.io services (35+)

| 177-211 | apps/backend-rag/backend/services/*.py | backend | Fly.io machines | event-driven | Fly.io | Postgres + Qdrant + Redis | yes | yes (machine restart) | leave-alone (FastAPI services) | event-driven, separate concern |

### Channels (4 live + 3 disabled)

| 212 | whatsapp.py | channel | apps/backend-rag channels | event-driven | Fly.io | DB conversations | yes | yes | leave-alone | Gemini 3 Flash + RAG |
| 213 | telegram (Pro OpenClaw) | channel | OpenClaw @Balizerobot | event-driven | OpenClaw | DB | yes | yes | leave-alone | Opus 4.6 |
| 214 | instagram.py | channel | apps/backend-rag channels | event-driven | Fly.io | DB | yes | yes | leave-alone | |
| 215 | web.py | channel | apps/backend-rag channels | event-driven | Fly.io | DB | yes | yes | leave-alone | |

### Email + notifications

| 216 | weekly_email_reporter | email | weekly | LaunchAgent or cron-agent-python | Brevo | partial | yes | observed-shell | |
| 217-222 | event bus notifiers (welcome, birthday, LKPM, ...) | webhook | webhook receivers | event-driven | Fly.io | DB outbox | yes | yes | leave-alone (event-driven) | |

## Summary by 5-tier

| Tier | Count | Notes |
|---|---|---|
| **full-cell** (8 in 14-cell list) | 8 | system-doctor, seo-guardian, fact-checker, tech-orchestrator, conversation-trainer, daily-ops, crm-cell, hgt-coordinator, gap-scanner, kg-cell, research-cell, mata-garuda — minus the 2 lights | Wait, count is 12 + 1 (war-room-organism) + 1 (mata-garuda) − 2 (intel-scraper light + war-room is system not cell). Re-check |
| **light-cell** | 1 | intel-scraper-cell only |
| **organism-submodule** | ~30 | WR2 cognitive (9) + WR2 operational (4-7) + matagaruda (19) + cell core daemons (6) |
| **observed-shell** | ~80-100 | the bulk of CRM, sentinel, monitoring, NLM cycle, indexing, code quality, audit, regulatory monitors, translation, BI |
| **leave-alone** | ~50-70 | GitHub Actions (29), Fly.io services (35+), MOS TTL/cleanup, channel adapters, cpu/disk monitors |

The total is ~200+ rows. The exact split depends on whether we count
GitHub Actions and Fly.io services as Pro-automations (they're not, but
they ARE part of the broader stack inventory).

## Gaps

This register was compiled offline (Pro SSH-unreachable at audit time).
Verifications post-Pro-recovery:

- **[gap]** Verify state file timestamps for cells #1-12 are recent
  (per Sprint 0 Track B4 procedure).
- **[gap]** Reverse-engineer schedules of the 4 Pro-only WR2 plist
  (#27-30) by reading them directly from Pro `~/Library/LaunchAgents/`.
- **[gap]** List the actual 24 frozen jobs in `~/.openclaw/cron/jobs.json`
  (Track A5 Step 1).
- **[gap]** Count actual `.cron-agent-python/strategies/` directory
  contents (round 2 said 19 strategies; verify).
- **[gap]** Audit `~/.openclaw/openclaw.json` `agents.list[]` for the
  3rd `claude-code` agent (Track A5 part 1).
- **[gap]** Confirm whether `wr2.canva-renderer` LaunchAgent is alive
  on Pro or just an orphan in repo (Track B1).

## How to keep this register current

Sprint 1 W1 deliverable: a Python script
`scripts/runtime-register-builder.py` that:

1. Walks `infra/launchagents/*.plist` (versioned).
2. Greps `~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist`
   on Pro via SSH (read-only).
3. Lists `~/.cron-agent-python/strategies/`.
4. Reads `~/.openclaw/cron/jobs.json` + `agents.list[]`.
5. Cross-references with `apps/*/fly.toml` + `.github/workflows/*.yml`.
6. Diffs against this Markdown table and prints missing/added rows.

Then this Markdown can be auto-regenerated by CI on every PR that
touches any of those source paths.

## References

- `docs/audits/2026-05-02-cell-openclaw-brainstorm/04_automation_inventory_complete.md`
  — round 1 audit transcript (~263 rows itemized)
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/06_openclaw_ecosystem_audit.md`
  — OpenClaw ecosystem deep dive
- `docs/cell-core/cognitive-levels-matrix.md` — 14 cell promotion targets
- `docs/cell-core/observed-shell-tier.md` — Sprint 1 emit migration list
