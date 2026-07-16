---
date: 2026-07-17
domain: operations
client_case: none (WR2 infra reliability)
sources:
  - "scripts/wr2-deploy-pull.sh (canon, ~/nuzantara-deploy puller — read this session)"
  - "scripts/wr2_supervisor.py (read this session)"
  - "scripts/wr2_supervisor_watchdog.py (read this session)"
  - "scripts/lib/wr2_runtime_stamp.py (read this session)"
  - "live disk (Pro, read-only): ~/.organism/last_seen/wr2.supervisor.runtime.json, wr2.html_apply.runtime.json, wr2.deploy_pull.json"
  - "live disk (Pro, read-only): ~/logs/wr2-deploy-pull.log, ~/logs/wr2_supervisor_watchdog.log"
  - "live disk (Pro, read-only): git -C ~/nuzantara-deploy log; ps -o pid,lstart,etime for pid 88059"
  - ".claude/skills/modus/PENDING-ARMS.md (WR2 C1+C2 arming ledger entry, closed 2026-07-03)"
adversarial_review: none (diagnosis-only, no code change — per mandate the reload-on-pull fix is NOT touched tonight)
---

# WR2 supervisor reload-on-pull — drift diagnosis (not fixed by design tonight)

**Scope**: diagnostic only. No code touching `wr2_supervisor.py` (a live daemon) was written for
this report — per explicit mandate, Part B is diagnose-and-document, not fix. Part A (the
`wr2-cron-wrapper.sh` guard heartbeat) is a separate, already-shipped fix in this same PR.

## 0. Executive summary

The reported symptom — `wr2_supervisor.py` (live daemon) running code 2 commits behind the
`html_apply` worker on the same machine (Pro) — **is real, empirically confirmed on disk from last
night's logs, and had already self-resolved by the time of this investigation** (2026-07-17, ~02:00
WITA). The mechanism that resolved it — a puller-triggered hard restart
(`launchctl kickstart -k`) — **already exists, is armed, and worked correctly on every one of the 7
hourly ticks visible in last night's log (18:43→00:57 WITA)**. The actual disease is narrower and
more precise than "nothing reloads the supervisor": **detection worked, but the alert layer's
24-hour blanket cooldown key swallowed the page.** The watchdog detected the drift and logged it
**49 times, one per minute, for at least 49 consecutive minutes (23:54–00:42 WITA)** — every one of
those after the first was suppressed as "cooldown active" and never reached Telegram. This is a
scar-family #2 (*esiste ≠ armato* / "green mente, muore muto") variant: the alert exists and the
detector is correct — the **dedup key granularity** is the defect.

## 1. How the drift is detected today (the mechanism that already exists)

Two parallel signals, both real, both read this session:

1. **Runtime provenance stamps** (`scripts/lib/wr2_runtime_stamp.py`) — any organ can call
   `compute_runtime_stamp(checkout, modules)` to capture `{ts, pid, host, checkout, head_sha, dirty,
   stale_modules[], errors[]}` and `write_runtime_stamp(organ_id, stamp)` to
   `~/.organism/last_seen/<organ_id>.runtime.json`. Two writers exist today:
   - `wr2_supervisor.py:784-810` (`_write_runtime_stamp_best_effort`) — called **once**, at daemon
     boot (`main()`, line 816), before the async event loop starts. The stamp freezes at that
     instant and never updates again for the life of the process.
   - `wr2_html_render_apply` (one-shot worker) — stamps **per run**, so its stamp is always ≈
     current disk HEAD at the moment it last executed.

2. **The watchdog cross-check** (`scripts/wr2_supervisor_watchdog.py:619-681`,
   `_probe_runtime_stale()`), polled every `POLL_INTERVAL_SEC=60` (line 131) inside
   `_evaluate_outcome_probes` (lines 740-759): for each organ in
   `RUNTIME_STALE_ORGANS = ("wr2.html_apply", "wr2.supervisor")` (line 619) it reads that organ's
   `.runtime.json`, and — **only if the stamped `pid` is still alive** (`_pid_alive`, line 673, so a
   dead one-shot worker's old stamp is correctly never flagged) — runs `git -C <checkout> rev-parse
   HEAD` **live** and compares it to the stamp's frozen `head_sha`. A mismatch is logged as
   `head-moved:<old>-><new> (live pid <pid> on old code)` (line 677) and a `runtime_stale` finding is
   appended.

   **Important nuance**: this check compares each organ **independently against the live checkout
   HEAD**, not the two organs' stamps **against each other**. In the common case (html_apply's own
   stamp is always ≈ disk-fresh) this converges to the same practical signal as "supervisor vs
   html_apply", but it is not literally that comparison — see Option B below.

3. **git log** as ground truth for how far behind: `git -C ~/nuzantara-deploy log --oneline` gives
   the commit chain; comparing a stale stamp's `head_sha` position in that chain against the current
   tip is how "2 commits behind" gets a number (verified live this session — see §2).

## 2. Empirical timeline, last night (Pro, all times WITA, all read from disk this session)

`scripts/wr2-deploy-pull.sh` (canon; the live puller invoked hourly by
`com.balizero.wr2.deploy-puller.plist`, `StartInterval=3600`) ran cleanly every hour, 18:43→00:57,
each time fast-forwarding `~/nuzantara-deploy` and — because
`WR2_DEPLOY_PULL_KICKSTART=1` is set in that plist's `EnvironmentVariables` (armed since
2026-07-03, per the closed PENDING-ARMS line "WR2 C1+C2 arming... kickstarted 13:42;
`WR2_DEPLOY_PULL_KICKSTART=1` written into deploy-puller plist") — kickstarting all three consumer
organs (`wr2-deploy-pull.sh:389-405`):

```
2026-07-16 23:43:33 WITA  OK: fast-forwarded b348162b8 -> a1cee94d1 (2 commits)
                          kickstart html-apply OK / kickstart -k supervisor OK / kickstart -k supervisor-watchdog OK
2026-07-16 23:53:50,163   wr2_supervisor_watchdog: WARNING ALERT P1 runtime_stale organs=1   <- REAL page sent
2026-07-16 23:54:51 .. 2026-07-17 00:42:42  (49 lines, ~60s apart)
                          wr2_supervisor_watchdog: INFO runtime_stale found but cooldown active (organs=1)
2026-07-17 00:43:40 WITA  OK: fast-forwarded e3e954e0b -> 20ef16e15 (2 commits)
                          kickstart html-apply OK / kickstart -k supervisor OK / kickstart -k supervisor-watchdog OK
2026-07-17 00:57:24 WITA  OK: fast-forwarded 20ef16e15 -> c43b22330 (3 commits)
                          kickstart html-apply OK / kickstart -k supervisor OK (pid 88059 born 00:57:24) / kickstart -k supervisor-watchdog OK
```

Right now (investigation time): `wr2.supervisor.runtime.json` = `{pid:88059, head_sha:
c43b22330...}`, `wr2.html_apply.runtime.json` = `{pid:22310, head_sha: c43b22330...}`, live `git -C
~/nuzantara-deploy rev-parse HEAD` = `c43b22330...` — **all three agree, zero drift now.** Pid 88059
was confirmed alive via `ps` (started 2026-07-17 00:57:24, elapsed 54m at check time).

**Reading this timeline**: the puller's own kickstart mechanism never failed once (zero `WARN:
kickstart ... failed` lines in the whole window — grepped the full log, not just a tail). The
watchdog's `_probe_runtime_stale()` correctly caught the "supervisor on old code" condition **within
minutes of it starting** (first at 23:53:50, immediately real-alerted) and **kept catching it every
single minute for the next 49 minutes** — this is the detector working exactly as designed. What
failed is that **only the first of those ~50 detections ever reached Telegram** — everything after
it was silently logged as "cooldown active" until the 00:43:40 and 00:57:24 ticks eventually
fast-forwarded + kickstarted the daemon back onto current code, closing the gap on their own
schedule (not because anyone was paged to intervene).

## 3. Why the supervisor doesn't reload on its own

`wr2_supervisor.py` is a plain long-running Python process (`asyncio.run(_amain())`, line 818). Like
any CPython process, once its modules are imported at boot they stay resident in memory for the
life of the process — nothing inside its own tick loop re-imports or re-checks its own source files.
The **only** thing that can put fresh code into that process is killing it and letting it start
over. Today that trigger is **100% external and single-sourced**: `wr2-deploy-pull.sh`'s own
`launchctl kickstart -k` call, run **exclusively inside that one script**, **exclusively right after
its own `git merge --ff-only`** (lines 363 → 389-405, same process, sequential). There is no
in-process self-check, no signal handler, no independent second trigger.

This has one direct, verifiable consequence: **any advance of `~/nuzantara-deploy`'s HEAD that does
not go through `wr2-deploy-pull.sh` bypasses the only reload trigger that exists.** The script's own
comment (`wr2-deploy-pull.sh:227-238`) states the deploy clone is "BY CONTRACT read-only runtime" —
but that contract is documentation, not enforcement; nothing on disk stops an interactive `git -C
~/nuzantara-deploy fetch && git merge` (or a plain `git pull`) run by any human or agent session
from advancing the checkout outside the wrapper, silently orphaning the supervisor's frozen boot
stamp with zero kickstart. Given this diagnosis session and others were explicitly instructed to
treat `~/nuzantara-deploy` as read-only-inspectable (this task's own mandate, point 5), and given
last night's drift window (23:43→00:57) has no gap in the puller's own hourly cadence, an
out-of-band manual git operation against the deploy clone during an active diagnostic session is
the most likely proximate trigger for *why* the drift existed in the first place — the *why it
wasn't paged* answer (§2) is independent of this and fully evidenced regardless of which triggered
the original advance.

## 4. Cure options (none armed — proposal only)

### Option A — Split the alert cooldown key by organ (+ problem class)
Change the call site at `wr2_supervisor_watchdog.py:743` from a single blanket
`_alert_due("runtime_stale", now_epoch)` to a per-organ (optionally per-problem-class) key, e.g.
`_alert_due(f"runtime_stale:{finding['organ']}", now_epoch)`, and page once per organ instead of
once for the whole probe. **Trade-off**: lowest risk of the three — touches only the watchdog
(`wr2_supervisor_watchdog.py`), zero change to the live supervisor daemon itself, small diff.
Directly closes the exact gap proven in §2 (49 silent recurrences). Residual risk: keying too
finely (e.g. by exact `head_sha` pair, which changes every hour) would defeat the cooldown's actual
purpose (an organ stuck flapping every tick would re-page every hour); keying by
`organ` (or `organ:problem-type`) balances that.

### Option B — Direct pairwise cross-check (the literal "incrocio di 2 heartbeat")
Add a new, independent probe that reads `wr2.supervisor.runtime.json` and
`wr2.html_apply.runtime.json` **directly against each other** (no `git` subprocess needed — two JSON
reads), and pages distinctly (e.g. `SUPERVISOR_LAGS_WORKER`) when the supervisor's `head_sha` is
older than html_apply's most recent stamp AND the supervisor's `pid` is still alive. **Trade-off**:
cheapest to run (no subprocess), can poll as often as desired without git overhead, and matches the
task's own framing of the detection method exactly. It is complementary to, not a replacement for,
the existing vs-disk check (§1.2) — that one also catches the case where html_apply itself hasn't
run recently enough to be a fresh reference. Touches only the watchdog, not the supervisor.

### Option C — Supervisor self-checks its own drift and requests its own restart
On a coarse cadence inside `_amain()`'s tick loop, call `wr2_runtime_stamp.current_head(checkout)`
and compare to the boot-time `head_sha` already in memory; on mismatch, log WARN and — only if a new
env flag (e.g. `WR2_SUPERVISOR_SELF_RESTART_ON_DRIFT=1`) is armed — perform a graceful self-exit so
the existing `KeepAlive.SuccessfulExit` launchd config (confirmed present in
`com.balizero.wr2.supervisor.plist`) brings it back up on current code, independent of the puller
ever kickstarting it. **Trade-off**: the most structurally complete cure (removes the single-point
dependency on the puller's kickstart entirely) but is the only option that touches the live daemon's
own run loop — exactly the class of change this mandate said not to make tonight. Needs care around
in-flight work (a render/lease in progress) before a self-exit.

**Discarded alternative (documented, not proposed)**: SIGHUP-triggered in-process hot-reload
(`importlib.reload` of watched modules) instead of a full process restart. Rejected on inspection:
Python hot-reload of a long-running asyncio daemon is a known correctness hazard (stale class
identity across `isinstance` checks, half-reloaded module graphs, live object references to old
code) — `kickstart -k` (full restart) is simpler and almost certainly why the existing mechanism
chose it over a signal-based reload in the first place.

**Recommendation (non-binding)**: A + B together are same-risk-class (watchdog-only, zero daemon
touch) and jointly close both the paging gap (A) and give a cheaper, more direct signal (B). C is
the deeper fix but should be a deliberate, separate, tested change to a live daemon — not bundled
with A/B.

## 5. PENDING-ARMS

- opened 2026-07-17 | WR2 supervisor/html_apply runtime-drift paging gap (this report) — detection
  works (49/49 true positives logged 23:54-00:42 WITA), but the single blanket 24h `runtime_stale`
  cooldown key (`wr2_supervisor_watchdog.py:137,743`) suppressed every recurrence after the first
  real page at 23:53:50 | decision needed on which cure to arm — Option A (per-organ cooldown key)
  + Option B (direct pairwise stamp cross-check) are watchdog-only / same low-risk class and could
  ship together next session; Option C (supervisor self-restart-on-drift) touches the live daemon
  and should stay a separate, deliberate change | me (next session, on Zero's GO for which
  option(s)) | a repeat of last night's pattern (puller kickstart lands, watchdog re-detects within
  60s) produces exactly one distinct Telegram page per organ per new drift episode, not zero
