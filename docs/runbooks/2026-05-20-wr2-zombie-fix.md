# WR2 Supervisor Zombie Fix — 2026-05-20

**Date**: 2026-05-20 03:09–03:13 WITA
**Severity**: P0
**PR**: B1b (Phase B of Intel Lake + WR2 perfect-production plan)
**Plan**: `/Users/nuzantara/.claude/plans/vectorized-tinkering-moon.md`

---

## Trauma

Supervisor PID 83762 and watchdog PID 35922 were running with command path:

```
/Users/nuzantara/Desktop/nuzantara-deploy/apps/backend-rag/.venv/bin/python
/Users/nuzantara/Desktop/nuzantara-deploy/scripts/wr2_supervisor.py
```

But `/Users/nuzantara/Desktop/nuzantara-deploy` **DID NOT EXIST**. The deploy worktree had been removed at some point (likely manual `git worktree remove` or directory deletion). The 2 processes held deleted inodes — alive in memory, but unable to be restarted by launchd. One reboot would have caused total WR2 outage:

- supervisor stops processing `wr2_status_change` PG NOTIFY events
- watchdog cannot restart supervisor (plist `ProgramArguments` points to non-existent script)
- entire WR2 editorial carousel pipeline halts indefinitely

Detected during Phase A audit by agent A.3 (WR2 plist+log reality matrix). Confirmed empirically via `ps -p 83762 -o command` + `ls -ld /Users/nuzantara/Desktop/nuzantara-deploy → No such file or directory`.

Supervisor log `~/logs/wr2_supervisor.log` had been silent since 2026-05-19 13:04 (~14h before audit). Watchdog cooldown was masking the issue: `supervisor_down stale but cooldown active (age=49253s)` repeated for ~13.7h.

Two adjacent plists were also affected (same deploy-path issue):

- `com.balizero.wr2.plist-watchdog` — exit code 127 (script not found)
- `com.balizero.wr2.deploy-puller` — exit code 1

## Antibody (applied)

Steps executed in this order:

1. **Backup all 5 affected plists** to `~/p0-wr2-zombie-fix-2026-05-20/`:

   ```
   com.balizero.wr2.supervisor.plist
   com.balizero.wr2.supervisor-watchdog.plist
   com.balizero.wr2.deploy-puller.plist
   com.balizero.wr2.daily-metrics.plist
   com.balizero.wr2.canva-apply.plist
   com.balizero.wr2.canva-gc.weekly.plist
   com.balizero.wr2.plist-watchdog.plist
   ```

2. **Bootout the 2 zombie processes**:

   ```bash
   launchctl bootout gui/$(id -u)/com.balizero.wr2.supervisor
   launchctl bootout gui/$(id -u)/com.balizero.wr2.supervisor-watchdog
   ```

3. **Recreate the deploy worktree** on canonical branch:

   ```bash
   cd /Users/nuzantara/Desktop/nuzantara
   git worktree add /Users/nuzantara/Desktop/nuzantara-deploy deploy/main
   ```

4. **Workaround `cell-core` editable requirement issue** (auto-heal venv fails on monorepo workspace packages):

   ```bash
   rm -rf /Users/nuzantara/Desktop/nuzantara-deploy/apps/backend-rag/.venv
   ln -sf /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv \
          /Users/nuzantara/Desktop/nuzantara-deploy/apps/backend-rag/.venv
   ```

5. **Bootstrap new supervisor + watchdog**:

   ```bash
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.supervisor.plist
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.supervisor-watchdog.plist
   ```

6. **Verify new PIDs have valid CWD**:

   ```bash
   lsof -p <new_pid> | grep cwd
   # Should show: /Users/nuzantara/Desktop/nuzantara-deploy (existing dir)
   ```

7. **Restart plist-watchdog + deploy-puller** (no longer broken since deploy worktree exists):

   ```bash
   launchctl kickstart -k gui/$(id -u)/com.balizero.wr2.plist-watchdog
   launchctl kickstart -k gui/$(id -u)/com.balizero.wr2.deploy-puller
   ```

8. **Re-bootstrap 2 canva watchdogs** (label-vs-filename mismatch caused them to be "unloaded"):

   ```bash
   launchctl bootout gui/$(id -u)/com.balizero.wr2.canva-lease-watchdog
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.canva-lease-watchdog.10min.plist
   # same for canva-token-watchdog
   ```

## Post-fix state (verified)

```
Supervisor: pid=44221, state=running, runs=4, last exit=(never exited)
Watchdog:   pid=42618, state=spawn scheduled, runs=2
CWD: /Users/nuzantara/Desktop/nuzantara-deploy (exists)
Supervisor log: LISTEN wr2_status_change active, heartbeat conn open (interval=60s)
```

## Gotcha

- **The `.venv` symlink to main repo is a workaround**, not a clean fix. Long-term, the wrapper auto-heal should be enhanced to detect monorepo `cell-core` editable requirement and install it from `../../packages/cell-core` before pip install (currently fails with "not a valid editable requirement").
- **Filename-vs-Label mismatch** for `canva-lease-watchdog.10min.plist` (filename has `.10min` but Label is `canva-lease-watchdog`). Bootstrap requires the SHORT label form (`launchctl print gui/$UID/com.balizero.wr2.canva-lease-watchdog`).
- **Plist-watchdog reports exit=1 despite functional execution** (it correctly detected and bootstrapped 2 canva watchdogs). Out-of-scope micro-bug, doesn't affect production.
- **deploy/main branch is +1 commit ahead of origin/main** (`f1b18351e` vs `9912d6b5b`). The deploy worktree uses the local `deploy/main` branch which contains additional `fix(agent-library)` commits not in origin/main. Verify via `git -C /Users/nuzantara/Desktop/nuzantara-deploy log --oneline -3`.

## Rollback

If new supervisor exhibits unexpected behavior:

```bash
launchctl bootout gui/$(id -u)/com.balizero.wr2.supervisor
launchctl bootout gui/$(id -u)/com.balizero.wr2.supervisor-watchdog
# Original plists are unchanged — backup files identical to current files at:
#   ~/p0-wr2-zombie-fix-2026-05-20/
# Re-bootstrap original:
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.supervisor.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.supervisor-watchdog.plist
# (worktree may need to be removed first if going back to zombie state — but that's the bug state, don't do this unless emergency)
```

Note: rollback restores the BUG state. Only do this if the new supervisor is causing active production damage.

## Cicatrix entry

This bug is structurally identical to scar 2026-05-10 "WR2 canva-apply path coupling between deploy worktree and main repo" — same antibody pattern (worktree presence required), same trauma class (deleted/missing worktree). Append to `.claude/rules/cicatrix-scars.md` after PR-B1b merges to main.

## Verification commands (for ops)

```bash
# Quick health check anytime
launchctl print gui/$(id -u)/com.balizero.wr2.supervisor | grep -E "state|pid|last exit"
ps -p $(pgrep -f wr2_supervisor.py | head -1) -o pid,etime,command
lsof -p $(pgrep -f wr2_supervisor.py | head -1) | grep cwd
ls -ld /Users/nuzantara/Desktop/nuzantara-deploy
tail -5 ~/logs/wr2_supervisor.log
```
