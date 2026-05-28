---
date: 2026-05-28
domain: operations
client_case: none
status: investigation_complete_no_fix_applied
author: deep-researcher (read-only audit)
sources:
  - /Users/nuzantara/Desktop/nuzantara/shared/escalations_pro.jsonl
  - /Users/nuzantara/Desktop/nuzantara/scripts/dlq_autopilot.py
  - /Users/nuzantara/Desktop/nuzantara/scripts/nuzantara-sentinel.py
  - /Users/nuzantara/Desktop/nuzantara/scripts/sentinel_lib/repairer.py
  - /Users/nuzantara/Desktop/nuzantara/scripts/sentinel_lib/escalations.py
  - /Users/nuzantara/Desktop/nuzantara/scripts/sentinel_lib/classifier.py
  - /Users/nuzantara/scripts/launchagent-state-bridge.py
  - /Users/nuzantara/.agent/decisions/dlq.json
  - /Users/nuzantara/.agent/decisions/job_registry.json
  - /Users/nuzantara/.agent/decisions/state/{prime_tunnel,post_publish_poller,post_publish_webhook,zombie_hunter}.last.json
  - /Users/nuzantara/.agent/decisions/claude_tasks/*.json (379 files audited)
  - /Users/nuzantara/Library/LaunchAgents/com.{nuzantara.prime-tunnel,balizero.post-publish-{poller,webhook},nuzantara.zombie-hunter,nuzantara.launchagent-state-bridge,nuzantara.dlq-autopilot,nuzantara.sentinel}.plist
  - /Users/nuzantara/logs/{dlq_autopilot,sentinel,launchagent-state-bridge}.log
  - /tmp/cloudflared-prime.log
  - /Users/nuzantara/.openclaw/workspace/logs/post_publish_{poller,webhook}.{log,err}
  - launchctl list (live state of 4 jobs + bridge + dlq + sentinel)
---

# DLQ Autopilot Retry-Storm — Read-Only Audit

## Section 1 — Executive Summary

- **Root cause is upstream**: `com.nuzantara.launchagent-state-bridge` died at `2026-05-26 13:28 WITA` (~46h ago, log mtime confirms). It was the writer that refreshed `~/.agent/decisions/state/{prime_tunnel,post_publish_poller,post_publish_webhook,zombie_hunter}.last.json`. Its `*.plist` has **no `KeepAlive=true`** — once it exited, nothing restarted it. State files frozen → sentinel sees `age > staleness_threshold_s` → marks `stale` → enqueues DLQ entry → repeat every cron tick.
- **The retry-storm is amplified by an idempotency bug in `add_to_dlq()`**: `scripts/sentinel_lib/repairer.py:122` strips the existing entry and re-creates it with fresh `added_ts` and **no `autopilot_attempts` field**. Each sentinel tick resets the attempt counter, so `attempts >= max_attempts (10)` is never reached → entries never transition to `TERMINAL` → W53 suppression gate never fires for these 4 jobs. The same 4 entries cycle forever as `skipped_preflight`.
- **Scope-correction**: the user-supplied framing ("99% from 4 jobs") is incorrect at the file level — `escalations_pro.jsonl` actually has 4680 lines spanning **65 unique jobs**. The 4 named jobs account for `141 + 105 + 105 + 103 = 454 lines (9.7%)` over 48 days. The current open DLQ has 10 entries, 6 already `TERMINAL` and properly suppressed by W53; only these 4 are looping. The high-rate component during the last ~7 days (since the bridge died) IS dominated by these 4, at exactly **4 escalations / 30min = 192 escalations/day** — `dlq_autopilot.plist` runs `StartInterval=1800`.

## Section 2 — Per-Job Profile

### Job 1: `prime_tunnel`

- **LaunchAgent**: `~/Library/LaunchAgents/com.nuzantara.prime-tunnel.plist` (KeepAlive=true, RunAtLoad=true, no schedule).
- **Wrapper / Program**: `/opt/homebrew/bin/cloudflared tunnel --config /Users/nuzantara/.cloudflared/config-prime.yml run`.
- **Live launchctl status**: `PID=-, exit_code=1` (crash-looping, KeepAlive respawn).
- **Real error pattern** (`/tmp/cloudflared-prime.log`, last ~hundreds of lines all identical): `open /Users/nuzantara/.cloudflared/config-prime.yml: no such file or directory`. The entire `~/.cloudflared/` directory does not exist. cloudflared exits immediately on every restart.
- **State file** (`~/.agent/decisions/state/prime_tunnel.last.json`, mtime `2026-05-26 13:28`): `{"job": "prime_tunnel", "ts": 1779773299, "status": "ok", "host": "Nuzantara", "source": "launchagent-bridge", "label": "com.nuzantara.prime-tunnel", "pid": 975}`. Says `status=ok` because the bridge's last health check used PID-presence as the criterion and at that moment cloudflared had been respawned and held a PID for a few seconds.
- **DLQ entry** (`~/.agent/decisions/dlq.json`): `added_ts=1779928128.32 (2026-05-28T08:28:48)`, `status=skipped_preflight`, `autopilot_attempts=1`, `error_summary=""`, `subtype=cli_failed`.
- **Latest escalation payload** (`prime_tunnel_1779928283.json`): `error_summary=""`, `log_tail=""`, `files_implicated=["unknown"]`, `priority=NORMAL`, `dlq_reasoning=null`. No actionable content.

### Job 2: `post_publish_poller`

- **LaunchAgent**: `~/Library/LaunchAgents/com.balizero.post-publish-poller.plist` (RunAtLoad=true, **no KeepAlive**, no StartInterval).
- **Wrapper / Program**: `/Users/nuzantara/Projects/nuzantara/apps/bali-intel-scraper/venv/bin/python3 /Users/nuzantara/Projects/nuzantara/apps/bali-intel-scraper/scripts/post_publish_poller.py`. Note the path is `~/Projects/nuzantara/` (Air-era path, decommissioned 2026-05-05 per CLAUDE.md). The Pro path is `~/Desktop/nuzantara/`. The `Projects/` script still exists (April mtime, not synced) but is referenced by a 5-month-old plist.
- **Live launchctl status**: `PID=-, exit_code=0` (one-shot, exited cleanly on last run, never restarts because no KeepAlive and no schedule).
- **Real error pattern** (`/Users/nuzantara/.openclaw/workspace/logs/post_publish_poller.err`): `subprocess.TimeoutExpired: Command [translate-articles.py ... --lang all] timed out after 900 seconds`. Translation script hangs / Gemini call slow. Log mtime `22 mag 17:51` → no run since 26 May 13:28.
- **State file** (mtime `2026-05-26 13:28`): `{status: ok, source: launchagent-bridge}`. Bridge tagged it OK because exit_code=0 at that moment.
- **DLQ entry**: same shape as prime_tunnel — `error_summary=""`, `subtype=cli_failed`, attempts=1.

### Job 3: `post_publish_webhook`

- **LaunchAgent**: `~/Library/LaunchAgents/com.balizero.post-publish-webhook.plist` (KeepAlive=true, RunAtLoad=true).
- **Wrapper / Program**: `/Users/nuzantara/Desktop/nuzantara/apps/bali-intel-scraper/.venv/bin/python3 .../post_publish_webhook.py`. HTTP webhook listener on port 7788 (per log: `🌐 Post-publish webhook su ::7788`).
- **Live launchctl status**: `PID=1016, exit_code=0` (HEALTHY — actually running).
- **Real error pattern** (`post_publish_webhook.err`): historical `subprocess.TimeoutExpired: translate_articles.py ... after 2700 seconds` followed by `Fatal Python error: error evaluating path` + `InterruptedError: [Errno 4] Interrupted system call`. These are crashes from before 2026-04-27 (err log mtime). The webhook itself has been restarted clean and is currently running.
- **State file** (mtime `2026-05-26 13:28`): `{status: ok}`. Bridge correctly identified it but hasn't updated since.
- **DLQ entry**: same empty pattern. This is a **false positive** — process is alive and healthy, but state file is stale because the bridge that updates it died.

### Job 4: `zombie_hunter`

- **LaunchAgent**: `~/Library/LaunchAgents/com.nuzantara.zombie-hunter.plist` (RunAtLoad=true, **StartInterval=60** seconds, stdout/stderr → `/dev/null`).
- **Wrapper / Program**: `/bin/bash /Users/nuzantara/.claude/scripts/zombie-hunter.sh` (133 LOC, kills runaway processes, emits sidecar).
- **Live launchctl status**: `PID=98166, exit_code=0` (running).
- **Real activity** (`/Users/nuzantara/.claude/scripts/zombie-hunter.log`, last entry `2026-05-28 07:36:12 KILLED: openclaw-stale(...×30)`): script is firing every 60s and actively killing stale openclaw processes. Genuine production utility.
- **State file** (mtime `2026-05-26 13:28`): `{status: ok}`. Stale.
- **DLQ entry**: same empty pattern. **Also a false positive** — zombie-hunter is the most active job on the box; it just doesn't write its own heartbeat (the script emits an organism sidecar via `_organism_lib.sh` but that's a different state path).

## Section 3 — Common Root Cause

Three independent failures compound:

1. **Upstream sensor death (P0)**: `com.nuzantara.launchagent-state-bridge` exited at `2026-05-26 13:28` (last log line) and never came back because its `*.plist` defines `RunAtLoad=true` but **no `KeepAlive`** and **no `StartInterval`**. Without one of those, launchd treats one-shot exit as terminal. The bridge is the SOLE writer for the 4 listed jobs' state files (`launchagent-state-bridge.py:17-23` hardcodes them in `UNMONITORED`). With the bridge dead, the state files freeze → sentinel computes `age = now - last_ts > staleness_threshold_s` → marks `status="stale"` → calls `add_to_dlq(...)`.

2. **Idempotency / attempt-counter bug (P1)** in `scripts/sentinel_lib/repairer.py:120-138`: `add_to_dlq()` removes any existing entry for the same job (`data["queue"] = [e for e in data["queue"] if e.get("job") != job]`) and creates a NEW dict that omits `autopilot_attempts`. Then `dlq_autopilot.process_entry()` reads `attempts = entry.get("autopilot_attempts", 0) → 0`. After processing (action = `skipped_preflight`), `run_autopilot()` increments to 1 (`scripts/dlq_autopilot.py:632-635`) and re-saves. Next sentinel tick: REPLACE again → back to 0. `attempts >= max_attempts (10)` is unreachable. Entry never transitions to `TERMINAL` → W53 suppression never engages.

3. **Classifier silent failure (P2)** in `scripts/sentinel_lib/classifier.py:151,169`: when sentinel passes an empty `last_error` (because state file has no `last_error` field — bridge only writes `status/ts/host/source/label/pid`), `classify()` returns `UNKNOWN` → falls through to `classify_with_llm()` → claude CLI gets empty error text → returns `subtype="cli_failed"` (the catch-all on JSON parse failure or empty response). The DLQ entry is created with `subtype="cli_failed"` and `error_summary=""`. Then `dlq_autopilot.process_entry()` hits the preflight gate at line 486 (`if len(error) < MIN_ERROR_LEN: ... → escalating directly`), which calls `escalate_to_claude_code()` — writes a JSON to `~/.agent/decisions/claude_tasks/` AND appends a line to `escalations_pro.jsonl` via `_write_escalation()` (`scripts/dlq_autopilot.py:417-424`). No backoff, no rate-limiting on the escalation write itself.

Net effect: a hard-broken health sensor + an idempotency contract violation + a degenerate classifier path = 4 escalations every 30min that contain zero diagnostic information.

Secondary observations (non-blocking):

- `dlq_autopilot.log` shows **every line duplicated** (e.g., two identical `DLQ entries: 10` lines, two identical `escalated to Claude Code` lines per run). Cause: dual handlers configured at module import (`FileHandler` + `StreamHandler` on lines 26+31) and the LaunchAgent wrapper redirects stdout to a file too — but the duplication shape in `dlq_autopilot.log` is exact pair-wise, suggesting the module is being imported twice in the same process (likely `from sentinel_lib.escalations import ...` chain re-imports). Cosmetic but doubles log size.
- `prime_tunnel` is **genuinely broken** independent of the bridge: cloudflared crash-loop because `~/.cloudflared/config-prime.yml` was deleted/never-created. Even after bridge repair, this job will continue producing `last_exit=1`, which the bridge interprets as `status=failed` → sentinel → DLQ. Fixing the bridge alone leaves prime_tunnel as a legitimate escalation (probably the only one that deserves operator attention).
- `escalations_pro.jsonl` has no rotation — `escalations_prune_cron.sh` prunes the SQLite mirror only. The JSONL grows append-only (currently 1.2MB / 4680 lines, mature: April 10 to today).

## Section 4 — Proposed Fix Options

### Option A — Reset / restart `launchagent-state-bridge` + add `KeepAlive`

- **What**: `launchctl bootstrap` the bridge plist after patching it to add `<key>KeepAlive</key><true/>` (and optionally `StartInterval=300` since the script comment says "Run every 5 minutes via cron").
- **Pro**: addresses the upstream sensor that originally died. With the bridge alive again, state files refresh, sentinel sees fresh `ok` status for healthy jobs (post_publish_webhook, zombie_hunter), DLQ entries get cleared on the next tick (`record_success` → `clear_dlq_entry`). Storm drops from 4×/30min to 1×/30min (prime_tunnel only). Minimal code change.
- **Con**: does NOT fix the underlying idempotency bug, so any future bridge outage repeats the storm. Does NOT fix the unbounded escalations_pro.jsonl growth. Leaves prime_tunnel cloudflared crash-loop unaddressed.
- **Effort**: ~5min (edit plist, `launchctl bootout && launchctl bootstrap`).
- **Risk**: low. KeepAlive on a 5-min poll script is the documented pattern for this script per its own header.

### Option B — Patch `add_to_dlq()` to preserve `autopilot_attempts` + `first_seen_at`

- **What**: in `scripts/sentinel_lib/repairer.py:120-138`, before replacing the entry, read the existing one and carry forward `autopilot_attempts` and `first_seen_at` (or `added_ts` original). Then `attempts >= max_attempts (10)` actually triggers within ~5 hours (10 sentinel ticks at 30min each), promoting the entry to TERMINAL → W53 silences it.
- **Pro**: addresses the systemic loop bug independent of which job is the trigger. Defense-in-depth against future bridge / classifier failures. Makes existing W53 gate actually work for empty-error escalations.
- **Con**: requires code change + test. Doesn't fix the upstream stale state (post_publish_webhook and zombie_hunter would still false-positive once, then go TERMINAL within 5h → must be manually `dlq clear`'ed before they can re-monitor). Doesn't fix prime_tunnel's actual crash.
- **Effort**: ~30min (5 LOC change + unit test in `scripts/tests/test_sentinel_v33.py` + verify on staging dlq.json).
- **Risk**: medium. Need to ensure carry-forward doesn't break the "DLQ re-add after manual fix" flow (operator expects fresh entry to have attempts=0).

### Option C — Disable obsolete jobs

- **What**: `launchctl bootout` for jobs that are no longer needed. Candidates:
  - `post_publish_poller`: references the decommissioned `~/Projects/nuzantara/` Air path. If it has been deprecated by `post_publish_webhook` (more modern push-based), bootout the poller.
  - `prime_tunnel`: if Antonello no longer uses cloudflared tunnel for prime dashboard, bootout the plist + remove from `UNMONITORED` map.
- **Pro**: eliminates the noise at source. Cheapest possible action per job.
- **Con**: requires operator-level decision on whether each job is genuinely obsolete. Cannot be derived from code alone. If `prime_tunnel` is needed (e.g., for `prime.balizero.com` external access), this option is wrong. Doesn't fix the systemic loop bug for other future stragglers.
- **Effort**: ~2min per job, decision time variable.
- **Risk**: high if any disabled job turns out to be needed. Operator-only call.

### Option D — Job-specific fixes

- **D.prime_tunnel**: investigate where `~/.cloudflared/config-prime.yml` should come from (was it ever in git? cf. `infra/cloudflared/`?). Either restore the config file, or replace the cloudflared tunnel with a different transport (Tailscale Funnel? Direct port-forward?). Genuine operational issue separate from the storm.
- **D.post_publish_poller**: migrate plist `Program/ProgramArguments` from `~/Projects/nuzantara/` (Air-era) to `~/Desktop/nuzantara/` (Pro), then verify the script runs successfully against current Fly backend. Likely also needs `KeepAlive=false` + `StartInterval=600` (the script logs "🔄 Post-publish poller v3 started" suggesting it's a one-shot batch runner, not a daemon).
- **D.post_publish_webhook + zombie_hunter**: nothing — these are healthy false-positives. Resolved by Option A or B.
- **Pro**: addresses real bugs that have been hidden by the storm noise (prime_tunnel cloudflared crash is a legitimate broken state since the config file disappeared). Makes the actual job catalog truthful again.
- **Con**: most expensive in human effort, requires per-job investigation. Doesn't address other future jobs that might enter the same loop.
- **Effort**: ~30-60min per job depending on findings.
- **Risk**: low per-job (changes are local). High aggregate if scope creeps.

## Section 5 — Recommended Next Action (Single Sentence)

Apply Option A first (restart launchagent-state-bridge + add KeepAlive) to immediately collapse the storm to ~1 escalation/30min from `prime_tunnel` alone, then schedule Option B (patch add_to_dlq attempt-preservation) as a P1 followup hardening, then triage Option D.prime_tunnel separately as a real operational bug (cloudflared config file disappeared).

## Verifications Performed (read-only)

- [x] Listed all 4 LaunchAgent plists under `~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*` matching the job names.
- [x] Read each plist to extract Program / ProgramArguments / KeepAlive / StartInterval / log paths.
- [x] Read each wrapper script: `cloudflared run` (prime), `post_publish_poller.py`, `post_publish_webhook.py`, `zombie-hunter.sh`.
- [x] Tailed each job's stdout/err log under `/tmp/cloudflared-prime.log`, `~/.openclaw/workspace/logs/post_publish_*.{log,err}`, `~/.claude/scripts/zombie-hunter.log`.
- [x] Sampled 5 most-recent claude_tasks JSON files per job — confirmed all 20 are identical empty-payload templates with `subtype=cli_failed`.
- [x] Read full `scripts/dlq_autopilot.py` (690 LOC) — traced retry logic, lock, TERMINAL gate (line 453), preflight (line 486), tier1/2/3 dispatch, queue mutation (line 617-635), no exponential backoff, no per-job rate limit.
- [x] Read full `scripts/sentinel_lib/repairer.py` `add_to_dlq()` (line 120-138) — confirmed it replaces entry without preserving `autopilot_attempts`.
- [x] Read `scripts/nuzantara-sentinel.py` lines 450-735 — confirmed sentinel calls `add_to_dlq` on each cron tick when status=stale.
- [x] Read `scripts/sentinel_lib/classifier.py:151,169` — confirmed `cli_failed` subtype is the catch-all on claude CLI non-zero exit or JSON parse failure.
- [x] Read `scripts/launchagent-state-bridge.py:1-80` — confirmed it's the SOLE writer for the 4 jobs' state files, `UNMONITORED` map line 17-23.
- [x] Live `launchctl list` snapshot: bridge=`-`, prime-tunnel=`-,exit=1`, post-publish-poller=`-,exit=0`, post-publish-webhook=`PID=1016`, zombie-hunter=`PID=98166`.
- [x] Read 4 stale state files — confirmed mtime `2026-05-26 13:28`, all with `source=launchagent-bridge`, `status=ok` (stale optimistic).
- [x] Parsed `dlq.json` — confirmed 10 entries, 6 already TERMINAL (correctly suppressed by W53), 4 looping as `skipped_preflight` attempts=1.
- [x] Counted escalations_pro.jsonl: `wc -l = 4680`, `awk` distribution per job = 65 unique jobs, 4 named jobs = 454 lines (9.7% of total, 100% of last ~7 days at 4/30min cadence).
- [x] Tailed `~/logs/dlq_autopilot.log` last 100 lines — confirmed every log line is DOUBLED in output (dual handler / double-import bug).
- [x] Tailed `~/logs/sentinel.log` — confirmed `WARNING <job>: status=stale, error=` for all 4 jobs on the 08:28 tick, followed by `Sentinel done: 27 checked, 23 healthy, 4 escalated`.
- [x] Confirmed `escalations_prune_cron.sh` only prunes SQLite mirror, not the JSONL file (no rotation policy on append-only JSONL).
- [x] First / last timestamp in escalations_pro.jsonl: `2026-04-10T01:55:54` → `2026-05-28T08:31:25` (48d, ~97 entries/day average; current rate ~4/30min = 192/day = 2× average, consistent with bridge died 2 days ago + concurrent old patterns).
- [x] Verified NO fix applied: no LaunchAgent touched, no escalations.jsonl modified, no process killed, no plist edited. dlq.json mtime unchanged (`28 mag 08:31` = before this audit, last sentinel tick).
