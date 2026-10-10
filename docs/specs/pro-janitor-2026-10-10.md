# pro.janitor — a free-space keeper for Pro (2026-10-10)

Zero, 2026-10-08: Pro keeps more than 100 GB free, always. The LOCALCI lead assigned this organ on 2026-10-10 and set its
boundaries (below).

## What exists, measured on Pro (2026-10-10, read-only)

- `pro.disk_floor` (`scripts/ops/pro_disk_floor_tick.sh`, every 30 min) only observes and pages: ok above 100 GB, warning
  60–100, failed under 60. It stays the independent witness of the floor; this organ never writes its sidecar and never
  judges the floor for it (generator is not grader).
- `pro.disk_janitor` (`scripts/disk_janitor.sh`, daily, APPLY) prunes scratch, codex transcripts, log archives, the qdrant
  backups, restic and brew. Its docker and `colima fstrim` steps leave in their own PR (ruled: the VM has one owner,
  `scripts/localci/prune.py`). Its `uv cache prune` has been skipped on every run (`uv-lock-held`): the guard is
  `pgrep -x uv`, any process named `uv` alive at that minute, not the cache lock; `uv` (0.12.3) runs its own in-use check
  before pruning, and `--force` is the flag that skips it.
- Free on the Data volume: 148 GB (df -H, 2026-10-10 05:0xZ); 97 GiB before the 03:38Z reboot.
- Where the space is: `~/.colima` 41.5 GB (the VM disk), `~/.ollama` 31.2 (live: `ollama serve` with loaded models),
  `~/.nuzantara-pilots` 11.1 (local-ci state), worktrees 10.4, `~/.codex` 7.4, `~/.cache` 13.1 (`uv` 8.75, `restic` 1.82,
  `codex-runtimes` 1.60 — one runtime, in use — `puppeteer` 0.57), `~/Library/Caches` 4.2 (`ms-playwright` 1.60 in seven
  revision directories), `~/.npm` 0.8. The host caches this organ may touch hold about 10 GB; the trough that crosses the
  floor is the VM's, and it is the lead's.

## Boundaries (the lead, 2026-10-10)

- Nothing inside Colima or docker: no image, volume, builder cache, fstrim or GC policy. Never `prune.py` (it runs under the
  merger's lease and judges plans in progress): at BLACK this organ pages, it does not call it.
- Never: other agents' worktrees, checkouts, secrets or `.env*`, `~/.agent/decisions`, client data, `~/.ollama`,
  `~/.nuzantara-pilots`, `~/.claude`, `~/.codex`, anything outside the allowlist below. Never kill a process.

## Design

Every 10 minutes (launchd `StartInterval` 600, no `KeepAlive`), `/usr/bin/python3 -I` runs the payload
(`scripts/ops/pro_janitor.py`, stdlib only, Python 3.9).

**Tiers with hysteresis** (GB of 10^9 bytes, available on `/System/Volumes/Data`, as `pro.disk_floor` reads it). A tier is
entered when free space falls under its entry mark and left only at or above its exit mark (kubelet's high/low marks):

| tier  | enter under | leave at or above |
| ----- | ----------- | ----------------- |
| AMBER | 130         | 140               |
| RED   | 115         | 125               |
| BLACK | 105         | 112               |

Escalation is immediate; the way down passes each exit mark, one band at a time (RED at 132 GB is AMBER until 140). GREEN does
nothing but read and write the heartbeat. The tier is recomputed after every free-space reading, so a run escalates mid-run when
space collapses and de-escalates once it recovers; the final tier is what the state, the journal, the heartbeat and the exit code
carry.

**The allowlist** — the only things this organ removes, safest first; a rule acts when the tier is at or past its own and its
cooldown has passed; after each action the free space is read again and the run stops once it is at or above the exit mark of the
tier it acted in. BLACK adds no rule: it runs the lower ones and pages. (`uv cache clean` was dropped: a held uv cache lock is the
sign of a live uv process, and clean is not safe under it.)

| rule             | tier  | action                                                                                                                                               | cooldown |
| ---------------- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `uv-prune`       | AMBER | `uv --no-config cache prune --cache-dir ~/.cache/uv` (uv's own in-use check, never `--force`)                                                        | 6 h      |
| `npm-verify`     | AMBER | `npm cache verify --cache ~/.npm` (npm's own garbage collection; user and global npmrc set to `/dev/null`)                                           | 24 h     |
| `playwright-old` | RED   | `~/Library/Caches/ms-playwright/<family>-<rev>`: all but the newest rev of each family and all but the revisions Playwright's `.links` registry pins | 24 h     |

Tools run with exactly `HOME`, `PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin` and `LANG=C` (never the parent's
environment, so no `UV_CACHE_DIR`, `XDG_CACHE_HOME` or `npm_config_cache` decoy can redirect them), against a cache dir that is a
real directory under `$HOME` (no symlink), otherwise `skipped:root-missing-or-symlinked`. Their stdout and stderr go to
`/dev/null`; the deadline is 300 s per tool (TERM to the process group, 5 s, KILL, reap). A timeout or a failure is an error of
that rule, and the later rules still run. A grandchild that left the group is not the janitor's to kill.

**Playwright's registry pin** (the same logic as Playwright's own GC). `playwright-old` reads `<root>/.links/*`: each file (a
regular file of at most 64 KiB, opened without following a symlink) holds the absolute path of a playwright-core package dir. A
dir that does not exist (`FileNotFoundError`) is a stale link and pins nothing; any other stat error skips the rule. Otherwise
that dir's `browsers.json` (a regular file of at most 1 MiB, a JSON object whose `browsers` is a NON-EMPTY list) must be exactly
well-formed: every item a dict with `name` matching `[a-z][a-z0-9-]*` and `revision` a string of ASCII digits, and an optional
`revisionOverrides` a dict of strings to ASCII-digit strings. It pins `name.replace("-", "_") + "-" + revision` for every
browser and every override value; a pinned revision is never removed. Fail closed: a missing `.links`, an unreadable link, or any
deviation makes the rule `skipped:link-registry-unreadable` and removes nothing. An EMPTY `.links` directory (no link file at all)
means no live install, which is Playwright's own GC view, and is accepted. If `<root>/__dirlock` (Playwright's install lock)
exists the rule is `skipped:install-in-progress`. The pins and the lock are read again immediately before the removal loop: a
changed pin set is `skipped:registry-changed`, a new lock `skipped:install-in-progress`, and nothing is removed. Why: the rule as
first written would have deleted browsers pinned by live installs, measured on Pro (3 links pinning chromium-1208/1217/1243,
their headless shells, ffmpeg-1011, webkit-2359). There is no puppeteer rule: puppeteer has no registry of which project uses
which version.

A directory rule removes an entry only if: the root is a real directory (no symlink) under `$HOME`; the entry is a real directory
on the root's filesystem whose name is `<family>-<ASCII digits>` for an allowlisted family (`chromium`,
`chromium_headless_shell`, `chromium_tip_of_tree`, `firefox`, `firefox_beta`, `webkit`, `ffmpeg`, `winldd`; any other name is
never a candidate); nothing below it is a symlink that leaves it, a `.git` (any case: APFS folds it), or open; its youngest mtime
is older than 7 days; it is not pinned; and it is not the newest of its family. "Open" comes from one `lsof -w -F n +D <root>`
per rule root, capped at 16 MiB, with a canary: the janitor holds `<root>/.pro-janitor-canary-<pid>` open (`O_EXCL|O_NOFOLLOW`,
removed in a `finally`) and the canary's path must appear in the output, else `error:lsof-incomplete` and nothing is removed (a
probe that cannot run is `error:lsof-unreadable`). Open files are matched to entries by realpath prefix. Immediately before each
removal the entry is audited again (real directory, not a symlink, `realpath` unchanged, the root unchanged, same device, no
`.git`, nothing young, no escaping symlink) and only then `shutil.rmtree`d; each entry is journaled `removed` or `failed` with
its bytes, and the rule is `done` only if every candidate was removed, else `error:rmtree-partial`.

**Modes.** Dry-run by default: the run decides and journals what it would do and removes nothing (the lsof canary is the one
file it creates, and deletes). `PRO_JANITOR_APPLY=true` in the plist acts. Kill switch `PRO_JANITOR_ENABLED=false` (heartbeat
`disabled`). The node guard exits off Pro. A second run while one is alive exits: the payload takes `flock` on
`<state_dir>/lock` and exits 11 without touching state or journal (the wrapper also keeps its pidfile, and writes `warning`,
never `ok`, when it skips).

**State** (`~/.local/state/nuzantara/pro-janitor/state.json`): the tier and each rule's last-run time, written atomically
(temp file, fsync, rename). Every number must be finite (a non-finite `PRO_JANITOR_NOW` is a config error, exit 2); cooldown
stamps more than 60 s in the future are dropped. An existing but invalid `state.json` forces that tick to dry-run (no removal,
no tool run), journals `state_invalid: true`, exits 10 and rewrites the state valid.

**Journal** (`~/logs/pro-janitor/journal.jsonl`, one line per tick): ts, mode, free before and after, the previous and the final
tier, a `transition` field when the tier changed (the lead correlates these with the merger tick's journal), `tiers_seen` when
it changed mid-run, and per rule acted on: id, status (`done`, `dry-run`, `skipped:<reason>`, `error:<reason>`), the df delta,
and for directory rules the entries by name (tool cache revisions, never a user path) with their bytes and, when applied, their
`removed`/`failed` state.

**Exit codes and heartbeat** (`~/.organism/last_seen/pro.janitor.json`, written atomically): payload exit 0 is `ok` whatever the
tier; 10 (a rule error, the final tier BLACK, or an invalid state) and 11 (lock held) are `warning` (BLACK is the page: free GB,
freed GB, "the VM-side trough is localci's"); anything else is `error`; `disabled` for the kill switch or the wrong node. The
note is the payload's own `pro_janitor: ...` summary line when it is printable ASCII, otherwise `payload rc=N`; a traceback, and
the paths in it, never reach the sidecar.

## Rollout

1. The docker/fstrim removal from `disk_janitor.sh` (its own PR, first).
2. This organ, deployed dry-run; observed through at least one merger-tick trough.
3. Apply on, and `disk_janitor.sh`'s `uv cache prune` step removed (one owner per cache).

Bites (the lead): free space held above 100 GiB through a full CI-tick trough, and the journal of what it removed.
