"""Prepared B02 one-shot wrapper. Dux-pinned receipts are the external authority.

Source self-checks run after imports and cannot establish pre-import integrity.
The Dux must first enforce the exact seven-file stage contract with isolated Python.
No receipt is issued here. Native CLI pins must come from the existing admitted
Dux invocation, never from an untrusted packet. The template grants nothing.
"""

from datetime import UTC, datetime
import hashlib
import io
import json
import os
from pathlib import Path
import pwd
import socket
import stat
import sys

from dotenv import dotenv_values

import redis_observer_admission as admission

DEADLINE = datetime.fromisoformat("2026-10-16T08:23:00.050644+00:00")
SCOPE = "ONE_B02_TEMPORARY_OBSERVER_PER_HOST"
ROUTE = "CANONICAL_DOTENV_DEFAULT_BOOTSTRAP_ONLY"
SOURCES = (
    "redis_observer_native_once.py",
    "test_redis_observer_native_once.py",
    "redis_observer_admission.py",
    "test_redis_observer_admission.py",
    "redis_observer_probe.py",
    "REDIS-TEMPORARY-OBSERVER-PREPARED.md",
)
HOSTS = {
    "Pro": "f32816d8433d1b52853fb5abbe919098f8566e426ce147f8b197f3d63892e79e",
    "Mini": "11624124c032b79f9df5ba409eba1423af1804d434708fb1da6ad3c3d8f12bbe",
}


def require(condition, code):
    if not condition:
        raise admission.AdmissionError(code)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def private_bytes(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        meta = os.fstat(fd)
        require(
            stat.S_ISREG(meta.st_mode)
            and stat.S_IMODE(meta.st_mode) == 0o600
            and meta.st_uid == os.getuid()
            and meta.st_nlink == 1
            and meta.st_size <= 1048576,
            "PRIVATE_FILE_REJECTED",
        )
        return os.read(fd, 1048577)
    finally:
        os.close(fd)


def credentials(path):
    # Parse in memory with interpolation and environment fallback disabled.
    raw = private_bytes(path).decode("utf-8")
    values = dotenv_values(stream=io.StringIO(raw), interpolate=False)
    password = values.get("REDIS_PASSWORD")
    require(isinstance(password, str) and bool(password), "PASSWORD_MISSING")
    require(
        not any(
            values.get(k)
            for k in (
                "REDIS_USERNAME",
                "REDIS_USER",
                "REDIS_PROVISIONER_USERNAME",
                "REDIS_PROVISIONER_USER",
                "REDIS_PROVISIONER_PASSWORD",
            )
        ),
        "BOOTSTRAP_IDENTITY_CONFLICT",
    )
    return "default", password


def validate(packet_path, owner_path, gate_path, owner_pin, gate_pin, isolated):
    raw = packet_path.read_bytes()
    packet = json.loads(raw)
    require(datetime.now(UTC) < DEADLINE, "CAMPAIGN_EXPIRED")
    require(packet.get("permission") == "GRANTED", "OWNER_PERMISSION_UNGRANTED")
    require(
        set(packet)
        == {
            "permission",
            "campaign",
            "scope",
            "credential_route",
            "host",
            "host_sha256",
            "endpoint",
            "deadline",
            "source_pins",
            "evidence_kind",
        },
        "PACKET_FIELDS_REJECTED",
    )
    require(
        packet["campaign"] == "universal-db-wave8-20261015"
        and packet["scope"] == SCOPE
        and packet["credential_route"] == ROUTE
        and packet["deadline"] == DEADLINE.isoformat(),
        "SCOPE_REJECTED",
    )
    actual_host = sha(socket.gethostname().encode())
    require(packet["host_sha256"] == actual_host, "HOST_REJECTED")
    host, port = packet["endpoint"]
    require(host == "127.0.0.1" and type(port) is int, "ENDPOINT_REJECTED")
    if isolated:
        require(
            1024 <= port <= 65535
            and port != 6379
            and packet["evidence_kind"] == "ISOLATED_TEST",
            "TEST_NATIVE_REJECTED",
        )
    else:
        require(
            port == 6379
            and packet["evidence_kind"] == "NATIVE_ADMITTED"
            and HOSTS.get(packet["host"]) == actual_host,
            "NATIVE_OVERRIDE_REJECTED",
        )
    owner_raw, gate_raw = private_bytes(owner_path), private_bytes(gate_path)
    require(
        sha(owner_raw) == owner_pin and sha(gate_raw) == gate_pin,
        "EXTERNAL_RECEIPT_PIN_MISMATCH",
    )
    owner, gate = json.loads(owner_raw), json.loads(gate_raw)
    require(
        owner
        == {
            "authorized": True,
            "scope": SCOPE,
            "campaign": packet["campaign"],
            "credential_route": ROUTE,
            "run_packet_sha256": sha(raw),
        },
        "OWNER_SCOPE_REJECTED",
    )
    require(
        gate.get("report_status") == "SAFETY: PASS"
        and gate.get("run_packet_sha256") == sha(raw)
        and gate.get("owner_receipt_sha256") == owner_pin
        and gate.get("source_pins") == packet["source_pins"]
        and gate.get("template_sha256")
        == sha(Path(__file__).with_name("REDIS-NATIVE-RUN-TEMPLATE.json").read_bytes()),
        "SOURCE_RUN_GATE_REJECTED",
    )
    pins = {name: sha(Path(__file__).with_name(name).read_bytes()) for name in SOURCES}
    require(pins == packet["source_pins"], "SOURCE_CHANGED")
    return packet


def run(packet_path, owner_path, gate_path, owner_pin, gate_pin, *, isolated_root=None):
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    require(os.environ.get("HOME") in (None, str(home)), "HOME_OVERRIDE_REJECTED")
    isolated = isolated_root is not None
    packet = validate(packet_path, owner_path, gate_path, owner_pin, gate_pin, isolated)
    root = home / ".udb-b02-native-once"
    secret = home / ".nuzantara-secrets.env"
    if isolated:
        import tempfile

        root = Path(isolated_root)
        require(
            root.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
            and root.resolve() != secret.parent,
            "TEST_PATH_REJECTED",
        )
        secret = root / "synthetic.env"
    else:
        template = json.loads(
            Path(__file__).with_name("REDIS-NATIVE-RUN-TEMPLATE.json").read_bytes()
        )
        require(
            root == Path(template["single_use"]["private_root"])
            and secret == Path(template["credential_delivery"]["path"])
            and template["single_use"]["endpoint_lease"] == "endpoint.lease"
            and template["single_use"]["recovery_journal"] == "recovery.json",
            "NATIVE_ROUTE_REJECTED",
        )
    root.mkdir(mode=0o700, exist_ok=True)
    meta = root.lstat()
    require(
        stat.S_ISDIR(meta.st_mode)
        and stat.S_IMODE(meta.st_mode) == 0o700
        and meta.st_uid == os.getuid(),
        "PRIVATE_DIRECTORY_REJECTED",
    )
    journal = root / "recovery.json"
    require(not journal.exists() and not journal.is_symlink(), "JOURNAL_EXISTS")
    fd = os.open(
        root / "endpoint.lease",
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    with os.fdopen(fd, "wb") as lease:
        lease.write(
            json.dumps({"run_packet_sha256": sha(packet_path.read_bytes())}).encode()
        )
        lease.flush()
        os.fsync(lease.fileno())
    require(datetime.now(UTC) < DEADLINE, "CAMPAIGN_EXPIRED")
    provisioner = credentials(secret)
    require(datetime.now(UTC) < DEADLINE, "CAMPAIGN_EXPIRED")
    return admission.exercise_temporary_observer(
        host=packet["endpoint"][0],
        port=packet["endpoint"][1],
        provisioner_credentials=provisioner,
        provisioner_identity_sha256=sha(b"default"),
        admitted_endpoint=tuple(packet["endpoint"]),
        evidence_kind=packet["evidence_kind"],
        journal_path=journal,
    )


if __name__ == "__main__":
    try:
        require(len(sys.argv) == 6, "NATIVE_ARGUMENTS_REJECTED")
        result = run(*(Path(p) for p in sys.argv[1:4]), *sys.argv[4:6])
        print(json.dumps(result, sort_keys=True))
        raise SystemExit(0 if result["status"] == "VERIFIED_TEMPORARY_EXERCISE" else 1)
    except Exception:
        print(
            json.dumps(
                {"status": "BLOCKED", "diagnostic": "PRECONDITION_OR_RUN_FAILED"}
            )
        )
        raise SystemExit(1) from None
