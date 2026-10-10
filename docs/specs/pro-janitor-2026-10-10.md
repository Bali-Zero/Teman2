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

Escalation is immediate; the way down passes each exit mark. GREEN does nothing but read and write the heartbeat.

**The allowlist** — the only things this organ removes, safest first; a rule acts when the tier is at or past its own and its
cooldown has passed; after each action the free space is read again and the run stops once it is at or above the current
tier's exit mark:

| rule             | tier  | action                                                                                                                                               | cooldown |
| ---------------- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `uv-prune`       | AMBER | `uv cache prune` (uv's own in-use check, never `--force`)                                                                                            | 6 h      |
| `npm-verify`     | AMBER | `npm cache verify` (npm's own garbage collection)                                                                                                    | 24 h     |
| `playwright-old` | RED   | `~/Library/Caches/ms-playwright/<family>-<rev>`: all but the newest rev of each family and all but the revisions Playwright's `.links` registry pins | 24 h     |
| `uv-clean`       | BLACK | `uv cache clean` (in-use check kept; everything re-downloadable)                                                                                     | 6 h      |

**Playwright's registry pin** (the same logic as Playwright's own GC). `playwright-old` reads `<root>/.links/*`: each file holds
the path of a playwright-core package dir; a link whose dir is gone is stale and pins nothing; otherwise that dir's `browsers.json`
pins `name.replace("-", "_") + "-" + revision` for every listed browser and for every value of its `revisionOverrides`. A pinned
revision is never removed. Fail closed: a missing `.links`, an unreadable link file, or an existing package dir with an unreadable
or malformed `browsers.json` makes the rule `skipped:link-registry-unreadable` and removes nothing. Why: the rule as first written
would have deleted browsers pinned by live installs, measured on Pro (3 links pinning chromium-1208/1217/1243, their headless
shells, ffmpeg-1011, webkit-2359). There is no `puppeteer-old` rule: puppeteer has no registry of which project uses which
version, and Pro holds one version, so it would gain nothing.

A directory rule removes an entry only if: the root is a real directory (no symlink) under `$HOME`; the entry is a real
directory on the root's filesystem, matching the rule's name pattern; nothing below it is a symlink that leaves it, a `.git`,
or open (`lsof +D` on the root, once; an unreadable probe skips the rule); its youngest mtime is older than 7 days; and it is
not the newest of its family. Every tool runs under a deadline (TERM, then KILL); a timeout or a failure is an error of that
rule, and the later rules still run.

**Modes.** Dry-run by default: the run decides and journals what it would do and removes nothing. `PRO_JANITOR_APPLY=true` in
the plist acts. Kill switch `PRO_JANITOR_ENABLED=false` (heartbeat `disabled`). A second run while one is alive exits
(`flock`). The node guard exits off Pro.

**Journal** (`~/logs/pro-janitor/journal.jsonl`, one line per tick): ts, mode, free before and after, the previous and the new
tier, a `transition` field when the tier changed (the lead correlates these with the merger tick's journal), and per rule
acted on: id, status (`done`, `dry-run`, `skipped:<reason>`, `error:<reason>`), the df delta, and for directory rules the
removed entries by name (tool cache revisions, never a user path) with their bytes.

**Heartbeat** (`~/.organism/last_seen/pro.janitor.json`): `ok` when the tick ran without a rule error, whatever the tier;
`warning` on a rule error or at BLACK (the page: free GB, freed GB, "the VM-side trough is localci's"); `disabled` for the
kill switch or the wrong node.

## Rollout

1. The docker/fstrim removal from `disk_janitor.sh` (its own PR, first).
2. This organ, deployed dry-run; observed through at least one merger-tick trough.
3. Apply on, and `disk_janitor.sh`'s `uv cache prune` step removed (one owner per cache).

Bites (the lead): free space held above 100 GiB through a full CI-tick trough, and the journal of what it removed.
