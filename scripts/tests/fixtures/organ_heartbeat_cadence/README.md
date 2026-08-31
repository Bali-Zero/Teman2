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

So `test_organ_heartbeat_exceeds_poller_interval.py` reads the interval from
this fixture instead: a real plist, parsed with the real `plistlib` code
path, but living somewhere every checkout actually has it. This also sidesteps
a second tension in reading `_snapshot-live/` directly: that path's content
originates from `~/Library/LaunchAgents` (a live-machine mirror), which is
arguably itself a "live-machine read" — this fixture is 100% static git
content.

**Maintenance note**: if `com.nuzantara.launchagent-state-bridge`'s real
`StartInterval` ever changes on Pro, this fixture must be updated to match,
or the guard will reason from a stale interval. There is no automated sync
for this today (tracked as a follow-up, not solved by this PR).
