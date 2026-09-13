# Flaky-test harvest reports

One markdown file per run, named `<YYYY-MM-DD>.md`, produced by `scripts/ci/flaky_harvest.py`
(Lane 5 of Zero's 2026-09-10 queue-time mandate, R4 of
`research/operations/2026-08-28-beyond-sota-ci-merge-queue-ship-pipeline.md`).

**MEASURE-ONLY.** Every report compares `tests.yml` job conclusions between a PR's
`pull_request` run and its `merge_group` (merge-queue) run(s), plus repeated queue re-entries of
the same PR head, and lists jobs whose conclusion flips with no code change — a flake candidate.
It never quarantines, skips, or disables anything. The quarantine thresholds a future tool might
apply (>= 5 failures on >= 50 runs, a 2% suite cap, an expiry window) are Zero's decision, not
this script's, and every report says so in its own header — "not applied — owner ruling
pending". Treat a report as evidence for that decision, not as an action already taken.

Generated weekly (Monday 03:30 WITA, `scripts/flaky_harvest_cron.sh`, not yet installed — see
that script's own header for the crontab line and prerequisites) and postable on demand via:

```bash
python3 scripts/ci/flaky_harvest.py
```

Raw `gh` JSON/log responses are cached under `$TMPDIR/flaky_harvest/` for the run that produced
each report — inspect that cache to see exactly what the API returned, not a reconstruction.

The delivery wire also broadcasts a one-line summary to the fleet mailbox under key
`flaky-harvest:weekly` via `scripts/fleet_mail.sh` (same argv shape as
`scripts/queue_stall_notify.py`), pointing back at the day's report file.
