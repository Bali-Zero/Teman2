---
date: 2026-07-17
domain: operations
client_case: none (WR2 infra reliability)
sources:
  - "scripts/wr2-deploy-pull.sh (canon, ~/nuzantara-deploy puller — read this session)"
  - "scripts/wr2_supervisor.py (read this session)"
  - "scripts/wr2_supervisor_watchdog.py (read this session)"
  - "scripts/lib/wr2_runtime_stamp.py (read this session)"
  - "scripts/cli/nz, infra/eventbus/meta_dispatcher.py, infra/launchagents/com.balizero.wr2.supervisor.plist (cross-checked during adversarial review, this session)"
  - "live disk (Pro, read-only): ~/.organism/last_seen/wr2.supervisor.runtime.json, wr2.html_apply.runtime.json, wr2.deploy_pull.json"
  - "live disk (Pro, read-only): ~/logs/wr2-deploy-pull.log, ~/logs/wr2_supervisor_watchdog.log"
  - "live disk (Pro, read-only): git -C ~/nuzantara-deploy log; ps -o pid,lstart,etime for pid 88059"
  - ".claude/skills/modus/PENDING-ARMS.md (WR2 C1+C2 arming ledger entry, closed 2026-07-03)"
adversarial_review: codex
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
(`launchctl kickstart -k`) — **already exists and is armed**; `launchctl` accepted the restart on
every tick in last night's log, and the *final* on-disk state (pid 88059 alive on the current HEAD,
§2) proves the last restart landed. (Caveat, per adversarial review: a 0-exit `launchctl` return
proves the command was accepted, not that each intervening restart fully re-executed on the intended
code — only the final observed state is independently confirmed; and the late ticks 00:43→00:57 are
~14 min apart, i.e. NOT purely the hourly `StartInterval`.) The actual disease is a **code-level
alert-dedup defect**, not "nothing reloads the supervisor": all `runtime_stale` findings share a
**single 24-hour cooldown key** (`_alert_due("runtime_stale", …)`, watchdog line 743; cooldown
`ALERT_COOLDOWN_SEC=86400`, line 137), so after the first page fires the key is armed for 24h and
**every subsequent `runtime_stale` alert is suppressed — including a genuinely NEW drift episode or a
SECOND organ drifting in the same window.** (Collapsing the ~49 per-minute recurrences of ONE ongoing
episode into a single page is *correct* dedup, not the bug — the bug is that the cooldown never resets
on recovery and is keyed per-probe rather than per-episode/organ.) Two honesty caveats the code forces
(both from adversarial review): the watchdog log records only `organs=<count>`, NOT organ identity or
problem-type, so "all ~49 suppressed lines were the supervisor on old code" is an *inference* from the
surrounding kickstart timeline, not something the suppressed lines themselves prove; and the cooldown
state + `ALERT P1` log line are set *unconditionally* after a best-effort `_send_telegram()` that
swallows send failures (watchdog lines 748-756), so the log proves the alert PATH was entered, not
that Telegram delivered. This is a scar-family #2 (*esiste ≠ armato* / "green mente, muore muto")
variant: the detector is correct — the **cooldown-key granularity + missing recovery reset** is the
defect.

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

2. **The watchdog cross-check** (`scripts/wr2_supervisor_watchdog.py:654-681`,
   `_probe_runtime_stale()`), polled every `POLL_INTERVAL_SEC=60` (line 131) inside
   `_evaluate_outcome_probes` (line 741) for each organ in
   `RUNTIME_STALE_ORGANS = ("wr2.html_apply", "wr2.supervisor")` (line 619): it reads that organ's
   `.runtime.json` and appends a `runtime_stale` finding when the stamp diverges from disk.
   **Precision nuance (corrected per adversarial review):** the `pid`-alive gate (`_pid_alive`, line
   673) guards **only the `head-moved` comparison** — i.e. only for a live pid does it run `git -C
   <checkout> rev-parse HEAD` **live** and compare it to the stamp's frozen `head_sha`, logging
   `head-moved:<old>-><new> (live pid <pid> on old code)` (line 677). The other two problem classes —
   `dirty-checkout` and `stale-modules:<…>` (lines 667-670) — are appended **regardless of process
   liveness**, straight from the stamp's stored fields. So "a dead one-shot worker's old stamp is
   never flagged" holds *only* for head-moved, not for a stamp that was `dirty`/`stale` at its last
   run. (`_pid_alive` also only tests that *some* process holds that pid — PID reuse could read as a
   false "live", lines 645-651.)

   **Important nuance**: this check compares each organ **independently against the live checkout
   HEAD**, not the two organs' stamps **against each other**. In the common case (html_apply's own
   stamp is always ≈ disk-fresh) this converges to the same practical signal as "supervisor vs
   html_apply", but it is not literally that comparison — see Option B below.

3. **git log** as ground truth for how far behind: `git -C ~/nuzantara-deploy log --oneline` gives
   the commit chain; comparing a stale stamp's `head_sha` position in that chain against the current
   tip is how "2 commits behind" gets a number (verified live this session — see §2).

## 2. Empirical timeline, last night (Pro, all times WITA, all read from disk this session)

`scripts/wr2-deploy-pull.sh` (canon; the live puller invoked by
`com.balizero.wr2.deploy-puller.plist`, `StartInterval=3600`) ran cleanly on its hourly schedule
18:43→23:43 and then twice more closely-spaced at 00:43 and 00:57, each time fast-forwarding
`~/nuzantara-deploy` and — because `WR2_DEPLOY_PULL_KICKSTART=1` is set in that plist's
`EnvironmentVariables` (per the closed PENDING-ARMS line "WR2 C1+C2 arming... kickstarted 13:42;
`WR2_DEPLOY_PULL_KICKSTART=1` written into deploy-puller plist"; **and evidenced live by the kickstart
lines below actually firing, which `wr2-deploy-pull.sh:389` only emits when that env var is set**) —
kickstarting all three consumer organs (`wr2-deploy-pull.sh:389-405`):

```
2026-07-16 23:43:33 WITA  OK: fast-forwarded b348162b8 -> a1cee94d1 (2 commits)
                          kickstart html-apply OK / kickstart -k supervisor OK / kickstart -k supervisor-watchdog OK
2026-07-16 23:53:50,163   wr2_supervisor_watchdog: WARNING ALERT P1 runtime_stale organs=1   <- alert path entered; send attempted (delivery not proven by this line)
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

**Reading this timeline**: the puller's own kickstart mechanism logged no failures (zero `WARN:
kickstart ... failed` lines in the whole window — grepped the full log, not just a tail), and the
final observed state (above) confirms the last restart landed. The watchdog's `_probe_runtime_stale()`
logged a `runtime_stale` finding **within minutes** (first `ALERT P1` at 23:53:50) and **kept logging
one every ~60s for ~49 minutes**, then `cooldown active` thereafter — the detector polling exactly as
designed. **Two claims here are weaker than they first read (per adversarial review) and are stated
honestly:** (1) the watchdog log emits only `organs=<count>`, not identity, so that the ~49
recurrences were *all* "supervisor on old code" is an inference from the bracketing kickstart events,
not proven by the lines themselves (a line could in principle be an html_apply
`dirty-checkout`/`stale-modules` or a PID-reuse misfire); (2) the first `ALERT P1` proves the alert
PATH executed, not that Telegram delivered — `_send_telegram()` is best-effort and swallows
missing-token/POST failures while the caller still arms the 24h cooldown (lines 748-756), so a failed
send would suppress the next 24h with *zero* delivered pages. What is solid: after the first fire the
single `runtime_stale` cooldown key was armed, everything after was logged `cooldown active`, and the
00:43:40 and 00:57:24 ticks (~14 min apart — note NOT the hourly `StartInterval`) fast-forwarded +
kickstarted the daemon back onto current code, closing the gap on their own schedule (not because
anyone was paged to intervene).

## 3. Why the supervisor doesn't reload on its own

`wr2_supervisor.py` is a plain long-running Python process (`asyncio.run(_amain())`, line 818). Like
any CPython process, once its modules are imported at boot they stay resident in memory for the
life of the process — nothing inside its own tick loop re-imports or re-checks its own source files.
The **only** thing that can put fresh code into that process is killing it and letting it start
over. Today the **automatic, scheduled** trigger is external and single-sourced in one place:
`wr2-deploy-pull.sh`'s own `launchctl kickstart -k` call, run right after its own `git merge
--ff-only` (lines 363 → 389-405, same process, sequential). There is no in-process self-check and no
signal handler inside the daemon. **Correction (per adversarial review): "single-sourced" is true only
of the scheduled/automatic path — it is NOT the only `kickstart -k` of the supervisor in the repo.**
At least two other restart paths exist: the manual operator command `nz wr2 supervisor restart`
(`scripts/cli/nz:437`) and the event-driven eventbus route `topic.candidate.created →
launchctl_kickstart com.balizero.wr2.supervisor` (`infra/eventbus/meta_dispatcher.py:68-69`, via
`_kickstart` = `kickstart -k`). Whether the eventbus path is armed live is a separate question, but the
categorical "no independent second trigger" claim is false as written — the puller is the only
*hourly* trigger, not the only trigger.

This has one direct, verifiable consequence: **any advance of `~/nuzantara-deploy`'s HEAD that does
not go through `wr2-deploy-pull.sh` bypasses the reload trigger** (unless it happens to route through
`nz`/eventbus). The script's own comment (`wr2-deploy-pull.sh:227-238`) states the deploy clone is "BY
CONTRACT read-only runtime" — but that contract is documentation, not enforcement; nothing on disk
stops an interactive `git -C ~/nuzantara-deploy fetch && git merge` (or a plain `git pull`) run by any
human or agent session from advancing the checkout outside the wrapper, silently orphaning the
supervisor's frozen boot stamp with zero kickstart. **This "out-of-band manual git op was the proximate
trigger" is an explicitly UNVERIFIED hypothesis, not a finding (flagged by adversarial review):** no
reflog, command audit, or actor evidence was collected on `~/nuzantara-deploy`, and the observed drift
is equally consistent with an *ineffective/incomplete* kickstart, a `dirty`/`stale-modules` stamp, a
PID-reuse misfire, or any of the other checkout-advance paths above (nz / eventbus). It is offered as
the plausible-but-unproven mechanism for *why* the drift existed; the *why it wasn't paged more than
once* answer (§2) is the code-level cooldown defect and stands independently of whichever mechanism
advanced the checkout.

## 4. Cure options (none armed — proposal only)

### Option A — Split the alert cooldown key by organ (+ problem class)
Change the single blanket `_alert_due("runtime_stale", now_epoch)` (`wr2_supervisor_watchdog.py:743`,
state key `last_alert_runtime_stale` at line 755) into a **per-organ** (optionally per-problem-class)
key + per-organ state, iterating the findings list (`for r in runtime`, lines 744-746) and calling
e.g. `_alert_due(f"runtime_stale:{r['organ']}", …)` with a matching per-organ `_state_set`.
**Trade-off**: lowest risk of the three — touches only the watchdog, zero change to the live
supervisor daemon, small-ish diff (note it is *not* a one-line change: the list handling, message
generation, and per-key state update must all be restructured — the naive `finding['organ']` sketch is
wrong, `finding` is not in scope at line 743). **Scope correction (per adversarial review): Option A
does NOT close "the 49 silent recurrences."** Those 49 were (inferably) ONE ongoing episode of ONE
organ; a per-*organ* key still fires once and suppresses that organ's next-24h recurrences exactly as
today — which is *correct* dedup. What A actually buys is: **a SECOND, different organ drifting inside
the same 24h window is no longer masked** by the supervisor's cooldown. It does **not**, by itself,
re-page for a genuinely NEW drift *episode of the same organ* within 24h — that needs a **recovery-edge
reset** (clear/expire the key when the organ's finding clears) or an episode fingerprint, which A
should be paired with. Residual risk: keying by the exact `head_sha` pair (changes hourly) would
re-page every tick; `organ` (or `organ:problem-type`) + recovery reset is the balance.

### Option B — Direct pairwise cross-check (the literal "incrocio di 2 heartbeat")
Add a new, independent probe that reads `wr2.supervisor.runtime.json` and
`wr2.html_apply.runtime.json` **directly against each other** and pages distinctly (e.g.
`SUPERVISOR_LAGS_WORKER`) when the supervisor is running different code from a more-recently-stamped
worker AND the supervisor's `pid` is still alive. **Mechanism correction (per adversarial review):**
two JSON reads alone can NOT establish that the supervisor's `head_sha` is *older* — a SHA is an opaque
identifier, and inequality proves only *difference*, not ancestry/age. The orderable signal that IS in
the stamp is the `ts` field: fire when `supervisor.head_sha != html_apply.head_sha` **AND**
`html_apply.ts` is more recent than `supervisor.ts` (html_apply ran later, on different code) — a
recency **heuristic**, not a proof of git ancestry. If true ancestry ("supervisor's HEAD is strictly
behind") is required, that still needs one `git merge-base --is-ancestor` call, so B is not strictly
git-free for the strong claim. **Trade-off**: still cheap (at most one git call, not a per-organ
`rev-parse`), can poll often, complementary to — not a replacement for — the existing vs-disk check
(§1.2), which also catches the case where html_apply itself hasn't run recently enough to be a fresh
reference. Touches only the watchdog, not the supervisor.

### Option C — Supervisor self-checks its own drift and requests its own restart
On a coarse cadence, compare `wr2_runtime_stamp.current_head(checkout)` to the boot provenance; on
mismatch, log WARN and — only if a new env flag (e.g. `WR2_SUPERVISOR_SELF_RESTART_ON_DRIFT=1`) is
armed — trigger its own restart. **Three implementation corrections (per adversarial review — the
original sketch was both misplaced and dangerously backwards):** (1) there is **no tick loop in
`_amain()`** — `_amain()` (line 745) creates the shutdown event, spawns `runner =
create_task(_run_loop())`, then `await _shutdown_event.wait()`; the periodic work lives in
`_run_loop()`, which is where the drift check must be added (not `_amain`). (2) The boot `head_sha` is
**not** "already in memory": `_write_runtime_stamp_best_effort()` computes `stamp` as a discarded local
and only writes it to disk (lines 803-804); C must either stash the boot SHA in a module global at boot
or re-read `~/.organism/last_seen/wr2.supervisor.runtime.json`. (3) **The restart trigger must be a
NON-zero exit, not a "graceful" exit(0).** `com.balizero.wr2.supervisor.plist` sets `KeepAlive =
{SuccessfulExit=false, Crashed=true}` (lines 30-35) — launchd restarts on crash / *un*successful exit,
NOT on a clean exit. A graceful `exit(0)` (or the current `main()` returning `0`) would leave the
daemon **DOWN**, not respawned. C must therefore `os._exit(1)` / `sys.exit(1)` (after draining
in-flight work) so `SuccessfulExit=false` fires the respawn — or, alternatively, flip the plist to
`SuccessfulExit=true`. **Trade-off**: the most structurally complete cure (removes the single-point
dependency on the puller's kickstart) but the only option that touches the live daemon's own run loop —
exactly the class of change this mandate said not to make tonight — and it now clearly needs a paired
plist/exit-code decision. Needs care around in-flight work (a render/lease in progress) before any
self-exit.

**Discarded alternative (documented, not proposed)**: SIGHUP-triggered in-process hot-reload
(`importlib.reload` of watched modules) instead of a full process restart. Rejected on inspection:
Python hot-reload of a long-running asyncio daemon is a known correctness hazard (stale class
identity across `isinstance` checks, half-reloaded module graphs, live object references to old
code) — `kickstart -k` (full restart) is simpler and almost certainly why the existing mechanism
chose it over a signal-based reload in the first place.

**Recommendation (non-binding, revised post-review)**: A (per-organ key) **paired with a
recovery-edge cooldown reset** is the minimum that actually restores per-episode paging — A alone only
un-masks a *second* organ, it does not re-page a new same-organ episode (see Option A). B adds a
cheaper, more-direct lag signal but only as a `ts`-recency heuristic (not SHA-age). Both are
watchdog-only / zero-daemon-touch. Separately, note the **delivery-ack gap** surfaced by review (the
cooldown arms even when `_send_telegram()` silently fails, lines 748-756) — none of A/B/C fixes that;
it wants its own small change (only arm the cooldown on a confirmed send). C is the deeper fix but must
be a deliberate, separate, tested change to the live daemon, with the exit-code/plist correction above
— not bundled with A/B.

## 5. PENDING-ARMS

- opened 2026-07-17 | WR2 supervisor/html_apply runtime-drift paging gap (this report) — the detector
  polls correctly (~49 `runtime_stale` recurrences logged 23:54-00:42 WITA; the log records only
  `organs=<count>`, so "all supervisor-on-old-code" is inference from the bracketing kickstarts, not
  proven per-line), but the single blanket 24h `runtime_stale` cooldown key
  (`wr2_supervisor_watchdog.py:137,743`) suppressed every subsequent alert after the first at
  23:53:50, and the cooldown arms even if that first `_send_telegram()` silently failed (lines
  748-756) | decision needed on which cure to arm — Option A (per-organ key) **+ recovery-edge reset**
  and Option B (`ts`-recency pairwise cross-check) are watchdog-only / same low-risk class and could
  ship together next session; Option C (supervisor self-restart-on-drift) touches the live daemon,
  needs the NON-zero-exit / plist `SuccessfulExit` correction (see §4), and should stay a separate,
  deliberate change | me (next session, on Zero's GO for which option(s)) | a repeat of last night's
  pattern (puller kickstart lands, watchdog re-detects within 60s) produces one distinct Telegram page
  per organ per NEW drift episode (A + recovery reset), not zero

## Adversarial review

**Seat:** `codex` (OpenAI GPT-5.6, model `gpt-5.6-sol`, `model_reasoning_effort=high`,
`--sandbox read-only` against this worktree). Cross-family refutation (generator = Claude/Sonnet,
grader = Codex — generator ≠ grader, per R1 / `scripts/check_adversarial_review.py`). The refuter was
instructed to be hostile, to VERIFY every concrete file:line claim against the real repo, and to
return surviving objections or an explicit "diagnosis holds". Its verdict: **DIAGNOSIS HAS DEFECTS.**
Codex confirmed the core code-level mechanism (boot-only supervisor stamp; per-organ
stamp-vs-live-HEAD comparison; puller `kickstart -k` gated on `WR2_DEPLOY_PULL_KICKSTART=1`; the
default 24h blanket `runtime_stale` cooldown key at lines 137/743; persistent cooldown state) but
refuted several load-bearing claims. **Each surviving objection was independently re-verified against
the code THIS session** before the diagnosis above was corrected (W65 — the refuter can also
hallucinate; the father's last grep is never delegated).

**Surviving objections — all accepted, diagnosis text corrected (not papered over):**

1. **Option A does NOT "close the 49 recurrences."** Re-verified (`_alert_due` lines 218-223 + state
   key line 755): a per-*organ* key still fires once per organ and suppresses that organ's next-24h
   recurrences — which is *correct* dedup. A only un-masks a *second, different* organ in the same
   window; re-paging a NEW same-organ episode needs a recovery-edge cooldown reset. → §0, §4-A,
   §4-Rec, §5 rewritten; A now explicitly paired with a recovery reset.
2. **Option B cannot order SHAs by "age" from two JSON reads.** Re-verified (stamp carries `ts`, line
   680): SHA inequality proves difference, not ancestry. B corrected to a `ts`-recency heuristic
   (`html_apply.ts` newer + head_sha differs), with a `git merge-base --is-ancestor` call noted as the
   only way to prove strict ancestry. → §4-B rewritten.
3. **Option C was dangerously backwards.** Re-verified `com.balizero.wr2.supervisor.plist:30-35` =
   `KeepAlive{SuccessfulExit=false, Crashed=true}` → a clean `exit(0)` is NOT respawned (daemon would
   stay DOWN). Also `_amain()` (line 745) has no tick loop (work is in `_run_loop()`), and the boot
   `head_sha` is a discarded local (lines 803-804), not "in memory." C rewritten: must exit NON-zero
   (or flip the plist), add the check in `_run_loop`, and stash/re-read the boot SHA. → §4-C rewritten.
   (This was the most dangerous defect — the original "confirmed present KeepAlive.SuccessfulExit
   brings it back up" was a phantom confirmation of the *opposite* of what the plist says.)
4. **"REAL page sent" overstated.** Re-verified `_send_telegram` (lines 239-268) swallows
   missing-token/POST failures, and the caller arms the cooldown + logs `ALERT P1` unconditionally
   (lines 748-756). The log proves the alert PATH ran, not Telegram delivery — and the cooldown arms
   even on a failed send (a distinct latent defect none of A/B/C fixes). → §0, §2, §4-Rec, §5 corrected.
5. **"49/49 true positives" unprovable from the log.** Re-verified: the log emits only
   `organs=<count>` (line 756), not identity/problem-type. "All 49 = supervisor on old code" is an
   inference from the bracketing kickstarts, not proven per-line. → §0, §2, §5 softened to inference.
6. **"100% single-sourced" is false.** Re-verified two other `kickstart -k` paths of the supervisor:
   `nz wr2 supervisor restart` (`scripts/cli/nz:437`) and eventbus `topic.candidate.created`
   (`infra/eventbus/meta_dispatcher.py:68-69`). The puller is the only *hourly* trigger, not the only
   trigger. → §3 corrected.
7. **`_pid_alive` gate mis-described.** Re-verified (lines 662-681): only `head-moved` is pid-gated;
   `dirty-checkout`/`stale-modules` fire regardless of liveness; `_pid_alive` is existence-only (PID
   reuse). → §1.2 corrected.
8. **"Manual git op = most likely proximate trigger" is speculation.** No reflog/audit was done; the
   drift is equally consistent with an incomplete restart, a dirty/stale stamp, PID reuse, or the
   nz/eventbus paths. → §3 relabelled as an explicitly unverified hypothesis.
9. **`launchctl` 0-exit ≠ each restart fully succeeded**, and the 00:43→00:57 ticks are ~14 min apart
   (NOT the hourly `StartInterval`). Only the final observed state is independently confirmed. → §0,
   §2 caveated.

**Objections raised but which do NOT survive (honest accounting):**
- *"Repo cannot prove the live deploy-puller plist is armed"* (Codex on the plist env var): the arming
  is evidenced not by the repo but by the **live log's kickstart lines**, which
  `wr2-deploy-pull.sh:389` only emits when `WR2_DEPLOY_PULL_KICKSTART=1` — so the claim is evidenced,
  just from the log, not the repo. Diagnosis stands (wording tightened in §2).
- *"The tracked plist runs `/Users/nuzantara/scripts/wr2-deploy-pull.sh`, not the repo copy"* — true and
  noted (this is a HOME-fork, cicatrix family #1; live-vs-repo equivalence was not diff-checked this
  session), but it is adjacent to, not a defect in, this diagnosis's substance.

**Net:** no objection invalidated the *root cause* (single blanket 24h `runtime_stale` cooldown key,
no recovery reset). The corrections tightened every *empirical* overclaim and fixed all three cure
options — most importantly Option C, whose original form would have killed the daemon. Full refuter
transcript captured out-of-tree this session (scratchpad, not committed).
