# PR-C5 — Dead code uninstall (2026-04-30)

Phase C of the Pro automations renaissance. Removes / reduces 6 cron
entries the 2026-04-29 audit
(`research/ops/2026-04-29-pro-automations-audit/`) flagged as **dead**,
**dormant**, or **duplicated**.

Applied via `scripts/ops/pr-c5-dead-code-disable.sh` (idempotent,
backup + verify, runs on Pro only).

## Targets

| #   | Job                                | Old schedule   | New schedule  | Reason                                                                                                                                                                                               |
| --- | ---------------------------------- | -------------- | ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `core-guardian`                    | `0 */3 * * *`  | DELETED       | 56 runs/week, every run logs `candidates=0 fixed=0` (dead code in practice)                                                                                                                          |
| 2   | `weekly-review` (Python)           | `0 9 * * 5`    | DELETED       | never produced a log file — cron schedule misfire or upstream `nlm` CLI broken; bash predecessor at `~/logs/cron-agent/weekly-review.log` last ran 2026-04-14 (~30 weeks ago)                        |
| 3   | `intel-feed-processor`             | `*/30 * * * *` | `0 */2 * * *` | starved 95% of runs (`no_incoming_items`); occasional `telegram_sent` justifies keeping a slower cadence                                                                                             |
| 4   | `vision-doc-extractor`             | `5 * * * *`    | `5 */6 * * *` | always `inbox_empty` (100+ runs); no upstream actually drops files in `~/.intel_scraper/inbox/`                                                                                                      |
| 5   | `fly-restart-loop-detector` (cron) | `*/15 * * * *` | DELETED       | duplicate of `~/Library/LaunchAgents/com.nuzantara.fly-restart-loop-detector.plist` which already handles the cadence; cooldown prevents alert spam but doubles `fly status` calls (rate-limit risk) |
| 6   | `system-doctor` (cron-wrapper)     | `0 0 * * *`    | DELETED       | TCC `PermissionError: [Errno 1] Operation not permitted: '/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/pyvenv...'`; `cron-agent-python` version `0 */4 * * *` already runs healthy      |

Net: -7 lines from crontab, +0 lines, 2 cadence rewrites. `wc -l`:
251 → 243.

## Verification (live, 2026-04-29 17:25 UTC = 2026-04-30 01:25 WITA)

```
[2026-04-29T17:25:41Z] snapshot saved: /Users/nuzantara/.crontab.backups/20260429T172541Z.cron (251 lines)
[2026-04-29T17:25:41Z] line delta: 251 -> 243 (-8)
[2026-04-29T17:25:41Z] crontab installed.
[2026-04-29T17:25:41Z] post-install verified: crontab matches intended state.
[2026-04-29T17:25:41Z] PR-C5 applied. Backup: /Users/nuzantara/.crontab.backups/20260429T172541Z.cron
```

Re-run six seconds later:

```
[2026-04-29T17:25:47Z] no-op: crontab already matches PR-C5 target state
```

(Delta=8 includes 2 blank lines that were adjacent to the deleted
"# core-guardian" and "# C2.3 system-doctor" comment blocks.)

## Rollback

```bash
ssh pro 'crontab "$HOME/.crontab.backups/20260429T172541Z.cron"'
```

Backup files persist indefinitely; one-shot rollback is safe even
weeks later (no shared state between deleted jobs and other crons).

## Why the script (not just doc'd commands)

The Pro crontab is owned by the user, edited live with `crontab -e`,
and **not version-controlled**. A reproducible script is the only way
to:

1. Document the exact transformation (the awk pipeline IS the spec).
2. Make it idempotent so a future PR-C5 rerun (e.g. after machine
   migration or crontab restore from backup) doesn't fail.
3. Provide a safety net (line-delta sanity check, rejected if
   transformation produces unexpected mass deletion).
4. Auto-snapshot before edit (`~/.crontab.backups/<UTC-ts>.cron`).
5. Keep an audit trail (`~/logs/ops/pr-c5-dead-code-disable.log`).

## Related

- Plan: `~/.claude/plans/RESUME-renaissance-2026-04-29.md` (PR-C5 row)
- Audit SSOT: `research/ops/2026-04-29-pro-automations-audit/automations-audit-2026-04-29.csv`
- Renaissance phases A/B/C predecessors: PR #358, #359, #361, #362, #364
- Constraint: lint baseline expects no `core-guardian` / `weekly-review`
  / `cron-wrapper.sh system-doctor` cron entries on Pro after this PR
