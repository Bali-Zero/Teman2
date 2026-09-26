# Wave 3 Final — owner_cashout_sync DISABLED

## Decision

Disabled `owner_cashout_sync` (Monday 01:00 weekly cron) on 2026-05-19.

## Rationale

- Antonello (owner): "lo Sheet si ferma a gennaio, siamo a maggio"
- Sheet `1OZzgvDLgf3yd9eUh5CyADjHCHLoXmE5nIRoJlut_jBE` stale 5+ months
- Service Account 403 — likely revoked because nobody noticed it was gone
- No user complaints in 5 months → not load-bearing

## Actions

1. `crontab -l` line 202 commented out with disable note (Wave 3, Sheet stale)
2. State file `owner_cashout_sync.last.json` moved to
   `~/.agent/decisions/state/.archive-2026-05-19/`
3. Script `scripts/sync_owner_cashout_fly.sh` moved to
   `scripts/.disabled-2026-05-19/sync_owner_cashout_fly.sh.disabled`
   (via `git mv`)
4. Backend code (`apps/backend-rag/backend/services/hr/owner_cashout/`)
   left in place — endpoint still works for historical queries up to
   January 2026. No DB row removed.

## Rollback

```bash
# 1. Re-enable cron
crontab -l | sed 's/^# DISABLED 2026-05-19.*: //' | crontab -

# 2. Restore script
git mv scripts/.disabled-2026-05-19/sync_owner_cashout_fly.sh.disabled \
       scripts/sync_owner_cashout_fly.sh

# 3. Restore state file
mv ~/.agent/decisions/state/.archive-2026-05-19/owner_cashout_sync.last.json \
   ~/.agent/decisions/state/

# 4. Re-share Sheet with SA + flyctl auth login (still required)
```

## Lesson learned

A cron that has been failing for 5 months without anybody noticing is
strong signal that it isn't load-bearing. Don't keep "dead but loud"
cron jobs — they pollute monitoring (sentinel escalations) and create
fake-urgency. Better: deliberate decommission with documented rollback.

Reference: research/operations/2026-05-19-wave3-sentinel-triage.md item 3C
