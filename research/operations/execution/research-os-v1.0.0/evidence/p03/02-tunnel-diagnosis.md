# P03 Deliverable 3 — `com.balizero.flowkit-pro-tunnel` (M5 → Pro)

**Method:** read-only. No `launchctl load/unload/bootout/kickstart`, no plist edit, no write on M5
beyond the repo probe's own heartbeat sidecar. `service_control: none` respected.

## Verdict: the mandate's premise is FALSIFIED — the tunnel is ALIVE

The dispatch states the tunnel "is **exit 255 / silent 43h** … currently dead". Measured this
session, it is not dead and, on the evidence, was not dead then either.

| Claim | Measurement (2026-08-23 ~11:55 WITA) |
|---|---|
| tunnel dead | **`curl http://127.0.0.1:8100/health` FROM M5 → HTTP 200**, returning byte-identical JSON to what Pro's gateway serves locally (`connects:17,disconnects:17`). A real HTTP reply traversed the tunnel. |
| exit 255 | `launchctl print` returns **`state = running`, `pid = 18724`, `last exit code = 255` in the same read**. 255 belongs to a PREVIOUS instance. `ps -p 18724` → alive, ELAPSED **09:52:31**. |
| silent 43h | `~/Library/Logs/flowkit-pro-tunnel.err` last write **Aug 23 02:02:46**, i.e. ~9h52m of silence — and this log is written **only on failure**. For this organ, **silence is the signature of health.** |

**Why the false alarm is structural, not a typo.** `ssh -N -T` writes nothing to stdout and nothing
to stderr while it works. So a healthy tunnel produces an eternally silent error log. The digest
used *log silence* + *last exit code* as evidence of death — for an organ whose healthy output IS
silence. The modus doctrine already names this exact failure ("a receptor whose HEALTHY output is
silence must expose a self-probe that distinguishes healthy-silent from dead"); the digest violated
it. Silence was read as death, and the 43h of quiet was 43h of the tunnel working.

## Root cause, ATTRIBUTED (not inferred) — two organs disagree, right now

Running M5's own detector read-only, live:

```json
{"label":"com.balizero.flowkit-pro-tunnel","verdict":"FAILING-HONESTLY",
 "last_exit":255,"program":"/usr/bin/ssh","program_exists":true,
 "log_marker":null,"stale_green":false}
```
— `scripts/launchd_liveness_detector.py --json`, on M5, **while the tunnel was serving HTTP 200**.

Its sibling, `scripts/check_flowkit_tunnel.py` (registered in `proprioception.py:1056`, `machines:
["m5"]`, P2), had written 1 minute earlier:

```json
{"organ":"m5.flowkit_tunnel","status":"ok","degraded":false,
 "note":"PID 18724 alive, http://127.0.0.1:8100/ answered (HTTP 404)","ts":"2026-08-23T03:54:23Z"}
```

**Two probes, same machine, same job, opposite verdicts in the same minute — and the digest quotes
the wrong one.** `launchd_liveness_detector.py` judges on `last_exit` and never reads `state`/`pid`,
so it structurally cannot tell "currently running" from "dead". `check_flowkit_tunnel.py` — written
2026-08-21, whose docstring documents this precise trap ("`launchctl list` prints the LAST exit code
even while the job is CURRENTLY RUNNING") — gets it right and is already armed.

**CORRECTION to my own first reading.** I initially inferred from the sidecar's fresh mtime that
`check_flowkit_tunnel.py` was armed and running. That was false: the 11:54 write was **this
dispatch's own manual invocation** — I measured a system my own agent was perturbing. Verified
after the fact:

- M5 has **no proprioception plist and no proprioception cron** — the sweep is session-triggered only.
- M5's last sweep is `2026-08-22T01:56:41+0800` (**34h old**) and ran **1 probe out of the whole
  registry** — `organs_heartbeat` alone. `flowkit` is **ABSENT from `last.json`**.

So the probe is **registered but never armed**: `proprioception.py:1056` declares it, nothing
schedules it, and it did not run in the last recorded sweep. Between 2026-08-22 01:56 and my manual
run at 11:54 today, nothing on M5 ever contradicted the detector's false verdict.

## The two defects compose — that is the actual disease

1. `launchd_liveness_detector.py` **emits** the false signal (judges `last_exit`, never reads
   `state`/`pid`, so it cannot distinguish running from dead).
2. `check_flowkit_tunnel.py` — the probe written specifically to refute that signal, whose docstring
   names the trap verbatim — is **registered and unscheduled**, so nothing periodically refutes it.

Either alone is survivable. Together they produce a confident, wrong, unchallenged claim that
outlived two days and reached a work-packet dispatch as a stated fact. Superscar #2 (Esiste ≠
Armato) in its purest form: the cure was written on 2026-08-21, and has never run.

## NAMED DECISION: **REPAIR** — of the detector, not of the tunnel

- **Not RETIREMENT**: the tunnel is live, needed (M5 control → Pro render), correctly configured
  (`KeepAlive` + `ThrottleInterval=10` is the right shape for a persistent `-N -T` forward, and it
  self-healed twice through real Tailscale flaps).
- **Not "write a probe"**: it exists, is armed, and is right.
- **The repair, both halves** (fixing only one leaves the disease):
  (a) `scripts/launchd_liveness_detector.py` must not return a failure verdict for a job whose
      `state = running` with a live pid. `last exit code` is not a verdict for a KeepAlive
      long-runner — it is the previous instance's epitaph. Classify on the CURRENT instance.
  (b) **Arm `check_flowkit_tunnel.py`** — it exists, is tested, is right, and is scheduled nowhere.
      A `StartInterval` LaunchAgent on M5 (NOT `KeepAlive` — it is one-shot, superscar #7), or a
      Mini cron given that Pro's crontab is TCC-blocked over ssh.
  Proof-of-armed for (b) is NOT "the plist is installed": it is the sidecar
  `~/.organism/last_seen/m5.flowkit_tunnel.json` showing a `ts` that advances **without anyone
  running it by hand** — the exact distinction this dispatch just got wrong once.

**This is a successor dispatch, not mine.** `launchd_liveness_detector.py` is outside P03's owned
scope (`wr3_*`, `docs/wr3/`, `evidence/p03/`). It ships as a PENDING-ARMS line, per the dispatch's
own instruction that the ledger line — not the `launchctl` call — is this deliverable.

## Ruled out, each with its evidence
- **HOME-fork (#1)**: `ProgramArguments[0]` = `/usr/bin/ssh`, a system binary. No `~/scripts/` wrapper exists to diverge.
- **Pro-side listener absent**: Pro PID 1062 `~/flowkit/venv/bin/python -m agent.main`, uptime 2d17h51m — never restarted across the incident window.
- **KeepAlive-on-one-shot (#7)**: `-N -T` is a persistent forward; `KeepAlive=true` is correct here and is what performed the self-heal.
- **TCC/keychain (#4/W84)**: `BatchMode=yes` + `IdentitiesOnly yes` + explicit `IdentityFile`; no host-key or auth failure in 844 lines of stderr.

## Evidence caveat I corrected
The lane's first end-to-end proof was `nc -z` on M5. That probe cannot be red in the right way:
`ssh -L` binds the local port **even when the remote side is unreachable**, so `nc -z` succeeds
against a bound-but-dead tunnel — the lane's own log excerpt (`channel 2: open failed: connect
failed`) is that exact state. Replaced with a real HTTP request through the forward, which is the
probe that can fail. The verdict survived the stronger probe; the evidence for it did not.
