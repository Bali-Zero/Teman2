"""Redis 8.x keyless observer probe & separate provisioner ACL DRYRUN verifier (B02).

Security & Governance Invariants (Owner Rule / DUX-NOTE-CORRECTION.md):
1. Observer live denial probes NEVER send destructive or non-allowlisted commands on the
   observer connection. Stage 1 and Stage 2 observer negative execution paths do not exist.
2. The observer transport (`role="observer"`) enforces a strict command allowlist BEFORE
   encoding or writing a single byte to the socket (`validate_observer_command`). Any
   non-allowlisted command (`GET`, `KEYS`, `SCAN`, `HGETALL`, `XRANGE`, `SET`, `DEL`,
   `FLUSHDB`, `FLUSHALL`, `EVAL`, `CONFIG`, `ACL GETUSER`, `ACL LIST`, `ACL SETUSER`,
   `ACL DRYRUN`, or unapproved `INFO` section) raises `ObserverCommandNotAllowedError`
   prior to socket write.
3. Forbidden-command denial verification uses a SEPARATE, explicitly passed provisioner
   transport (`role="provisioner"`) that only simulates permissions via
   `ACL DRYRUN <observer_user> <cmd> [args...]` (`evaluate_provisioner_dryrun_matrix`)
   and NEVER falls back to executing live commands.
4. `observer_evidence` and `dryrun_evidence` are separate evidence planes and are bound
   together (`combine_observer_and_dryrun_evidence`) by `endpoint`, `observer_identity`,
   `acl_policy_sha256`, and `source_version`. Promotion to `x_observer_state =
   "ADMITTED_VERIFIED"` occurs if and only if both planes succeed and all bindings match.
5. Never reuse `REDIS_PASSWORD` or `REDIS_URL`, never pass secret values on process
   command lines (`argv`), and never emit secret values in stdout, logs, or JSON artifacts.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import re
import socket
import stat
import sys
from typing import Any

STORE_ID = "redis:mini:6379/db0"
BASE_COMMIT_SHA = "8061c88e0c43dd42e735fd012f9ed072df3ef3d6"
BASE_COMMIT_TIMESTAMP = "2026-10-15T07:06:22Z"
EXPECTED_OBSERVER_USER = "nuzantara_observer"
DEFAULT_OBSERVER_ENV_FILE = Path.home() / ".nuzantara-redis-observer.env"

EXPECTED_OBSERVER_ACL_RULE = (
    "user nuzantara_observer on resetkeys resetchannels "
    "-@all +ping +info +dbsize +role +time +command|count +acl|whoami +client|info +client|id"
)
EXPECTED_OBSERVER_ACL_POLICY_SHA256 = hashlib.sha256(
    EXPECTED_OBSERVER_ACL_RULE.encode("utf-8")
).hexdigest()

ALLOWED_INFO_SECTIONS: tuple[str, ...] = (
    "server",
    "persistence",
    "keyspace",
    "memory",
    "clients",
    "stats",
    "replication",
)

ALLOWED_INFO_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "server": (
        re.compile(r"^redis_version:"),
        re.compile(r"^redis_mode:"),
        re.compile(r"^os:"),
        re.compile(r"^arch_bits:"),
        re.compile(r"^tcp_port:"),
        re.compile(r"^uptime_in_seconds:"),
        re.compile(r"^executable:"),
        re.compile(r"^config_file:"),
    ),
    "persistence": (
        re.compile(r"^loading:"),
        re.compile(r"^aof_enabled:"),
        re.compile(r"^aof_last_write_status:"),
        re.compile(r"^rdb_last_bgsave_status:"),
        re.compile(r"^rdb_last_save_time:"),
        re.compile(r"^rdb_changes_since_last_save:"),
    ),
    "keyspace": (re.compile(r"^db\d+:keys=\d+,expires=\d+,avg_ttl=\d+"),),
    "memory": (
        re.compile(r"^used_memory:"),
        re.compile(r"^used_memory_human:"),
        re.compile(r"^used_memory_peak:"),
        re.compile(r"^maxmemory:"),
        re.compile(r"^maxmemory_policy:"),
        re.compile(r"^mem_fragmentation_ratio:"),
    ),
    "clients": (
        re.compile(r"^connected_clients:"),
        re.compile(r"^blocked_clients:"),
        re.compile(r"^maxclients:"),
    ),
    "stats": (
        re.compile(r"^total_connections_received:"),
        re.compile(r"^total_commands_processed:"),
        re.compile(r"^instantaneous_ops_per_sec:"),
        re.compile(r"^rejected_connections:"),
        re.compile(r"^keyspace_hits:"),
        re.compile(r"^keyspace_misses:"),
        re.compile(r"^evicted_keys:"),
        re.compile(r"^expired_keys:"),
    ),
    "replication": (
        re.compile(r"^role:"),
        re.compile(r"^connected_slaves:"),
        re.compile(r"^master_repl_offset:"),
    ),
}

CONTRACT_FROZEN_KEYS: tuple[str, ...] = (
    "consumer_id",
    "kind",
    "path",
    "line",
    "raw_target",
    "evidence_source",
    "confidence",
    "reason",
)

CONTRACT_INSTANCE_KEYS: tuple[str, ...] = (
    "operation_id",
    "store_id",
    "subcontainer",
    "op_kind",
    "shape_or_key_pattern",
    "WriteConsequence",
    "CrossStoreLink",
    "AuthoritativeStore",
    "CacheInvalidationRule",
    "LockScope",
    "CallerSet",
)

CONTRACT_STATUS_VALUES: frozenset[str] = frozenset(
    {"EVIDENCED", "PARTIAL", "BLOCKED", "CONFLICT", "UNKNOWN"}
)


class _BoundaryArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("CLI_ARGUMENTS_REJECTED")


class ObserverCommandNotAllowedError(PermissionError):
    """Raised before writing any byte when a command is outside the observer allowlist."""


class ProvisionerCommandNotAllowedError(PermissionError):
    """Raised before writing any byte when a command is outside the provisioner DRYRUN allowlist."""


@dataclass(frozen=True)
class RespError:
    """Represents a RESP2 error reply (`-CODE message`)."""

    raw: str

    @property
    def code(self) -> str:
        parts = self.raw.strip().split(" ", 1)
        code = parts[0].upper() if parts else ""
        return code if code in {
            "ERR", "NOPERM", "NOAUTH", "WRONGPASS", "UNK", "LOADING",
            "READONLY", "BUSY", "MISCONF", "OOM", "EXECABORT", "MASTERDOWN", "NOSCRIPT",
        } else "UNKNOWN"

    @property
    def message(self) -> str:
        return self.raw.strip()


@dataclass(frozen=True)
class DryrunSpec:
    """Specification for a provisioner-only `ACL DRYRUN <user> <cmd> ...` check."""

    test_id: str
    category: str
    command: tuple[str, ...]
    expect_allowed: bool
    rationale: str


POSITIVE_DRYRUN_SPECS: tuple[DryrunSpec, ...] = (
    DryrunSpec(
        test_id="POS-DRY-01",
        category="allowlisted_liveness",
        command=("PING",),
        expect_allowed=True,
        rationale="Observer must be permitted to run PING.",
    ),
    DryrunSpec(
        test_id="POS-DRY-02",
        category="allowlisted_identity",
        command=("ACL", "WHOAMI"),
        expect_allowed=True,
        rationale="Observer must be permitted to run ACL WHOAMI.",
    ),
    DryrunSpec(
        test_id="POS-DRY-03",
        category="allowlisted_metadata",
        command=("ROLE",),
        expect_allowed=True,
        rationale="Observer must be permitted to run ROLE.",
    ),
    DryrunSpec(
        test_id="POS-DRY-04",
        category="allowlisted_metadata",
        command=("DBSIZE",),
        expect_allowed=True,
        rationale="Observer must be permitted to run DBSIZE.",
    ),
    DryrunSpec(
        test_id="POS-DRY-05",
        category="allowlisted_metadata",
        command=("CLIENT", "INFO"),
        expect_allowed=True,
        rationale="Observer must be permitted to run CLIENT INFO.",
    ),
    DryrunSpec(
        test_id="POS-DRY-06",
        category="allowlisted_metadata",
        command=("INFO", "server"),
        expect_allowed=True,
        rationale="Observer must be permitted to run INFO server.",
    ),
)

NEGATIVE_DRYRUN_SPECS: tuple[DryrunSpec, ...] = (
    DryrunSpec(
        test_id="DRY-01",
        category="value_read",
        command=("GET", "__udb_b02_dryrun_probe__"),
        expect_allowed=False,
        rationale="String value read must be denied by -@all and resetkeys.",
    ),
    DryrunSpec(
        test_id="DRY-02",
        category="key_enumeration",
        command=("KEYS", "__udb_b02_dryrun_probe__*"),
        expect_allowed=False,
        rationale="Full keyspace glob enumeration must be denied.",
    ),
    DryrunSpec(
        test_id="DRY-03",
        category="key_enumeration",
        command=("SCAN", "0", "MATCH", "__udb_b02_dryrun_probe__*", "COUNT", "1"),
        expect_allowed=False,
        rationale="Cursor keyspace enumeration must be denied.",
    ),
    DryrunSpec(
        test_id="DRY-04",
        category="hash_read",
        command=("HGETALL", "__udb_b02_dryrun_probe__"),
        expect_allowed=False,
        rationale="Hash payload read must be denied.",
    ),
    DryrunSpec(
        test_id="DRY-05",
        category="stream_read",
        command=("XRANGE", "__udb_b02_dryrun_probe__", "-", "+", "COUNT", "1"),
        expect_allowed=False,
        rationale="Stream payload read must be denied.",
    ),
    DryrunSpec(
        test_id="DRY-06",
        category="admin_config_read",
        command=("CONFIG", "GET", "maxmemory"),
        expect_allowed=False,
        rationale="CONFIG GET must be denied (prevents reading requirepass/masterauth).",
    ),
    DryrunSpec(
        test_id="DRY-07",
        category="admin_config_write",
        command=("CONFIG", "SET", "maxmemory", "0"),
        expect_allowed=False,
        rationale="CONFIG SET runtime mutation must be denied.",
    ),
    DryrunSpec(
        test_id="DRY-08",
        category="acl_enumeration",
        command=("ACL", "LIST"),
        expect_allowed=False,
        rationale="ACL LIST must be denied (prevents reading password hashes).",
    ),
    DryrunSpec(
        test_id="DRY-09",
        category="acl_user_read",
        command=("ACL", "GETUSER", "default"),
        expect_allowed=False,
        rationale="ACL GETUSER must be denied (B02-F2: prevents reading default user hashes).",
    ),
    DryrunSpec(
        test_id="DRY-10",
        category="acl_dryrun_admin",
        command=("ACL", "DRYRUN", EXPECTED_OBSERVER_USER, "PING"),
        expect_allowed=False,
        rationale="ACL DRYRUN is an admin subcommand and must be denied to the observer (B02-F3).",
    ),
    DryrunSpec(
        test_id="DRY-11",
        category="write_mutation",
        command=("SET", "__udb_b02_dryrun_probe__", "1", "NX", "EX", "1"),
        expect_allowed=False,
        rationale="Key write mutation must be simulated via DRYRUN and denied.",
    ),
    DryrunSpec(
        test_id="DRY-12",
        category="delete_mutation",
        command=("DEL", "__udb_b02_dryrun_probe__"),
        expect_allowed=False,
        rationale="Key delete mutation must be simulated via DRYRUN and denied.",
    ),
    DryrunSpec(
        test_id="DRY-13",
        category="lua_scripting",
        command=("EVAL", "return 1", "0"),
        expect_allowed=False,
        rationale="Lua script execution must be simulated via DRYRUN and denied.",
    ),
    DryrunSpec(
        test_id="DRY-14",
        category="acl_escalation",
        command=("ACL", "SETUSER", "__udb_b02_dryrun_probe__", "off"),
        expect_allowed=False,
        rationale="ACL privilege mutation must be simulated via DRYRUN and denied.",
    ),
    DryrunSpec(
        test_id="DRY-15",
        category="destructive_flush",
        command=("FLUSHDB",),
        expect_allowed=False,
        rationale="Database flush must be simulated via DRYRUN and denied.",
    ),
    DryrunSpec(
        test_id="DRY-16",
        category="destructive_flush",
        command=("FLUSHALL",),
        expect_allowed=False,
        rationale="Instance flush must be simulated via DRYRUN and denied.",
    ),
    DryrunSpec(
        test_id="DRY-17",
        category="destructive_shutdown",
        command=("SHUTDOWN", "NOSAVE"),
        expect_allowed=False,
        rationale="Server shutdown must be simulated via DRYRUN and denied.",
    ),
)


def _redact_command_for_log(args: Sequence[str]) -> tuple[str, ...]:
    """Return a secret-redacted command tuple safe for recording and error messages."""
    tokens = tuple(str(a) for a in args)
    if not tokens:
        return ()
    upper0 = tokens[0].upper()
    if upper0 == "AUTH":
        if len(tokens) == 2:
            return ("AUTH", "<REDACTED>")
        if len(tokens) >= 3:
            return ("AUTH", tokens[1], "<REDACTED>")
    if upper0 == "HELLO" and len(tokens) >= 5 and tokens[2].upper() == "AUTH":
        return (tokens[0], tokens[1], tokens[2], tokens[3], "<REDACTED>")
    return tokens


def validate_observer_command(args: Sequence[str]) -> None:
    """Enforce the strict keyless observer allowlist before any socket byte is written.

    Allowed shapes on the observer connection:
      - ("AUTH", <username>, <token>)
      - ("HELLO", ...)
      - ("PING",)
      - ("ACL", "WHOAMI")
      - ("ROLE",)
      - ("DBSIZE",)
      - ("TIME",)
      - ("COMMAND", "COUNT")
      - ("CLIENT", "INFO") | ("CLIENT", "ID")
      - ("INFO", <section>) where <section> in ALLOWED_INFO_SECTIONS
    Everything else raises ObserverCommandNotAllowedError immediately.
    """
    if not args:
        raise ObserverCommandNotAllowedError("Empty Redis command is not allowed.")
    tokens = [str(a) for a in args]
    cmd = tokens[0].upper()

    if cmd == "AUTH":
        if len(tokens) == 3 and tokens[1] and tokens[2]:
            return
        raise ObserverCommandNotAllowedError(
            "Observer AUTH must use explicit ACL username + token (3 tokens)."
        )
    if cmd == "HELLO":
        if len(tokens) in {1, 2, 5}:
            return
        raise ObserverCommandNotAllowedError("Unsupported HELLO shape on observer transport.")
    if cmd in {"PING", "ROLE", "DBSIZE", "TIME"} and len(tokens) == 1:
        return
    if cmd == "ACL" and len(tokens) == 2 and tokens[1].upper() == "WHOAMI":
        return
    if cmd == "COMMAND" and len(tokens) == 2 and tokens[1].upper() == "COUNT":
        return
    if cmd == "CLIENT" and len(tokens) == 2 and tokens[1].upper() in {"INFO", "ID"}:
        return
    if cmd == "INFO" and len(tokens) == 2 and tokens[1].lower() in ALLOWED_INFO_SECTIONS:
        return

    raise ObserverCommandNotAllowedError(
        "OBSERVER_COMMAND_REJECTED_BEFORE_WRITE"
    )


def validate_provisioner_command(args: Sequence[str]) -> None:
    """Enforce the provisioner verification allowlist before any socket byte is written.

    The provisioner verifier connection may only execute:
      - ("AUTH", ...)
      - ("PING",)
      - ("ACL", "WHOAMI")
      - ("INFO", "server")
      - ("ACL", "DRYRUN", <observer_user>, <simulated_cmd>, ...)
    It may NEVER execute live destructive or keyspace commands directly.
    """
    if not args:
        raise ProvisionerCommandNotAllowedError("Empty Redis command is not allowed.")
    tokens = [str(a) for a in args]
    cmd = tokens[0].upper()

    if cmd == "AUTH" and len(tokens) in {2, 3}:
        return
    if cmd == "PING" and len(tokens) == 1:
        return
    if cmd == "ACL" and len(tokens) == 2 and tokens[1].upper() == "WHOAMI":
        return
    if cmd == "INFO" and len(tokens) == 2 and tokens[1].lower() == "server":
        return
    if cmd == "ACL" and len(tokens) >= 4 and tokens[1].upper() == "DRYRUN":
        return

    raise ProvisionerCommandNotAllowedError(
        "PROVISIONER_COMMAND_REJECTED_BEFORE_WRITE"
    )


def encode_resp_command(args: Sequence[str]) -> bytes:
    """Serialize a Redis command into a RESP2 array of bulk strings."""
    parts = [f"*{len(args)}\r\n".encode("ascii")]
    for arg in args:
        raw = str(arg).encode("utf-8")
        parts.append(f"${len(raw)}\r\n".encode("ascii"))
        parts.append(raw + b"\r\n")
    return b"".join(parts)


class RespSocketClient:
    """Minimal synchronous RESP2 client with pre-write transport allowlist enforcement."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        timeout: float = 3.0,
        role: str = "observer",
    ) -> None:
        if role not in {"observer", "provisioner"}:
            raise ValueError("UNSUPPORTED_TRANSPORT_ROLE")
        self.host = host
        self.port = port
        self.timeout = timeout
        self.role = role
        self._sock: socket.socket | None = None
        self._fp: Any = None
        self.recorded_commands: list[tuple[str, ...]] = []

    def __enter__(self) -> RespSocketClient:
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._fp = self._sock.makefile("rb")
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._fp is not None:
            try:
                self._fp.close()
            except OSError:
                pass
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass

    def _validate_before_write(self, args: Sequence[str]) -> None:
        if self.role == "observer":
            validate_observer_command(args)
        else:
            validate_provisioner_command(args)

    def _write_encoded_bytes(self, payload: bytes) -> None:
        if self._sock is None or self._fp is None:
            raise RuntimeError("RespSocketClient is not connected")
        self._sock.sendall(payload)

    def execute(self, *args: str) -> Any:
        """Validate command against role allowlist, then send and parse RESP2 reply."""
        self._validate_before_write(args)
        self.recorded_commands.append(_redact_command_for_log(args))
        payload = encode_resp_command(args)
        self._write_encoded_bytes(payload)
        try:
            return self._read_reply()
        except (ValueError, UnicodeError, TypeError):
            raise ValueError("RESP_REPLY_REJECTED") from None

    def _read_line(self) -> bytes:
        line: bytes = self._fp.readline()
        if not line or not line.endswith(b"\r\n"):
            raise ConnectionError("Unexpected EOF reading RESP2 line")
        return line[:-2]

    def _read_reply(self) -> Any:
        line = self._read_line()
        if not line:
            raise ConnectionError("Empty RESP2 reply line")
        prefix = line[:1]
        body = line[1:]
        if prefix == b"+":
            return body.decode("utf-8", errors="replace")
        if prefix == b"-":
            return RespError(body.decode("utf-8", errors="replace"))
        if prefix == b":":
            return int(body.decode("ascii"))
        if prefix == b"$":
            length = int(body.decode("ascii"))
            if length == -1:
                return None
            data: bytes = self._fp.read(length)
            crlf: bytes = self._fp.read(2)
            if len(data) != length or crlf != b"\r\n":
                raise ConnectionError("Truncated RESP2 bulk string")
            return data.decode("utf-8", errors="replace")
        if prefix == b"*":
            count = int(body.decode("ascii"))
            if count == -1:
                return None
            return [self._read_reply() for _ in range(count)]
        raise ValueError("UNSUPPORTED_RESP2_PREFIX")


def identity_sha256(identity: str) -> str:
    """Hash measured identity for outward evidence; authorization compares raw WHOAMI first."""
    if not isinstance(identity, str):
        raise ValueError("IDENTITY_TYPE_REJECTED")
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _metadata_count(value: Any, minimum: int = 0, maximum: int = 2**63 - 1) -> int | None:
    if type(value) is int:
        return value if minimum <= value <= maximum else None
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,19}", value):
        number = int(value)
        return number if minimum <= number <= maximum else None
    return None


def parse_and_filter_info(section: str, raw_text: str) -> dict[str, Any]:
    """Export only typed counters, closed enums, strict numeric version and database counts."""
    patterns = ALLOWED_INFO_PATTERNS.get(section, ())
    filtered: dict[str, Any] = {}
    if not isinstance(raw_text, str):
        return filtered
    enums = {
        "redis_mode": {"standalone", "cluster", "sentinel"},
        "aof_last_write_status": {"ok", "err"},
        "rdb_last_bgsave_status": {"ok", "err"},
        "maxmemory_policy": {
            "noeviction", "allkeys-lru", "allkeys-lfu", "allkeys-random",
            "volatile-lru", "volatile-lfu", "volatile-random", "volatile-ttl",
        },
        "role": {"master", "slave"},
    }
    counts = {
        "uptime_in_seconds", "rdb_last_save_time", "rdb_changes_since_last_save",
        "used_memory", "used_memory_peak", "maxmemory", "connected_clients",
        "blocked_clients", "maxclients", "total_connections_received",
        "total_commands_processed", "instantaneous_ops_per_sec", "rejected_connections",
        "keyspace_hits", "keyspace_misses", "evicted_keys", "expired_keys",
        "connected_slaves", "master_repl_offset",
    }
    for line in raw_text.splitlines():
        line = line.strip()
        if not any(pattern.search(line) for pattern in patterns):
            continue
        key, _, value = line.partition(":")
        if key in enums:
            filtered[key] = value if value in enums[key] else None
        elif key in counts:
            filtered[key] = _metadata_count(value)
        elif key in {"loading", "aof_enabled"}:
            filtered[key] = bool(int(value)) if value in {"0", "1"} else None
        elif key == "arch_bits":
            filtered[key] = int(value) if value in {"32", "64"} else None
        elif key == "tcp_port":
            filtered[key] = _metadata_count(value, 1, 65535)
        elif key == "redis_version":
            filtered[key] = value if re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", value) else None
        elif key == "mem_fragmentation_ratio":
            filtered[key] = float(value) if re.fullmatch(r"[0-9]{1,6}(\.[0-9]{1,6})?", value) else None
        elif section == "keyspace" and re.fullmatch(r"db[0-9]{1,5}", key):
            match = re.fullmatch(r"keys=([0-9]{1,19}),expires=([0-9]{1,19}),avg_ttl=([0-9]{1,19})(?:,subexpiry=([0-9]{1,19}))?", value)
            if match and int(key[2:]) <= 65535:
                filtered[key] = {
                    label: _metadata_count(match.group(index))
                    for index, label in enumerate(("keys", "expires", "avg_ttl"), 1)
                }
            else:
                filtered[key] = None
        # OS, executable/config paths, human-readable sizes and other free text are omitted.
    return filtered


def load_credentials_from_env_file(
    env_file: Path = DEFAULT_OBSERVER_ENV_FILE,
    user_key: str = "REDIS_OBSERVER_USER",
    pass_key: str = "REDIS_OBSERVER_PASSWORD",
) -> tuple[str, str] | None:
    """Read credentials in-process from a mode-0600 file without shell or argv expansion."""
    if not env_file.exists():
        return None
    mode = stat.S_IMODE(env_file.stat().st_mode)
    if mode != 0o600:
        raise PermissionError(
            "CREDENTIAL_FILE_PERMISSION_REJECTED: expected 0o600"
        )
    user_val: str | None = None
    pass_val: str | None = None
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip("'").strip('"')
        if k == user_key:
            user_val = v
        elif k == pass_key:
            pass_val = v
    if user_val and pass_val:
        return (user_val, pass_val)
    return None


def resolve_observer_credentials(
    explicit_credentials: tuple[str, str] | None = None,
    env_file: Path = DEFAULT_OBSERVER_ENV_FILE,
) -> tuple[str, str, str] | None:
    """Resolve (username, password, source_label) without reading REDIS_PASSWORD/REDIS_URL or argv."""
    if explicit_credentials is not None:
        user, pw = explicit_credentials
        return (user, pw, "explicit_in_memory")
    file_creds = load_credentials_from_env_file(env_file=env_file)
    if file_creds is not None:
        return (file_creds[0], file_creds[1], f"env_file_0600:{env_file.name}")
    return None


def _validate_observer_context(
    host: str, port: int, store_id: str, acl_policy_sha256: str, source_version: str,
) -> None:
    """Reject untrusted caller context before credentials, connection or report creation."""
    if (
        not isinstance(host, str) or host not in {"127.0.0.1", "localhost", "::1"}
        or type(port) is not int or not 1 <= port <= 65535
        or not isinstance(store_id, str)
        or store_id not in {"redis:mini:6379/db0", "redis:pro:6379/db0"}
        or not isinstance(acl_policy_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", acl_policy_sha256) is None
        or not isinstance(source_version, str)
        or re.fullmatch(r"[0-9a-f]{40}", source_version) is None
    ):
        raise ValueError("OBSERVER_CONTEXT_REJECTED")


def evaluate_provisioner_dryrun_matrix(
    provisioner_client: RespSocketClient | None,
    observer_user: str = EXPECTED_OBSERVER_USER,
    host: str = "127.0.0.1",
    port: int = 6379,
    store_id: str = STORE_ID,
    acl_policy_sha256: str = EXPECTED_OBSERVER_ACL_POLICY_SHA256,
    source_version: str = BASE_COMMIT_SHA,
) -> dict[str, Any]:
    """Verify observer permissions via a separate provisioner connection using ACL DRYRUN.

    Never sends real forbidden commands; never falls back to live command execution on error.
    """
    _validate_observer_context(host, port, store_id, acl_policy_sha256, source_version)
    endpoint = f"{host}:{port}"
    evidence: dict[str, Any] = {
        "plane": "provisioner_acl_dryrun",
        "store_id": store_id,
        "endpoint": endpoint,
        "observer_identity": identity_sha256(observer_user),
        "acl_policy_sha256": acl_policy_sha256,
        "source_version": source_version,
        "evidence_timestamp": datetime.now(UTC).isoformat(),
        "status": "NOT_EXECUTED",
        "x_dryrun_state": "NOT_EXECUTED",
        "positive_dryrun_results": [],
        "negative_dryrun_results": [],
        "unknowns": [],
    }
    if provisioner_client is None:
        evidence["unknowns"].append("LIVE_DRYRUN_MATRIX_NOT_EXECUTED_NO_PROVISIONER_ADMISSION")
        return evidence

    if provisioner_client.role != "provisioner":
        raise ProvisionerCommandNotAllowedError(
            "evaluate_provisioner_dryrun_matrix requires a client with role='provisioner'."
        )

    pos_results: list[dict[str, Any]] = []
    neg_results: list[dict[str, Any]] = []

    for spec in POSITIVE_DRYRUN_SPECS:
        reply = provisioner_client.execute("ACL", "DRYRUN", observer_user, *spec.command)
        classified = _classify_dryrun_reply(spec, reply)
        pos_results.append(classified)
        if classified["outcome"] != "VERIFIED":
            evidence["positive_dryrun_results"] = pos_results
            evidence["status"] = classified["failure_status"]
            evidence["x_dryrun_state"] = classified["failure_state"]
            evidence["unknowns"].append(classified["unknown_token"])
            return evidence

    for spec in NEGATIVE_DRYRUN_SPECS:
        reply = provisioner_client.execute("ACL", "DRYRUN", observer_user, *spec.command)
        classified = _classify_dryrun_reply(spec, reply)
        neg_results.append(classified)
        if classified["outcome"] != "VERIFIED":
            evidence["positive_dryrun_results"] = pos_results
            evidence["negative_dryrun_results"] = neg_results
            evidence["status"] = classified["failure_status"]
            evidence["x_dryrun_state"] = classified["failure_state"]
            evidence["unknowns"].append(classified["unknown_token"])
            return evidence

    evidence["positive_dryrun_results"] = pos_results
    evidence["negative_dryrun_results"] = neg_results
    evidence["status"] = "EVIDENCED"
    evidence["x_dryrun_state"] = "DRYRUN_MATRIX_VERIFIED"
    return evidence


def _classify_dryrun_reply(spec: DryrunSpec, reply: Any) -> dict[str, Any]:
    """Classify a single `ACL DRYRUN` response without any live-command fallback."""
    if spec not in (*POSITIVE_DRYRUN_SPECS, *NEGATIVE_DRYRUN_SPECS):
        raise ProvisionerCommandNotAllowedError("UNTRUSTED_DRYRUN_SPEC")
    cmd_display = " ".join(spec.command)
    if isinstance(reply, RespError):
        msg_lower = reply.message.lower()
        if reply.code in {"NOPERM", "NOAUTH", "WRONGPASS"}:
            return {
                "test_id": spec.test_id,
                "category": spec.category,
                "simulated_command": cmd_display,
                "expect_allowed": spec.expect_allowed,
                "outcome": "DRYRUN_DENIED",
                "reply_summary": reply.code,
                "failure_status": "BLOCKED",
                "failure_state": "DRYRUN_DENIED",
                "unknown_token": f"ACL_DRYRUN_{reply.code}",
            }
        if (
            reply.code == "UNK"
            or "unknown subcommand" in msg_lower
            or "unknown command" in msg_lower
        ):
            return {
                "test_id": spec.test_id,
                "category": spec.category,
                "simulated_command": cmd_display,
                "expect_allowed": spec.expect_allowed,
                "outcome": "DRYRUN_UNSUPPORTED",
                "reply_summary": "SERVER_ERROR_REDACTED",
                "failure_status": "UNKNOWN",
                "failure_state": "DRYRUN_UNSUPPORTED",
                "unknown_token": "ACL_DRYRUN_UNSUPPORTED",
            }
        return {
            "test_id": spec.test_id,
            "category": spec.category,
            "simulated_command": cmd_display,
            "expect_allowed": spec.expect_allowed,
            "outcome": "DRYRUN_UNEXPECTED_REPLY",
            "reply_summary": "SERVER_ERROR_REDACTED",
            "failure_status": "UNKNOWN",
            "failure_state": "DRYRUN_UNEXPECTED_REPLY",
            "unknown_token": "ACL_DRYRUN_UNEXPECTED_REPLY",
        }

    if isinstance(reply, str):
        text = reply.strip()
        if spec.expect_allowed:
            if text == "OK":
                return {
                    "test_id": spec.test_id,
                    "category": spec.category,
                    "simulated_command": cmd_display,
                    "expect_allowed": True,
                    "outcome": "VERIFIED",
                    "reply_summary": "OK",
                }
            if "has no permissions to " in text.lower():
                return {
                    "test_id": spec.test_id,
                    "category": spec.category,
                    "simulated_command": cmd_display,
                    "expect_allowed": True,
                    "outcome": "FAILED_UNDERPRIVILEGED",
                    "reply_summary": "PERMISSION_DENIED",
                    "failure_status": "BLOCKED",
                    "failure_state": "FAILED_UNDERPRIVILEGED",
                    "unknown_token": f"DRYRUN_REQUIRED_COMMAND_DENIED:{spec.test_id}",
                }
        else:
            if "has no permissions to " in text.lower():
                return {
                    "test_id": spec.test_id,
                    "category": spec.category,
                    "simulated_command": cmd_display,
                    "expect_allowed": False,
                    "outcome": "VERIFIED",
                    "reply_summary": "PERMISSION_DENIED",
                }
            if text == "OK":
                return {
                    "test_id": spec.test_id,
                    "category": spec.category,
                    "simulated_command": cmd_display,
                    "expect_allowed": False,
                    "outcome": "FAILED_OVERPRIVILEGED",
                    "reply_summary": "OK",
                    "failure_status": "CONFLICT",
                    "failure_state": "FAILED_OVERPRIVILEGED",
                    "unknown_token": f"DRYRUN_FORBIDDEN_COMMAND_PERMITTED:{spec.test_id}",
                }

    return {
        "test_id": spec.test_id,
        "category": spec.category,
        "simulated_command": cmd_display,
        "expect_allowed": spec.expect_allowed,
        "outcome": "DRYRUN_UNEXPECTED_REPLY",
        "reply_summary": "UNEXPECTED_REPLY",
        "failure_status": "UNKNOWN",
        "failure_state": "DRYRUN_UNEXPECTED_REPLY",
        "unknown_token": "ACL_DRYRUN_UNEXPECTED_REPLY",
    }


def combine_observer_and_dryrun_evidence(
    observer_evidence: dict[str, Any],
    dryrun_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Bind observer metadata evidence and provisioner DRYRUN evidence.

    Promotes `x_observer_state` to `ADMITTED_VERIFIED` if and only if:
      1. `observer_evidence["x_observer_state"] == "OBSERVER_METADATA_ADMITTED"`
      2. `dryrun_evidence["x_dryrun_state"] == "DRYRUN_MATRIX_VERIFIED"`
      3. Both planes agree on `endpoint`, `observer_identity`, `acl_policy_sha256`,
         and `source_version`.
    """
    plane = observer_evidence.get("observer_evidence", observer_evidence)
    combined = dict(observer_evidence)
    combined["observer_evidence"] = dict(plane)
    combined["dryrun_evidence"] = dict(dryrun_evidence)
    unknowns: list[str] = list(observer_evidence.get("unknowns", []))
    for u in dryrun_evidence.get("unknowns", []):
        if u not in unknowns:
            unknowns.append(u)
    if dryrun_evidence.get("x_dryrun_state") != "NOT_EXECUTED":
        unknowns = [u for u in unknowns if u != "LIVE_DRYRUN_MATRIX_NOT_EXECUTED_NO_PROVISIONER_ADMISSION"]

    if plane.get("x_observer_state") != "OBSERVER_METADATA_ADMITTED":
        combined["unknowns"] = unknowns
        return combined

    binding_errors: list[str] = []
    if plane.get("endpoint") != dryrun_evidence.get("endpoint"):
        binding_errors.append("EVIDENCE_BINDING_MISMATCH_ENDPOINT")
    if plane.get("effective_principal") != dryrun_evidence.get("observer_identity"):
        binding_errors.append("EVIDENCE_BINDING_MISMATCH_IDENTITY")
    obs_hash = plane.get("acl_policy_sha256")
    dry_hash = dryrun_evidence.get("acl_policy_sha256")
    if not obs_hash or obs_hash != dry_hash:
        binding_errors.append("EVIDENCE_BINDING_MISMATCH_ACL_POLICY_HASH")
    obs_src = plane.get("source_version")
    dry_src = dryrun_evidence.get("source_version")
    if not obs_src or obs_src != dry_src or obs_src != BASE_COMMIT_SHA:
        binding_errors.append("EVIDENCE_BINDING_MISMATCH_SOURCE_VERSION")

    if binding_errors:
        # Rejected identity/binding fields must not survive in the outward record.
        combined["dryrun_evidence"] = {
            "plane": "provisioner_acl_dryrun",
            "status": "CONFLICT",
            "x_dryrun_state": "EVIDENCE_BINDING_REJECTED",
        }
        for err in binding_errors:
            if err not in unknowns:
                unknowns.append(err)
        combined["status"] = "CONFLICT"
        combined["x_observer_state"] = "FAILED_EVIDENCE_BINDING_MISMATCH"
        combined["unknowns"] = unknowns
        return combined

    dry_state = dryrun_evidence.get("x_dryrun_state")
    if dry_state == "DRYRUN_MATRIX_VERIFIED":
        combined["status"] = "EVIDENCED"
        combined["x_observer_state"] = "ADMITTED_VERIFIED"
        combined["unknowns"] = unknowns
        return combined

    if dry_state == "NOT_EXECUTED":
        combined["status"] = "BLOCKED"
        combined["x_observer_state"] = "OBSERVER_METADATA_ONLY_DRYRUN_PENDING"
        combined["unknowns"] = unknowns
        return combined

    if dry_state == "FAILED_OVERPRIVILEGED":
        combined["status"] = "CONFLICT"
        combined["x_observer_state"] = "FAILED_OVERPRIVILEGED"
        combined["unknowns"] = unknowns
        return combined

    combined["status"] = dryrun_evidence.get("status", "UNKNOWN")
    combined["x_observer_state"] = str(dry_state or "DRYRUN_UNVERIFIED")
    combined["unknowns"] = unknowns
    return combined


def probe_redis_observer(
    host: str = "127.0.0.1",
    port: int = 6379,
    store_id: str = STORE_ID,
    credentials: tuple[str, str] | None = None,
    env_file: Path = DEFAULT_OBSERVER_ENV_FILE,
    expected_observer_user: str = EXPECTED_OBSERVER_USER,
    acl_policy_sha256: str = EXPECTED_OBSERVER_ACL_POLICY_SHA256,
    source_version: str = BASE_COMMIT_SHA,
    observer_client: RespSocketClient | None = None,
    provisioner_client: RespSocketClient | None = None,
    dryrun_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute the keyless observer metadata probe and bind optional provisioner DRYRUN evidence.

    The observer connection NEVER sends any non-allowlisted command.
    """
    _validate_observer_context(host, port, store_id, acl_policy_sha256, source_version)
    now_iso = datetime.now(UTC).isoformat()
    endpoint = f"{host}:{port}"
    resolved = resolve_observer_credentials(
        explicit_credentials=credentials,
        env_file=env_file,
    )
    credential_source = resolved[2] if resolved is not None else "unauthenticated_none"

    report: dict[str, Any] = {
        "plane": "observer_keyless_metadata",
        "store_id": store_id,
        "endpoint": endpoint,
        "host": host,
        "port": port,
        "evidence_timestamp": now_iso,
        "source_version": source_version,
        "acl_policy_sha256": acl_policy_sha256,
        "credential_source": credential_source,
        "status": "BLOCKED",
        "x_observer_state": "UNPROVISIONED",
        "effective_principal": None,
        "positive_metadata": {},
        "unknowns": ["OPERATION_ID_PENDING_B05"],
    }

    if resolved is not None and resolved[0] == "default":
        report["status"] = "CONFLICT"
        report["x_observer_state"] = "REJECTED_OVERPRIVILEGED_DEFAULT"
        report["effective_principal"] = identity_sha256("default")
        report["unknowns"].append("OBSERVER_USER_MUST_NOT_BE_DEFAULT")
        return report

    def _run_on_observer(client: RespSocketClient) -> dict[str, Any]:
        if resolved is not None:
            username, password, _ = resolved
            auth_reply = client.execute("AUTH", username, password)
            if isinstance(auth_reply, RespError):
                report["status"] = "BLOCKED"
                report["x_observer_state"] = f"AUTH_FAILED_{auth_reply.code}"
                report["unknowns"].append("OWNER_CONSENT_REQUIRED_REDIS_OBSERVER_ACL")
                return report

        ping_reply = client.execute("PING")
        if isinstance(ping_reply, RespError):
            if ping_reply.code in {"NOAUTH", "WRONGPASS"}:
                report["status"] = "BLOCKED"
                report["x_observer_state"] = "UNAUTHENTICATED_NOAUTH"
                report["unknowns"].append("OWNER_CONSENT_REQUIRED_REDIS_OBSERVER_ACL")
                return report
            report["status"] = "BLOCKED"
            report["x_observer_state"] = f"PING_ERROR_{ping_reply.code}"
            return report

        whoami_reply = client.execute("ACL", "WHOAMI")
        if isinstance(whoami_reply, RespError):
            report["status"] = "BLOCKED"
            report["x_observer_state"] = f"WHOAMI_ERROR_{whoami_reply.code}"
            return report

        effective_principal = whoami_reply.strip() if isinstance(whoami_reply, str) else None
        report["effective_principal"] = (
            identity_sha256(effective_principal) if effective_principal is not None else None
        )
        if effective_principal == "default":
            report["status"] = "CONFLICT"
            report["x_observer_state"] = "REJECTED_OVERPRIVILEGED_DEFAULT"
            report["unknowns"].append("OBSERVER_PRINCIPAL_RESOLVED_TO_DEFAULT")
            return report
        if effective_principal != expected_observer_user:
            report["status"] = "CONFLICT"
            report["x_observer_state"] = "REJECTED_UNEXPECTED_PRINCIPAL"
            report["unknowns"].append("UNEXPECTED_PRINCIPAL")
            return report

        role_reply = client.execute("ROLE")
        dbsize_reply = client.execute("DBSIZE")
        time_reply = client.execute("TIME")
        cmd_count_reply = client.execute("COMMAND", "COUNT")
        client_id_reply = client.execute("CLIENT", "ID")
        client_info_reply = client.execute("CLIENT", "INFO")

        sections_data: dict[str, dict[str, Any]] = {}
        for section in ALLOWED_INFO_SECTIONS:
            info_reply = client.execute("INFO", section)
            if isinstance(info_reply, RespError):
                report["status"] = "BLOCKED"
                report["x_observer_state"] = f"INFO_{section.upper()}_FAILED_{info_reply.code}"
                return report
            sections_data[section] = parse_and_filter_info(section, info_reply)

        client_info_summary: dict[str, Any] = {}
        if isinstance(client_info_reply, str):
            for token in client_info_reply.strip().split():
                key, separator, value = token.partition("=")
                if not separator:
                    continue
                if key == "user":
                    client_info_summary["user"] = identity_sha256(value)
                elif key == "db":
                    client_info_summary["db"] = _metadata_count(value, 0, 65535)
                elif key == "resp":
                    client_info_summary["resp"] = int(value) if value in {"2", "3"} else None

        report["positive_metadata"] = {
            "ping": ping_reply == "PONG",
            "acl_whoami": identity_sha256(effective_principal),
            "role": role_reply[0] if isinstance(role_reply, list) and role_reply and role_reply[0] in ("master", "slave") else None,
            "dbsize": _metadata_count(dbsize_reply) if type(dbsize_reply) is int else None,
            "server_time_epoch": (
                _metadata_count(time_reply[0], 1) if isinstance(time_reply, list) and time_reply else None
            ),
            "command_count": _metadata_count(cmd_count_reply, 1) if type(cmd_count_reply) is int else None,
            "client_id": _metadata_count(client_id_reply, 1) if type(client_id_reply) is int else None,
            "client_info": client_info_summary,
            "info_sections": sections_data,
        }
        measured = report["positive_metadata"]
        if (
            measured["ping"] is not True
            or any(measured[key] is None for key in ("role", "dbsize", "server_time_epoch", "command_count", "client_id"))
            or client_info_summary.get("user") != identity_sha256(effective_principal)
            or any(value is None for value in client_info_summary.values())
            or any(
                (section != "keyspace" and not values)
                or any(value is None or (isinstance(value, dict) and any(v is None for v in value.values())) for value in values.values())
                for section, values in sections_data.items()
            )
        ):
            report["status"] = "BLOCKED"
            report["x_observer_state"] = "OBSERVER_METADATA_INCOMPLETE"
            report["unknowns"].append("OBSERVER_METADATA_INCOMPLETE")
            return report
        report["status"] = "PARTIAL"
        report["x_observer_state"] = "OBSERVER_METADATA_ADMITTED"
        report["observer_evidence"] = {
            "plane": "observer_keyless_metadata",
            "endpoint": endpoint,
            "store_id": store_id,
            "effective_principal": identity_sha256(effective_principal),
            "acl_policy_sha256": acl_policy_sha256,
            "source_version": source_version,
            "x_observer_state": "OBSERVER_METADATA_ADMITTED",
        }
        return report

    try:
        if observer_client is not None:
            if observer_client.role != "observer":
                raise ObserverCommandNotAllowedError(
                    "observer_client must have role='observer'."
                )
            _run_on_observer(observer_client)
        else:
            with RespSocketClient(host=host, port=port, role="observer") as live_obs:
                _run_on_observer(live_obs)
    except (OSError, ValueError, TypeError, KeyError):
        report["status"] = "BLOCKED"
        report["x_observer_state"] = "CONNECTION_ERROR"
        report["unknowns"].append("OBSERVER_TRANSPORT_ERROR")
        return report

    if report["x_observer_state"] != "OBSERVER_METADATA_ADMITTED":
        return report

    resolved_dryrun = dryrun_evidence
    if resolved_dryrun is None:
        resolved_dryrun = evaluate_provisioner_dryrun_matrix(
            provisioner_client=provisioner_client,
            observer_user=expected_observer_user,
            host=host,
            port=port,
            store_id=store_id,
            acl_policy_sha256=acl_policy_sha256,
            source_version=source_version,
        )

    return combine_observer_and_dryrun_evidence(report, resolved_dryrun)


def _cell(value: Any, status: str, evidence_ref: str) -> dict[str, Any]:
    if status not in CONTRACT_STATUS_VALUES:
        raise ValueError("INVALID_CONTRACT_STATUS")
    return {"value": value, "status": status, "evidence_ref": evidence_ref}


def build_contract_row(
    probe_report: dict[str, Any],
    evidence_ref: str,
    consumer_id: str = "B02:probe:redis_observer_probe",
    path: str = "research/operations/udb-wave8/B02/redis_observer_probe.py",
    line: int = 1,
) -> dict[str, Any]:
    """Format a probe report as a 19-key + x_* row per CONTRACT-CONVENTIONS.md."""
    top_status = probe_report["status"]
    if top_status not in CONTRACT_STATUS_VALUES:
        top_status = "BLOCKED"

    row: dict[str, Any] = {
        "consumer_id": consumer_id,
        "kind": "runtime_observer_probe",
        "path": path,
        "line": line,
        "raw_target": f"redis://{probe_report['host']}:{probe_report['port']}/0",
        "evidence_source": "runtime_receipt",
        "confidence": "HIGH" if top_status == "EVIDENCED" else "MEDIUM",
        "reason": (
            f"Redis 8.x observer probe ({probe_report['x_observer_state']}) "
            f"via {probe_report['credential_source']}"
        ),
        "operation_id": _cell("UNASSIGNED_B05", "UNKNOWN", evidence_ref),
        "store_id": _cell(probe_report["store_id"], top_status, evidence_ref),
        "subcontainer": _cell("db0", top_status, evidence_ref),
        "op_kind": _cell("ADMIN", top_status, evidence_ref),
        "shape_or_key_pattern": _cell(
            "ACL WHOAMI / INFO server,persistence,keyspace,memory,clients,stats,replication / DBSIZE / ROLE",
            top_status,
            evidence_ref,
        ),
        "WriteConsequence": _cell("NONE_READ_ONLY_OBSERVER", top_status, evidence_ref),
        "CrossStoreLink": _cell("NONE", top_status, evidence_ref),
        "AuthoritativeStore": _cell(probe_report["store_id"], top_status, evidence_ref),
        "CacheInvalidationRule": _cell("NOT_APPLICABLE_OBSERVER", top_status, evidence_ref),
        "LockScope": _cell("NONE", top_status, evidence_ref),
        "CallerSet": _cell(["research/operations/udb-wave8/B02/redis_observer_probe.py"], top_status, evidence_ref),
        "status": top_status,
        "evidence_timestamp": probe_report["evidence_timestamp"],
        "source_version": probe_report["source_version"],
        "unknowns": list(probe_report["unknowns"]),
        "x_observer_state": probe_report["x_observer_state"],
        "x_effective_principal": probe_report["effective_principal"],
        "x_positive_metadata": probe_report["positive_metadata"],
        "x_dryrun_evidence": probe_report.get("dryrun_evidence"),
    }
    return row


def main(argv: Sequence[str] | None = None) -> int:
    parser = _BoundaryArgumentParser(
        description="Redis 8.x keyless observer metadata probe (B02)."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=6379)
    parser.add_argument("--store-id", default=STORE_ID)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_OBSERVER_ENV_FILE,
        help="Path to mode-0600 observer env file (never pass secrets on argv).",
    )
    args = parser.parse_args(argv)
    report = probe_redis_observer(
        host=args.host,
        port=args.port,
        store_id=args.store_id,
        env_file=args.env_file,
    )
    import json

    sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if report["x_observer_state"] == "ADMITTED_VERIFIED" else 1


if __name__ == "__main__":
    try:
        exit_code = main()
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        sys.stderr.write("B02_PROBE_INPUT_OR_TRANSPORT_REJECTED\n")
        exit_code = 1
    raise SystemExit(exit_code)
