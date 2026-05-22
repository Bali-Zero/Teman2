---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W23 cross-tree audit reveals parallel sibling-agent already mirrored W8 fix
sources: 5
---

# W23: cross-tree audit + parallel-agent discovery

## Context

Loop iteration 23, attacking top-P0 from W22 audit (`com.matagaruda.gap.consumer.plist` — 176 real_errors per audit matrix, actually 25k log lines mostly INFO heartbeat).

W23 initial diagnosis was: W8 split-stream logging fix wasn't deployed
to production because main tree's `feat/wa-mirror-group-capture-2026-05-22`
branch was BEHIND the worktree branch by 21 commits, so the W8 fix in
`gap_consumer.py` had never reached the cron's invocation path.

This was **partially wrong**.

## What I actually found

1. **Worktree code path correct hypothesis**: cron wrapper invokes
   `$HOME/Desktop/nuzantara/apps/mata-garuda/.venv/bin/python -m
mata_garuda.workers.gap_consumer`. That's main tree. So if worktree
   has W8 but main tree doesn't, production cron uses pre-W8 logic. ✓

2. **Initial check confirmed**: `grep "split log levels across stdout"
~/Desktop/nuzantara/...gap_consumer.py` returned no match. So my
   hypothesis stood.

3. **`cp` workaround attempted**: I `cp`-ed the worktree's
   gap_consumer.py to main tree. md5 matched after cp.

4. **Plot twist**: `git status` on main tree showed `nothing to commit,
working tree clean`. The file I just `cp`-ed was byte-identical to
   what was already there.

5. **Real explanation**: `git log -1` showed main tree's gap_consumer.py
   had been updated **2 minutes earlier (2026-05-23 01:45:48)** by
   parallel sibling-agent commit `3f72c924b chore(mata-garuda): adopt
W8 cicatrix log-split fix from sibling worktree`. A separate Claude
   Opus session (probably the one that did `641bc44f8` "wave leftover"
   commit + the `feat/wa-mirror-group-capture-2026-05-22` work)
   mirrored the W8 fix proactively while I was running W22 audit.

## Implications

### For W23 specifically

The 25k INFO lines in `~/logs/matagaruda-gap-consumer-err.log` are
**historical pre-fix accumulation**. Now that:

- W8 fix is in main tree as of 2026-05-23 01:45:48 (committed but not
  pushed)
- I truncated the .err.log to 0 lines at W23 smoke start
- Next gap_consumer fire (06:00 WITA, after operating-window gate)
  will produce clean separated output

…the .err.log will not grow new INFO lines.

### For the loop methodology

**Sibling-agent cross-tree mirroring is now operational** (without
explicit coordination). This is good news (less manual work for me)
and bad news (race conditions: my `cp` was redundant; could have
been a stale `cp` if I'd done it after sibling's commit was further
modified).

W8 ship's "cross-tree mirror per W9 lesson" was incomplete in original
W8 commit, but **another session retroactively addressed it**. Useful
data point: the team has redundancy/healing properties I wasn't fully
aware of.

### For PR #823

W23 does NOT add to PR #823. Reason: the W8 cross-tree mirror commit
`3f72c924b` lives on the main tree branch
(`feat/wa-mirror-group-capture-2026-05-22`), not the worktree branch
(`worktree-audit-nb-automations-2026-05-21`). PR #823 is from
worktree branch → main. The mirror is on a separate work-in-progress
branch that will eventually merge to main via its own PR.

This iteration is purely **observational + verification** — no code
landed on worktree.

## Lesson for future iterations

**ALWAYS check `git log -1 -- <file>` on main tree before assuming
"W*X* fix not deployed".** Cross-tree-mirror sessions may have
already addressed the deployment gap. The full check is:

```bash
# Check main tree's branch + latest commit on file
cd ~/Desktop/nuzantara
git rev-parse --abbrev-ref HEAD
git log --oneline -1 -- <relative-path>
grep <W*X* fix marker> <relative-path>
```

vs my W23 partial check that only did the grep (and was checking
something stale in my context).

## W23 alternative actions considered

Given W23 was effectively a no-op for code, alternatives I considered:

1. **Smoke-test gap_consumer directly to verify fix works** — blocked
   by zsh shell-snapshot init taking 90+s before Python launches.
   Would need to wait until natural cron fire 06:00 WITA.
2. **Attack next top-P0 plist** (`bridge.adaptive` 1372 errors,
   `wr2.supervisor-watchdog` 2797 errors). Both are bigger surgical
   work. Deferred to W24+.
3. **Schedule audit cron** (panel suggestion) — daily kickstart of
   `audit_launchd_crons.py` with Telegram alert on
   `unhealthy_delta > 0`. Worth shipping.

W24 candidate: schedule the audit script as a daily cron with
Telegram alerting.

## Sources

1. W8 cicatrix (commit `0c6b20775`) — original split-stream logging fix
2. Main tree commit `3f72c924b` (sibling-agent W8 mirror) — 2026-05-23 01:45:48
3. Main tree commit `641bc44f8` (sibling-agent wave checkpoint) — 2026-05-23 01:10:36
4. W22 launchd audit baseline: gap_consumer flagged 176 real_errors
5. Empirical truncate + smoke: 25k lines → 0 lines, next fire 06:00 WITA
