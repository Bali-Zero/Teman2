---
adversarial_review: codex
review_scope: recorded_evidence_reconciliation_only
---

# B02 Analysis — Redis Observer Admission (Pro & Mini)

Current evidence (2026-10-16): both one-shot Pro/Mini temporary observer exercises completed with role cleanup; current focused source suite153P. Active actor coverage and denominator remain UNKNOWN. Earlier analysis/proposals below are historical; no further native run is authorized. block_closed:false. Final package review is independent and pending.

- **Campaign**: `universal-db-wave8-20261015`
- **Block**: `B02` — Redis observer admission
- **Host**: `Mini` (`[Mini]`)
- **Worktree**: `<block worktree>`
- **Base Commit SHA**: `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Colour / Gear / Role**: `BLUE` / Gear `3` / `EXTERNAL PREPARER, NO_DUX` (`requested_model: Gemini 4 Argon`, `requested_effort: high`, `effective_model: UNOBSERVED`, `effective_effort: UNOBSERVED`)
- **Stage**: `ANALYSIS` (read-only analysis; zero live store probes, zero commits)
- **Sibling Dependencies**: `B04` (Identity, authentication, roles, tenancy)

---

## 1. Verified Facts (Repository & Frozen Wave-8 Inputs)

### 1.1 Scoped Frozen Input Manifest (`.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json:1-38`)
All seven scoped Wave-8 inputs are present in `.agent-receipts/udb-wave8-inputs/`:
1. `REPORT.md` — SHA256 `d289fb8660a6bd634cb7785fef3a8c0b47ceefe82463d134c4bbf66dc0563e9a` (`INPUT-MANIFEST.json:8`)
2. `STATE.json` — SHA256 `caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4` (`INPUT-MANIFEST.json:13`)
3. `FINAL-BLUE-GATE.json` — SHA256 `b9d284e1dba9e87ad340cbd4076061e7a35a93fdf8bc1c910340e6099d711856` (`INPUT-MANIFEST.json:18`)
4. `REAL-RUN-RECEIPT.json` — SHA256 `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d` (`INPUT-MANIFEST.json:23`)
5. `research-lines.csv` — SHA256 `1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f45ff808c7203654c10` (`INPUT-MANIFEST.json:28`)
6. `consumer-matrix.csv` — SHA256 `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` (`INPUT-MANIFEST.json:33`)
7. `ASTRA-ADVICE.md` — SHA256 `72f349f285bc681013b67ad1d25cdad54d3d4478080dc1f5e7e0512dd9e1fdb8` (`INPUT-MANIFEST.json:36`)

### 1.2 Baseline Redis Discovery State (`REPORT.md`, `STATE.json`, `FINAL-BLUE-GATE.json`)
- **Unauthenticated `INFO` Rejected on Pro and Mini**: During `completion-20261015-0831`, `redis_info_probe.py` (SHA256 `2be3a8bd99c29c69c79a02d27699ff310f58f9dc9e06b3963cd72e93b6b29f20`, `FINAL-BLUE-GATE.json:29`) executed an unauthenticated `INFO` check with a minimal environment and no `AUTH` (`REPORT.md:49`).
- Both Pro and Mini Redis instances rejected unauthenticated `INFO` (`REPORT.md:47`, `FINAL-BLUE-GATE.json:119`):
  - `STATE.json:44-47` records `"redis_metadata": { "pro": "AUTHORIZATION_REQUIRED", "mini": "AUTHORIZATION_REQUIRED" }`.
  - Prior evidence receipts are pinned by SHA256 in `FINAL-BLUE-GATE.json:31-32`: `REDIS-PRO-METADATA.json` (`e77cefd1e69ccff94db34292cfecc73e87e1888ad433e3bd0dffb2ff58b3cda0`) and `REDIS-MINI-METADATA.json` (`6ad6b9b9d4839906061610fa54392880d08699efd66162a7f30e58ff79087e30`).
- **Hard Governance Constraint on Credentials**: `REPORT.md:5-6` and `FINAL-BLUE-GATE.json:120` establish that the campaign did **not** substitute an application or admin credential for an observer identity, nor weaken Redis authentication.
- **Astra 6 Guidance (`ASTRA-ADVICE.md:7`)**: *"B02 needs effective read-only privileges and negative tests, not just authentication."*
- **Mandate Scope (`BATTLE.md:3-6,20-25`)**: B02 must establish authenticated observer metadata on Pro and Mini, effective identity/privileges, admitted commands, and negative permission tests, with zero keys/values or credential output. Authentication alone is insufficient.

### 1.3 Existing Redis Clients, Configuration & Auth Patterns in Repository
- **Backend FastAPI Configuration (`apps/backend-rag/backend/app/core/config.py:531`)**:
  - Declares `redis_url: str | None = None  # Set via REDIS_URL env var`. No separate `redis_observer_url` or ACL username setting exists in `Settings`.
- **Backend Connection Manager (`apps/backend-rag/backend/core/redis_manager.py:50-156`)**:
  - `RedisManager` connects via `aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True, socket_connect_timeout=5, socket_timeout=5, retry_on_timeout=True, health_check_interval=30)` (`redis_manager.py:101-109`).
  - Redacts credentials in URLs via `redact_url_BasicAuth(redis_url)` (`redis_manager.py:30-42`) and `apps/backend-rag/backend/core/secret_log_redaction.py:21-25` (`_URL_PASSWORD_RE`).
  - Executes `ping()`, `get()`, `setex()`, `delete()`, `scan()`, `hset()`, `hget()`, `hgetall()`, `expire()`, `incr()`, `info("memory")`, and `info("stats")` (`redis_manager.py:112,202,226,251,336,374,394,413,432,451,467-468`).
- **Backend Cache Services (`apps/backend-rag/backend/core/cache.py:67-115` & `apps/backend-rag/backend/services/common/cache.py:31-79`)**:
  - Connect via `redis.from_url(url, ...)` using `settings.redis_url` and fall back to in-memory cache on failure.
  - `CacheService.get_stats()` (`apps/backend-rag/backend/core/cache.py:310-335`) calls `await self.redis_client.info("stats")` and `await self.redis_client.dbsize()`.
- **Pro/Mini Local Redis Auth History (`scripts/pg-to-organism-bridge.py:93-108,202-219`)**:
  - Comment at `scripts/pg-to-organism-bridge.py:202-203` documents: `# Local Redis has requirepass since 2026-06-29 — redis-cli honours REDISCLI_AUTH. Password comes from _load_secrets() (REDIS_PASSWORD).`
  - `_load_secrets()` (`scripts/pg-to-organism-bridge.py:93-95`) reads `~/.nuzantara-secrets.env` and exports `REDIS_PASSWORD` into `REDISCLI_AUTH` (`pg-to-organism-bridge.py:205-206`).
- **Agent Worktree Lease Registry (`scripts/agent_lease.py:246-259`, `scripts/ci/redis_lease_check.py:42-92`)**:
  - `scripts/agent_lease.py:248-259` resolves `REDIS_URL`, or builds a Redis connection URI (with optional auth prefix `<OBSERVER_SECRET>`) from `REDIS_HOST` (default `127.0.0.1`), `REDIS_PORT` (default `6379`), `REDIS_DB` (default `0`), and `REDIS_PASSWORD` (default `""`).
  - Uses write commands (`SET ... NX EX`, `EVAL` Lua renewal/release scripts, `HSET`, `EXPIRE`, `SADD`) and scan/read commands (`SCAN`, `GET`, `TTL`, `HGETALL`) (`scripts/agent_lease.py:124-156,317-487`).
- **Canonical Read-Only Observer Precedent (`scripts/pg.sh:48-77`, `docs/runbooks/prod-db-writes.md:27-35`)**:
  - For PostgreSQL, `scripts/pg.sh` enforces a dedicated read-only role (`nuzantara_readonly` / `b01_readonly_probe`) whose DSN is fetched from macOS Keychain first (`security find-generic-password`), then from a mode-`0600`-enforced env file (`~/.nuzantara-pg-readonly.env` via `stat -f '%Lp'`), never passing credentials on argv or printing them to stdout/stderr.

---

## 2. Counterexamples & Structural Discrepancies

### Counterexample 1 — Application `REDIS_PASSWORD` (`default` user) vs Dedicated Observer Principal
- **Evidence**: `scripts/pg-to-organism-bridge.py:202-206`, `scripts/system_doctor.py:1675-1679`, and `scripts/agent_lease.py:248-259` authenticate using `REDIS_PASSWORD` without a username, which in Redis 6/7 authenticates as the `default` ACL user configured via `requirepass`.
- **Contradiction**: The `default` user holds `+@all ~* &*` privileges (used by `pg-to-organism-bridge.py:209` for `XADD`, `system_doctor.py:1692` for `SET`, and `agent_lease.py:322` for `SET NX EX` / `EVAL`). If B02 used `REDIS_PASSWORD` (`default` user) to run `INFO`, authentication would succeed, **but every negative permission test (`SET`, `DEL`, `GET`, `KEYS`, `CONFIG`) would also succeed**, violating `BATTLE.md:5-6` (*"effective identity/privileges, admitted commands and negative permission tests. No keys/values or credential output. Authentication alone is insufficient"*), `ASTRA-ADVICE.md:7`, and `REPORT.md:5-6`.

### Counterexample 2 — Standard Redis `+@read` ACL Still Leaks Keyspace Names and Values
- **Evidence**: In Redis 6/7 ACLs, granting the `@read` category (`+@read ~*`) admits `GET`, `MGET`, `HGETALL`, `LRANGE`, `SMEMBERS`, `ZRANGE`, `XRANGE`, `SCAN`, `KEYS`, `RANDOMKEY`, and `DUMP`.
- **Contradiction**: `BATTLE.md:5-6` states: *"No keys/values or credential output."* A naive "read-only" Redis user with `+@read ~*` can read arbitrary cached client payloads, session tokens, or stream payloads (`organism:events`, `zantara:cache:*`).
- **Resolution Requirement**: The Redis observer ACL user (`nuzantara_observer`) must be configured with **`resetkeys`** (zero permitted key patterns — no `~*`) and **`resetchannels`** (zero pub/sub channels), plus `-@all` followed by an explicit command allowlist of keyless server-metadata commands (`+ping +info +dbsize +role +time +command|count +acl|whoami +acl|getuser +client|info +client|id`). Under `resetkeys -@all ...`, both write commands (`SET`, `DEL`, `FLUSHDB`) **and** key-reading commands (`GET`, `KEYS`, `SCAN`, `HGETALL`, `XRANGE`) deterministically fail with `NOPERM`.

### Counterexample 3 — `idempotent-runner.sh` Misinterprets `NOAUTH` as "Key Already Claimed" and Silently Skips Cron Jobs
- **Evidence**: `scripts/mini-migration/idempotent-runner.sh:88-118` invokes:
  ```bash
  SET_RESULT=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" \
    SET "$KEY" "claimed_by_$(hostname)_$$_$(date +%s)" NX EX "$TTL" 2>&1)
  REDIS_RC=$?
  ```
  without loading `~/.nuzantara-secrets.env` or setting `REDISCLI_AUTH` beforehand (`~/.nuzantara-secrets.env` is only sourced inside `if [ "$REDIS_RC" -ne 0 ]` at `idempotent-runner.sh:100-102`).
- **Contradiction**: When Redis enforces `requirepass` (`STATE.json:45-46`: `"pro": "AUTHORIZATION_REQUIRED"`, `"mini": "AUTHORIZATION_REQUIRED"`), `redis-cli` exits with `REDIS_RC=0` and prints `NOAUTH Authentication required.` to stdout (`pg-to-organism-bridge.py:215`). At `idempotent-runner.sh:112-117`, `[ "$SET_RESULT" = "OK" ]` evaluates false and enters `else`, logging `"skipped — key=$KEY already claimed (result: NOAUTH Authentication required.)"` and exiting `0` without running the wrapped job.

### Counterexample 4 — Unauthenticated Local Redis Assumptions in `metabolic_rollup.py`, `sentinel-aggregate.py`, and `agent_lease.py`
- **Evidence**:
  - `scripts/metabolic_rollup.py:128-150` connects via `redis.Redis(host="localhost", port=6379, decode_responses=True)` with no `password` or `username`, catching all exceptions at line 148 (`logger.debug(f"Redis push failed (non-fatal): {e}")`).
  - `scripts/sentinel-aggregate.py:525-531` runs `["redis-cli", "XADD", ORGANISM_STREAM_KEY, ...]` without `REDISCLI_AUTH`.
  - `docs/runbooks/redis-lease-registry.md:42,130,166-170` states *"No auth required on localhost or Tailscale peer"* while `STATE.json:45-46` proves both Pro and Mini require authentication.

### Counterexample 5 — Tailscale IP Inversion Between `redis-lease-registry.md` / `agent_lease.py` and Canonical Fleet Topology
- **Evidence**:
  - `INDEX.md:131`, `docs/agents/m5-thin-client-routing.md:40,83`, and `scripts/mini-migration/idempotent-runner.sh:62` (`PRO_REDIS_HOST="${PRO_REDIS_HOST:-100.107.22.111}"`) establish that **Pro (`Nuzantara`)** is `100.107.22.111` and **Mini (`Mini-Pro2`)** is `100.93.236.6`.
  - Conversely, `docs/runbooks/redis-lease-registry.md:42,166` and `scripts/agent_lease.py:21` instruct Mini to set `REDIS_HOST=100.93.236.6` (Mini's own Tailscale IP) to reach Pro's Redis. Any Mini process following `redis-lease-registry.md:166` connects to Mini's local Redis (`100.93.236.6:6379`) instead of Pro (`100.107.22.111:6379`), creating a split-brain lease registry.

### Counterexample 6 — Blocking `KEYS` in `CacheService.clear_pattern` vs `SCAN` in `RedisManager`
- **Evidence**: `apps/backend-rag/backend/core/cache.py:281` executes `keys = await self.redis_client.keys(pattern)` (O(N) blocking command on single-threaded Redis), whereas `apps/backend-rag/backend/core/redis_manager.py:336,352` uses cursor-based `scan(cursor=cursor, match=pattern, count=100)`.

### Counterexample 7 — Untracked HOME-Fork Runtime Consumer (`runtime_6e9b0846bcc0bc34`)
- **Evidence**: `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv:4642` records `runtime_6e9b0846bcc0bc34` at `~/scripts/redis_liveness_check.py` (registered under `Nuzantara:com.nuzantara.redis-liveness:loaded=True`, SHA256 `6adec8ac61428ef1a2b1713cb5c21f5785dd03fb6224e0fb5d7226d272485475`), with disposition `OUTSIDE_TRACKED_CODE_INDEX` because it resides outside the git repository.

---

## 3. Inferences & Sibling Contract Alignment (`B02` ↔ `B04`)

### 3.1 Frozen Sibling Contract Schema (`BATTLE.md:12-18`)
Every B02 observer evidence record and consumer-operation mapping must emit the exact frozen sibling contract fields without renaming:
- **Frozen Envelope Fields**:
  `consumer_id,operation_id,store_id,source_version,evidence_timestamp,evidence_sha256,status,unknowns`
- **Operation Instance Fields**:
  `principal,role,tenant,authorization,transaction,effects,retries,idempotency,failure,retention,recovery`

### 3.2 Expected B02 Observer Operation Instance Values (Once Provisioned & Probed)
| Field | Target Value for B02 Observer Admission | Rationale / Dependency (`B04`) |
|---|---|---|
| `consumer_id` | `udb_b02_redis_observer_probe` | Dedicated Wave-8 B02 observer probe |
| `operation_id` | `redis_observer_admission_and_negative_audit` | Positive metadata + negative ACL denial suite |
| `store_id` | `redis:pro:127.0.0.1:6379` / `redis:mini:127.0.0.1:6379` | Distinct store identities per host (avoiding IP conflation) |
| `principal` | `nuzantara_observer` | Dedicated Redis 6/7 ACL user (`ACL WHOAMI` verified; never `default`) |
| `role` | `redis_metadata_observer` | Keyless metadata-only ACL role (`resetkeys resetchannels -@all +...`) |
| `tenant` | `system_observability` | Infrastructure metadata plane; zero client tenancy or keyspace access |
| `authorization` | `redis_acl_user_pass_resetkeys` | Verified positively via `ACL GETUSER` and negatively via `NOPERM` probes |
| `transaction` | `none_single_command_resp` | Independent RESP commands; no `MULTI`/`EXEC` mutation |
| `effects` | `read_only_server_metadata_zero_keyspace` | Admits `PING`, `ACL WHOAMI`, `ACL GETUSER`, `CLIENT INFO`, `ROLE`, `DBSIZE`, whitelisted `INFO`; denies all key reads and writes |
| `retries` | `none_fail_closed` | Probe does not retry auth/ACL failures |
| `idempotency` | `idempotent_read_only` | Pure metadata inspection + rejected `NOPERM` probes |
| `failure` | `fail_closed_exit_nonzero` | Any `NOAUTH`, `WRONGPASS`, `principal == default`, or unexpected permission grant fails the probe |
| `retention` | `ephemeral_zero_store_mutation` | Zero keys created or modified in Redis; receipt JSON retained in evidence pack |
| `recovery` | `stateless_reconnect` | Stateless TCP connection closed via `QUIT` / socket close |

---

## 4. Missing Evidence & Unknowns

1. **Prior Unmerged Probe Artifacts (`UNKNOWN_PRIOR_PROBE_CONTENT`)**:
   - `FINAL-BLUE-GATE.json:29,31-32` pins `redis_info_probe.py` (`2be3a8bd...`), `REDIS-PRO-METADATA.json` (`e77cefd1...`), and `REDIS-MINI-METADATA.json` (`6ad6b9b9...`) under `evidence/2026-10/agent-air-m5-db-universal-db-astra-e38bdb80/corner/completion-20261015-0831/`, which are not in worktree `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`.
2. **Live Redis ACL Roster on Pro and Mini (`UNKNOWN_LIVE_ACL_USERS`)**:
   - Whether Pro and Mini Redis currently define only `user default on ...` (via `requirepass` in `redis.conf` / `~/.nuzantara-secrets.env`) or already have a non-default observer ACL user provisioned.
3. **Redis Server Version & ACL Syntax Compatibility on Pro and Mini (`UNKNOWN_REDIS_VERSION`)**:
   - Whether Pro and Mini run Redis 6.x, 7.0.x, or 7.2+ (which determines whether `ACL DRYRUN` is supported alongside live negative `NOPERM` command tests).
4. **Provisioning Authority for Observer ACL User (`OPERATOR_APPROVAL_REQUIRED`)**:
   - Creating or persisting `ACL SETUSER nuzantara_observer ...` on Pro and Mini Redis and storing its secret in Keychain / `~/.nuzantara-redis-observer.env` (`0600`) mutates live service ACL state and requires Dux / operator execution.
5. **Pro HOME-Fork `~/scripts/redis_liveness_check.py` (`UNKNOWN_HOME_FORK_AUTH`)**:
   - `consumer-matrix.csv:4642` marks this loaded daemon (`com.nuzantara.redis-liveness`) as `OUTSIDE_TRACKED_CODE_INDEX`; its auth mechanism (`REDIS_PASSWORD` vs unauthenticated `PING`) is unverified from tracked files.

## Adversarial review

Scoped coordinator review reconciles the reported result with the recorded independent source/run review and completed one-shot native receipts. This is a partial document reconciliation, not full runtime coverage, operational acceptance or the final committed-head gate. Source fixtures and preparation records retain their historical timing; the current status below supersedes conflicting execution-status claims.
