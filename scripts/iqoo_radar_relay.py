#!/usr/bin/env python3
"""Relay P0 metadata from the Telegram spool to the iQOO RADAR node.

The source spool may contain client or infrastructure details.  This relay
therefore never serializes ``record["text"]``, ``record["key"]`` or a raw
producer name.  It deterministically reduces each P0 to a small allow-listed
Incident Capsule and sends that capsule through a forced-command SSH key.

First start is intentionally quiet: cursors are placed at EOF so hundreds of
historical alerts are not replayed.  ``--replay-existing`` exists for hermetic
tests and deliberate recovery only.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import logging
import math
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
STATE_VERSION = 1
MAX_LINE_BYTES = 65_536
MAX_RECORDS_PER_RUN = 100
MAX_SSH_OUTPUT_BYTES = 4096
DEFAULT_PORT = 8022
EXIT_SOFTWARE = 70
EXIT_TEMPFAIL = 75
SPOOL_FILES = ("archive-p0.jsonl", "pending.jsonl")

ALLOWED_CATEGORIES = frozenset(
    {
        "availability",
        "billing",
        "communications",
        "compliance",
        "data_integrity",
        "security",
        "storage",
        "system",
    }
)
ALLOWED_SOURCE_CLASSES = frozenset(
    {
        "backup",
        "communications",
        "cron",
        "database",
        "healer",
        "security",
        "watchdog",
        "system",
    }
)

_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "security",
        (
            "security",
            "auth",
            "credential",
            "secret",
            "breach",
            "hijack",
            "revoked",
            "unauthor",
        ),
    ),
    (
        "data_integrity",
        (
            "database",
            "postgres",
            "qdrant",
            "backup",
            "corrupt",
            "migration",
            "data loss",
        ),
    ),
    ("billing", ("billing", "payment", "credit", "budget", "quota")),
    (
        "communications",
        ("whatsapp", "wa-", "telegram", "brevo", "email", "mail", "sms"),
    ),
    ("storage", ("disk", "storage", "inode", "log-size", "volume")),
    (
        "compliance",
        ("compliance", "lkpm", "tax", "pajak", "visa", "deadline"),
    ),
    (
        "availability",
        ("unavailable", "health", "timeout", "stuck", "zombie", "crash", "down"),
    ),
)

_SOURCE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("healer", ("healer", "autofix", "repair")),
    ("backup", ("backup", "snapshot")),
    ("database", ("postgres", "database", "qdrant", "redis", "db-")),
    ("communications", ("whatsapp", "wa-", "telegram", "brevo", "mail")),
    ("security", ("security", "auth", "credential", "guardian")),
    ("watchdog", ("watchdog", "sentinel", "monitor", "doctor", "health")),
    ("cron", ("cron", "scheduled", "launchd")),
)


class RelayError(RuntimeError):
    """Raised when a capsule cannot be delivered safely."""


class RetryableDeliveryError(RelayError):
    """Raised when the mobile receiver is temporarily unavailable or busy."""


@dataclass(frozen=True)
class DeliveryResult:
    """Bounded relay outcome used by the CLI and unit tests."""

    bootstrapped: int = 0
    delivered: int = 0
    ignored: int = 0
    malformed: int = 0
    failed: int = 0
    software_failed: int = 0

    def add(self, **changes: int) -> "DeliveryResult":
        values = {
            "bootstrapped": self.bootstrapped,
            "delivered": self.delivered,
            "ignored": self.ignored,
            "malformed": self.malformed,
            "failed": self.failed,
            "software_failed": self.software_failed,
        }
        for name, delta in changes.items():
            values[name] += delta
        return DeliveryResult(**values)


CapsuleSender = Callable[[dict[str, Any]], None]


def _safe_node(raw: object) -> str:
    value = str(raw or "").strip().lower()
    if value in {"nuzantara", "pro"}:
        return "pro"
    if value in {"mini-pro2", "mini-pro2.local", "mini"}:
        return "mini"
    return "other"


def _classification_material(record: Mapping[str, Any]) -> str:
    """Return local-only text used for coarse deterministic classification."""
    return " ".join(
        str(record.get(field, "")).lower() for field in ("source", "key", "text")
    )


def _classify(
    material: str,
    rules: tuple[tuple[str, tuple[str, ...]], ...],
    default: str,
) -> str:
    for label, needles in rules:
        if any(needle in material for needle in needles):
            return label
    return default


def classify_category(record: Mapping[str, Any]) -> str:
    """Classify locally; no classification input is ever copied to the capsule."""
    return _classify(_classification_material(record), _CATEGORY_RULES, "system")


def classify_source(record: Mapping[str, Any]) -> str:
    """Reduce arbitrary producer identity to a finite, non-PII vocabulary."""
    return _classify(_classification_material(record), _SOURCE_RULES, "system")


def _delivery_state(record: Mapping[str, Any], spool_name: str) -> str:
    if bool(record.get("p0_unsent")):
        return "transport_unsent"
    if bool(record.get("p0_overflow")):
        return "budget_holdback"
    if bool(record.get("sent")) or spool_name == "archive-p0.jsonl":
        return "sent"
    return "queued"


def _timestamp(record: Mapping[str, Any]) -> tuple[float, str]:
    raw = record.get("ts")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise RelayError("record timestamp is not numeric")
    stamp = float(raw)
    if not math.isfinite(stamp) or stamp <= 0:
        raise RelayError("record timestamp is invalid")
    observed = datetime.fromtimestamp(stamp, tz=UTC).isoformat(timespec="seconds")
    return stamp, observed.replace("+00:00", "Z")


def _bounded_repeat_count(record: Mapping[str, Any]) -> int:
    raw = record.get("suppressed", 0)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return 1
    return max(1, min(100_000, int(raw) + 1))


def build_capsule(
    record: Mapping[str, Any], *, spool_name: str, byte_offset: int
) -> dict[str, Any]:
    """Create an allow-listed capsule without free text or raw identifiers."""
    if record.get("tier") != "p0":
        raise RelayError("only P0 records may become Incident Capsules")
    if spool_name not in SPOOL_FILES:
        raise RelayError("unrecognized spool source")
    if byte_offset < 0:
        raise RelayError("negative spool offset")

    stamp, observed_at = _timestamp(record)
    node = _safe_node(record.get("machine"))
    category = classify_category(record)
    source_class = classify_source(record)
    if category not in ALLOWED_CATEGORIES or source_class not in ALLOWED_SOURCE_CLASSES:
        raise RelayError("classifier produced a value outside the capsule vocabulary")

    # The event ID deliberately excludes spool name and byte offset. The
    # Telegram spool may atomically rewrite/re-append a pending record; the
    # source timestamp plus the finite classification must remain stable across
    # that storage move so the phone can reject the replay idempotently.
    # IDs never hash raw text, a dedup key, client name, phone or email.
    event_material = f"{node}|{source_class}|{category}|{stamp:.6f}"
    condition_material = f"{node}|{source_class}|{category}"
    incident_id = hashlib.sha256(event_material.encode("utf-8")).hexdigest()[:32]
    condition_id = hashlib.sha256(condition_material.encode("utf-8")).hexdigest()[:16]
    high_risk = category in {"security", "data_integrity", "billing"}

    return {
        "schema_version": SCHEMA_VERSION,
        "incident_id": incident_id,
        "condition_id": condition_id,
        "observed_at": observed_at,
        "severity": "critical",
        "stage": "detected",
        "source_node": node,
        "source_class": source_class,
        "category": category,
        "delivery_state": _delivery_state(record, spool_name),
        "repeat_count": _bounded_repeat_count(record),
        "details": "kept_on_source",
        "pii_policy": "no_raw_logs_no_free_text",
        "route": {
            "repairer": "bounded_sonnet5_healer",
            "reviewer": "independent_medium",
            "supervisor": "opus5_for_high_risk" if high_risk else "medium_review",
            "owner_gate": "irreversible_only",
        },
    }


def _is_relay_candidate(record: Mapping[str, Any], spool_name: str) -> bool:
    if record.get("tier") != "p0":
        return False
    if spool_name == "archive-p0.jsonl":
        return True
    return bool(record.get("p0_unsent") or record.get("p0_overflow"))


def _read_state(path: Path) -> dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": STATE_VERSION, "files": {}}
    except (OSError, json.JSONDecodeError) as exc:
        raise RelayError(f"cursor state is unreadable: {type(exc).__name__}") from exc
    if state.get("version") != STATE_VERSION or not isinstance(
        state.get("files"), dict
    ):
        raise RelayError("cursor state has an unsupported schema")
    return state


def _write_state(path: Path, state: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n"
    fd: int | None = None
    tmp: Path | None = None
    try:
        fd, raw_tmp = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        tmp = Path(raw_tmp)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        tmp = None
        path.chmod(0o600)
    except OSError as exc:
        raise RelayError(f"cursor state write failed: {type(exc).__name__}") from exc
    finally:
        if fd is not None:
            os.close(fd)
        if tmp is not None:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                logger.warning("cursor temporary cleanup failed reason=OSError")


def _validate_ssh_configuration(
    *,
    target: str,
    port: int,
    identity: Path,
    known_hosts: Path,
) -> None:
    """Fail before spool processing when the source-side SSH setup is invalid."""
    if not target or re.fullmatch(r"[A-Za-z0-9_.@:-]{3,255}", target) is None:
        raise RelayError("SSH target is missing or malformed")
    if target.startswith("-"):
        raise RelayError("SSH target may not begin with an option prefix")
    if not identity.is_file():
        raise RelayError("dedicated SSH identity is missing")
    if not known_hosts.is_file():
        raise RelayError("pinned known_hosts file is missing")
    if not 1 <= port <= 65_535:
        raise RelayError("SSH port is outside the valid range")


def _send_via_ssh(
    capsule: Mapping[str, Any],
    *,
    target: str,
    port: int,
    identity: Path,
    known_hosts: Path,
    timeout_seconds: int,
) -> None:
    _validate_ssh_configuration(
        target=target,
        port=port,
        identity=identity,
        known_hosts=known_hosts,
    )
    payload = json.dumps(capsule, sort_keys=True, separators=(",", ":")) + "\n"
    command = [
        "ssh",
        "-F",
        "/dev/null",
        "-T",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        f"ConnectTimeout={min(max(timeout_seconds, 1), 30)}",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-o",
        "GlobalKnownHostsFile=/dev/null",
        "-i",
        str(identity),
        "-p",
        str(port),
        "--",
        target,
    ]
    try:
        # File-backed capture places a hard memory ceiling on a hostile or broken
        # receiver.  Only a bounded prefix is ever read back into this process.
        with (
            tempfile.TemporaryFile() as stdout_file,
            tempfile.TemporaryFile() as stderr_file,
        ):
            result = subprocess.run(
                command,
                input=payload,
                text=True,
                stdout=stdout_file,
                stderr=stderr_file,
                timeout=timeout_seconds,
                check=False,
            )
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout_bytes = stdout_file.read(MAX_SSH_OUTPUT_BYTES + 1)
            stderr_bytes = stderr_file.read(MAX_SSH_OUTPUT_BYTES + 1)
    except subprocess.TimeoutExpired as exc:
        raise RetryableDeliveryError("SSH transport timed out") from exc
    except OSError as exc:
        raise RelayError(f"SSH launch failed: {type(exc).__name__}") from exc

    if (
        len(stdout_bytes) > MAX_SSH_OUTPUT_BYTES
        or len(stderr_bytes) > MAX_SSH_OUTPUT_BYTES
    ):
        raise RelayError("receiver output exceeded the bounded capture limit")

    expected = {
        f"RADAR_OK {capsule['incident_id']}",
        f"RADAR_DUPLICATE {capsule['incident_id']}",
    }
    receipt = stdout_bytes.decode("utf-8", errors="replace").strip()
    if result.returncode == 0 and receipt in expected:
        return

    stderr_lower = stderr_bytes.lower()
    fatal_ssh_markers = (
        b"host key verification failed",
        b"remote host identification has changed",
        b"bad configuration option",
        b"no such identity",
        b"identity file",
        b"permission denied (publickey",
        b"too many authentication failures",
    )
    if result.returncode == 255 and any(
        marker in stderr_lower for marker in fatal_ssh_markers
    ):
        raise RelayError("SSH security/configuration failure (ssh_rc=255)")
    if result.returncode in {75, 255}:
        raise RetryableDeliveryError(
            f"receiver temporarily unavailable (ssh_rc={result.returncode})"
        )
    raise RelayError(f"receiver rejected capsule (ssh_rc={result.returncode})")


def _drain_oversized_line(handle: BinaryIO, raw_line: bytes) -> int:
    """Consume the rest of an oversized physical line using bounded reads."""
    chunk = raw_line
    while chunk and not chunk.endswith(b"\n"):
        chunk = handle.readline(MAX_LINE_BYTES + 1)
    return int(handle.tell())


def relay_once(
    *,
    spool_dir: Path,
    state_dir: Path,
    sender: CapsuleSender,
    replay_existing: bool = False,
    max_records: int = MAX_RECORDS_PER_RUN,
) -> DeliveryResult:
    """Relay at most ``max_records`` records with retry-safe cursor semantics."""
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_dir.chmod(0o700)
    state_path = state_dir / "cursor.json"
    lock_path = state_dir / ".relay.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    result = DeliveryResult()

    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(lock_fd)
        raise RelayError("another relay instance is active") from exc

    try:
        state = _read_state(state_path)
        files_state = state["files"]
        remaining = max(1, min(max_records, 1_000))

        for spool_name in SPOOL_FILES:
            if remaining <= 0:
                break
            source = spool_dir / spool_name
            try:
                stat = source.stat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise RelayError(
                    f"cannot stat {spool_name}: {type(exc).__name__}"
                ) from exc
            if not source.is_file():
                continue

            cursor = files_state.get(spool_name)
            identity = {"dev": stat.st_dev, "ino": stat.st_ino}
            if cursor is None:
                initial_offset = 0 if replay_existing else stat.st_size
                files_state[spool_name] = {**identity, "offset": initial_offset}
                result = result.add(bootstrapped=1)
                if not replay_existing:
                    continue
                cursor = files_state[spool_name]

            offset = int(cursor.get("offset", 0))
            rotated = (
                cursor.get("dev") != stat.st_dev or cursor.get("ino") != stat.st_ino
            )
            if rotated or stat.st_size < offset:
                offset = 0
            files_state[spool_name] = {**identity, "offset": offset}

            try:
                handle = source.open("rb")
            except OSError as exc:
                raise RelayError(
                    f"cannot open {spool_name}: {type(exc).__name__}"
                ) from exc
            with handle:
                handle.seek(offset)
                while remaining > 0:
                    byte_offset = handle.tell()
                    raw_line = handle.readline(MAX_LINE_BYTES + 1)
                    if not raw_line:
                        break
                    next_offset = handle.tell()
                    remaining -= 1

                    if len(raw_line) > MAX_LINE_BYTES:
                        next_offset = _drain_oversized_line(handle, raw_line)
                        result = result.add(malformed=1)
                        files_state[spool_name]["offset"] = next_offset
                        continue
                    if not raw_line.endswith(b"\n"):
                        # The producer may still be appending this physical
                        # line. Keep the cursor at its start and retry on the
                        # next run instead of permanently losing a P0.
                        break
                    try:
                        record = json.loads(raw_line.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        result = result.add(malformed=1)
                        files_state[spool_name]["offset"] = next_offset
                        continue
                    if not isinstance(record, dict) or not _is_relay_candidate(
                        record, spool_name
                    ):
                        result = result.add(ignored=1)
                        files_state[spool_name]["offset"] = next_offset
                        continue
                    try:
                        capsule = build_capsule(
                            record,
                            spool_name=spool_name,
                            byte_offset=byte_offset,
                        )
                        sender(capsule)
                    except RetryableDeliveryError as exc:
                        logger.error(
                            "capsule delivery failed file=%s offset=%d reason=%s",
                            spool_name,
                            byte_offset,
                            str(exc),
                        )
                        result = result.add(failed=1)
                        # Do not advance: the same deterministic incident ID will
                        # be retried, and the phone receiver is idempotent.
                        break
                    except RelayError as exc:
                        logger.error(
                            "capsule delivery blocked file=%s offset=%d reason=%s",
                            spool_name,
                            byte_offset,
                            str(exc),
                        )
                        result = result.add(software_failed=1)
                        break
                    except Exception as exc:
                        # Unknown exception messages may contain producer data.
                        # Log only their type while still preserving the cursor.
                        logger.error(
                            "capsule delivery crashed file=%s offset=%d reason=%s",
                            spool_name,
                            byte_offset,
                            type(exc).__name__,
                        )
                        result = result.add(software_failed=1)
                        break
                    files_state[spool_name]["offset"] = next_offset
                    result = result.add(delivered=1)

        _write_state(state_path, state)
        return result
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spool-dir",
        type=Path,
        default=Path.home() / ".organism" / "tg_spool",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path.home() / ".organism" / "iqoo-radar-relay",
    )
    parser.add_argument("--target", default=os.environ.get("IQOO_RADAR_TARGET", ""))
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("IQOO_RADAR_PORT", DEFAULT_PORT))
    )
    parser.add_argument(
        "--identity",
        type=Path,
        default=Path(
            os.environ.get(
                "IQOO_RADAR_IDENTITY",
                str(Path.home() / ".ssh" / "nuzantara_iqoo_radar"),
            )
        ),
    )
    parser.add_argument(
        "--known-hosts",
        type=Path,
        default=Path(
            os.environ.get(
                "IQOO_RADAR_KNOWN_HOSTS",
                str(Path.home() / ".ssh" / "known_hosts_iqoo_radar"),
            )
        ),
    )
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--max-records", type=int, default=MAX_RECORDS_PER_RUN)
    parser.add_argument("--replay-existing", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=os.environ.get("IQOO_RADAR_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s iqoo-radar-relay: %(message)s",
    )

    identity = args.identity.expanduser()
    known_hosts = args.known_hosts.expanduser()
    try:
        _validate_ssh_configuration(
            target=args.target,
            port=args.port,
            identity=identity,
            known_hosts=known_hosts,
        )
    except RelayError as exc:
        logger.error("relay configuration invalid reason=%s", str(exc))
        return EXIT_SOFTWARE

    def sender(capsule: dict[str, Any]) -> None:
        _send_via_ssh(
            capsule,
            target=args.target,
            port=args.port,
            identity=identity,
            known_hosts=known_hosts,
            timeout_seconds=args.timeout,
        )

    try:
        outcome = relay_once(
            spool_dir=args.spool_dir.expanduser(),
            state_dir=args.state_dir.expanduser(),
            sender=sender,
            replay_existing=args.replay_existing,
            max_records=args.max_records,
        )
    except RelayError as exc:
        logger.error("relay stopped reason=%s", type(exc).__name__)
        return EXIT_SOFTWARE
    logger.info(
        "run complete bootstrapped=%d delivered=%d ignored=%d malformed=%d failed=%d software_failed=%d",
        outcome.bootstrapped,
        outcome.delivered,
        outcome.ignored,
        outcome.malformed,
        outcome.failed,
        outcome.software_failed,
    )
    # A sleeping/offline phone is normal for a mobile pager.  Distinguish that
    # retryable transport state from a broken local relay so the source-node
    # healer does not enter a pointless kickstart loop.
    if outcome.software_failed:
        return EXIT_SOFTWARE
    return EXIT_TEMPFAIL if outcome.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
