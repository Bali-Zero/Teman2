"""SOTA Social Loop 90gg — cron entry points invoked via wr2-cron-wrapper.sh.

Modules:
  - m13_collect   every 6h — pull IG Graph insights → post_metrics_history
  - m13_weekly    Sun 06:00 WITA — pillar deltas + publisher auto-toggle
  - m13_monthly   1st 04:30 WITA — Consiglio v1 retrain over past 30d data
  - m13_checkpoint daily 09:00 WITA — 30/60/90 loop-day formal review trigger

All modules are invoked by plist files in infra/launchagents/ through
scripts/wr2-cron-wrapper.sh, which:
  1. sources ~/.nuzantara-secrets.env
  2. maps DATABASE_URL_LOCAL → DATABASE_URL (pg-proxy 127.0.0.1:15432)
  3. activates apps/backend-rag/.venv
  4. execs `python -m backend.services.sota_loop.<module>`
"""
