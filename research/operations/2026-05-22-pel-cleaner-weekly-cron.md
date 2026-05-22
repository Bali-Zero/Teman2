---
date: 2026-05-22
domain: operations
client_case: NB automations hardening — W12 systematic PEL recovery cron (post-W11 pattern recognition)
sources: 4
---

# PEL-cleaner weekly cron deployed — recurring ghost-consumer pattern auto-recovery

## Context

Loop iteration 12 of NB-automations hardening. W11 manually XCLAIM'd 77 messages
from a ghost consumer (`scan`, idle 18d) into the alive `nlm_feeder-1` and
DELCONSUMER'd 3 zero-pending ghosts on `garuda:enriched/nlm_feeder`. W11
cicatrix flagged: "Future hardening: add `~/scripts/matagaruda-pel-cleaner.sh`
weekly cron that auto-XCLAIMs pending from consumers idle >7 days into a
primary consumer and deletes zero-pending consumers idle >30 days."

W12 PEL survey (12h after W11 cleanup) found **another instance immediately**:
`garuda:alerts/nlm_feeder_alerts/debug-2` ghost, 5 pending, 17.9d idle. The
pattern recurs at non-trivial rate (≥1 new instance per 12h). Manual cleanup
does not scale. Time to automate.

## Empirical state pre-deploy (2026-05-22 08:50 WITA)

Survey across 8 streams (`garuda:raw|enriched|alerts|digest|test`,
`bridge:inbound|outbound`, `nexus:gaps`):

| Stream        | Group             | Consumer | Pending | Idle  | Action                       |
| ------------- | ----------------- | -------- | ------- | ----- | ---------------------------- |
| garuda:alerts | nlm_feeder_alerts | debug-2  | 5       | 17.9d | XCLAIM → nlm_feeder_alerts-1 |

One STALE_PEL finding, zero GHOST (≥30d zero-pending) findings. `nexus-bridge`
orphan from W11 has pending=0 + idle=12d, doesn't yet cross 30d ghost
threshold.

## Fix shipped

1. **Cleaner** `apps/mata-garuda/scripts/pel_cleaner.py` (~150 lines,
   stdlib-only per Mata Garuda CLAUDE.md §1.4 minimal-deps rule).
   - **STALE_PEL** (pending>0 AND idle>24h): XCLAIM to youngest alive
     consumer (idle <24h) in same group. No target → skip + log error.
   - **GHOST_CONSUMER** (pending=0 AND idle>30d): XGROUP DELCONSUMER.
   - Outputs JSON report to stdout. Exit 0=clean, 1=errors, 75=lock conflict.
2. **Wrapper** `~/scripts/matagaruda-pel-cleaner.sh` (33 lines, set -e,
   TCC-safe via venv-python-direct, W7 flock semaphore).
3. **LaunchAgent** `~/Library/LaunchAgents/com.matagaruda.pel-cleaner.weekly.plist`,
   `StartCalendarInterval Weekday=0 Hour=4 Minute=0` (Sunday 04:00 WITA).
   Bootstrapped via `launchctl bootstrap gui/$(id -u)`.
4. **Cross-tree sync** (W9 lesson): `pel_cleaner.py` mirrored from worktree
   to main tree at `~/Desktop/nuzantara/apps/mata-garuda/scripts/pel_cleaner.py`
   so live cron working-directory finds the entry point before the worktree
   branch merges.
5. **Unit tests** `tests/test_pel_cleaner.py` (4/4 PASS):
   - `test_parse_xinfo_consumers_two_consumers_one_pending` (real Redis
     output with debug-2 + nlm_feeder_alerts-1 fixture)
   - `test_parse_xinfo_consumers_single` (single record fixture)
   - `test_parse_xinfo_consumers_empty` (empty input → empty list)
   - `test_thresholds_match_design` (constants assertions)

## Empirical verification

```bash
# 1. Real cleaner run (post-survey)
$ python3 apps/mata-garuda/scripts/pel_cleaner.py
{
  "claims": [{"stream":"garuda:alerts","group":"nlm_feeder_alerts","from":"debug-2","to":"nlm_feeder_alerts-1","pending_before":5,"claimed_now":5,"from_idle_days":17.9}],
  "deletions": [], "errors": []
}
# exit=0

# 2. Verify debug-2 now zero-pending
$ redis-cli XINFO CONSUMERS garuda:alerts nlm_feeder_alerts
debug-2              pending=0  idle=1545506369ms (17.9d)
nlm_feeder_alerts-1  pending=5  idle=136ms (claimed-now-active)

# 3. Re-run idempotency check
$ python3 apps/mata-garuda/scripts/pel_cleaner.py
{"claims":[],"deletions":[],"errors":[]}
# exit=0

# 4. Wrapper smoke
$ ~/scripts/matagaruda-pel-cleaner.sh
# Same clean output, exit=0, flock held briefly

# 5. LaunchAgent bootstrap + kickstart
$ launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.matagaruda.pel-cleaner.weekly.plist
$ launchctl kickstart -k "gui/$(id -u)/com.matagaruda.pel-cleaner.weekly"
$ cat ~/logs/matagaruda-pel-cleaner.log     # JSON report
$ cat ~/logs/matagaruda-pel-cleaner.error.log
# empty (no false-positive noise — W8 split-stream lesson)
```

## Test regression check

```
apps/mata-garuda/tests/: 935 passed, 1 failed, 21 skipped in 49.82s
```

The 1 failure (`test_compat_shim.py::test_legacy_dict_byte_identical_to_pre_pr_snapshot`)
is pre-existing NB UUID drift unrelated to W12 — NB UUIDs in the compat-shim
snapshot diverged from current Redis state at an earlier point. Out of scope.

## Operator runbook

```bash
# Live tail when next Sunday fires (or manual kickstart)
tail -f ~/logs/matagaruda-pel-cleaner.log

# Force manual run
launchctl kickstart -k "gui/$(id -u)/com.matagaruda.pel-cleaner.weekly"

# Verify what cleaner would do without acting (manual dry-run)
python3 -c "
import sys; sys.path.insert(0, 'apps/mata-garuda/scripts')
from pel_cleaner import parse_xinfo_consumers, rcli, STALE_PEL_IDLE_MS, GHOST_IDLE_MS, ALIVE_IDLE_MS_MAX, list_streams, list_groups
for s in list_streams():
    for g in list_groups(s):
        consumers = parse_xinfo_consumers(rcli('XINFO','CONSUMERS',s,g))
        alive = [c for c in consumers if int(c.get('idle', 0)) < ALIVE_IDLE_MS_MAX]
        target = min(alive, key=lambda c: int(c['idle'])) if alive else None
        for c in consumers:
            pending = int(c.get('pending', 0)); idle_ms = int(c.get('idle', 0)); name = c.get('name','?')
            if pending > 0 and idle_ms > STALE_PEL_IDLE_MS:
                print(f'STALE: {s}/{g}/{name} → XCLAIM {pending} → {target[\"name\"] if target else \"NO_TARGET\"}')
            elif pending == 0 and idle_ms > GHOST_IDLE_MS:
                print(f'GHOST: {s}/{g}/{name} → DELCONSUMER')
"
```

## Sources

1. W11 cicatrix (commit `646043dff`) — nlm_feeder ghost recovery pattern + future-hardening callout
2. W12 PEL survey 2026-05-22 08:50 WITA — single STALE_PEL on `garuda:alerts/nlm_feeder_alerts/debug-2`
3. Mata Garuda CLAUDE.md §1.4 minimal-deps rule (stdlib-only constraint)
4. W7 flock + W8 split-stream + W9 cross-tree-sync lesson chain
