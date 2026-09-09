# Integrated validation receipt

Date: 2026-09-07 WITA. Executor: `/root/local_transport_consumer`.

Exact worktree: `/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro`.
Branch verified immediately before integration: `codex/website-pro-continuation`.
HEAD: `b740b2cc3e94b1a46c9e9811bb369289fc21ea3d`.
The whole dirty overlay includes inherited and sibling work; its contents are
not attributed to this bounded UI batch.

## Completed sequential checks

| Command | Actual result | UTC interval | Evidence |
| --- | --- | --- | --- |
| `npm --prefix apps/website test` | 56 tests, 12 files passed; exit 0; Vitest 5.23s | 19:08:27–19:08:33, September 6 | `integrated-website-tests.json`, `integrated-website-tests.log` |
| `npm --prefix apps/website run test:architecture` | 93 tests, 4 files passed; exit 0; Vitest 10.45s | 19:08:41–19:08:53, September 6 | `integrated-architecture-tests.json`, `integrated-architecture-tests.log` |
| `npm --prefix apps/website run build` | Next 16.3.1 webpack build passed, including its TypeScript phase; exit 0 | 19:09:38–19:10:12, September 6 | `integrated-build.json`, `integrated-build.log` |
| `npm --prefix apps/website run typecheck` | Separate post-build typecheck passed; exit 0; executed by `/root/magazine_producer` after delegated handoff | 19:10:56–19:10:57, September 6 | `integrated-typecheck.json`, `integrated-typecheck.log` |

The full architecture suite collected the three existing proof files plus the
new Track A proof. Its independent 46-test boundary run and 15-file stable hash
receipt are separate in `boundary-review.md` and `boundary-evidence.json`.

The build reports `/`, `/journal`, `/services`, all four service detail routes,
`/team` and the custom not-found output. There was exactly one integrated build.
Vite emitted its existing future native config-loader compatibility notice;
the ordinary tests also emitted jsdom's unsupported document navigation notice.
Both suites exited successfully. These are not browser runtime errors.

## Preview ownership and stop

Immediately before build, the listener was rediscovered and verified as one
`127.0.0.1:3100` listener, PID 12876 (`next-server (v16.3.1)`), launched by PID
12825 (`npm start`). The listener cwd was exactly this worktree's `apps/website`;
the launcher cwd was exactly this worktree. Only these verified processes were
sent SIGTERM. A separate `lsof` check confirmed port 3100 was clear before build.
Evidence: `integrated-preview-stop.json`.

`integrated-source-before.json` records hashes for 101 source/config files
immediately before the build. Its whole-worktree status count is diagnostic,
not a replacement for the previous 224-entry checkpoint's explicit manifest.

## Remaining execution handoff

After build, the separate `npm --prefix apps/website run typecheck` command was
blocked **before execution** by ORCHESTRATE-GATE. The rejection said this session
had 808 lines and no subagent dispatch in its last 300 lines. No gate override,
new subagent, repeat build or alternate command path was used. The parent was
notified to assign the remaining work to an existing execution worker.

The delegated worker subsequently reported the separate post-build typecheck
passed at `2026-09-06T19:10:56.278Z`–`2026-09-06T19:10:57.791Z`, exit 0;
log SHA-256 `6d32a87cb757acf1234ccd5182eb619acdbf1a699d686ca8fd6eb971de79e98e`.
This result is attributed to that worker and its receipt, not a second run by
this reviewer. The worker's next port-check command was also blocked before
execution. No preview was started by either worker.

At this receipt snapshot the preview is stopped. Remaining next steps are to
start one explicit loopback fixture preview, verify its new PID/cwd and noindex
header, then perform rebuilt browser and independent visual review. The parent
owns integration; later receipts must record the actual executor and timestamps.
Track A remains an unwired local HTTP proof, and this preview must continue to
use only `WEBSITE_EDITORIAL_FIXTURE=1` with the existing loader.
