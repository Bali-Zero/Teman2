# B02 Proposal — Redis Observer Admission & Negative Permission Verification

- **Campaign**: `universal-db-wave8-20261015`
- **Block**: `B02` — Redis observer admission
- **Host**: `Mini` (`[Mini]`)
- **Worktree**: `<block worktree>`
- **Base Commit SHA**: `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Colour / Gear / Role**: `BLUE` / Gear `3` / `EXTERNAL PREPARER, NO_DUX` (`requested_model: Gemini 4 Argon`, `requested_effort: high`, `effective_model: UNOBSERVED`, `effective_effort: UNOBSERVED`)
- **Stage**: `ANALYSIS` (proposal + `DUX-REQUESTS`; awaiting `DUX-NOTE-SYNTHESIS.md` and `DUX-NOTE-EXECUTION.md`)

---

## 1. Proposed Redis Observer Identity & Least-Privilege ACL Specification

### 1.1 Why a Dedicated Keyless ACL Role Is Required
Per `BATTLE.md:3-6`, `ASTRA-ADVICE.md:7`, and `REPORT.md:5-6`:
1. Authenticating with the existing application/admin secret (`REDIS_PASSWORD` as `default` user) is **forbidden** because `default` holds `+@all ~*` and would pass write/keyspace operations instead of failing negative tests.
2. Granting standard Redis `+@read ~*` is **insufficient** because `@read` permits `GET`, `MGET`, `HGETALL`, `XRANGE`, `SCAN`, and `KEYS`, exposing key names and cached client/session values.

### 1.2 Target Redis 6/7 ACL Rule (`nuzantara_observer`)
On both **Pro** (`127.0.0.1:6379`) and **Mini** (`127.0.0.1:6379`), provision a dedicated ACL principal `nuzantara_observer` with **zero key patterns (`resetkeys`)** and **zero pub/sub channels (`resetchannels`)**:

```redis
ACL SETUSER nuzantara_observer on ><OBSERVER_SECRET> resetkeys resetchannels -@all +ping +info +dbsize +role +time +command|count +acl|whoami +acl|getuser +client|info +client|id
```

- **Keyless Guarantee (`resetkeys`)**: Because no `~pattern` is attached to `nuzantara_observer`, Redis deterministically rejects every command that touches any key (`GET`, `SET`, `DEL`, `MGET`, `HGETALL`, `SCAN`, `KEYS`, `XRANGE`, `EVAL`) with `-NOPERM`.
- **Admitted Commands**: Only server-level metadata and self-identity inspection (`PING`, `INFO`, `DBSIZE`, `ROLE`, `TIME`, `COMMAND COUNT`, `ACL WHOAMI`, `ACL GETUSER`, `CLIENT INFO`, `CLIENT ID`).
- **Denied Commands**: All `@write`, `@admin` (`CONFIG`, `FLUSHDB`, `FLUSHALL`, `SAVE`, `BGSAVE`, `SHUTDOWN`, `REPLICAOF`, `SLAVEOF`, `ACL SETUSER`, `ACL DELUSER`, `ACL SAVE`, `ACL CAT`, `ACL LIST`, `CLIENT KILL`, `SLOWLOG`, `MONITOR`, `DEBUG`), `@scripting` (`EVAL`, `EVALSHA`, `FUNCTION`), and all keyspace `@read` commands.

### 1.3 Credential Storage & Resolution Contract (Mirroring `scripts/pg.sh:48-67`)
Never pass credentials on `argv`, never echo values, and never reuse `REDIS_PASSWORD` / `REDIS_URL`:
1. **macOS Keychain (Primary)**:
   - Service: `nuzantara-redis-observer` (Account: `nuzantara_observer`).
2. **Mode-`0600` Dedicated Env File (Fallback)**:
   - Path: `~/.nuzantara-redis-observer.env`
   - Enforced check: reject if `stat.S_IMODE(os.stat(path).st_mode) != 0o600`.
   - Variable names: `REDIS_OBSERVER_USER` (`nuzantara_observer`) and `REDIS_OBSERVER_SECRET_REF` (`<OBSERVER_SECRET>`).
   - Explicit guard: if `REDIS_OBSERVER_USER == "default"`, fail closed immediately before opening a socket.

---

## 2. Proposed Narrow Tooling (`scripts/redis_observer_probe.py`)

A deterministic, dependency-light Python CLI (`scripts/redis_observer_probe.py`) using standard-library `socket`/`ssl` RESP2/RESP3 framing (or `redis-py` when available, with a pure-stdlib RESP fallback so it runs identically on Pro, Mini, and CI without external venv drift).

### 2.1 Execution Sequence
1. **Credential & Guard Validation**:
   - Load `REDIS_OBSERVER_USER` (must not be `default` or empty) and `REDIS_OBSERVER_PASSWORD` via Keychain or mode-`0600` `~/.nuzantara-redis-observer.env`.
2. **Authentication (`AUTH <user> <password>`)**:
   - Send `["AUTH", user, password]` over TCP (`127.0.0.1:6379` or SSH local-forwarded tunnel from Mini to Pro). Never log or include `password` in error strings; sanitize all error messages via `redact_secrets` (`apps/backend-rag/backend/core/secret_log_redaction.py:137`).
3. **Effective Identity & Privilege Verification (Positive Suite)**:
   - `PING` → must return `PONG`.
   - `ACL WHOAMI` → must return `"nuzantara_observer"` (fail closed if `"default"`).
   - `ACL GETUSER nuzantara_observer` → parse `flags`, `commands`, `keys`, `channels`:
     - Verify `"on"` in `flags` and `"allkeys"` **not** in `flags` and `"allcommands"` **not** in `flags`.
     - Verify `keys` list is empty (`[]` / `resetkeys`).
     - Compute `acl_rules_sha256` (redacting password hashes in the `passwords` array to `["<REDACTED_HASH_COUNT:N>"]`).
   - `ROLE` & `CLIENT INFO` → extract role (`master`/`replica`) and `user=nuzantara_observer` (strip ephemeral `addr`/`laddr`/`fd`).
   - `DBSIZE` → integer key count.
   - `INFO` (`server`, `memory`, `clients`, `stats`, `replication`, `persistence`, `keyspace`) → extract **only** a strict allowlist of safe operational fields (`redis_version`, `redis_mode`, `os`, `arch_bits`, `tcp_port`, `uptime_in_seconds`, `connected_clients`, `used_memory`, `used_memory_human`, `maxmemory`, `maxmemory_policy`, `total_connections_received`, `total_commands_processed`, `keyspace_hits`, `keyspace_misses`, `evicted_keys`, `expired_keys`, `role`, `connected_slaves`, `aof_enabled`, `rdb_last_bgsave_status`, `db0`..`db15` counts). Omit filesystem paths (`executable`, `config_file`) and never dump raw `INFO` text.
4. **Negative Permission Test Matrix (Mandatory — Must All Return `-NOPERM`)**:
   Every negative probe must receive a Redis `-NOPERM` error reply. If **any** negative probe returns `OK`, a value, or `nil` instead of `-NOPERM`, the probe sets `status = "FAILED_OVERPRIVILEGED"` and exits non-zero:

   | Test ID | Command | Category Tested | Expected Reply |
   |---|---|---|---|
   | `NEG-01` | `GET __udb_b02_nonexistent_probe__` | Keyspace value read (`@read` / key access) | `-NOPERM` |
   | `NEG-02` | `SET __udb_b02_nonexistent_probe__ 1 EX 1` | Keyspace write (`@write`) | `-NOPERM` |
   | `NEG-03` | `DEL __udb_b02_nonexistent_probe__` | Keyspace delete (`@write`) | `-NOPERM` |
   | `NEG-04` | `KEYS *` | Keyspace enumeration (`@dangerous` / `@read`) | `-NOPERM` |
   | `NEG-05` | `SCAN 0 COUNT 1` | Cursor keyspace enumeration (`@read`) | `-NOPERM` |
   | `NEG-06` | `HGETALL __udb_b02_nonexistent_probe__` | Hash read (`@hash` / `@read`) | `-NOPERM` |
   | `NEG-07` | `XRANGE organism:events - + COUNT 1` | Stream read (`@stream` / `@read`) | `-NOPERM` |
   | `NEG-08` | `EVAL "return 1" 0` | Lua scripting (`@scripting`) | `-NOPERM` |
   | `NEG-09` | `CONFIG GET maxmemory` | Server configuration read (`@admin`) | `-NOPERM` |
   | `NEG-10` | `ACL LIST` | ACL secret/rule enumeration (`@admin`) | `-NOPERM` |
   | `NEG-11` | `ACL SETUSER __udb_b02_test__ off` | ACL mutation (`@admin`) | `-NOPERM` |
   | `NEG-12` | `FLUSHDB` (tested via `ACL DRYRUN nuzantara_observer FLUSHDB` on Redis 7+, plus command-table check; never sent if `allcommands` or `+flushdb` is present in `ACL GETUSER`) | Destructive admin (`@dangerous`) | `-NOPERM` / dry-run denial |

   *(Safety note on `NEG-12`: `scripts/redis_observer_probe.py` inspects `ACL GETUSER` first; it only sends live negative commands for non-destructive probes `NEG-01`..`NEG-11` after confirming `keys == []`, and tests `FLUSHDB` via `ACL DRYRUN` or static `ACL GETUSER` command-bitmap verification so a misconfigured server can never be flushed.)*

5. **Output Artifact Generation**:
   - Emits `REDIS-PRO-OBSERVER.json`, `REDIS-MINI-OBSERVER.json`, and `RESULT.json` conforming to the frozen sibling contract fields (`BATTLE.md:12-18`):
     - `consumer_id`, `operation_id`, `store_id`, `source_version`, `evidence_timestamp`, `evidence_sha256`, `status`, `unknowns`
     - `principal`, `role`, `tenant`, `authorization`, `transaction`, `effects`, `retries`, `idempotency`, `failure`, `retention`, `recovery`

---

## 3. Proposed Verification & Unit Test Suite (`scripts/tests/test_redis_observer_probe.py`)

1. **Synthetic RESP Mock Server Tests**:
   - Verifies full positive + negative handshake against an in-process loopback TCP RESP server simulating Redis 7 ACLs:
     - Case A: Compliant `nuzantara_observer` (`ACL WHOAMI` -> `nuzantara_observer`, `keys` -> `[]`, `NEG-01`..`NEG-11` -> `-NOPERM`) => `status == "ADMITTED_VERIFIED"`.
     - Case B: Over-privileged `default` user or `+@read ~*` user where `GET` returns `$-1` (nil) instead of `-NOPERM` => fails closed with `status == "FAILED_OVERPRIVILEGED"`.
     - Case C: Unauthenticated / `NOAUTH` response => fails closed with `status == "AUTHORIZATION_REQUIRED"`.
     - Case D: File permission guard rejects `~/.nuzantara-redis-observer.env` when mode is `0644` instead of `0600`.
     - Case E: Redaction guard proves password strings never appear in stdout, stderr, or output JSON.
2. **Optional Adjacent Fixes (Subject to Dux Scope Confirmation in Synthesis)**:
   - Document or patch the Tailscale IP inversion in `docs/runbooks/redis-lease-registry.md:42,166` and `scripts/agent_lease.py:21` (`100.93.236.6` Mini vs `100.107.22.111` Pro) if Dux includes doc/comment alignment in B02; otherwise record strictly as a B02/B04 finding.

---

## DUX-REQUESTS

### `DUX-REQ-B02-01` — Extract Prior Phase Unmerged `redis_info_probe.py` & Metadata Receipts
- **ID**: `DUX-REQ-B02-01`
- **Read-Only Command**:
  ```bash
  git show agent-air-m5-db-universal-db-astra-e38bdb80:evidence/2026-10/agent-air-m5-db-universal-db-astra-e38bdb80/corner/completion-20261015-0831/redis_info_probe.py
  git show agent-air-m5-db-universal-db-astra-e38bdb80:evidence/2026-10/agent-air-m5-db-universal-db-astra-e38bdb80/corner/completion-20261015-0831/REDIS-PRO-METADATA.json
  git show agent-air-m5-db-universal-db-astra-e38bdb80:evidence/2026-10/agent-air-m5-db-universal-db-astra-e38bdb80/corner/completion-20261015-0831/REDIS-MINI-METADATA.json
  ```
  *(or read from the Dux archive path where `FINAL-BLUE-GATE.json:29,31-32` artifacts are stored)*
- **Inputs**: Prior phase artifacts pinned in `.agent-receipts/udb-wave8-inputs/FINAL-BLUE-GATE.json:29,31-32` (`2be3a8bd...`, `e77cefd1...`, `6ad6b9b9...`).
- **Expected Output Shape**: Full source of `redis_info_probe.py` and the JSON schema/fields of `REDIS-PRO-METADATA.json` and `REDIS-MINI-METADATA.json`.
- **Why It Matters**: Ensures `scripts/redis_observer_probe.py` preserves 100% schema continuity with the prior probe while adding authenticated `ACL WHOAMI`/`ACL GETUSER` and negative permission tests.

### `DUX-REQ-B02-02` — Deterministic Census of All Redis Rows in `consumer-matrix.csv`
- **ID**: `DUX-REQ-B02-02`
- **Read-Only Command**:
  ```bash
  python3 -c '
  import csv, json
  from collections import Counter
  rows = []
  with open(".agent-receipts/udb-wave8-inputs/consumer-matrix.csv", newline="", encoding="utf-8") as f:
      for r in csv.DictReader(f):
          if "redis" in (r.get("store","") + ";" + r.get("observed_stores_all","")).lower():
              rows.append({
                  "consumer_id": r["consumer_id"],
                  "entry_point": r["entry_point"],
                  "runtime_registration": r["runtime_registration"],
                  "disposition": r["disposition"],
                  "actor_resolution_status": r["actor_resolution_status"],
              })
  print(json.dumps({
      "total_redis_rows": len(rows),
      "by_disposition": dict(Counter(x["disposition"] for x in rows)),
      "by_actor_status": dict(Counter(x["actor_resolution_status"] for x in rows)),
      "registered_runtime_rows": [x for x in rows if x["runtime_registration"] != "UNKNOWN"],
  }, indent=2))
  '
  ```
- **Inputs**: `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (SHA256 `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`).
- **Expected Output Shape**: JSON summary with `total_redis_rows`, counts by `disposition` and `actor_resolution_status`, and the full list of `registered_runtime_rows` touching Redis.
- **Why It Matters**: Replaces manual slice sampling of the 6,031-line CSV with exact, deterministic counts for the B02/B04 synthesis table.

### `DUX-REQ-B02-03` — Safe Presence & Version Check for Redis on Mini and Pro (Zero Secret Output)
- **ID**: `DUX-REQ-B02-03`
- **Read-Only Command**:
  ```bash
  # On Mini (local) and on Pro (via ssh pro):
  redis-server --version
  redis-cli --version
  security find-generic-password -s "nuzantara-redis-observer" >/dev/null 2>&1 && echo "KEYCHAIN_OBSERVER=SET" || echo "KEYCHAIN_OBSERVER=UNSET"
  test -f "$HOME/.nuzantara-redis-observer.env" && stat -f "ENV_OBSERVER_MODE=%Lp" "$HOME/.nuzantara-redis-observer.env" || echo "ENV_OBSERVER=ABSENT"
  ```
- **Inputs**: Host environment on `Mini` and `Pro` (`ssh pro`).
- **Expected Output Shape**: Redis server/CLI versions (`Redis server v=...`) and presence/mode flags (`SET`/`UNSET`/`ABSENT`) without printing any secret or connecting with admin credentials.
- **Why It Matters**: Confirms Redis major/minor version (6.x vs 7.x ACL syntax and `ACL DRYRUN` support) and whether the `nuzantara_observer` ACL credential has already been provisioned by the operator/Dux on Pro and Mini before `EXECUTION`.

### `DUX-REQ-B02-04` — Inspect Pro HOME-Fork `~/scripts/redis_liveness_check.py` (Redacted Auth Pattern)
- **ID**: `DUX-REQ-B02-04`
- **Read-Only Command**:
  ```bash
  ssh pro 'shasum -a 256 ~/scripts/redis_liveness_check.py && sed -n "1,120p" ~/scripts/redis_liveness_check.py'
  ```
- **Inputs**: `~/scripts/redis_liveness_check.py` on Pro (`runtime_6e9b0846bcc0bc34`, `consumer-matrix.csv:4642`).
- **Expected Output Shape**: SHA256 verification matching `6adec8ac61428ef1a2b1713cb5c21f5785dd03fb6224e0fb5d7226d272485475` and source lines showing how `com.nuzantara.redis-liveness` connects/authenticates to Redis.
- **Why It Matters**: Closes the `OUTSIDE_TRACKED_CODE_INDEX` gap on Pro's loaded Redis liveness daemon and verifies whether it already uses an observer credential, `REDIS_PASSWORD`, or unauthenticated `PING`.
