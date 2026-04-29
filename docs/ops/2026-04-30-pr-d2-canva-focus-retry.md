# PR-D2 — WR2 canva-apply focus retry envelope (2026-04-30)

Phase D (self-learning chains) of the Pro automations renaissance.
Sblocca self-learning chain #3 (canva-apply → measurer → learner-nightly).

## Bug

`scripts/wr2_canva_desktop_apply.py:_focus_claude_and_send_command`
calls `_verify_frontmost()` (line 230) **once, immediately** after
activating Claude Desktop. If iTerm2, Chrome, or any other macOS
process steals focus in the millisecond window between `tell
application "Claude" to activate` and the AppleScript `frontmost is`
read, `_verify_frontmost()` raises:

> RuntimeError: frontmost is 'iTerm2'/'Google Chrome'/..., expected 'Claude' —
> refusing to keystroke (would paste into wrong app).

The script then exits, the draft stays in `status='drafts'`, and
audit 2026-04-29 shows the cascade:

> canva-apply broken → measurer 0 posts → learner-nightly 0
> posts_considered → self-learning chain #3 ferma. Last working
> render 2026-04-26 10:10.

That's the chain that writes to cell-core genome. With it stuck, the
organism does not record skills/scars from published-post outcomes.

## Fix

Wrap `_focus_claude_and_send_command(command_text)` in a 5×30s retry
envelope at the call site (`_process_draft`):

```python
last_error: Exception | None = None
for attempt in range(1, 6):
    try:
        _launch_claude()
        _focus_claude_and_send_command(command_text)
        if attempt > 1:
            logger.info("GUI automation succeeded on attempt %d/5", attempt)
        last_error = None
        break
    except Exception as e:
        last_error = e
        logger.warning("GUI automation attempt %d/5 failed: %s", attempt, e)
        if attempt < 5:
            time.sleep(30)
if last_error is not None:
    logger.error("GUI automation exhausted 5 retries: %s", last_error)
    _send_telegram(f"WR2 Canva apply GUI failed after 5 retries: {last_error}")
    return False
```

Why this shape:

- **5 attempts**: focus theft is bursty (e.g. Slack notification, IDE
  autocomplete popup, Spotlight); a 5-attempt window of 30s gaps gives
  the user 2 minutes of "transient bad luck" tolerance before paging.
- **30s gap**: long enough for the user to see the focus moved (and
  not steal it back), short enough that 5 attempts complete inside
  the existing supervisor reschedule cadence.
- **Telegram only on final fail**: avoid the noise of per-attempt
  alerts — Zero only needs to know when intervention is required.
- **`_launch_claude()` re-called per attempt**: cheap when Claude is
  already up; brings it back if it was minimized between attempts.

The inner `_focus_claude_and_send_command` is unchanged. Its
`_verify_frontmost()` guards stay — if all 5 attempts fail the
verify check, the script still refuses to paste into the wrong app
(safety preserved).

## Out of scope

- **Migrate to Canva REST API.** The script comment (line 1-7) says
  "Canva Connect REST API doesn't support element-level text
  replacement on custom Instagram designs" — that's the architectural
  reason GUI automation exists at all. A REST migration needs Canva
  to ship the missing API or a workaround design template; out of
  scope for ops cleanup.
- **Suppress macOS focus-stealing apps.** Some apps (Slack, Karabiner,
  CleanShot) steal focus on notifications. A persistent fix would be
  `defaults write` quirks per app, but that's user-environment policy,
  not WR2 logic. Out of scope.

## Verification

- `python3 -m py_compile scripts/wr2_canva_desktop_apply.py` → OK

There is no unit test for this script (it's GUI automation, not
testable in CI). Live verification will happen on the next
canva-apply trigger after merge.

## Test plan

- [x] py_compile wr2_canva_desktop_apply.py
- [ ] (Post-merge, next supervisor kick to canva-apply) Verify in
      `~/logs/wr2_canva_desktop_apply.log` that retries actually fire
      under transient focus theft. If 5/5 succeed → only one log line
      (`Draft X rendered`). If 1-4 retries fire → `GUI automation
attempt N/5 failed: ...` followed by `succeeded on attempt N/5`.
- [ ] (Post-merge, 24-72h soak) `learner-nightly.log` should show
      `posts_considered > 0` once a successful canva-apply lands a
      post and it ages into the T+72h measurer window.

## Related

- Plan: `~/.claude/plans/RESUME-renaissance-2026-04-29.md` (PR-D2 row)
- Audit SSOT:
  `research/ops/2026-04-29-pro-automations-audit/automations-audit-2026-04-29.csv`
- Predecessors: PR #367 (C5), #368 (C3), #369 (C4), #371 (E1),
  #372 (D1), #374 (D3)
