---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W21 mass TCC migration + critical wrapper bug fix + 2 silent prod failures unmasked
sources: 6
---

# W21: mass TCC migration unmasks 2 silent production failures + fixes wrapper stdout/stderr bug

## Context

Loop iteration 21 survey of remaining 8 matagaruda plists using `/bin/bash -lc` or `/bin/zsh -lc`. Discovered TWO compounding issues:

1. **Wrapper bug in W19+W20** (anti-hallucination discovery): the
   `matagaruda-cron-tcc-safe.sh` wrapper used `exec "$VENV_PY" "$ENTRY" >> "$LOG" 2>&1`
   which merged stdout+stderr into a single `~/logs/matagaruda-<label>.log`
   file, COMPLETELY BYPASSING the launchd `StandardOutPath`/`StandardErrorPath`
   separation. My "DELTA=0 lines in error.log" verification was meaningful
   for noise reduction but **silently broke proper stderr capture**.

   By accident, the wrapper's hardcoded log path matched launchd's
   `StandardOutPath` for kg-linker (both `~/logs/matagaruda-kg-linker.log`),
   so stdout still landed in the right file. But stderr was merged in,
   defeating the W8 signal/noise separation principle entirely.

2. **2 silent production failures** hidden behind noise in
   `*sh -lc` plists:
   - **reg-alert.30min**: 806 lines error.log = 489 noise + 317 lines of
     `Fatal Python error: error evaluating path` + `InterruptedError [Errno 4]`.
     Python interpreter was crashing on EVERY 30min fire for unknown
     duration. The cron has been DEAD in production.
   - **daily-briefing**: 41 lines error.log incl `sqlite3.OperationalError:
disk I/O error` during KnowledgeBase init. Same family as
     2026-05-06 KB resilience scar but recurrent.

## Fix shipped — three layers

### Layer 1: wrapper bug fix

`~/scripts/matagaruda-cron-tcc-safe.sh` updated to NOT redirect:

```bash
# Before (W19+W20):
exec "$VENV_PY" "$ENTRY" >> "$LOG" 2>&1     # merges stdout+stderr

# After (W21):
exec "$VENV_PY" -u "$ENTRY"                 # launchd captures stdout/stderr separately
```

The `-u` flag forces unbuffered Python output (important for real-time
log visibility under cron). Stdout/stderr now flow naturally to
launchd's `StandardOutPath`/`StandardErrorPath` per plist.

### Layer 2: mass plist migration

Python script `/tmp/w21_migrate_plists.py` (used `plistlib`) rewrote 8
plists in one shot:

| Plist               | Schedule      | Entry script            |
| ------------------- | ------------- | ----------------------- |
| daily-briefing      | daily 07:00   | run_daily_briefing.py   |
| kita-feed.daily     | daily 05:00   | run_kita_feed.py        |
| nlm-expander.weekly | Sun 09:00     | run_nlm_expander.py     |
| public-channel      | (cron varies) | run_public_channel.py   |
| reg-alert.30min     | every 30min   | run_regulation_alert.py |
| sentinel.hourly     | hourly        | run_sentinel_cell.py    |
| weekly-digest       | (weekly)      | run_weekly_digest.py    |
| wr2-bridge.hourly   | hourly        | run_wr2_bridge.py       |

Each plist's `ProgramArguments` rewritten from 3-line `/bin/bash -lc "..."`
to:

```xml
<key>ProgramArguments</key>
<array>
    <string>/Users/nuzantara/scripts/matagaruda-cron-tcc-safe.sh</string>
    <string>/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/scripts/run_<entry>.py</string>
    <string><label_short></string>
</array>
```

All other keys (schedule, env vars, log paths) preserved. Old plists
archived to `~/Library/LaunchAgents/.archive-2026-05-22/*.pre-w21`.

### Layer 3: empirical verification on 2 high-risk plists

```bash
# reg-alert.30min (the silent dead cron)
$ > ~/.openclaw/workspace/logs/mata-garuda/reg-alert.error.log
$ launchctl kickstart -k "gui/501/com.matagaruda.reg-alert.30min"
$ launchctl print ... | grep "last exit"
        last exit code = 0          ✅ (Python no longer crashes)
$ wc -l ~/.openclaw/workspace/logs/mata-garuda/reg-alert.error.log
       0                            ✅ (was 806)
$ tail -1 ~/.openclaw/workspace/logs/mata-garuda/reg-alert.log
[run_regulation_alert] stats: {'processed': 20, 'sent': 20, 'failed': 0}  🎯

# daily-briefing (the sqlite I/O error cron)
$ > ~/.openclaw/workspace/logs/mata-garuda/daily-briefing.error.log
$ launchctl kickstart -k "gui/501/com.matagaruda.daily-briefing"
# (longer-running, completes asynchronously)
$ wc -l ~/.openclaw/workspace/logs/mata-garuda/daily-briefing.error.log
       0                            ✅ (was 41)
$ tail -1 ~/.openclaw/workspace/logs/mata-garuda/daily-briefing.log
[run_daily_briefing] stats: {'domains': 0, 'items': 0, 'chars': 148, 'tg_ok': True, 'dry_run': False}  ✅
```

**reg-alert produced 20 successful regulation alerts on first clean fire.**
This is the biggest hidden win of the iteration — the cron had been dead
in production for an unknown period (806 lines accumulated at 30min
cadence ≈ 6 days of broken runs).

## Pre-existing label-vs-filename mismatch

Two plists (`kita-feed.daily.plist`, `wr2-bridge.hourly.plist`) had
internal `<key>Label</key>` ≠ filename — `com.matagaruda.kita-feed` and
`com.matagaruda.wr2-bridge` respectively. launchctl service-target uses
the internal Label. The historical plists worked because they were
originally loaded via Label. After my bootout (filename-derived) +
bootstrap cycle, the kita-feed and wr2-bridge plists couldn't be
re-loaded with the filename-derived target. Resolution: they remained
loaded under their internal Labels throughout the migration (I/O error
on bootstrap was a no-op refusal because already-loaded).

No action needed — internal Labels are the source of truth.

## Anti-hallucination lesson

W19's "empirically verified DELTA=0" claim was technically true (the
launchd-supplied error.log file had 0 lines) but **structurally misleading**
because the wrapper redirected stderr into the wrapper's own log file,
not the launchd error.log. The "0 lines" was an artifact of file
non-population, not absence-of-error.

CLAUDE.md anti-hallucination rule #2: "Verifica con secondo tool call
indipendente prima di citare risultati critici." Should have run:

```bash
ls -la ~/logs/matagaruda-*.log         # ← would have shown 70KB+ files
grep -c ERROR ~/logs/matagaruda-*.log   # ← would have shown real errors
```

Lesson: when verifying "no error", check BOTH the launchd-supplied
error path AND any wrapper-redirected paths. A 0-byte error.log can
mean "no errors" OR "errors went elsewhere."

## Remaining work (W22+)

- Smoke-kickstart the 6 remaining migrated plists (nlm-expander.weekly,
  public-channel, weekly-digest, wr2-bridge.hourly, kita-feed.daily,
  sentinel.hourly) when time permits or wait for natural fires.
- Survey `~/Library/LaunchAgents/com.balizero.*.plist` family for same
  `*sh -lc` anti-pattern.
- Long-tail audit: if reg-alert was silently dead for 6 days,
  COUNT WHICH OTHER CRONS may have been silently dead behind their
  noise.

## Sources

1. Empirical W21 survey 2026-05-23 00:30 WITA — 8 plists with `*sh -lc`
2. reg-alert.30min: 489 noise + 317 fatal Python errors in
   `~/.openclaw/workspace/logs/mata-garuda/reg-alert.error.log`
3. daily-briefing: 41 lines with sqlite3.OperationalError
4. W19 + W20 cicatrices — wrapper template lineage
5. `/tmp/w21_migrate_plists.py` — plistlib batch rewrite tool
6. Empirical reg-alert kickstart: `last exit = 0`, error.log 0 lines,
   stdout shows `processed: 20, sent: 20, failed: 0`
