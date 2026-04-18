# Backend Jobs Schedule

Generated from `backend/jobs/registry.py`. Do not edit by hand — run
`python scripts/gen_jobs_schedule_doc.py` to regenerate.

| Name | Cron | TZ | Timeout (s) | Max Attempts | Skip Middleware |
|------|------|----|-------------|--------------|-----------------|
| `auto-practice-creator` | `30 7 * * *` | Asia/Makassar | 300 | 3 | — |
| `conversation-cleanup` | `15 4 * * *` | Asia/Makassar | 600 | 3 | — |
