# organ_heartbeat_cadence fixtures

`com.nuzantara.launchagent-state-bridge.plist` is a **verbatim, secret-free
copy** of the live LaunchAgent plist for `scripts/launchagent-state-bridge.py`,
captured 2026-08-31 (re-verified byte-identical immediately before commit).
Contains no secrets: only `HOME`/`PATH` env vars, program path, and schedule
keys — nothing matching the redaction pattern `plist_snapshot_dr.sh` enforces
for its own DR mirror.

## Why a committed copy exists here, instead of reading the live plist directly

The obvious source — `infra/launchagents/_snapshot-live/com.nuzantara.
launchagent-state-bridge.plist` — is a disaster-recovery mirror that
`.gitignore` (see the comment directly above the
`infra/launchagents/_snapshot-live/` entry) documents as living **only on the
`chore/plist-snapshot-dr` branch, ignored on every working branch**. It
physically exists on Pro's live main checkout only as an untracked side
effect of the daily `plist_snapshot_dr.sh` cron — `git worktree add` (the
mandatory pattern for every agent session, `scripts/agent_start.py`) never
materializes it, and neither does any CI checkout of `main` or a PR branch.
A test wired to that path would be permanently unable to prove GREEN outside
one specific machine's dirty disk state — verified empirically 2026-08-31
(`git ls-files` returns nothing for it; a fresh worktree lacks the file).

So the arithmetic test in `test_organ_heartbeat_exceeds_poller_interval.py`
(`test_bridge_fed_organs_declare_a_safe_multiple_of_the_poller_interval`)
reads the interval from THIS FIXTURE ONLY — never from `_snapshot-live/`,
even when that happens to be present. A real plist, parsed with the real
`plistlib` code path, living somewhere every checkout actually has it. This
also sidesteps a second tension in reading `_snapshot-live/` directly: that
path's content originates from `~/Library/LaunchAgents` (a live-machine
mirror), which is arguably itself a "live-machine read" — this fixture is
100% static git content.

Deliberately NOT a live-preferred-with-fixture-fallback design: that would
let the arithmetic test compute a DIFFERENT verdict on Pro (if `_snapshot-
live/` happened to be present and had drifted) than everywhere else, with
nothing flagging the disagreement — the same disease this guard exists to
cure, one level up.

**Staleness is an ARMED check, not an open follow-up.** The same test file
has a second test, `test_fixture_plist_matches_live_snapshot_when_present`,
that asserts this fixture is byte-for-byte identical (structurally, via
`plistlib`) to the live snapshot WHENEVER the live snapshot is present. In
practice that is only ever true on Pro's own live main checkout (an
untracked side effect of the daily `plist_snapshot_dr.sh` cron) — it SKIPS,
naming the absent path, everywhere else (CI, any fresh worktree), because
the live value simply isn't observable there. That is also the only place
drift COULD be caught: if `com.nuzantara.launchagent-state-bridge`'s real
`StartInterval` ever changes on Pro, this fixture must be updated to match
it (a normal `Edit` + commit), and the drift test will fail loudly on the
next Pro-side test run until that happens — it stays silent on any other
machine in the meantime, since there is nothing there to compare against.
