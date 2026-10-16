# Redis 8.x Observer Admission Proposal (`nuzantara_observer`) — Pro & Mini

- **Block**: `B02` (`universal-db-wave8-20261015`)
- **Target Stores**:
  - `redis:pro:6379/db0` — Host `Pro` (`Nuzantara`, `127.0.0.1:6379`, observed `Redis server v=8.6.1`, `DUX-REQ-B02-03.pro.out:1`)
  - `redis:mini:6379/db0` — Host `Mini` (`Mini-Pro2`, `127.0.0.1:6379`, observed `Redis server v=8.10.2`, `DUX-REQ-B02-03.out:1`)
- **Decision Status**: **PROPOSED — REQUIRES EXPLICIT OWNER (`Zero`) CONSENT AND SECRET DELIVERY PATH APPROVAL BEFORE EXECUTION** (`B02-F1`, `DUX-NOTE-CORRECTION.md:10-13,52-58`)

---

## 1. Objective & Non-Negotiable Security Invariants

Both `redis:pro:6379/db0` (`Redis 8.6.1`) and `redis:mini:6379/db0` (`Redis 8.10.2`) enforce `requirepass` on the `default` ACL user (`REDIS-PRO-METADATA.json:12`, `REDIS-MINI-METADATA.json:12`), and neither host currently has an observer credential provisioned (`KEYCHAIN_OBSERVER=UNSET`, `ENV_OBSERVER=ABSENT` on both Mini and Pro at `2026-10-15T08:54:05Z`, `DUX-REQ-B02-03.out:3-4`, `DUX-REQ-B02-03.pro.out:3-4`).

Per the Owner Rule (`DUX-NOTE-CORRECTION.md:10-13`) and `DUX-CONSOLIDATION.md:25-26,41`:
1. **Never reuse `REDIS_PASSWORD`, `REDIS_URL`, or the `default` ACL user** for observability (`X7`).
2. **Never send destructive or non-allowlisted commands on the observer connection**, regardless of earlier `NOPERM` replies.
3. **Use admitted provisioner `ACL DRYRUN` for denial verification**, and **keyless metadata reads only on the observer connection**.
4. **Never place secret values in output, logs, or process command-line arguments (`argv`)**. Per the official Redis CLI documentation (<https://redis.io/docs/latest/develop/tools/cli/>) and Redis `ACL DRYRUN` documentation (<https://redis.io/docs/latest/commands/acl-dryrun/>), passing credentials on command lines (`-a`, `ACL SETUSER ... ><secret>`, or a macOS Keychain add command given `-w <secret>`) exposes secrets to local process table inspection (`ps`).

---

## 2. Proposed Redis 8.x ACL Principal & Exact Rule

- **Principal Name**: `nuzantara_observer`
- **Target Engine Versions**: Redis `8.6.1` (Pro) and Redis `8.10.2` (Mini)
- **Canonical ACL Rule String (without secret token)**:
  ```text
  user nuzantara_observer on resetkeys resetchannels -@all +ping +info +dbsize +role +time +command|count +acl|whoami +client|info +client|id
  ```
- **Canonical Policy SHA-256 (`EXPECTED_OBSERVER_ACL_POLICY_SHA256` in `redis_observer_probe.py`)**:
  `e98f6189e2bf79cf1035efdc701d99710018a58130833658bc8dddf6998f86ef`

### Why Each Token Exists (and Why `+acl|getuser` and `+acl|dryrun` Are Excluded)
| Token | Effect in Redis 8.x | Security Rationale |
|---|---|---|
| `on` | Enables the ACL user | Required for `AUTH nuzantara_observer <secret>`. |
| `resetkeys` | Revokes all keyspace patterns (no `~*`, no `%R~*`, no `%W~*`) | Guarantees the user cannot touch any key in `db0`..`db15` even if a command permission were misconfigured. |
| `resetchannels` | Revokes all Pub/Sub channel patterns | Prevents eavesdropping on or publishing to Pub/Sub channels. |
| `-@all` | Revokes all command categories (`@read`, `@write`, `@admin`, `@dangerous`, `@scripting`, etc.) | Default-deny baseline. |
| `+ping` | Permits `PING` | Liveness check. |
| `+info` | Permits `INFO [section]` | Server, persistence, keyspace counts, memory, clients, stats, and replication metadata. |
| `+dbsize` | Permits `DBSIZE` | Key count in current DB without key enumeration. |
| `+role` | Permits `ROLE` | Master/replica topology verification. |
| `+time` | Permits `TIME` | Server clock skew check. |
| `+command\|count` | Permits `COMMAND COUNT` only | Introspects total command count without enabling `COMMAND` / `COMMAND DOCS`. |
| `+acl\|whoami` | Permits `ACL WHOAMI` only | Self-identity verification (`nuzantara_observer`). **Note (`B02-F2`)**: `+acl\|getuser` is **intentionally excluded** because `ACL GETUSER default` exposes `default`'s password hashes and ACL rules. **Note (`B02-F3`)**: `+acl\|dryrun` is **intentionally excluded** from the observer because `ACL DRYRUN` is an administrative inspection subcommand executed exclusively on the separate provisioner connection. |
| `+client\|info` `+client\|id` | Permits `CLIENT INFO` and `CLIENT ID` only | Verifies the current connection's authenticated user and flags without enabling `CLIENT LIST` or `CLIENT KILL`. |

---

## 3. Secret-Safe Credential Storage & Approved Delivery Path

### 3.1 Blocker Notice: `SECRET_DELIVERY_PATH_UNAPPROVED`
Until the owner (`Zero`) approves the credential storage and delivery mechanism below, `SECRET_DELIVERY_PATH_UNAPPROVED` and `OWNER_CONSENT_REQUIRED_REDIS_OBSERVER_ACL` remain active blockers in `RESULT.json`.

### 3.2 Mode-`0600` File Read Directly in Python Memory (Zero `argv`, Zero Shell Expansion)
To guarantee that neither the admin credential nor the observer credential ever appears in process arguments (`argv`), shell history, or child process environments:
- **Observer Credential File**: `~/.nuzantara-redis-observer.env` (mode `0600`, owned by `nuzantara`)
  ```ini
  REDIS_OBSERVER_USER=nuzantara_observer
  REDIS_OBSERVER_PASSWORD=<REDACTED_256_BIT_HEX_TOKEN>
  ```
- **In-Process Generation & Provisioning Pattern (Owner-Executed Local Python, Zero `argv` Secrets)**:
  1. Generate the 32-byte token in Python (`secrets.token_hex(32)`) and write `~/.nuzantara-redis-observer.env` directly using `os.open(..., os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)`.
  2. Read the owner's existing admin credential in-process from `~/.nuzantara-secrets.env` (never passing it to a subprocess or `redis-cli` argument) and open a local loopback socket (`127.0.0.1:6379`) in Python to send `ACL SETUSER nuzantara_observer on ><token> resetkeys resetchannels -@all +ping +info +dbsize +role +time +command|count +acl|whoami +client|info +client|id` over the socket stream.
  3. Persist according to the active Redis 8.x configuration:
     - **Option A (`aclfile` configured)**: Send `ACL SAVE` over the admin socket.
     - **Option B (inline `redis.conf`)**: Append the `user nuzantara_observer ...` directive to `/opt/homebrew/etc/redis.conf` (mode `0600`) so it survives `brew services restart redis`.

### 3.3 Secret Rotation & Rollback Procedure
- **Zero-Downtime Rotation**:
  1. Generate a new 256-bit hex secret in Python and send `ACL SETUSER nuzantara_observer ><new_token>` over the in-process admin socket.
  2. Atomically replace `~/.nuzantara-redis-observer.env` (mode `0600`) with the new token.
  3. Send `ACL SETUSER nuzantara_observer <<old_token>` over the in-process admin socket and persist via `ACL SAVE` / `/opt/homebrew/etc/redis.conf`.
- **Immediate Rollback**:
  - Send `ACL DELUSER nuzantara_observer` over the in-process admin socket (and `ACL SAVE` if `aclfile` is active) and remove `~/.nuzantara-redis-observer.env`.

---

## 4. Two-Plane Verification Architecture (Provisioner `ACL DRYRUN` vs. Observer Keyless Allowlist)

Verification is strictly split across two separate connections and two separate evidence planes (`redis_observer_probe.py`), bound together by `endpoint`, `observer_identity`, `acl_policy_sha256`, and `source_version`:

### Plane A — Provisioner `ACL DRYRUN` Matrix (`evaluate_provisioner_dryrun_matrix`)
Executed on the **separate provisioner connection** (`role="provisioner"`), which wraps every simulated check in `ACL DRYRUN nuzantara_observer <cmd> [args...]` (<https://redis.io/docs/latest/commands/acl-dryrun/>) and **never executes the underlying command**:
- **6 Positive `ACL DRYRUN` Checks (`POS-DRY-01`..`POS-DRY-06`)**:
  - `ACL DRYRUN nuzantara_observer PING` -> `"OK"`
  - `ACL DRYRUN nuzantara_observer ACL WHOAMI` -> `"OK"`
  - `ACL DRYRUN nuzantara_observer ROLE` -> `"OK"`
  - `ACL DRYRUN nuzantara_observer DBSIZE` -> `"OK"`
  - `ACL DRYRUN nuzantara_observer CLIENT INFO` -> `"OK"`
  - `ACL DRYRUN nuzantara_observer INFO server` -> `"OK"`
- **17 Negative `ACL DRYRUN` Checks (`DRY-01`..`DRY-17`)** — every check must return `"This user has no permissions to ..."`:
  | ID | Simulated Command via `ACL DRYRUN nuzantara_observer ...` | Category |
  |---|---|---|
  | `DRY-01` | `GET __udb_b02_dryrun_probe__` | String value read |
  | `DRY-02` | `KEYS __udb_b02_dryrun_probe__*` | Full keyspace glob enumeration |
  | `DRY-03` | `SCAN 0 MATCH __udb_b02_dryrun_probe__* COUNT 1` | Cursor keyspace enumeration |
  | `DRY-04` | `HGETALL __udb_b02_dryrun_probe__` | Hash value read |
  | `DRY-05` | `XRANGE __udb_b02_dryrun_probe__ - + COUNT 1` | Stream payload read |
  | `DRY-06` | `CONFIG GET maxmemory` | Admin config read |
  | `DRY-07` | `CONFIG SET maxmemory 0` | Admin config write |
  | `DRY-08` | `ACL LIST` | ACL hash enumeration |
  | `DRY-09` | `ACL GETUSER default` | ACL user rule inspection (`B02-F2`) |
  | `DRY-10` | `ACL DRYRUN nuzantara_observer PING` | Admin `ACL DRYRUN` self-invocation (`B02-F3`) |
  | `DRY-11` | `SET __udb_b02_dryrun_probe__ 1 NX EX 1` | Key write mutation |
  | `DRY-12` | `DEL __udb_b02_dryrun_probe__` | Key delete mutation |
  | `DRY-13` | `EVAL "return 1" 0` | Lua script execution |
  | `DRY-14` | `ACL SETUSER __udb_b02_dryrun_probe__ off` | ACL privilege escalation |
  | `DRY-15` | `FLUSHDB` | Destructive DB flush |
  | `DRY-16` | `FLUSHALL` | Destructive instance flush |
  | `DRY-17` | `SHUTDOWN NOSAVE` | Destructive server shutdown |
- **Fail-Closed `ACL DRYRUN` Handling**:
  - If any `DRY-01`..`DRY-17` returns `"OK"`, `x_dryrun_state` is set to `"FAILED_OVERPRIVILEGED"` (`status = "CONFLICT"`).
  - If `ACL DRYRUN` is unsupported, denied (`-NOPERM`), or returns an unexpected reply, `evaluate_provisioner_dryrun_matrix` records `DRYRUN_UNSUPPORTED`, `DRYRUN_DENIED`, or `DRYRUN_UNEXPECTED_REPLY` and **never falls back to sending the live command**.
  - When no provisioner connection is admitted (`provisioner_client=None`), `x_dryrun_state` is `"NOT_EXECUTED"` and `unknowns` records `"LIVE_DRYRUN_MATRIX_NOT_EXECUTED_NO_PROVISIONER_ADMISSION"`.

### Plane B — Observer Keyless Metadata Allowlist (`probe_redis_observer`)
Executed on the **observer connection** (`role="observer"`), where `validate_observer_command` rejects any non-allowlisted command before a single byte is written to the socket:
- Allowed commands on the observer connection:
  - `AUTH nuzantara_observer <redacted>` (or `HELLO`)
  - `PING`
  - `ACL WHOAMI` (must equal `nuzantara_observer`; `default` is rejected immediately)
  - `ROLE`, `DBSIZE`, `TIME`, `COMMAND COUNT`, `CLIENT ID`, `CLIENT INFO`
  - `INFO server`, `INFO persistence`, `INFO keyspace`, `INFO memory`, `INFO clients`, `INFO stats`, `INFO replication` (filtered through line-level regexes in `ALLOWED_INFO_PATTERNS`).
- Promotion to `x_observer_state = "ADMITTED_VERIFIED"` occurs in `combine_observer_and_dryrun_evidence` **only** when Plane B succeeds (`OBSERVER_METADATA_ADMITTED`), Plane A succeeds (`DRYRUN_MATRIX_VERIFIED`), and both planes match on `endpoint`, `observer_identity`, `acl_policy_sha256`, and `source_version`.
