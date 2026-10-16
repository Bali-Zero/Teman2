"""Prepared temporary observer exercise; native use requires separate admission.

Reuse the existing RESP transport, keyless probe and ACL DRYRUN matrix. This
module has no CLI, credential fallback, installer or native scheduling path.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import threading
from typing import Any

import redis_observer_probe as probe


class AdmissionError(Exception):
    """A constant diagnostic code, never a server or credential message."""


_TARGET = re.compile(r"nuzantara_observer_wave8_[0-9a-f]{32}\Z")
_COMMANDS = frozenset(
    "-@all +ping +info +dbsize +role +time +command|count "
    "+acl|whoami +client|info +client|id".split()
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def load_provisioner_credentials(path: Path) -> tuple[str, str]:
    """Read only an explicitly admitted, owned 0600 regular private JSON file."""
    fd = -1
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        s = os.fstat(fd)
        if (
            not stat.S_ISREG(s.st_mode)
            or s.st_uid != os.getuid()
            or stat.S_IMODE(s.st_mode) != 0o600
            or s.st_nlink != 1
            or s.st_size > 8192
        ):
            raise AdmissionError("CREDENTIAL_FILE_REJECTED")
        raw = os.read(fd, 8193)
        value = json.loads(raw)
        if set(value) != {"user", "password"}:
            raise AdmissionError("CREDENTIAL_FILE_REJECTED")
        user, password = value["user"], value["password"]
        if (
            not isinstance(user, str)
            or not isinstance(password, str)
            or not user
            or not password
        ):
            raise AdmissionError("CREDENTIAL_FILE_REJECTED")
        return user, password
    except (OSError, ValueError, TypeError, KeyError):
        raise AdmissionError("CREDENTIAL_FILE_REJECTED") from None
    finally:
        if fd >= 0:
            os.close(fd)


class _LifecycleClient(probe.RespSocketClient):
    """Allow only one generated role's exact setup, activation and cleanup."""

    def __init__(self, host: str, port: int, target: str, password_hash: str):
        if not _TARGET.fullmatch(target) or not re.fullmatch(
            r"[0-9a-f]{64}", password_hash
        ):
            raise AdmissionError("INVALID_TEMPORARY_ROLE")
        super().__init__(host=host, port=port, role="provisioner")
        self.target = target
        self.claimed = False
        self.setup = (
            "ACL",
            "SETUSER",
            target,
            "reset",
            "off",
            "resetkeys",
            "resetchannels",
            "-@all",
            *sorted(_COMMANDS.difference({"-@all"})),
            "#" + password_hash,
        )

    def _validate_before_write(self, args: tuple[str, ...]) -> None:
        command = tuple(args)
        if command in [("ACL", "GETUSER", self.target), ("ACL", "WHOAMI"), ("PING",)]:
            return
        if len(command) == 3 and command[0] == "AUTH":
            return
        if self.claimed and command in [
            self.setup,
            ("ACL", "SETUSER", self.target, "on"),
            ("ACL", "DELUSER", self.target),
        ]:
            return
        raise AdmissionError("LIFECYCLE_COMMAND_NOT_ALLOWED")

    def execute(self, *args: str) -> Any:
        self._validate_before_write(args)
        # The generic logger masks AUTH, but does not mask SETUSER password hashes.
        if args[:2] == ("ACL", "SETUSER"):
            logged = ("ACL", "SETUSER", self.target, "[RULES_REDACTED]")
        else:
            logged = probe._redact_command_for_log(args)
        self.recorded_commands.append(logged)
        self._write_encoded_bytes(probe.encode_resp_command(args))
        return self._read_reply()


def _ok(reply: Any, expected: Any, code: str) -> None:
    if isinstance(reply, probe.RespError) or reply != expected:
        raise AdmissionError(code)


def _authenticate(
    client: probe.RespSocketClient, credentials: tuple[str, str], actor_pin: str
) -> None:
    if (
        not re.fullmatch(r"[0-9a-f]{64}", actor_pin)
        or _sha(credentials[0]) != actor_pin
    ):
        raise AdmissionError("PROVISIONER_IDENTITY_NOT_ADMITTED")
    _ok(client.execute("AUTH", *credentials), "OK", "PROVISIONER_AUTH_FAILED")
    actual = client.execute("ACL", "WHOAMI")
    if not isinstance(actual, str) or _sha(actual) != actor_pin:
        raise AdmissionError("PROVISIONER_IDENTITY_MISMATCH")


def _policy(reply: Any, target: str, password_hash: str, active: bool) -> str:
    if not isinstance(reply, list) or len(reply) % 2:
        raise AdmissionError("POLICY_UNMEASURED")
    value = dict(zip(reply[::2], reply[1::2]))
    flags = set(value.get("flags", []))
    expected_flags = {"on" if active else "off"}
    if (
        flags.difference({"sanitize-payload"}) != expected_flags
        or set(str(value.get("commands", "")).split()) != _COMMANDS
        or value.get("keys") != ""
        or value.get("channels") != ""
        or value.get("selectors", []) != []
        or value.get("passwords") != [password_hash]
    ):
        raise AdmissionError("POLICY_MISMATCH")
    public_policy = {
        "identity_sha256": _sha(target),
        "commands": sorted(str(value["commands"]).split()),
        "keys": value["keys"],
        "channels": value["channels"],
        "selectors": value.get("selectors", []),
        "password_count": len(value["passwords"]),
    }
    return _sha(json.dumps(public_policy, sort_keys=True, separators=(",", ":")))


def _remove_owned_role(host, port, target, password_hash, credentials, actor_pin):
    """Never reuse a possibly desynchronized lifecycle socket for cleanup."""
    with _LifecycleClient(host, port, target, password_hash) as cleanup:
        cleanup.claimed = True
        _authenticate(cleanup, credentials, actor_pin)
        if cleanup.execute("ACL", "GETUSER", target) is None:
            return
        reply = cleanup.execute("ACL", "DELUSER", target)
        if isinstance(reply, probe.RespError) or reply not in (0, 1):
            raise AdmissionError("ROLE_CLEANUP_FAILED")
        if cleanup.execute("ACL", "GETUSER", target) is not None:
            raise AdmissionError("ROLE_CLEANUP_UNVERIFIED")


def _exercise_temporary_observer(
    *,
    host: str,
    port: int,
    provisioner_credentials: tuple[str, str],
    provisioner_identity_sha256: str,
    admitted_endpoint: tuple[str, int],
    evidence_kind: str,
    target: str,
) -> dict[str, Any]:
    """Exercise one ephemeral role and remove it; this does not grant permission.

    Call only after exact-source gate, owner admission, exclusive endpoint lease,
    and approval of the credential delivery route. Never substitute app secrets.
    The credential tuple and generated observer password/hash are memory only.
    """
    if (
        admitted_endpoint != (host, port)
        or host != "127.0.0.1"
        or not 1 <= port <= 65535
    ):
        raise AdmissionError("ENDPOINT_NOT_ADMITTED")
    if evidence_kind not in {"ISOLATED_TEST", "NATIVE_ADMITTED"}:
        raise AdmissionError("EVIDENCE_KIND_REQUIRED")
    password = secrets.token_urlsafe(48)
    password_hash = _sha(password)
    result: dict[str, Any] = {
        "schema_version": 1,
        "evidence_started_at": datetime.now(UTC).isoformat(),
        "evidence_kind": evidence_kind,
        "status": "BLOCKED",
        "endpoint_sha256": _sha(f"{host}:{port}"),
        "observer_identity_sha256": _sha(target),
        "role_created": False,
        "role_removed": False,
        "policy_off_verified": False,
        "policy_on_verified": False,
        "observer_metadata_verified": False,
        "dryrun_verified": False,
        "positive_permission_count": 0,
        "negative_permission_count": 0,
        "diagnostic": "NOT_EXECUTED",
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), Path(probe.__file__)]
        },
    }
    with _LifecycleClient(host, port, target, password_hash) as lifecycle:
        try:
            _authenticate(
                lifecycle, provisioner_credentials, provisioner_identity_sha256
            )
            if lifecycle.execute("ACL", "GETUSER", target) is not None:
                raise AdmissionError("ROLE_COLLISION_NO_MUTATION")
            lifecycle.claimed = (
                True  # cleanup also covers an uncertain SETUSER response
            )
            _ok(lifecycle.execute(*lifecycle.setup), "OK", "ROLE_SETUP_FAILED")
            result["role_created"] = True
            fingerprint = _policy(
                lifecycle.execute("ACL", "GETUSER", target),
                target,
                password_hash,
                False,
            )
            result["policy_off_verified"] = True
            with probe.RespSocketClient(
                host=host, port=port, role="provisioner"
            ) as verifier:
                _authenticate(
                    verifier, provisioner_credentials, provisioner_identity_sha256
                )
                dryrun = probe.evaluate_provisioner_dryrun_matrix(
                    verifier,
                    observer_user=target,
                    host=host,
                    port=port,
                    acl_policy_sha256=fingerprint,
                )
            if dryrun.get("x_dryrun_state") != "DRYRUN_MATRIX_VERIFIED":
                raise AdmissionError("DRYRUN_MATRIX_NOT_VERIFIED")
            result["dryrun_verified"] = True
            result["positive_permission_count"] = len(dryrun["positive_dryrun_results"])
            result["negative_permission_count"] = len(dryrun["negative_dryrun_results"])
            _ok(
                lifecycle.execute("ACL", "SETUSER", target, "on"),
                "OK",
                "ROLE_ACTIVATION_FAILED",
            )
            active = _policy(
                lifecycle.execute("ACL", "GETUSER", target), target, password_hash, True
            )
            if active != fingerprint:
                raise AdmissionError("POLICY_CHANGED_AFTER_ACTIVATION")
            result["policy_on_verified"] = True
            metadata = probe.probe_redis_observer(
                host=host,
                port=port,
                credentials=(target, password),
                expected_observer_user=target,
                acl_policy_sha256=active,
                dryrun_evidence=dryrun,
            )
            if metadata.get("x_observer_state") != "ADMITTED_VERIFIED":
                raise AdmissionError("OBSERVER_METADATA_NOT_VERIFIED")
            measured = metadata.get("positive_metadata", {})
            if (
                measured.get("ping") is not True
                or measured.get("acl_whoami") != probe.identity_sha256(target)
                or measured.get("role") not in {"master", "slave"}
                or any(
                    type(measured.get(key)) is not int or measured[key] < minimum
                    for key, minimum in [
                        ("dbsize", 0),
                        ("server_time_epoch", 1),
                        ("command_count", 1),
                        ("client_id", 1),
                    ]
                )
                or measured.get("client_info", {}).get("user") != probe.identity_sha256(target)
                or set(measured.get("info_sections", {}))
                != set(probe.ALLOWED_INFO_SECTIONS)
            ):
                raise AdmissionError("OBSERVER_METADATA_INCOMPLETE")
            result["observer_metadata_verified"] = True
            result["metadata_counts"] = {
                "dbsize": measured["dbsize"],
                "command_count": measured["command_count"],
            }
            result["policy_sha256"] = active
            result["diagnostic"] = "VERIFIED_PENDING_CLEANUP"
        except AdmissionError as exc:
            result["diagnostic"] = str(exc)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            result["diagnostic"] = "EXERCISE_ERROR_REDACTED"
        finally:
            result["exercise_diagnostic"] = result["diagnostic"]
            if lifecycle.claimed:
                try:
                    lifecycle.__exit__(None, None, None)
                    _remove_owned_role(
                        host,
                        port,
                        target,
                        password_hash,
                        provisioner_credentials,
                        provisioner_identity_sha256,
                    )
                    result["role_removed"] = True
                except (AdmissionError, OSError, ValueError, RuntimeError):
                    result["diagnostic"] = "ROLE_CLEANUP_FAILED"
            if (
                result["observer_metadata_verified"]
                and result["role_removed"]
                and result["diagnostic"] == "VERIFIED_PENDING_CLEANUP"
            ):
                result["status"] = "VERIFIED_TEMPORARY_EXERCISE"
                result["diagnostic"] = "NONE"
            result["evidence_finished_at"] = datetime.now(UTC).isoformat()
    return result


def exercise_temporary_observer(
    *,
    host: str,
    port: int,
    provisioner_credentials: tuple[str, str],
    provisioner_identity_sha256: str,
    admitted_endpoint: tuple[str, int],
    evidence_kind: str,
    journal_path: Path | None = None,
) -> dict[str, Any]:
    """Reserve an exact owned role before mutation; retain recovery metadata.

    Native execution requires an explicit private journal and the main thread.
    The immutable reservation contains no password/hash. SIGTERM follows the
    cleanup path; power loss/SIGKILL/network loss can leave the recorded role.
    Such a run is not verified and requires separately admitted exact-role cleanup.
    """
    if (
        admitted_endpoint != (host, port)
        or host != "127.0.0.1"
        or not 1 <= port <= 65535
    ):
        raise AdmissionError("ENDPOINT_NOT_ADMITTED")
    if evidence_kind not in {"ISOLATED_TEST", "NATIVE_ADMITTED"}:
        raise AdmissionError("EVIDENCE_KIND_REQUIRED")
    if evidence_kind == "ISOLATED_TEST" and port == 6379:
        raise AdmissionError("ISOLATED_TEST_NATIVE_PORT_REJECTED")
    if evidence_kind == "NATIVE_ADMITTED" and journal_path is None:
        raise AdmissionError("NATIVE_JOURNAL_REQUIRED")
    target = "nuzantara_observer_wave8_" + secrets.token_hex(16)
    previous = None
    if journal_path is not None:
        if threading.current_thread() is not threading.main_thread():
            raise AdmissionError("EXERCISE_MAIN_THREAD_REQUIRED")
        if signal.getsignal(signal.SIGTERM) is None:
            raise AdmissionError("EXERCISE_SIGNAL_HANDLER_UNSUPPORTED")
        reservation = {
            "state": "RESERVED_NOT_PROOF_OF_EXECUTION",
            "temporary_role": target,
            "endpoint_sha256": _sha(f"{host}:{port}"),
            "evidence_kind": evidence_kind,
        }
        try:
            fd = os.open(
                journal_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
        except OSError:
            raise AdmissionError("EXERCISE_RESERVATION_REJECTED") from None
        try:
            data = (json.dumps(reservation, sort_keys=True) + "\n").encode()
            with os.fdopen(fd, "wb") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
        except OSError:
            raise AdmissionError("EXERCISE_RESERVATION_FAILED") from None

        def interrupted(_signum, _frame):
            raise AdmissionError("EXERCISE_INTERRUPTED")

        previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        return _exercise_temporary_observer(
            host=host,
            port=port,
            provisioner_credentials=provisioner_credentials,
            provisioner_identity_sha256=provisioner_identity_sha256,
            admitted_endpoint=admitted_endpoint,
            evidence_kind=evidence_kind,
            target=target,
        )
    finally:
        if journal_path is not None:
            signal.signal(signal.SIGTERM, previous)
