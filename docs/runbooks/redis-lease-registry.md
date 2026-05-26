# Redis Lease Registry (SOTA wave 2026-05-24)

Runbook for `scripts/agent_lease.py` + the `pre-commit lease-check` hook.

## Rationale (closes cicatrix family W40 / W50 / W51 / W52)

Multi-agent operation on Nuzantara (Pro, Mini-Pro2, parallel Claude sessions,
Codex worktrees, Antigravity) repeatedly produced **silent concurrent
mutations of the same shared file**:

- **W40 (2026-05-23)** — Session-A's worktree picked migration number `194`
  for `194_organism_incident_ledger.sql` 5 minutes before PR #828 merged
  another `194_reconcile_107_bridge_outbox_tracking.sql`. Next deploy would
  have hard-failed at `_assert_unique_migration_numbers`.
- **W50 (2026-05-23)** — `launch_dlq_autopilot.sh` wrapper exec'd a stale
  HOME-fork of the script (May-11 copy) for 4+ days; repo fix never propagated.
- **W51 (2026-05-23)** — `com.nuzantara.sentinel.plist` exec'd a 24-day-stale
  HOME-fork of `nuzantara-sentinel.py`, missing 4 Phase features. Sentinel
  was making 60% more escalations / running 75% slower than the repo version
  for 3+ weeks.
- **W52 (2026-05-23)** — `scripts/lint_launchagents.sh` got a new rule to
  detect the W50/W51 class at CI time. Surveyed **84 of 167 plists (50%)**
  pointing at `$HOME/scripts/` HOME-forks of unknown drift.

Root pattern: **two agents touch the same file, neither knows about the other,
the later commit silently wins or both apply incompatible mutations**. The
existing lint scripts (`lint_launchagents.sh`, `lint_migration_numbers.py`,
`lint_migration_rollback.py`) catch the _symptom_ at commit time but not the
_race_. The Redis lease registry adds an upstream coordination layer:

> "I claim this file for the next 5 minutes. Any other agent who tries to
> commit a change to it gets blocked at pre-commit with my task_id."

## Architecture

| Component       | Path                                                        | Role                                                     |
| --------------- | ----------------------------------------------------------- | -------------------------------------------------------- |
| CLI             | `scripts/agent_lease.py`                                    | acquire / release / heartbeat / list / check             |
| Pre-commit gate | `.husky/pre-commit`                                         | block staged hot-zone files if leased by another task    |
| Tests           | `scripts/tests/test_agent_lease.py`                         | 20+ unit tests via fakeredis + optional real-Redis e2e   |
| Audit trail     | `~/.agent/leases.jsonl`                                     | one JSON line per acquire / release / heartbeat / denied |
| Redis backend   | `127.0.0.1:6379` (Pro) — Tailscale `100.93.236.6` from Mini | already live (`brew services list \| grep redis`)        |

**Key pattern:** `agent_lock:<resource>` (e.g. `agent_lock:apps/backend-rag/backend/db/migrations_v2`).
**Value:** JSON `{task_id, host, pid, lane, created_at, ttl_s}`.
**Atomicity:** acquire uses `SET key value NX EX ttl`; release + heartbeat use
Lua scripts (`GET → check task_id → DEL/EXPIRE`) for token-owned mutations.

## Hot-zone paths (regex enforced by pre-commit)

```
^infra/launchagents/.*\.sh$
^apps/backend-rag/backend/db/migrations_v2/.*\.sql$
^shared/escalations.*\.jsonl$
^scripts/(nuzantara-sentinel|dlq_autopilot|pg-to-organism-bridge)\.py$
^.github/workflows/.*$
^apps/backend-rag/backend/services/(auth|billing|pricing)/.*$
```

Files outside the hot-zone regex skip the lease check entirely — the typical
commit (docs, tests, app code, frontend) is unaffected.

## Usage

### Acquire a lease before editing

```bash
export TASK_ID="W56-fix-sentinel-restart-loop-$(date +%s)"
python3 scripts/agent_lease.py acquire \
    scripts/nuzantara-sentinel.py \
    --task-id "$TASK_ID" \
    --ttl-s 600 \
    --lane backend

# … edit + stage + commit normally; pre-commit sees TASK_ID env and lets you through …
git add scripts/nuzantara-sentinel.py
git commit -m "fix(sentinel): …"

# Release when done
python3 scripts/agent_lease.py release scripts/nuzantara-sentinel.py --task-id "$TASK_ID"
```

### Long-running session — keep the lease alive

```bash
# Started a 30-min editing session, default ttl=300 (5min) too short
( while true; do
    python3 scripts/agent_lease.py heartbeat \
        scripts/nuzantara-sentinel.py --task-id "$TASK_ID" --extend-s 600
    sleep 240
done ) &
```

### List active leases (dashboards / debug)

```bash
python3 scripts/agent_lease.py list                # tabular
python3 scripts/agent_lease.py list --json         # for jq / scripts
python3 scripts/agent_lease.py list --lane backend # filter by lane
```

### Manual lease conflict resolution

When `git commit` blocks with `BLOCKED: path '…' is leased by another task`:

1. **Read the holder details** printed by the hook (task_id, host, pid, ttl_remaining).
2. **Check if the holder is alive**:
   - Same host → `ps -p <pid>` — if dead, lease is stale, see step 4.
   - Other host → `ssh <host> "ps -p <pid>"` (works for `Nuzantara` ↔ `Mini-Pro2`).
3. **If holder alive** → coordinate via Slack / Telegram / talk to the operator
   running that task_id. The lease is doing its job.
4. **If holder dead / stuck** → wait for TTL expiry (max `ttl_remaining` seconds),
   OR force-release if you understand the consequences:
   ```bash
   # Force-release someone else's lease (emergency only)
   redis-cli DEL agent_lock:scripts/nuzantara-sentinel.py
   ```

## Troubleshooting

### Redis is down → commits pass through silently with WARN

Brief HARD constraint: "MAI block commit per Redis outage". The CLI's `check`
sub-command catches `RedisUnavailable` exceptions and returns exit 0 + emits
a WARN to stderr. The pre-commit hook therefore exits 0 → the W41/W42/print
checks proceed normally.

To diagnose:

```bash
redis-cli ping                                                    # PONG expected
brew services list | grep redis                                   # 'started' expected
python3 -c "import redis; redis.Redis().ping()" && echo OK
tail -n 20 ~/.agent/leases.jsonl                                  # check audit trail freshness
```

### Kill switch for emergencies / CI

```bash
export AGENT_LEASE_ENFORCEMENT=false
git commit -m "…"                                                 # bypasses the lease check entirely
```

Use sparingly. CI environments (GitHub Actions runners) should set this to
`false` since they don't participate in the multi-agent coordination — they
run on ephemeral hosts with no Redis access.

### "lease registry has stale entries from a crashed agent"

Each lease has a default TTL of 300s (5min). If an agent crashes mid-session
without releasing, the lease auto-expires within `ttl_s` seconds. For longer
TTLs, use a heartbeat loop (see _Long-running session_ above).

To purge ALL leases (nuclear option, blocks no one currently):

```bash
redis-cli --scan --pattern 'agent_lock:*' | xargs -r redis-cli DEL
```

### Cross-host coordination (Pro ↔ Mini-Pro2)

Mini-Pro2 should point at Pro's Redis via Tailscale:

```bash
# On Mini-Pro2 — add to ~/.zshrc or ~/.nuzantara-secrets.env
export REDIS_HOST=100.93.236.6
export REDIS_PORT=6379
```

Verify: `REDIS_HOST=100.93.236.6 redis-cli ping` from Mini.

If you forget, Mini will use its own local Redis (if any) and the two hosts
won't see each other's leases — exactly the pattern this system exists to
prevent. Add a `mem save unresolved "Mini lacks REDIS_HOST=100.93.236.6 — leases not shared"` if you find this state.

## Audit trail format

`~/.agent/leases.jsonl` — one event per line, JSON:

```json
{"event":"acquire","lane":"backend","resource":"scripts/nuzantara-sentinel.py","task_id":"W56-fix-…","ts":1779620669.58,"ttl_s":600}
{"event":"heartbeat","extend_s":600,"resource":"scripts/nuzantara-sentinel.py","task_id":"W56-fix-…","ts":1779620909.12}
{"event":"release","resource":"scripts/nuzantara-sentinel.py","task_id":"W56-fix-…","ts":1779621203.44}
{"event":"release-denied","holder":"W56-fix-…","resource":"scripts/nuzantara-sentinel.py","task_id":"WRONG-id","ts":1779621210.01}
```

Common queries:

```bash
# Most recent 20 events
tail -n 20 ~/.agent/leases.jsonl | jq

# Conflicts in last 24h
jq -c 'select(.event=="release-denied" or .event=="heartbeat-denied")' ~/.agent/leases.jsonl

# Lease activity for one task_id
jq -c 'select(.task_id=="W56-fix-…")' ~/.agent/leases.jsonl
```

## Related cicatrix entries

- **W40** (2026-05-23): migration 194 collision — `cicatrix-scars.md` line ~50
- **W50** (2026-05-23): dlq_autopilot HOME-fork — `cicatrix-scars.md` line ~150
- **W51** (2026-05-23): sentinel plist HOME-fork — `cicatrix-scars.md` line ~200
- **W52** (2026-05-23): launchagents-lint W52-rule — `cicatrix-scars.md` line ~80
- **SOTA synthesis** (2026-05-24): `research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md`

## Future work (deferred)

- **Auto-acquire on `Edit` tool use** via Claude Code hook — would make lease
  acquisition transparent. Requires PreToolUse hook reading the tool's
  `file_path` arg + acquiring with `TASK_ID=session-${SESSION_ID}`.
- **TTL-budget enforcement** on long-running leases — alert if a lease is
  refreshed > N times (suggests forgotten release).
- **CI integration** for GitHub Actions runners — set
  `AGENT_LEASE_ENFORCEMENT=false` in workflow defaults; reserve enforcement
  for local dev + cron-driven autonomous tasks.
- **Telegram alert on conflict** — when a hot-zone commit is blocked by a
  foreign lease, ping operator with holder details for fast triage.
