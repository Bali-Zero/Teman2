"""D2.3: Per-machine escalation JSONL writer/reader.

Architecture:
  shared/escalations_pro.jsonl  — written exclusively by Pro (nuzantara@Nuzantara)
  shared/escalations_air.jsonl  — written exclusively by Air (antonellosiano@Nuzantara-9)

Each file is append-only. O_APPEND provides local atomicity (writes < PIPE_BUF = 4096B).
Merge conflicts are structurally impossible because each file has a single writer.

Readers: read both files, parse each line as JSON, merge in-memory.

P1-8: in addition to the canonical JSONL (federation bus), every write is
mirrored into a per-machine local SQLite index at
``~/.agent/decisions/escalations.sqlite`` for indexed active-query and
bounded-retention pruning. The SQLite mirror lives OUTSIDE the git tree
(per ADR-3 v3.3 — no shared SQLite, no split-brain). Toggle off with
``ESCALATIONS_USE_SQLITE=false``.
"""
import json
import logging
import os
import socket
import time
from pathlib import Path
from typing import Iterator

_logger = logging.getLogger("sentinel_lib.escalations")

_NUZANTARA_ROOT = Path(__file__).parent.parent.parent  # scripts/sentinel_lib → project root
_SHARED_DIR = _NUZANTARA_ROOT / "shared"

_MACHINE_FILES = {
    "pro": _SHARED_DIR / "escalations_pro.jsonl",
    "air": _SHARED_DIR / "escalations_air.jsonl",
}

_HOSTNAME_TO_MACHINE = {
    "Nuzantara": "pro",
    "Nuzantara-9": "air",
    "Nuzantara-9.local": "air",
}


def _current_machine() -> str:
    hostname = socket.gethostname()
    return _HOSTNAME_TO_MACHINE.get(hostname, "pro")  # default: pro (conservative)


def write_escalation(entry: dict) -> None:
    """Append one escalation entry to the current machine's JSONL file.

    Adds machine/ts/_writer fields automatically.
    """
    machine = _current_machine()
    record = {
        **entry,
        "machine": machine,
        "ts": entry.get("ts", time.time()),
        "status": entry.get("status", "pending"),
        "_writer": machine,
    }
    path = _MACHINE_FILES[machine]
    path.parent.mkdir(parents=True, exist_ok=True)

    # O_APPEND + encode to bytes: atomic for writes < PIPE_BUF (~4096B on macOS)
    line = (json.dumps(record) + "\n").encode()
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)

    # P1-8: dual-write to local SQLite index (best-effort; never blocks JSONL).
    if os.environ.get("ESCALATIONS_USE_SQLITE", "true").lower() not in (
        "0", "false", "no", "off",
    ):
        try:
            _mirror_to_sqlite(record)
        except Exception as exc:  # noqa: BLE001 — mirror failures must NEVER break JSONL
            _logger.warning("SQLite mirror failed (record kept in JSONL): %s", exc)


def _mirror_to_sqlite(record: dict) -> None:
    """Insert one record into the SQLite mirror via the migration module.

    Imported lazily so test environments without the migration module on
    sys.path still get the JSONL behavior.
    """
    import sys as _sys

    scripts_dir = str(Path(__file__).resolve().parent.parent)
    if scripts_dir not in _sys.path:
        _sys.path.insert(0, scripts_dir)
    try:
        import migrate_escalations_to_sqlite as _mig
    except ImportError:
        return  # mirror module not available — skip silently
    _mig.write_escalation_to_sqlite(record)


def read_all_escalations(include_resolved: bool = False) -> list[dict]:
    """Read both machine files, merge in-memory, sort by ts.

    Returns a list of escalation dicts, newest first.
    """
    entries: list[dict] = []
    for _, path in _MACHINE_FILES.items():
        if not path.exists():
            continue
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                        if not include_resolved and e.get("status") == "resolved":
                            continue
                        entries.append(e)
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass

    return sorted(entries, key=lambda e: e.get("ts", 0), reverse=True)


def mark_resolved(job_id: str) -> int:
    """Append a resolution record to the current machine's file.

    Returns the number of matching pending entries that were found (for logging).
    The resolved marker is appended; the original entry is not mutated (immutable log).
    """
    pending = [e for e in read_all_escalations() if e.get("job") == job_id]
    if not pending:
        return 0
    write_escalation({"job": job_id, "status": "resolved", "resolved_at": time.time()})
    return len(pending)
