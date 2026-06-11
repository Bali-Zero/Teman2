# WR3 Supervisor Revival — STEP 0 prerequisite for F20 + F21

> **Status: DIAGNOSED — NOT EXECUTED.** Read-only diagnosis of the WR3 video-episode
> supervisor's "12 days no episodes" symptom. No process restarted, no plist/script/cron
> edited, no PG mutated. The fix below is **operator-decided**; this is docs only.
>
> Date: 2026-06-12 · Diagnosed-from: M5 (`balizero`) via `ssh pro` (runtime is the **Pro**,
> user `nuzantara`) · Audit lineage: Fable-5 system audit 2026-06-11 (F18/F20/F21),
> index `WR3-DEBT-INDEX.md`, cicatrix W74.

---

## TL;DR — the premise was wrong, and that IS the finding

The DEBT-INDEX cross-cutting note states the supervisor is **"FAILED, exit=78, zero new
episodes in 12 days."** Live read-only inspection on the Pro **falsifies three of those
four claims**:

| Claim (from DEBT-INDEX / task) | Verified live state | Verdict |
|---|---|---|
| exit **78** (EX_CONFIG) | `launchctl` `last exit code = 74: EX_IOERR` | **WRONG** — it's 74, from the wrapper |
| **FAILED** | `launchctl` `state = running`, pid 24008, alive **1d17h** | **WRONG** — it's running |
| config-validation refusal | supervisor `.py` has **zero** `exit(78)`/`EX_CONFIG`/`SystemExit` paths | **WRONG** — no such guard exists |
| ~12 days no episodes | last episode dir `content-creator-3-roads-2026-05-29`; **only 2 wr3 outbox rows EVER, newest 2026-05-22** | **TRUE** — but the cause is an **input drought**, not a supervisor fault |

**The supervisor is not dead and not misconfigured. It is a healthy, idle event-bus
*consumer* with nothing to consume.** The "no episodes" symptom is an **upstream producer
drought** (nobody has published a `wr3_episode_brief_requested` event since 2026-05-22),
plus a cosmetic-but-noisy `heartbeat-timeout` reconnect churn through the Fly proxy tunnel
that does **not** block work (there is no work queued).

So "revival" here is **not** "fix a crashed daemon" — it is **(a) trigger a real episode to
prove the pipeline end-to-end**, and optionally **(b) quiet the idle-tunnel reconnect churn**
so the next operator doesn't misread it as a failure (as this very index did).

---

## Context

`com.balizero.wr3.supervisor` (LaunchAgent, `KeepAlive=true`, `RunAtLoad=true`,
`ThrottleInterval=30`) runs `~/.openclaw/bin/wr3/wr3-supervisor-wrapper.sh`, which sources
secrets, pins `DATABASE_URL` to the local pg-proxy DSN (`127.0.0.1:15432`), and `exec`s
`apps/backend-rag/.venv/bin/python scripts/wr3_supervisor.py` from the **deploy worktree**
`~/Desktop/nuzantara-deploy` (NOT the main checkout).

`scripts/wr3_supervisor.py` is a long-lived asyncpg daemon: it `LISTEN`s on the 6 WR3 PG
channels (migration 183), and only does work when a NOTIFY arrives on one of them. It is the
*consumer* end of the WR3 EventBus. The *producer* — the thing that publishes the first
`wr3_episode_brief_requested` event — is the `wr3-design-architect` orchestrator, invoked by a
human/agent saying "produce WR3 episode for [topic]". **No producer = no events = supervisor
sits idle by design.**

---

## Root cause (verified, with file:line + the exact evidence)

### Finding 1 — exit 74, not 78; from the WRAPPER, not the supervisor (the headline correction)

- `ssh pro 'launchctl list | grep wr3'` → `24008  74  com.balizero.wr3.supervisor` (pid alive, LastExitStatus 74).
- `ssh pro 'launchctl print gui/<uid>/com.balizero.wr3.supervisor'` → `state = running`, `pid = 24008`, `runs = 2`, `last exit code = 74: EX_IOERR`.
- `ps -p 24008` → started **mer 10 giu 11:42:04 2026**, ELAPSED `01-17:15:38` (≈1d17h), command
  `…/nuzantara-deploy/apps/backend-rag/.venv/bin/python …/nuzantara-deploy/scripts/wr3_supervisor.py`.
- The exit-74 source is **`wr3-supervisor-wrapper.sh`**, which has `exit 74` on two preconditions:
  `DATABASE_URL_LOCAL` unset, and `nc -z 127.0.0.1 15432` failing (pg-proxy unreachable). The
  err log confirms the latter fired exactly **6 times** total
  (`grep -c "15432 unreachable"` → 6) — i.e. 6 transient pg-proxy gaps over the log's life, each
  bouncing the wrapper. `runs = 2` at launchd level means the KeepAlive has only re-spun the job
  twice; this is **not** a launchd crash-loop.
- **`scripts/wr3_supervisor.py` contains no `78` / `EX_CONFIG` / `sys.exit(78)` / `raise SystemExit`
  / `os._exit` anywhere** (grep returned exit 1 = zero matches). The script is a perpetual
  `while not stop_event.is_set()` loop (`run_supervisor`, lines 474–628) that reconnects on
  failure and only `return`s on graceful SIGTERM. **There is no config-validation exit-78 path to
  diagnose** — the "exit=78 EX_CONFIG" premise does not correspond to any code that exists.

> **Why "78" was assumed:** plausible but unverified. The real last-exit is 74 (EX_IOERR) and the
> daemon is running, so the entire "config error refusal" framing is a phantom. (Same class as
> cicatrix ℹ️ META 13-agent-autopsy phantom-citation — a report's specific claim re-checked
> against disk and found false.)

### Finding 2 — the live symptom is `heartbeat timed out after 2.0s` reconnect churn (cosmetic, non-blocking)

- `tail` of `~/Library/Logs/wr3-supervisor.err` is a wall of
  `[wr3-supervisor] reconnect required: heartbeat timed out after 2.0s` (102 occurrences in a
  495-line log) interleaved with occasional
  `listener crashed: ConnectionDoesNotExistError('connection was closed in the middle of operation')`.
- `~/Library/Logs/wr3-supervisor.log` is a matching wall of `Connected to PG (…:15432/nuzantara_rag…)`
  + the 6 `LISTEN wr3_episode_*` lines, repeated **105 times** (≈ one full reconnect cycle per
  heartbeat failure: 105 Connected vs 102 reconnect-required).
- **Mechanism**: the supervisor opens an asyncpg connection through the `fly proxy 15432:5432`
  tunnel, registers the 6 LISTENs, then sits idle (no NOTIFY traffic — see Finding 3). Its Layer-4
  liveness probe (`_heartbeat`, `scripts/wr3_supervisor.py:77-107`) issues a `SELECT 1` wrapped in
  `asyncio.wait_for(..., timeout=2.0)` every 30s (loop at `:573-575`). On a quiet Fly proxy tunnel
  the round-trip intermittently exceeds the **hard-coded 2.0s** ceiling (or the idle tunnel half-drops
  the connection between probes), so `_heartbeat` raises `_ReconnectRequired`, the outer loop
  (`:602-616`) closes the conn and reconnects with backoff. This is the daemon's **defensive design
  working as intended** (it was built precisely to avoid the 2026-05-22 zombie-with-dead-socket scar,
  documented in the `_ReconnectRequired` / `_reconcile_unconsumed` docstrings) — but with a 2.0s
  timeout over a Fly edge tunnel it self-triggers under pure idleness.
- **This churn is NOT the blocker.** The PID survives (caught by the outer loop), reconnects
  successfully each time, and would dispatch any queued event on reconnect via
  `_reconcile_unconsumed`. There is simply nothing to dispatch.

### Finding 3 — the actual "no episodes" cause: ZERO producer events since 2026-05-22 (input drought)

- Read-only PG query (via the deploy venv asyncpg + `DATABASE_URL_LOCAL`, run on the Pro):
  `SELECT channel,count(*),max(created_at) FROM events_outbox WHERE channel LIKE 'wr3_%' AND consumed_at IS NULL GROUP BY channel` → **NO unconsumed wr3 outbox rows.**
  `SELECT count(*), max(created_at) FROM events_outbox WHERE channel LIKE 'wr3_%'` →
  **TOTAL = 2 rows EVER, newest `2026-05-22 16:45:16+00`.**
- `grep -c "→ wr3" wr3-supervisor.log` → **0 dispatches ever.** `grep -c "Replaying" …` → **0**.
- Episode output dirs (`apps/war-room/output/episode/`, both checkouts) top out at
  `content-creator-3-roads-2026-05-29` — the last real run.

**Conclusion:** the WR3 pipeline has produced no new `brief_requested` events for ~21 days. The
supervisor cannot manufacture episodes; it reacts to producer events. The drought is upstream of
the supervisor entirely — at the `wr3-design-architect` invocation layer, which is human/operator-
triggered ("produce WR3 episode for [topic]") and simply hasn't been triggered. **There is no
broken precondition inside the supervisor to fix for episodes to flow — there is a missing trigger.**

### Finding 4 — pg-proxy is STABLE, not flapping (rules out the obvious red herring)

- `com.balizero.wr2.pg-proxy` `launchctl print` → `state = running`, `last exit code = 0`, `runs = 2`.
- `pg-proxy.error.log` `Proxying localhost:15432 …` restart timestamps are **days/weeks apart**
  (…2026-06-08, 06-09, 06-10 11:41, then 06-12 04:56) — NOT a per-minute flap. Last
  `fly proxy exited` was **2026-06-12 04:56 status=0** (one clean restart) and before that
  **2026-05-24 status=1** (a token-rejection burst that self-healed). The current `fly proxy` child
  (pid 22844) ELAPSED was only ~2 min at inspection because of that single 04:56 restart, **not**
  because it churns every 2 min.
- Port `15432` was OPEN at inspection (`nc -z` succeeded, `lsof` shows `flyctl … (LISTEN)`).
- So the heartbeat churn (Finding 2) is **idle-tunnel timeout sensitivity**, not pg-proxy
  instability.

---

## Why / when it "broke"

It did not break in the crash sense. Two independent things coincided:

1. **Producer drought since 2026-05-22** — the last `wr3_episode_brief_requested` event. The
   pipeline was a pilot/manifesto effort (last episode 2026-05-29) and no one has invoked
   `wr3-design-architect` since. This is the real "12 days" (actually ~21 days).
2. **Idle-tunnel heartbeat churn** — present whenever the daemon runs idle through `fly proxy`
   with the 2.0s `_heartbeat` ceiling. It is loud in the logs and produced the stale `74` last-exit
   from the 6 transient pg-proxy gaps, which together created the *appearance* of a failed,
   misconfigured daemon — which the DEBT-INDEX then recorded as "FAILED exit=78".

**No Air-decommission path-drift (W70 family), no HOME-fork drift, no missing TELEGRAM/Flow/Veo
token, no missing venv, no renamed skill dir was found to be the cause.** The wrapper, the venv
(`…/nuzantara-deploy/apps/backend-rag/.venv/bin/python` resolves and runs), the script path, the
secrets, and pg-proxy were all present and functional at inspection.

---

## Fix (operator-decided — NOT executed)

Because the supervisor is healthy and idle, "revival" splits into a **mandatory proof** and an
**optional hygiene** track.

### A. Prove the pipeline end-to-end (the real "revive") — REQUIRED to close F20/F21's blocker

The DEBT-INDEX correctly orders F20/F21 *after* "episodes flow again." To make episodes flow, a
**producer event** must be published — the supervisor will then dispatch it. Options:

- **A1 (recommended) — trigger one real episode.** Invoke `wr3-design-architect` ("produce WR3
  episode for [a safe, low-stakes topic]") in `WR3_DRY_RUN=false`. This publishes
  `wr3_episode_brief_requested`; the running supervisor (already LISTENing) picks it up and the
  lifecycle (brief → pre-render → gate → assembly → critic → staged) runs, producing a fresh
  `episode_manifest.json` — which is exactly the input F20's validator and F21's reflexion
  synthesizer need. **This is the load-bearing step: it both proves the supervisor works AND
  generates the corpus F20/F21 are starved for.**
- **A2 — dry-run smoke first.** If a full Flow/Veo spend is not wanted, publish a single
  `brief_requested` with `WR3_DRY_RUN=true` (plist already passes `WR3_DRY_RUN=false`, so this needs
  a one-shot manual publish, not a plist change) to confirm the consume→route→ack path fires
  (`route_event` logs `→ <agent> ep=…`) without spending credits. Note: dry-run does NOT produce a
  manifest, so it proves the supervisor but does NOT unblock F20/F21.

> Either way, **no supervisor code/plist/cron change is required for episodes to flow** — only a
> producer trigger. That is the corrected, verified shape of this prerequisite.

### B. Quiet the idle-tunnel reconnect churn (optional hygiene — prevents the next misread)

The churn is cosmetic but it is *what made this look like a failure*. To stop a future operator
(or audit) from re-recording "FAILED exit=78":

- **B1 — raise the `_heartbeat` timeout.** `scripts/wr3_supervisor.py:77` defaults `timeout: float = 2.0`;
  the call site `:574` passes `timeout=2.0`. Raise to e.g. 8–10s so a slow-but-alive Fly tunnel
  round-trip doesn't self-trigger a reconnect. (Code change → goes through the normal deploy-worktree
  sync, NOT a plist edit. Operator-decided.)
- **B2 — set a TCP keepalive / `server_settings` on the asyncpg connect** (`:504`
  `asyncpg.connect(database_url)`) so the idle LISTEN connection is kept warm at the socket layer
  rather than relying solely on the 30s `SELECT 1`.
- **B3 — accept the churn as benign** and instead add a one-line note to the DEBT-INDEX / cicatrix
  that "heartbeat-timeout churn on an idle WR3 supervisor is expected and non-blocking; check
  `events_outbox WHERE channel LIKE 'wr3_%' AND consumed_at IS NULL` for real backlog before
  treating it as a fault." (Cheapest; documents the trap.)

**Recommendation:** A1 (trigger one real episode) is the only step that actually unblocks F20/F21.
B is polish — B1 is the highest-leverage of the three if the churn noise is judged worth removing,
but it is not required for episodes to flow.

---

## Verification (how to confirm success, read-only)

After the chosen fix:

1. **Producer event landed**:
   `SELECT id,channel,created_at FROM events_outbox WHERE channel LIKE 'wr3_%' ORDER BY id DESC LIMIT 5;`
   → a fresh `wr3_episode_brief_requested` row newer than 2026-05-22.
2. **Supervisor dispatched it**: `grep "→ wr3" ~/Library/Logs/wr3-supervisor.log` → at least one
   `wr3_episode_brief_requested → <agent> ep=<id>` line, and the outbox row's `consumed_at` becomes
   non-NULL.
3. **A real manifest exists**: a new dir under `apps/war-room/output/episode/<id>/` with
   `episode_manifest.json` (the F20 input).
4. **(If B1 applied)** the reconnect churn rate drops:
   `grep -c "reconnect required: heartbeat" ~/Library/Logs/wr3-supervisor.err` stops climbing over a
   30-min window (compare two `grep -c` snapshots).
5. **Daemon still healthy**: `launchctl print gui/<uid>/com.balizero.wr3.supervisor` → `state = running`,
   `last exit code` no longer 74 after a clean window.

---

## Guardrails

- **Nothing executed by this spec.** Triggering an episode (A1) spends Flow/Veo credits and must be
  an explicit operator action; the heartbeat-timeout change (B1) is a code edit that goes through the
  normal deploy-worktree sync + review, not a hot plist edit.
- **Off-limits**: do not edit `fly.toml`, `.env*`, or hot plists in place. The pg-proxy and supervisor
  plists are `0400`-class hardened — any plist change is its own hardening dance (W65 family).
- **PII boundary**: episode topics for the A1 smoke must be non-PII (public regulatory content), per
  WR3 brief-interpreter Law 2 / NB-ground-truth contract.
- **Anti-hallucination note**: every claim above (exit code 74, state=running, pid/etime, the
  zero-exit-78-paths grep, the 2-rows-ever outbox, the stable pg-proxy timeline) was observed via
  `ssh pro` / grep / Read in the diagnosis turn 2026-06-12. The **only** thing NOT independently
  verified is *why* the producer drought happened (whether `wr3-design-architect` was deliberately
  paused or merely untriggered) — that is an operator-knowledge question, not a disk-observable fact.

---

## Cross-reference

This spec **is the STEP 0 prerequisite** the DEBT-INDEX names for F20 + F21 — but it **corrects** the
index's mechanism claim: the supervisor is **not "FAILED exit=78"**; it is **healthy and idle**, and
the blocker is an **upstream producer drought**, not a dead daemon. F20 (manifest validator) and F21
(reflexion synthesizer) remain correctly ordered *after* "a real episode flows" — which step **A1**
provides. F18 stays independent.

A 2-line pointer to this spec is appended to `WR3-DEBT-INDEX.md` under "STEP 0" (the index is on
`origin/main` as of #1345, so the pointer ships in the same PR as this file).
