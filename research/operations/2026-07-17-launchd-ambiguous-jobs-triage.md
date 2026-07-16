---
date: 2026-07-17
domain: operations
client_case: none
sources:
  - "scripts/launchd_liveness_detector.py (PR #1518, cicatrix W84)"
  - "scripts/tests/test_launchd_liveness_exit_status_decode.py, test_launchd_liveness_stale_exit_recovery.py, test_launchd_liveness_marker_freshness.py, test_launchd_liveness_ours_scope.py"
  - "live `launchctl list` / `launchctl print` on Pro, 2026-07-17"
  - "live log tails: ~/logs/*, ~/.cache/nuzantara-drive-sync/*, ~/.openclaw/workspace/logs/war-room-v2/*"
  - "infra/launchagents/*.plist (repo-tracked) + ~/Library/LaunchAgents/*.plist (live, incl. .bak-tcc-20260716 diffs)"
  - "infra/launchagents/wrappers/{regulatory-watcher-run.sh, audit-launchd-daily.sh, matagaruda-redis-split-brain-check.sh, lib/trampoline.sh}"
  - "scripts/lib/heartbeat.{sh,py}, scripts/tg_notify.py"
adversarial_review: codex
---

# Arming `launchd_liveness_detector.py` + triage of 10 launchd jobs with non-zero last-exit (Pro, 2026-07-17)

## Mandate

LANE D (Fleet Infra / Immune), rush production-ready. Two linked findings from the prior TAC:

1. `scripts/launchd_liveness_detector.py` (the tool that cross-references a job's launchd exit
   code against its actual LOG CONTENT to catch the W84 "green-but-TCC-dead" vector) has 4 test
   suites but **zero attachment to crontab/launchctl/plist** — it has never run automatically.
2. ~10-12 launchd jobs on Pro have `last-exit != 0` never disambiguated log-by-log: is the
   non-zero exit an honest, by-design signal, or a real crash?

This note GROUNDs the detector, ships the wrapper+plist to arm it (**not installed** — see
PENDING-ARMS), and answers (2) for the 10 named jobs with real log evidence, verified in this
session (not the detector's own narrow verdict field alone — see §Detector coverage vs this
triage's depth).

## GROUND — how the detector works today

`scripts/launchd_liveness_detector.py` (461 lines, stdlib-only):

- `audit()` (line 351) globs `~/Library/LaunchAgents/*.plist`, filters to `OURS_RE` (line 74),
  and for each job: reads `launchctl list <label>` (decoding the raw POSIX wait-status via
  `_decode_wait_status`, line 116 — a plain `exit 1` shows up as raw `256`, a signal death
  unshifted), extracts `StandardOutPath`/`StandardErrorPath` from the plist (falling back to
  `launchctl print` if the plist XML is malformed), and checks the log tail for a
  launch-failure marker (`_log_has_failure_marker`, line 227 — "operation not permitted",
  `getcwd: cannot access parent directories`, `bad interpreter`, or a `sh: <path>: <reason>`
  shape) gated to the last `MARKER_FRESH_SEC` (default 48h, line 87) so a **cured** job's stale
  error tail stops being reported dead once it stops recurring.
- `_classify()` (line 312) crosses `exit_code x marker x process_uptime` into one of 6 verdicts:
  `DEAD-GREEN` (exit 0 + marker — the W84 vector itself), `DEAD-NONZERO` (marker + non-zero),
  `RECOVERED` (non-zero but the PID has been alive > `UPTIME_STABLE_SEC` with no marker — the
  exit code is a sticky historical artifact), `FAILING-HONESTLY` (non-zero, no marker, not
  recovered), `ARMED-TO-NOTHING` (plist points at a missing program), `OK`.
- `main()` prints a table or `--json`, and **only sends anything** with `--alert` (own
  `_send_telegram()`, reads `~/.nuzantara-secrets.env` directly — this pre-dates the
  `tg_notify.py` gateway consolidation and is a separate code path from what the new wrapper
  uses; left untouched, out of this change's scope).
- **The script itself writes nothing to disk** — no heartbeat, no state file. The wrapper (new,
  this PR) owns the heartbeat sidecar and the P0 alert-on-alarm, per the mandate.

### Discovery: `OURS_RE` was blind to `com.matagaruda.*` — 3 of the 10 named jobs

`scripts/launchd_liveness_detector.py:74` (before this PR):
`OURS_RE = re.compile(r"\b(nuzantara|balizero)\b", re.IGNORECASE)`.

Live-verified this session: `com.matagaruda.redis-split-brain.check`,
`com.matagaruda.pipeline-health.hourly`, and `com.matagaruda.kg-query-api` are all real, loaded
LaunchAgents, tracked in `infra/launchagents/` — but none match `nuzantara` or `balizero` as a
substring, so `audit()` silently skipped all three. Confirmed empirically (`OURS_RE.search()` on
the three live labels returned `False` pre-fix) and via `python3 scripts/launchd_liveness_detector.py
--json`, which omitted all three from `findings` entirely (not even classified — invisible).

Mata Garuda is the same organism (same repo, same `infra/launchagents/` directory, same "ours"
intent the comment above the regex states) — this is an oversight, not a deliberate exclusion,
and one of the three (`kg-query-api`, see below) turned out to be a real, severe, currently-active
crash loop this detector would never have surfaced. **Fixed in this PR**: `OURS_RE` now includes
`matagaruda` (word-boundary, not bare-substring — verified against Apple/Homebrew/Google/OpenClaw
noise labels to confirm no new false-positives), with a new guilt+innocence test suite
(`scripts/tests/test_launchd_liveness_ours_scope.py`, 4 tests) added alongside the existing 3.
All 30 tests (26 existing + 4 new) pass under `apps/backend-rag/.venv`.

### Detector coverage vs. this triage's depth (a limitation worth flagging, not fixed here)

The detector's marker set is deliberately narrow — it exists to catch the **TCC/launch-denial**
vector specifically, not to be a general "is this job's output pathological" analyzer. All 10
jobs below classify as `FAILING-HONESTLY` under the detector's own logic (no TCC marker, so
correctly "not the W84 vector") — that verdict is **necessary but not sufficient** to answer
"is this a real bug". Answering that required reading each job's actual log content by hand,
which is what §Triage below does. Two of the ten (`ig-metrics-analyst.weekly`,
`domain-mesh.foundations.daily`) additionally revealed a **second, structural** blind spot: their
wrappers redirect all real diagnostic output to a script-internal log path (e.g.
`~/logs/wr2-ig-metrics-analyst.log`, rotated by date), while the plist's own
`StandardOutPath`/`StandardErrorPath` — the ONLY paths `_log_paths()` ever reads — stay at 0
bytes forever. The detector is structurally blind to these jobs' real content; only the exit
code (via `launchctl list`) is visible to it. This is a real gap but a nontrivial one to close
(it would need a per-job "real log path" registry, not a regex), and is out of scope for this
wrapper+triage change — flagged here as a candidate follow-up, not fixed.

## What was built (this PR) — NOT installed

- `infra/launchagents/wrappers/launchd-liveness-detector.sh` — trampoline (shared
  `infra/launchagents/wrappers/lib/trampoline.sh`, same pattern as
  `matagaruda-redis-split-brain-check.sh`/`audit-launchd-daily.sh`) → runs the detector
  `--json` (read-only: `launchctl list`/`print` + log tails, no launchd mutation) → writes an
  organism heartbeat (`scripts/lib/heartbeat.sh` convention) to
  `~/.organism/last_seen/pro.launchd_liveness.json` (`ok` / `degraded` / `error`) → on real
  alarms (`DEAD-GREEN`/`DEAD-NONZERO`/`ARMED-TO-NOTHING`/`NOT-LOADED`) sends ONE P0 via the
  already-wired `scripts/tg_notify.py --tier p0` gateway (same mechanism
  `matagaruda-redis-split-brain-check.sh` already uses — no new channel invented). Propagates
  the detector's own exit code (matches the fleet's established "HONEST-nonzero-by-design"
  convention rather than swallowing it to 0).
- `infra/launchagents/com.nuzantara.launchd-liveness-detector.daily.plist` — `StartCalendarInterval`
  08:15 (after the bulk of the other daily crons have produced fresh log content),
  `KeepAlive=false` + one-shot (superscar #7: `KeepAlive=true` on a one-shot causes a
  restart-storm), `RunAtLoad=false`, Pro-only (per-host state; a Mini copy would need its own
  instance — superscar #10 active-active).
- `infra/home-fork/declared-pairs.json` — pre-emptively declared the future
  `~/scripts/launchd-liveness-detector.sh` HOME-fork pair so `lint_home_fork.py --discover`
  won't flag it as undeclared once installed.
- Verified end-to-end **in this session** (read-only + `TG_DRY_RUN=1`, artifacts removed after
  capture per confine "work only in your worktree"): wrapper ran against the real live fleet,
  correctly wrote the heartbeat (`status=degraded`, `note="3 alarm(s)..."`), correctly logged the
  full JSON, correctly exercised the `tg_notify.py` P0 code path in dry-run (visible in
  `~/.organism/tg_spool/sent-dry.jsonl`, no live send), exited 1 (honest — 3 real alarms found:
  `com.balizero.agent-library-evolver.daily/weekly` + `com.balizero.l5-2-phase2b-trigger`, all
  `NOT-LOADED` — unrelated to the 10 named jobs in this mandate, pre-existing).

**Not installed**: plist install (`cp` to `~/Library/LaunchAgents/` + `launchctl load` +
wrapper HOME-fork copy to `~/scripts/`) is `operator[control-plane]` per the task's hard
confines. See PENDING-ARMS.

## Triage — the 10 named jobs

Verdict legend: **HONEST/design** = the job's own contract is "exit non-zero to report a real
finding" (a health-checker doing its job) · **HONEST/external** = real failure, but an external
dependency (quota/network), not our bug · **REAL-CRASH** = a genuine bug in our code (exception,
hang, data defect) that needs an engineering fix · **INCONCLUSIVE** = evidence insufficient to
close out with certainty.

| # | Label | Last exit (decoded) | Verdict from log | Evidence | Action |
|---|---|---|---|---|---|
| 1 | `com.matagaruda.redis-split-brain.check` | 1 | **HONEST/design** | `matagaruda-redis-split-brain-check.sh:11-17`: "We do NOT translate exit 1 -> 0... should reflect split-brain active". Log shows structured `{"tag":"redis-split-brain","stream":...,"drift_h":380-450}` WARNINGs — a real, currently-active Pro↔Mini redis stream drift (~16-19 days), correctly reported. | None for the checker. Separately escalate the underlying drift to the Mata Garuda lane (not this lane). |
| 2 | `com.matagaruda.pipeline-health.hourly` | 1 | **HONEST/design** | `~/logs/matagaruda-pipeline-health.log`: clean structured JSON, `"verdict":"YELLOW"`, `"findings":["scorer not draining: lag=832..."]`. No traceback anywhere in the tail. | None — working as intended. |
| 3 | `com.matagaruda.kg-query-api` | 1 | **REAL-CRASH (severe, active)** | `~/logs/mata-garuda-kg-api.err` (112MB): `OSError: [Errno 49] Can't assign requested address` at `apps/mata-garuda/mata_garuda/api/kg_query.py:235` (`socketserver.TCPServer.server_bind`). `infra/launchagents/com.matagaruda.kg-query-api.plist` sets `KG_API_BIND=100.93.236.6` — **Mini's** Tailscale IP — but this exact plist is installed and `KeepAlive`-respawning under `~/Library/LaunchAgents/` on **Pro** (confirmed live: `hostname`=`Nuzantara`, Pro's own Tailscale IP is `100.107.22.111` via `ifconfig utun`, NOT `100.93.236.6`). `ThrottleInterval=15` respawns it every ~15s; **73,961** occurrences of "Errno 49" counted in the error log at adversarial-review time (~13+ days of continuous crash-loop, count still climbing since the original count). Confirmed the bind value is baked into the repo-tracked plist (not live-drift — diffed against `.bak-tcc-20260716`, whose only delta is the `~/Desktop` path fix). **CORRECTED after adversarial review**: per `docs/symbiosis/W2-kg-bridge-runbook.md` (topology diagram + install instructions), `com.matagaruda.kg-query-api` is architected as a **Mini-only singleton** — Pro is meant to be a remote *consumer* (`apps/nuzantara-mcp` → `httpx` → `http://100.93.236.6:8990`), never a second host of the server. Live-verified this session: Mini's real instance answers healthy right now (`curl http://100.93.236.6:8990/health` → `{"ok": true, "kg_path": "/Users/nuzantara/.agent/mata-garuda/kg.db", "schema_ok": true, "entities_count": 409, ...}`). So this is a **stray duplicate install on Pro**, not "the singleton that needs its bind redirected." | **Escalate P1** to whoever owns Mata Garuda — but the original draft of this Action was itself wrong and has been corrected: do **NOT** "fix `KG_API_BIND` to Pro's own bind address/interface, then reload" — that would stand up a second, independent kg-query-api instance on Pro (cicatrix superscar #10 active-active split-brain risk: two servers, potentially divergent SQLite state, both claiming to be *the* KG query API). The correct fix is `launchctl unload` + remove `~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist` from **Pro only** — Mini's copy is correct and stays. Out of Lane-D scope (different app, not named in this mandate's deliverables). |
| 4 | `com.balizero.wr2.image-generator` | 1 | **INCONCLUSIVE (leans HONEST)** | 526KB `.err.log` (stdout is unused — Python `logging` defaults to stderr). **CORRECTED after adversarial review**: the "zero tracebacks anywhere" claim below was FALSE — the file contains 4 real tracebacks, all old (2026-05-07 `BrowserType.launch_persistent_context` 180s timeout, 2026-05-13 missing headless-shell executable, 2026-05-19 x2 `No module named 'playwright'`), all Playwright/browser-launch environment issues ~2 months before this triage, none in the recent window. The 07-15/07-16 window itself is genuinely traceback-free: only graceful-degradation WARNINGs (`VLM scoring failed: timed out — accepting image`). Repeated `Done: 0/1 drafts imaged` across many hourly ticks on 07-15, then `Done: 2/2 drafts imaged` + `No drafts in 'drafts' status to process` (looks clean) at 05:39-05:40 on 07-16 — the LAST visible log activity, ~20h before this triage, looks like a clean completion, yet `last_exit=1` is what launchd currently reports. No plist `StartInterval`/`StartCalendarInterval`/`RunAtLoad`/`KeepAlive` key exists at all (event-triggered externally, not launchd-scheduled), so I cannot correlate the recorded exit to a specific dated invocation with certainty. Net effect of the correction: INCONCLUSIVE still holds (if anything slightly reinforced — this job has a real history of hard crashes, just not evidenced as current), but the "no tracebacks, period" framing was an overstatement. | Capture the next live invocation's exit code together with its log tail to close this out definitively — static log analysis alone is insufficient here (documented, not guessed). |
| 5 | `com.balizero.wr2.ig-metrics-analyst.weekly` | -15 (SIGTERM) | **REAL-CRASH (hang, killed)** | The plist-declared logs are a red herring: both empty (0 bytes) since creation 18 days ago. The wrapper's OWN internal log (`~/logs/wr2-ig-metrics-analyst.log`, set at `infra/launchagents/wrappers/wr2-ig-metrics-analyst-run.sh:37`) shows the 2026-07-12 22:07:05 run logging `starting` + `published-with-metrics count: 45` and then **nothing else** — no `done`, no error, no amendment file — for 5 days until now. Matches the launchd-recorded SIGTERM exactly: the run hung and had to be killed. | Investigate what step follows the "published-with-metrics count" log line (likely an `agy`/Gemini health-check or Sonnet call with no timeout) and add one. |
| 6 | `com.nuzantara.verify-the-verifiers` | 1 | **HONEST/design**, with a real environment bug behind the current finding | Fresh `.out.log` (today): `DISARMED: scar_W95_rh_linter_async ... ModuleNotFoundError: No module named 'pytest' ... VERDICT: RED (1 gate(s) DISARMED)` — the meta-verifier's contract is "exit non-zero when any gate reports disarmed", which is intentional. But the root cause is an env gap (whatever interpreter runs the `scar_W95` regression test lacks `pytest`), likely a false-positive gate-disarm (test harness broken, not necessarily the underlying guard). The `.err.log` content (`~/Desktop/nuzantara-deploy/...: No such file` + `No space left on device`) is 13 days stale and correctly ignored by the detector's own `MARKER_FRESH_SEC` gate (verified: `marker=None`). | Fix the interpreter used for `scar_W95_rh_linter_async` to have `pytest` available (separate lane); re-run to confirm the RED clears. |
| 7 | `com.balizero.nuzantara-drive-sync` | 1 | **HONEST/external** | `~/.cache/nuzantara-drive-sync/launchd.stdout.log` (5MB): explicit `googleapi: Error 403 ... RATE_LIMIT_EXCEEDED` (`Queries per minute` quota). Real, external, not a code bug. | If recurring often, tune sync interval/backoff against the Drive API quota (separate lane). |
| 8 | `com.balizero.wr2.dossier-compiler` | 2 | **REAL-CRASH** | `~/.openclaw/workspace/logs/war-room-v2/dossier-compiler.error.log`. **CORRECTED after adversarial review**: the original draft conflated two temporally-distinct failure classes as one bug — they are NOT the same. (a) `asyncpg.exceptions.ConnectionDoesNotExistError` tracebacks are logged by `intel.dossier_compiler.cli` at pool-init time (`dossier_compiler_cli.py:46`, `asyncpg.create_pool(...)` at run startup) — a DNS-resolution failure through 2026-05, becoming "connection was closed in the middle of operation" from 2026-06-13; **last occurrence 2026-06-25**, apparently dormant/resolved since (no recurrence in the ~3 weeks since, through today). (b) The `compiler: CLI failed for anchor=<uuid> err=None` lines are logged by a DIFFERENT logger (`backend.services.intel.dossier_compiler`, from `_compile_cluster`'s `self.runner.run_json()` failure branch, `dossier_compiler.py:195-201` — a `CLIRunner`, same shared component family as Council per the module docstring) — seen 2026-06-30 and again 2026-07-16 (the batch behind the `0 compiled / 11 failed` line below), with **no traceback adjacent to either occurrence**. Critically, TODAY's log (2026-07-17 04:37) shows the SAME code path populating a real value instead of None: `err=timeout after 90s` — proving `result.error` CAN carry a real reason and the "None" cases are an information-loss bug in the runner's error surface, not proof of a DB-connection root cause. The `.log` file's last recorded batch: `"dossiers_compiled": 0, "dossiers_failed": 11` — 100% failure on that batch is real; its cause is an unexplained `CLIRunner` failure/timeout, NOT confirmed to be the (separate, dormant) DB pool-init issue. | **Corrected action**: (1) immediate — fix `CLIRunner`/`self.runner.run_json()` (`backend/services/council/cli_runners.py` family) to always populate `result.error` with the real failure reason instead of `None`, so the current, ongoing failure can actually be diagnosed instead of guessed at; investigate whether the `self.timeout` used by `_compile_cluster` (90s per today's log) is simply too short for whatever CLI backend it invokes. (2) separately — the DB pool-init class (`dossier_compiler_cli.py:46`) has been quiet since 2026-06-25; no action needed unless it recurs. Both items separate lane, not this PR. |
| 9 | `com.balizero.domain-mesh.foundations.daily` | 1 | **REAL-CRASH (intermittent, ~50%)** | Plist-declared logs are a red herring again (0 bytes since 28 giu — the wrapper `/Users/nuzantara/scripts/domain-mesh-foundations-cron.sh:8,26` redirects everything to a date-stamped `foundations-daily-YYYYMMDD.log`). **CORRECTED after adversarial review**: the byte-size-to-outcome mapping below was INVERTED (self-contradictory even in the original draft, which described 07-16 as a crash one sentence before classifying 07-16 as a "success" by file size). Reading the wrapper's own logic (`domain-mesh-foundations-cron.sh`) confirms the correct polarity: the SUCCESS path writes only one short line (`"$(date) gov-apis snapshot: N/M operational"`, ~67 bytes); the FAILURE path writes the full Python traceback via `2>>"$LOG_FILE"` plus a `"FAILED foundations daily probe"` line (~6205 bytes). Content-verified directly: `foundations-daily-20260717.log` (67B) = clean `"gov-apis snapshot: 19/24 operational"`; `foundations-daily-20260716.log` (6205B) = full traceback ending `httpx.ReadError` inside `probe_portal()` (`apps/mata-garuda/mata_garuda/foundations/gov_apis_health.py:58`) + `"FAILED foundations daily probe"` — i.e. **large file = FAILURE, small file = SUCCESS**, the opposite of the original table. Corrected last-8-days read (07-10 through 07-17): 07-10 FAIL, 07-11 OK, 07-12 OK, 07-13 FAIL, 07-14 OK, 07-15 FAIL, 07-16 FAIL, 07-17 OK — **4 of the last 8 days failed** (same count as originally claimed, but the specific failing days and the file-size polarity were both wrong). No per-endpoint exception isolation in `probe_inventory()` is confirmed correct. | Wrap each `probe_portal()` call in its own try/except so one flaky government endpoint doesn't crash the whole daily inventory probe (separate lane/Mata Garuda). |
| 10 | `com.nuzantara.intake-gate-count-pusher` | 1 | **REAL-CRASH (data-quality bug, 100% reproducing since a precise cutover)** | `~/logs/intake-gate-count-pusher.log` (5.8MB, 50,718 lines). **CORRECTED after adversarial review**: "the push has not succeeded even once in the visible log window" was FALSE — the log's earliest entries (from 2026-06-08) show HTTP 401 Unauthorized, then a real, working period: **2,573** confirmed `HTTP/1.1 200 OK` pushes from 2026-06-09 through 2026-06-21. The true, more alarming finding: the pusher worked reliably for ~2 weeks, then broke abruptly and completely — the LAST `200 OK` is 2026-06-21 09:35:33, and exactly 5 minutes later, 2026-06-21 09:40:34, the FIRST real `HTTP/1.1 422 Unprocessable Entity` fires (`"loc":["body","counts",0,"user_email"],"msg":"String should have at least 1 character"`); **zero** `200 OK` responses appear anywhere after that timestamp. Precise recount: **6,357** consecutive 422 failures from that cutover through the latest tail (2026-07-17 04:31), i.e. **~26 unbroken days at 100% failure** with no self-recovery and apparently no alert ever raised for the regression. Some record in the counts payload has a blank/missing `user_email`, and the pusher never filters it before POSTing. | Fix the pusher to skip/backfill count entries with a missing `user_email`, or fix the upstream data producing the blank email (separate lane/CRM or backend) — and separately, find out what changed right at 2026-06-21 09:35-09:40 that flipped a working integration to permanently broken, since that's a more actionable lead than "it's always been broken." |

### Summary count

- **HONEST** (by-design or external, checker/job working as intended): **4** — #1, #2, #6 (contract honest; underlying gate content has a separate env bug), #7.
- **REAL-CRASH** (genuine bug, log-confirmed): **5** — #3 (severe, active crash-loop — stray Pro duplicate of a Mini-only singleton, see Adversarial review), #5 (hang), #8 (CLIRunner timeout + swallowed error surface, see Adversarial review), #9 (intermittent, unhandled network exception), #10 (persistent data-quality bug, abrupt cutover 2026-06-21).
- **INCONCLUSIVE**: **1** — #4 (no crash evidence found, but the exit-code/log-tail correlation could not be established with certainty from static logs alone).

None of the 10 are the W84 TCC-vector itself (`DEAD-GREEN`) — that's exactly what arming the
detector going forward is for for future occurrences; today's 10 were all already-honest launch
attempts (the program executed) with a mix of by-design signaling and real bugs beneath.

## Cross-reference

`.claude/skills/modus/PENDING-ARMS.md` already has an 2026-07-17 entry flagging
`mata-garuda-kg-api.err 111M` as part of an **unrotated-logs** finding (log-rotation angle only).
This triage adds the **root cause** underneath that same file: it's not merely unrotated, it's a
continuously crash-looping stray duplicate — per `docs/symbiosis/W2-kg-bridge-runbook.md`,
`com.matagaruda.kg-query-api` is a Mini-only singleton and Mini's real instance is confirmed alive
(§10 evidence above); the copy installed on Pro should be unloaded and removed, not bind-redirected
— the log is large because the process has failed to bind ~74k times, not because of missing
rotation policy alone, and not because it's "the" server needing a new bind address. Both fixes are
needed (rotation policy, AND removing the stray Pro install).

## Adversarial review

**Seat**: `codex` (`gpt-5.6-sol`, `model_reasoning_effort=high`, `--sandbox read-only`) — genuine
cross-family review, generator (Sonnet/Claude) != grader (GPT-5.6 family). Full transcript ran
against this doc verbatim plus live repo/filesystem reads from the same worktree.

Codex was instructed to hostilely re-verify every REAL-CRASH row against the actual evidence files
(not the doc's paraphrase), spot-check at least one HONEST + the INCONCLUSIVE verdict, and validate
the test-count arithmetic. It did not rubber-stamp: it raised concrete, falsifiable objections
against 5 of the 10 rows. Per the anti-hallucination discipline (a refuter can itself be wrong —
`lessons_hallucinating_tool_output_is_diabolical`), every objection below was independently
re-verified against the real files/logs/launchctl state in this same session before being accepted
or rejected — none were taken on Codex's word alone.

**Objections raised, and disposition:**

1. **Regex fix + test-count arithmetic (mandate items 1, 4)** — PASS, no objection. Independently
   re-confirmed: `OURS_RE` diff at `scripts/launchd_liveness_detector.py:74→82`, guilt+innocence
   corpus in `test_launchd_liveness_ours_scope.py`, and 6+16+4=26 existing + 4 new = 30 total tests.

2. **#3 `kg-query-api` remediation direction** — OBJECTION SURVIVED, doc corrected. Codex flagged
   that "fix `KG_API_BIND` to Pro's own address" contradicts `docs/symbiosis/W2-kg-bridge-runbook.md`
   (Mini-only singleton). Independently confirmed: this machine's hostname is `Nuzantara` (Pro) with
   Tailscale IP `100.107.22.111` (`ifconfig utun`), NOT `100.93.236.6`; Mini's real instance answers
   healthy right now (`curl http://100.93.236.6:8990/health` → `{"ok": true, entities_count: 409, ...}`).
   Table row + Cross-reference section corrected: this is a stray duplicate install on Pro; the fix
   is to unload/remove it from Pro, not redirect its bind (which would create an active-active
   split-brain server, cicatrix superscar #10). REAL-CRASH verdict itself unchanged — only the
   prescribed remediation was wrong and is now fixed.

3. **#5 `ig-metrics-analyst` SIGTERM correlation** — OBJECTION DID NOT SURVIVE. Codex could not reach
   `launchctl` from its read-only sandbox and flagged the `-15` correlation as unverifiable. This
   session has live `launchctl` access (not sandboxed the same way): `launchctl print` on the label
   shows `"LastExitStatus" = 15"`, i.e. exactly the `-15` (SIGTERM, unshifted) the doc claims. No
   doc change — the objection was a tooling limitation on the refuter's side, not a real defect.

4. **#8 `dossier-compiler` root-cause conflation** — OBJECTION SURVIVED, doc corrected. Verified by
   reading `dossier_compiler.py:195-217` and `dossier_compiler_cli.py:46` directly, plus dating every
   occurrence in the error log: the asyncpg pool-init tracebacks (`intel.dossier_compiler.cli` logger)
   last fired 2026-06-25 and are dormant; the CURRENT `err=None` failures (`backend.services.intel.
   dossier_compiler` logger, a different `CLIRunner` code path) have no adjacent traceback, and
   today's log (07-17) shows the same line populating a real value (`err=timeout after 90s`) —
   proving the "None" cases are an error-surface bug in the runner, not evidence of the (separate,
   dormant) DB issue. Table row corrected to attribute the current failure to the `CLIRunner`/timeout
   path and recommend fixing `result.error` propagation as the actionable next step. REAL-CRASH
   verdict unchanged — root cause and remediation were wrong and are now fixed.

5. **#9 `domain-mesh.foundations.daily` inverted evidence** — OBJECTION SURVIVED, doc corrected (this
   was the most serious catch — the original draft was self-contradictory, describing 07-16 as a
   crash and then classifying the same file as "success" one paragraph later). Verified directly:
   `foundations-daily-20260717.log` (67B) contains only a clean one-line success message;
   `foundations-daily-20260716.log` (6205B) contains a full Python traceback ending `httpx.ReadError`
   plus a literal "FAILED foundations daily probe" line. The wrapper script's own logic
   (`domain-mesh-foundations-cron.sh`) confirms this structurally: the success path writes one short
   line, the failure path writes the full traceback. Table corrected: large file = FAILURE, small
   file = SUCCESS (the doc had it backwards), with the specific failing days recomputed. The "4 of
   last 8 days" COUNT survives by coincidence; which specific days and what large/small means did
   not. REAL-CRASH verdict unchanged.

6. **#10 `intake-gate-count-pusher` "never succeeded"** — OBJECTION SURVIVED, doc corrected. Verified
   directly: 2,573 real `HTTP/1.1 200 OK` entries exist from 2026-06-09 to 2026-06-21 09:35:33; the
   first real 422 fires exactly 5 minutes later (09:40:34) and 6,357 consecutive 422s follow through
   today with zero successes in between. Corrected framing is more alarming than the original, not
   less: a working integration broke abruptly at an identifiable timestamp and has never recovered
   in ~26 days, which is a more actionable lead than "always broken." REAL-CRASH verdict unchanged
   and, if anything, strengthened.

7. **#1, #7 HONEST spot-check + #4 INCONCLUSIVE spot-check** — #1 and #7 hold as originally written
   (independently spot-checked: `matagaruda-redis-split-brain-check.sh` intentionally propagates
   non-zero, and the Drive-sync 403 quota message is real and current). #4 had one overstatement
   ("zero tracebacks anywhere" — 4 old, unrelated, environment-class tracebacks from May actually
   exist in the file) — corrected in the table; the INCONCLUSIVE verdict itself is unchanged.

**Final verdict**: none of the 10 classification VERDICTS (HONEST/REAL-CRASH/INCONCLUSIVE split)
changed as a result of this review — the triage's top-line conclusion (4 HONEST / 5 REAL-CRASH / 1
INCONCLUSIVE, zero W84 vectors) holds. But 5 of the 10 rows had real, falsifiable errors in their
supporting evidence or prescribed remediation (one of them — #9 — was flatly inverted, and #3's
original remediation would have made things worse, not better, if followed). All 5 are corrected
above with fresh verbatim evidence gathered in this session. Sandbox limitation disclosed: Codex's
own read-only sandbox could not reach live `launchctl`/`ps` state (item 3 above) — this session's
direct terminal access filled that gap.

## PENDING-ARMS

See `.claude/skills/modus/PENDING-ARMS.md` for the ledger row tracking plist install
(`operator[control-plane]`).
