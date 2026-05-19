# Sentinel State Cleanup — Wave 3 Fix 3F continuation

## Action

Archived 18 `.last.json` files from `~/.agent/decisions/state/` that hadn't been
updated for >30 days. Target: stale zombies (e.g. `seo_auto_fixer`,
`nightly_code_quality`, `health_check`, `kbli_indexing_daily`, etc.) that the
sentinel was still monitoring because it does
`glob("~/.agent/decisions/state/*.last.json")` indiscriminately
(`nuzantara-sentinel.py:232`).

Archived files moved to `~/.agent/decisions/state/.archive-2026-05-19/`.

## Empirical result (sentinel runs before/after)

| Time              | Checked | Healthy | Escalated |
| ----------------- | ------- | ------- | --------- |
| 11:27 (before)    | 67      | 36      | 29        |
| 12:27 (before)    | 67      | 36      | 29        |
| **13:23 (after)** | **49**  | **36**  | **13**    |

**18 fewer task monitored, 16 fewer escalations** (29 → 13 = 55% reduction).
Healthy count unchanged (36) — confirmed no live job was killed.

Sentinel auto-purged 43 phantom CB entries on next run (visible in
`~/logs/sentinel.log:13:21:16`).

## Files archived (18)

- articles_indexing_daily.last.json
- backend_prewarm.last.json
- biz_orchestrator.last.json
- compliance_autopilot.last.json
- daily_ops_autopilot.last.json
- fly_health_check.last.json
- fly_qdrant_backup.last.json
- gdrive_intel_archive.last.json
- gdrive_pg_backup.last.json
- health_check.last.json
- kbli_indexing_daily.last.json
- nightly_code_quality.last.json
- nlm_bridge.last.json
- practice_lifecycle_check.last.json
- quality_orchestrator.last.json
- seo_auto_fixer.last.json
- seo_guardian_measure.last.json
- weekly_report.last.json

All last-modified 2026-03-26 or 2026-04-15 (i.e. ~30-55 days ago).

## Rollback

```bash
mv ~/.agent/decisions/state/.archive-2026-05-19/*.last.json ~/.agent/decisions/state/
```

## Long-term recommendation (Wave 4 candidate)

Add TTL purge to `nuzantara-sentinel.py:collect_state_files()`: skip files
older than `STATE_FILE_TTL_DAYS=30` (or move them to archive automatically).
This prevents zombie state buildup from polluting sentinel reports.
