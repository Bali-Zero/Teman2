---
adversarial_review: kimi-k3
---

# P03 Deliverable 3 — `com.balizero.flowkit-pro-tunnel` (M5 → Pro)

**Method:** read-only. No `launchctl load/unload/bootout/kickstart`, no plist edit, no write on M5
beyond the repo probe's own heartbeat sidecar. `service_control: none` respected.

> This document was rewritten after adversarial review. An earlier draft claimed the tunnel "was
> not dead then either" and that "the 43h of quiet was 43h of the tunnel working". **Both were
> wrong**, and the refuter proved it from this document's own numbers. The correction is in the
> body, not in a footnote — an annotation underneath does not unsay an assertion above it.

## Verdict: the tunnel is ALIVE NOW — but it has been dying and self-healing

| Claim under test | Measurement (2026-08-23, this session) |
|---|---|
| tunnel currently dead | **FALSE.** `curl http://127.0.0.1:8100/health` **from M5** → HTTP 200, byte-identical JSON to what Pro's gateway serves locally (`connects:17,disconnects:17`). A real HTTP reply traversed the forward. |
| exit 255 means dead | **Misleading.** `launchctl print` returns `state = running`, `pid = 18724`, `last exit code = 255` **in the same read**. 255 is the *previous* instance's epitaph. `ps -p 18724` → alive, ELAPSED `09:52:31`. |
| silent 43h means dead | **The silence is real; the inference was wrong in BOTH directions — see below.** |

## The arithmetic that overturns the first draft

- `~/Library/Logs/flowkit-pro-tunnel.err` last write: **2026-08-23 02:02:46**.
- `ps` ELAPSED for pid 18724 at 11:55:17: **09:52:31** → the process started at **02:02:46**.
- `11:55:17 − 9:52:31 = 02:02:46`. **Delta zero, to the second.**

The current instance was born at the exact second of the last stderr write. Since this log is
written *only on failure*, that write is **the death of the previous instance**, and the pid's
birth is KeepAlive restarting it. So:

- The 9h52m of silence **since** 02:02:46 does indicate a healthy tunnel.
- But the tunnel **demonstrably died and was restarted today**, and its stderr holds **844 failure
  lines**. Deaths are happening; `KeepAlive` is hiding them by healing them.

**Corrected reading of the digest.** The digest was not simply wrong. It read a *real* signal —
this job does fail — through a *broken instrument* (last-exit-code plus log silence), and drew a
wrong conclusion (permanently dead for 43h) from partially true evidence. That is worse than a
plain false positive, because the underlying phenomenon is genuine and will recur.

## Root cause, ATTRIBUTED — two organs disagree, right now

M5's own detector, run read-only, live:

```json
{"label":"com.balizero.flowkit-pro-tunnel","verdict":"FAILING-HONESTLY",
 "last_exit":255,"program":"/usr/bin/ssh","program_exists":true,
 "log_marker":null,"stale_green":false}
```
— `scripts/launchd_liveness_detector.py --json`, **while the tunnel was serving HTTP 200**.

`launchd_liveness_detector.py` judges on `last_exit` and never reads `state`/`pid`, so it
structurally cannot tell "currently running" from "dead".

Its sibling `scripts/check_flowkit_tunnel.py` — written 2026-08-21, whose docstring names this exact
trap — gets it right. **But it is registered and NOT armed**, and the first draft of this document
got that wrong too: I inferred "armed" from a fresh heartbeat sidecar that **this dispatch's own
manual run had just written**. Measured properly afterwards:

- M5 has **no proprioception plist and no proprioception cron** — sweeps are session-triggered only.
- M5's last sweep is `2026-08-22T01:56:41+0800` (**34h old**) and ran **1 probe** — `organs_heartbeat`
  alone. `flowkit` is **ABSENT from `last.json`**.

So between 2026-08-22 01:56 and the manual run at 11:54 today, nothing on M5 ever contradicted the
detector's verdict.

## NAMED DECISION: **REPAIR** — of the instrumentation, not the tunnel

- **Not RETIREMENT**: the tunnel is live, needed (M5 control → Pro render), and correctly shaped
  (`KeepAlive` + `ThrottleInterval=10` is right for a persistent `-N -T` forward; it is what performed
  the self-heal).
- **Not "write a probe"**: the correct probe exists and is right.
- **The repair, all three parts** — fixing one leaves the disease:
  1. `launchd_liveness_detector.py` must not return a failure verdict for a job whose `state = running`
     with a live pid. `last exit code` is the previous instance's epitaph, not a verdict.
  2. **Arm `check_flowkit_tunnel.py`** — `StartInterval` LaunchAgent on M5 (**not** `KeepAlive`; it is
     one-shot, superscar #7), or a Mini cron given Pro's crontab is TCC-blocked over ssh.
  3. **Count the death-restart cycles.** This is the part the first draft would have missed entirely:
     a tunnel that dies and self-heals every few hours is *not* healthy, and both a point-in-time HTTP
     probe and an exit-code reader report it as fine. The signal is the stderr write rate and the pid's
     age resetting — neither is watched today.

Proof-of-armed for (2) is **not** "the plist is installed": it is the sidecar
`~/.organism/last_seen/m5.flowkit_tunnel.json` showing a `ts` that advances **with nobody running it
by hand** — the exact distinction this dispatch got wrong once.

**Successor dispatch, not mine.** `launchd_liveness_detector.py` is outside P03's owned scope. Ships
as a PENDING-ARMS line, per the dispatch's instruction that the ledger line — not the `launchctl`
call — is this deliverable.

## Ruled out, each with its evidence
- **HOME-fork (#1)**: `ProgramArguments[0]` = `/usr/bin/ssh`, a system binary. No `~/scripts/` wrapper can diverge.
- **Pro-side listener absent**: Pro PID 1062 `~/flowkit/venv/bin/python -m agent.main`, uptime 2d17h51m — never restarted across the window.
- **KeepAlive-on-one-shot (#7)**: `-N -T` is a persistent forward; `KeepAlive=true` is correct here.
- **TCC/keychain (#4/W84)**: `BatchMode=yes` + `IdentitiesOnly yes` + explicit `IdentityFile`; no auth or host-key failure in 844 stderr lines.

## Adversarial review

Refuted by **Kimi K3** (cross-family, fresh context), which attacked this document's tunnel verdict
directly. Findings accepted and applied:

1. **"Was not dead then either" / "the 43h of quiet was 43h of the tunnel working" — REFUTED.** The
   refuter derived from this document's own figures that the pid's birth coincides with the last
   stderr write. I re-computed it independently: `11:55:17 − 09:52:31 = 02:02:46`, **delta zero**.
   A log written only on failure, written at the instant the current process was born, records a
   death. Both sentences were removed and the section above replaces them.
2. **Self-contradiction — REFUTED.** The draft said both "is already armed" and "registered but never
   armed". Only the second is true; the first came from a heartbeat sidecar my own manual run had
   written moments earlier. Rewritten in place.
3. **"HTTP 200 proves the forward carried it" — PARTIALLY CONCEDED.** The refuter notes no
   `lsof -i :8100` on M5 was cited to bind the answering socket to pid 18724. The byte-identical
   payload including the `connects:17/disconnects:17` counters makes the attribution strong but not
   airtight. Recorded as a residual, not repaired — the successor's armed probe settles it.
4. **Residual, declared:** the death-restart *rate* over the digest's 43h window remains
   **UNVERIFIED** — 844 stderr lines are cited without a per-event breakdown. Repair part (3) exists
   precisely because nothing measures it today.
