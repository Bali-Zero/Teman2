---
date: 2026-05-23
domain: operations
client_case: pg-proxy flap observability hardening (panel-reviewed 3-LLM)
sources: 4
---

# pg-proxy Perl prefixer runbook (2026-05-23)

## Why this change

`~/scripts/fly-pg-proxy-wrapper.sh` (LaunchAgent `com.balizero.wr2.pg-proxy`,
KeepAlive=true, ThrottleInterval=30) had no timestamp on the child `fly proxy`
output. When the proxy flapped (Fly cloud transient, agent disconnect, token
issue) the operator could see _that_ it restarted but not _when_ — making
correlation with backend timeouts, EventBus drops, and WR3 supervisor restarts
guesswork.

## What changed

**File**: `~/scripts/fly-pg-proxy-wrapper.sh` (gitignored, lives in HOME).
**Backup**: `~/scripts/fly-pg-proxy-wrapper.sh.pre-perl-prefix-2026-05-23`.

Diff (the only meaningful change):

```diff
-# exec so launchd tracks the fly process directly (KeepAlive restarts it cleanly
-# if the proxy connection drops).
-export FLY_ACCESS_TOKEN="$TOKEN"
-exec "$FLY_BIN" proxy "${LOCAL_PORT}:${REMOTE_PORT}" -a "$APP"
+prefix_child_output() {
+  /usr/bin/perl -MPOSIX=strftime -ne '
+    $| = 1;
+    print STDERR "[" . strftime("%Y-%m-%d %H:%M:%S", localtime) . "] " . $_;
+  '
+}
+
+export FLY_ACCESS_TOKEN="$TOKEN"
+"$FLY_BIN" proxy "${LOCAL_PORT}:${REMOTE_PORT}" -a "$APP" 2>&1 | prefix_child_output
+status=${PIPESTATUS[0]}
+echo "[$(ts)] fly proxy exited status=${status}" >&2
+exit "$status"
```

## Panel review (4-LLM gate, 2026-05-23)

Gemini agy + DeepSeek V4 Pro + Codex GPT-5.5 reviewed the proposed diff
BEFORE implementation. Three P0 traps were caught and patched:

| Trap                                                                                                                                                                                    | Panelist                                                                   | Resolution                                                                                                                                             |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/usr/bin/awk` on macOS lacks `strftime()` (no GNU extensions); `gawk` and `ts` absent on this host. Original awk-based patch would crash the wrapper on startup → KeepAlive flap loop. | **Codex** (empirical: `/usr/bin/awk: calling undefined function strftime`) | Switched to `/usr/bin/perl -MPOSIX=strftime` — Perl ships with macOS, POSIX is a core module                                                           |
| `exec foo \| bar` in bash is **undefined behavior** — pipelines need a subshell, can't combine with `exec` process replacement.                                                         | **Gemini**                                                                 | Dropped `exec` keyword. KeepAlive=true + ThrottleInterval=30 respawn the wrapper cleanly on exit. `${PIPESTATUS[0]}` propagates the proxy's exit code. |
| `2>&1 \| prefix` redirects child stderr into the pipeline — if the prefixer writes to STDOUT, errors silently migrate from `pg-proxy.error.log` to `pg-proxy.log`.                      | **Codex**                                                                  | Prefixer writes to STDERR (`print STDERR "..."` in Perl) preserving log-stream segregation                                                             |

Skipped layers (panel convergence):

- **L2 daemon-level `pg_isready` health-check loop**: WR3 supervisor heartbeat (PR #819) already covers consumer-side zombie reconnect. Adding a daemon-level restart loop would race with WR3's recovery and could convert transient slow queries into forced proxy restarts. Skip until empirical evidence justifies it.
- **L3 fly-agent flap monitor**: alert fatigue risk. Existing `fly-restart-loop-detector.sh` already covers correlated symptoms via Telegram cooldown.

## Empirical verification (2026-05-23 04:14 WITA)

```
=== Reload state ===
launchctl bootout gui/501/com.balizero.wr2.pg-proxy
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.balizero.wr2.pg-proxy.plist
PID transition: 13602 (old wrapper) → 49113 (new wrapper) → 49282 (fly proxy child) + 49283 (Perl prefixer)

=== Timestamped log lines (NEW) ===
~/.openclaw/workspace/logs/war-room-v2/pg-proxy.error.log:
[2026-05-23 04:14:28] Proxying localhost:15432 to remote [nuzantara-postgres.internal]:5432
[2026-05-23 04:14:52] fly proxy exited status=0    ← stress-test kill
[2026-05-23 04:14:58] Proxying localhost:15432 to remote [nuzantara-postgres.internal]:5432  ← KeepAlive respawn

=== Stress test (kill child, verify respawn) ===
kill -TERM 49282 (fly proxy)
→ launchd KeepAlive=true respawn wrapper PID 49113 → 52218 within ~5s
→ `nc -z -w 2 127.0.0.1 15432` succeeds after ~10s
→ wrapper logs `fly proxy exited status=0` line correctly (PIPESTATUS propagated)
```

## Why this is not in the Nuzantara git repo

The wrapper script lives in `~/scripts/`, which is gitignored by design
(host-specific, contains paths to user-local Fly config + LaunchAgent labels).
The plist itself IS mirrored at `infra/launchagents/com.balizero.wr2.pg-proxy.plist`
but the wrapper is HOME-local. This runbook is the canonical record of the
change for future operators.

## Rollback procedure

```bash
cp ~/scripts/fly-pg-proxy-wrapper.sh.pre-perl-prefix-2026-05-23 ~/scripts/fly-pg-proxy-wrapper.sh
launchctl bootout gui/$(id -u)/com.balizero.wr2.pg-proxy
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.pg-proxy.plist
sleep 5
nc -z -w 2 127.0.0.1 15432 && echo "port 15432 OPEN"
```

## Cross-references

- **PR A (companion)**: `feat/mig-107-promotion-2026-05-23` (PR #828) — migration 107 promotion + 193 ledger reconcile. Separately mergeable.
- **WR3 supervisor heartbeat** (PR #819) — consumer-side reconnect, complementary to this observability fix.
- **fly-restart-loop-detector.sh** (`~/scripts/`) — Telegram-cooldown alerter on correlated Fly symptoms.
- **Panel synthesis**: `/tmp/107-flap-panel/SYNTHESIS.md` (also references Codex's `codex.md`, Gemini's `gemini.md`, DeepSeek's `deepseek.md`).
