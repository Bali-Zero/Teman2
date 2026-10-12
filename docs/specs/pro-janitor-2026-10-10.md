# pro.janitor — a free-space keeper for Pro (2026-10-10)

Zero, 2026-10-08: Pro keeps more than 100 GB free, always. Zero, 2026-10-11: lowered from 100 to 90 GB. The LOCALCI lead assigned this organ on 2026-10-10 and set its
boundaries (below).

## What exists, measured on Pro (2026-10-10, read-only)

- `pro.disk_floor` (`scripts/ops/pro_disk_floor_tick.sh`, every 30 min) only observes and pages: ok above 90 GB, warning
  60–90, failed under 60. It stays the independent witness of the floor; this organ never writes its sidecar and never
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

## Threat model and invariants (written 2026-10-10, after three council rounds)

Three rounds kept finding new orderings of the same race (audit, then unlink) because this section did not exist. It is the
arbiter: a finding is judged against it, and a change to it is a decision, not a fix.

The janitor runs as `nuzantara` on a single-user host. **In scope**, and the janitor must be safe against them:

- benign concurrent work of the same user, at any hour: Playwright installing or uninstalling (it holds `<root>/__dirlock` and
  writes `.links`), a browser launched from a revision (it holds files open, many of them mmap'd: lsof lists those as `mem` or
  `txt`, and they count as open like any other), uv and npm, and the H24 agent seats that run them — Claude Code sessions, agy,
  codex and the cron cascade;
- the janitor's own death at any point (SIGKILL, power loss): no half-written state, journal or sidecar is ever read as valid;
- untrusted content: link files, manifests, the state file, file names and numbers are input, never trusted;
- shape changes the janitor did not make: a directory that appears, vanishes, or is replaced by a symlink or another directory
  between the plan and an unlink.

**Out of scope**, stated so no reviewer has to guess:

- a hostile process of the same user. It already holds every right the janitor has and can delete the caches, or anything under
  `$HOME`, itself; no ordering of checks protects against it, and the janitor does not try;
- processes of other users and root. `lsof` without root cannot inspect them (1084 such processes on Pro, 2026-10-10); the roots
  are under the user's own `~/Library/Caches` and `~/.cache`, which no other user's process uses. A known blind spot, accepted.

The consequence, named: this organ is a hygiene tool, not a security boundary.

**Invariants**, each enforced at the moment it matters, not only by an earlier audit:

1. Every object unlinked is reached through descriptors anchored at `/` without following a symlink, so it lies under the root by
   construction.
2. The removal walk re-checks each object when it reaches it, before unlinking it: a `.git` in any case, an mtime or ctime younger
   than 7 days (a rename into the candidate refreshes the moved object's ctime), another device, or a directory whose inode is not
   the one it was opened as is left in place and the candidate is `failed:changed`.
3. The scan of open files is complete or the rule removes nothing: rc 0 or 1, the canary listed, stderr empty, and every `n` record
   an absolute path (an `n` record such as `FD info error: Operation not permitted` is a process lsof could not inspect; 0 such
   records on Pro's real root, 2026-10-10).
4. Nothing pinned by the registry, nothing open, nothing under an install lock: re-checked before each candidate.
5. No planted name, number or file makes the run crash: every such input is a skip or an error with its cause, and the journal and
   state are always written. `EPERM` or `EACCES` on an object (TCC- or SIP-protected) is a skip journaled with its cause and not
   retried within the run. `state.json` is read capped at 1 MiB and must be a regular file (else invalid); a state that cannot be
   saved (a directory in its place, a failed rename) unlinks its temp file, journals `state_unwritable: true` and exits 10.
6. **Blast radius.** The janitor's own unlinks (the directory rule) are capped per run at 10 GB and 200 000 objects (the
   measured roots hold about 1.6 GB of revisions); it stops at either cap and journals `capped`. A rate limit alone cannot bound
   one bad plan in one run. The tool rules are not the janitor's plan: `uv cache prune` and `npm cache verify` run the tool's own
   garbage collection with its own in-use checks and cannot be bounded per byte from outside; their cooldowns (6 h, 24 h) bound
   how often they run. (Decided 2026-10-10 after the conformance review: one bad plan means the janitor's.)
7. **The kill switch** (`PRO_JANITOR_ENABLED=false`, read from the environment and from `<state_dir>/disabled`, a file the operator
   can create without a plist edit) is checked before each candidate and at least once a second while a candidate is walked, so
   a stop takes effect within about a second; a candidate stopped midway is `failed:stopped`. A run stopped at its start exits
   12, which the wrapper reports as `disabled`.
8. **The janitor holds Playwright's lock while it unlinks, and proves it by a lease.** Playwright takes `<root>/__dirlock` with
   proper-lockfile: an atomic `mkdir`, judged stale (removed and taken over) once its mtime is 10 s older than the installer's
   wall clock, retried by the installer for about 10 minutes (see "Where the Playwright facts were read"). The janitor takes the
   same lock the same way before each candidate (`mkdir("__dirlock", dir_fd=root)`; `EEXIST` is `skipped:install-in-progress`).
   Ownership is never inferred from a name or an inode alone; it is a **lease** on the monotonic clock, written `lease_until`:

   - **Acquire.** `t0 = mono()` is read BEFORE the `mkdir`; then the lock is `stat`ed to record its `(st_dev, st_ino)`. If that
     `stat` returns at or after `t0 + 4 s`, the janitor cannot prove it saw its own directory: it records nothing, removes
     nothing, never `rmdir`s it, journals `skipped:lock-uncertain` and stops the rule. Otherwise `lease_until = t0 + 8 s`. Why it
     holds: our `mkdir` set the mtime at or after `t0`, so no installer can take the lock over before `t0 + 10 s`.
   - **Refresh.** A keepalive thread, holding its own `dup` of the root fd (closed by the thread itself), refreshes every 2 s:
     `t1 = mono()` BEFORE an identity `stat`; the `stat` must show our `(st_dev, st_ino)`; then `utime` by name. Only if both
     succeed AND the `utime` returned before the current `lease_until` does the lease become `t1 + 8 s`; the mtime it wrote is
     at or after `t1`. Anything else (an error, an inode other than ours, a `utime` that returned after the lease, a wall clock that moved
     more than 1 s apart from the monotonic clock since the previous refresh, since Playwright judges staleness by the wall
     clock) ends the thread, and the lease is no longer extended.
   - **Check.** Immediately before EVERY unlink and rmdir, after that object's own checks, the walk requires
     `mono() < lease_until` (else `failed:lock-stale`) and the lock still our inode (else `failed:lock-lost`). It never assumes the
     lock is held: a dead, failed or starved keepalive simply lets the lease run out, and the next check refuses.
     The check also compares the wall clock against the monotonic one since the last successful refresh (or the take), with the
     same 1 s tolerance, and a larger gap is `failed:lock-stale` at once, since Playwright judges staleness by the wall clock and a
     step of it can make the lock stale while the lease still reads valid. Release runs the same sequence: lease (and drift) valid,
     inode ours, lease valid again, only then `rmdir`.
   - **Release.** The thread is stopped and joined (5 s). The lock is `rmdir`ed only if the lease is still valid and the inode is
     ours; otherwise it is left to go stale, which Playwright handles. A keepalive still alive after the join is journaled
     `lock_thread_stuck: true` and ends the rule; it cannot touch a reused fd, since it holds its own.

   The margin is 2 s (8 s against Playwright's 10 s). An installer that arrives while the janitor holds the lock waits; one
   already holding it makes the janitor skip.

9. **A partial removal never looks installed.** Playwright treats a revision as installed when its `INSTALLATION_COMPLETE`
   marker exists, and then skips the download (see "Where the Playwright facts were read"). Removing the marker is a
   precondition of removing anything else: if a candidate has the marker, it is unlinked first, through the candidate's fd and
   under the same checks; if that fails for any reason (young, protected, `EPERM`, changed, capped, lease), the candidate stops
   at once with that cause and nothing else in it is touched. After the marker is gone, a candidate stopped midway is a
   half-deleted revision that Playwright re-downloads.

**Accounting.** The blast-radius budget (invariant 6) is reserved before each unlink, which keeps the cap conservative;
`unlinked_bytes` counts only objects whose unlink or rmdir returned success.

**Residual, accepted:** the stall between the last lease check and the unlink syscall itself: one object, and only if the
process stalls longer than the 2 s margin at that instant and an installer is installing that very revision.

**Residual, accepted:** none from the in-scope writers — the only writer of an old revision directory is a Playwright install,
which cannot run while the janitor holds `__dirlock` (invariant 8). What remains is a writer that ignores the lock, which is out
of scope. If the janitor dies holding the lock, Playwright judges it stale after 10 s and takes it over; the janitor's own next
runs skip (`skipped:install-in-progress`) until the directory is gone, and once it is older than an hour journal
`stale_dirlock: true` and exit 10, so the heartbeat shows it.

**Where the Playwright facts were read** (2026-10-10, so they can be re-checked when Playwright upgrades): playwright-core 1.63.0 `lib/coreBundle.js` (sha256 `549070af3acabb3efcc4f55bfe6210f9f7c2fcf633cf7eaa59bfe60719969171`), and `lib/server/registry/index.js` of 1.58.0 and 1.59.1 — the three versions Pro's live `.links` point to. All three take `<root>/__dirlock` with proper-lockfile (10 s stale, about 10 minutes of retries), mark an install with `INSTALLATION_COMPLETE`, and garbage-collect with `_deleteStaleBrowsers`. A Playwright upgrade that changes any of the three is a reason to re-read this section before apply stays on.

**Residual, accepted (decided 2026-10-10):** a browser launched by its path from an unpinned revision in the instant between the
last look and the unlinks. Browsers take no lock, so no lsof-based design closes that window. Playwright's own garbage collection
(`_deleteStaleBrowsers`, run by every `install` under the same lock) removes every revision no link uses, with no open-file check
and no age floor; this organ removes a subset of that set (older than 7 days, not the newest of its family, not open at the last
look). The consequence is one failed automation run and a re-download.

**Freed space is the filesystem's word.** The journal records, beside the bytes unlinked, the free-space delta of the Data volume
(`statvfs` before and after each action): APFS local snapshots keep unlinked blocks until they are thinned, so unlinking 1 GB can
free nothing, and the journal must show which happened.

## Design

Every 10 minutes (launchd `StartInterval` 600, no `KeepAlive`), `/usr/bin/python3 -I` runs the payload
(`scripts/ops/pro_janitor.py`, stdlib only, Python 3.9).

**Tiers with hysteresis** (GB of 10^9 bytes, available on `/System/Volumes/Data`, as `pro.disk_floor` reads it). A tier is
entered when free space falls under its entry mark and left only at or above its exit mark (kubelet's high/low marks):

| tier  | enter under | leave at or above |
| ----- | ----------- | ----------------- |
| AMBER | 120         | 130               |
| RED   | 105         | 115               |
| BLACK | 95          | 102               |

Escalation is immediate; the way down passes each exit mark, one band at a time (RED at 122 GB is AMBER until 130). GREEN does
nothing but read and write the heartbeat. The tier is recomputed after every free-space reading, so a run escalates mid-run when
space collapses and de-escalates once it recovers; the final tier is what the state, the journal, the heartbeat and the exit code
carry.

**The allowlist** — the only things this organ removes, safest first; a rule acts when the tier is at or past its own and its
cooldown has passed; after each action the free space is read again and the run stops once it is at or above the exit mark of the
tier it acted in. BLACK adds no rule: it runs the lower ones and pages. (`uv cache clean` was dropped: a held uv cache lock is the
sign of a live uv process, and clean is not safe under it.)

| rule             | tier  | action                                                                                                                                                | cooldown |
| ---------------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `uv-prune`       | AMBER | `uv --no-config cache prune --cache-dir ~/.cache/uv` (uv's own in-use check, never `--force`)                                                         | 6 h      |
| `npm-verify`     | AMBER | `npm cache verify --cache ~/.npm` (npm's own garbage collection; user npmrc `/dev/null`, global `/var/empty/pro-janitor-npmrc`, never one file twice) | 24 h     |
| `playwright-old` | RED   | `~/Library/Caches/ms-playwright/<family>-<rev>`: all but the newest rev of each family and all but the revisions Playwright's `.links` registry pins  | 24 h     |

Tools run with exactly `HOME`, `PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin` and `LANG=C` (never the parent's
environment, so no `UV_CACHE_DIR`, `XDG_CACHE_HOME` or `npm_config_cache` decoy can redirect them), against a cache dir that is a
real directory under `$HOME` (no symlink), otherwise `skipped:root-missing-or-symlinked`. Their stdout and stderr go to
`/dev/null`; the deadline is 300 s per tool. Past it the janitor sends TERM to the tool's process group and gives the WHOLE
group 5 s, polling `killpg(pgid, 0)` until it no longer succeeds; then KILL to the group; and only then reaps the leader. The
leader is never reaped (no `poll`, `wait` or `send_signal`) before the last `killpg`, so its un-reaped zombie holds the pid and
with it the group id: the KILL reaches the tool's own group or nobody, never a group that reused the id (measured on macOS
Python 3.9, 2026-10-11: `os.waitid` is absent and `WNOWAIT` is refused by `waitpid`, so holding the zombie is the mechanism).
A timeout or a failure is an error of
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

A directory rule removes an entry only if: the root is a real directory (no symlink) under `$HOME`; the entry is a real directory on the root's filesystem whose name is `<family>-<ASCII digits>` for an allowlisted family (`chromium`, `chromium_headless_shell`, `chromium_tip_of_tree`, `chromium_tip_of_tree_headless_shell` (named by Pro's `browsers.json`), `firefox`, `firefox_beta`, `webkit`, `ffmpeg`, `winldd`; any other name is never a candidate); nothing below it is a symlink that leaves it, a `.git` (any case: APFS folds it), or open; its youngest mtime is older than 7 days; it is not pinned; and it is not the newest of its family. "Open" comes from one `lsof -F n +D <root>` (never `-w`) per rule root, capped at 16 MiB, with a canary: the janitor holds `<root>/.pro-janitor-canary-<pid>-<16 hex>` open, a name unique to the run (created `O_EXCL|O_NOFOLLOW` relative to the anchored root fd and unlinked through it in a `finally`) and the scan is complete iff rc is 0 or 1, the canary's path appears in the output, and stderr is empty (stderr is read capped at 64 KiB, tested and never journaled or printed: it carries paths); anything else - a stderr warning, no canary, another rc, a timeout, an oversized stdout or stderr - is `error:lsof-incomplete` and nothing is removed (a probe that cannot be started is `error:lsof-unreadable`). Measured on Pro, 2026-10-10, lsof 4.91: with `+D` every file under the dir is a search target and any file that is not open makes lsof exit 1, so rc 1 is the normal healthy result (a temp dir with an open canary: rc 1, canary listed, stderr empty; the real ms-playwright root: rc 1, 30 open-file lines, stderr empty); an incomplete scan shows only on stderr, and only without `-w` (a dir with an unreadable subdir: rc 1, one `can't opendir ... Permission denied` line). Open files are matched to entries by realpath prefix. Removal is fd-anchored and never resolves a pathname after the plan. At plan time the `(st_dev, st_ino)` of the root and of each candidate is recorded. To remove, the root is opened by walking from `/` one component at a time with `O_NOFOLLOW` (no ancestor can be a symlink at open time) and must be the recorded inode; each candidate is opened `O_NOFOLLOW|O_DIRECTORY` relative to that fd and must be the recorded inode on the root's device. It is audited through the fd (no `.git` in any case, nothing younger than 7 days, no other device, depth-bounded), emptied by a fd-relative recursion (`stat`/`open`/`unlink`/`rmdir` with `dir_fd`; a symlink is unlinked itself, never its target; another device is never entered) and removed with `rmdir(dir_fd)`; `shutil.rmtree` on a path is not used. Without `dir_fd` support the rule is `skipped:no-fd-support`. Immediately before EACH candidate the last look repeats: lsof again (canary held, same completeness rule), then `__dirlock`, then the pins; a candidate now open, pinned or under an install lock is journaled `skipped:open`, `skipped:pinned-late` or `skipped:install-in-progress` and the loop goes on. Each entry is journaled `removed`, `failed:<cause>` (cause one of `changed`, `lsof-incomplete`, `root-changed`, `vanished`, `enotempty`, `eperm`, `lock-lost`, `lock-stale`, `capped`, `stopped`) or one of those skips, with its bytes; the rule is `error:rmtree-partial` if any entry failed, else `done` if any was removed. At the start of an applied run, stale canaries of ours (regular, zero bytes, exactly `.pro-janitor-canary-<digits>-<16 hex>`, pid gone per `kill(pid, 0)`, nothing ever signalled) are swept through the anchored root fd; a canary whose pid is alive is left, and since every run's name is unique it can never block a later run.

**Modes.** Dry-run by default: the run decides and journals what it would do and removes nothing (the lsof canary is the one file it creates, and deletes). `PRO_JANITOR_APPLY=true` in the plist acts. Kill switch `PRO_JANITOR_ENABLED=false` (heartbeat `disabled`). The node guard exits off Pro. A second run while one is alive exits: the payload takes `flock` on `<state_dir>/lock` and exits 11 without touching state or journal (the wrapper also keeps its pidfile, and writes `warning`, never `ok`, when it skips).

Input the janitor cannot resolve is a skip or an error with its cause, never a crash: a candidate whose audit cannot resolve a path (a symlink chain too deep, a link that vanished mid-resolution) is ineligible and journaled `skipped:audit-error`; an `lsof` path that cannot be resolved is `error:lsof-unreadable`; and any other unexpected exception is never a crash either. Inside a directory rule's candidate loop it ends that candidate as `failed:internal` and stops the loop: the entries already decided, their bytes, `unlinked_bytes` and the free-space delta are journaled as for any stop, and the rule is `error:rmtree-partial` if anything was removed, else `error:internal`. Anywhere else in a rule it is the rule's `error:internal`. Either way there is no traceback and no path, the later rules still run, the journal and state are written, and the exit is 10. An `error:internal` of a rule that acted in apply mode is an attempted action: its cooldown is stamped and the free space is read again after it, as for any other action. `skipped:audit-error` entries are journaled on every path out of the rule, including its early returns (an lsof error, an install lock, a changed registry). If the keepalive thread cannot be started, the lock just taken is removed within its lease and the rule is `error:internal`; `release()` never joins a thread that did not start.

A cooldown is stamped on an attempted action even when it failed (`error:rc=`, `error:timeout`, `error:rmtree-partial`, `error:internal` in apply mode): that is anti-thrash, and the next attempt waits for the cooldown instead of hammering a broken tool every ten minutes. Pins and candidate revisions are compared numerically as `(family, int(revision))`, so `01100` protects `chromium-1100`.

**State** (`~/.local/state/nuzantara/pro-janitor/state.json`): the tier and each rule's last-run time, written atomically (temp file, fsync, rename). Every number must be finite (a non-finite `PRO_JANITOR_NOW` is a config error, exit 2); cooldown stamps more than 60 s in the future are dropped. An existing but invalid `state.json` forces that tick to dry-run (no removal, no tool run), journals `state_invalid: true`, exits 10 and rewrites the state valid. Every timestamp must be a finite number in [0, 4e9] (a JSON integer such as `10**400` is invalid, not an exception). The state dir must be a real directory under `$HOME` (else exit 1, `state dir unusable`); the temp file is created `O_EXCL|O_NOFOLLOW` under a random name, fsynced, renamed, and the directory fsynced. The lock is `flock`: contention is exit 11, any other error exit 1 (`lock unusable`).

**Journal** (`~/logs/pro-janitor/journal.jsonl`, one line per tick): ts, mode, free before and after, the previous and the final
tier, a `transition` field when the tier changed (the lead correlates these with the merger tick's journal), `tiers_seen` when
it changed mid-run, and per rule acted on: id, status (`done`, `dry-run`, `skipped:<reason>`, `error:<reason>`), the df delta,
and for directory rules the entries by name (tool cache revisions, never a user path) with their bytes and, when applied, their
`removed`/`failed` state.

**Exit codes and heartbeat** (`~/.organism/last_seen/pro.janitor.json`, written atomically): payload exit 0 is `ok` whatever the tier; 10 (a rule error, the final tier BLACK, or an invalid state) and 11 (lock held) are `warning` (BLACK is the page: free GB, freed GB, "the VM-side trough is localci's"); anything else is `error`; `disabled` for the kill switch or the wrong node. The note is the payload's own `pro_janitor: ...` summary line when it is printable ASCII, otherwise `payload rc=N`; a traceback, and the paths in it, never reach the sidecar. A free-space read that fails after an action stops all further actions, is journaled `free_read_failed: true` with `free_gb_after` null, and exits 10, never 0.

## Rollout

1. The docker/fstrim removal from `disk_janitor.sh` (its own PR, first).
2. This organ, deployed dry-run; observed through at least one merger-tick trough.
3. (this PR: `infra/janitor-apply-1012`) Apply on, and `disk_janitor.sh`'s `uv cache prune` step removed (one owner per cache).

Bites (the lead): free space held at or above 90 GB (decimal, as this spec measures) through a full CI-tick trough, and the journal of what it removed.
