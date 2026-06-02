#!/usr/bin/env python3
"""S3 — Canonical escalations JSONL rotation (defense-in-depth backstop).

The canonical per-machine ledger ``shared/escalations_<machine>.jsonl`` is the
federation bus (single-writer, append-only, O_APPEND). The out-of-tree SQLite
mirror (``~/.agent/decisions/escalations.sqlite``) already has prune/archive
(see ``migrate_escalations_to_sqlite.py``) — BUT nothing ever rotates the
canonical JSONL itself. A W61-class retry storm (see cicatrix W61) can refill it
to >1 MB / thousands of lines, as it did with the 4519-entry graveyard hand-
truncated by PR #972 (2026-05-31).

This script is the missing backstop: when the canonical JSONL exceeds a line or
byte threshold, it

  1. **gzip-archives** the current content to
     ``~/.agent/decisions/escalations_archive_<machine>_<date>.jsonl.gz``
     (same naming convention as the SQLite ``archive`` subcommand), then
  2. **truncates** the canonical file to 0 bytes.

Safety (empirically established in the S3 forensic audit, see
``research/operations/S3-escalation-debt-FROZEN.json``):

- **No data loss**: every line written via ``sentinel_lib.escalations.write_escalation``
  is dual-written to the SQLite mirror, and this script additionally writes the
  gzip archive *before* truncating. Truncation only happens after a successful
  ``gz.close()`` + ``fsync``.
- **No torn line**: the sole writer uses ``O_APPEND``; on POSIX (incl. APFS) each
  ``write(2)`` < ``PIPE_BUF`` (4096 B; our lines are ~200 B) is atomic and
  re-seeks EOF. A concurrent truncate therefore cannot corrupt a line — at worst
  one in-flight append lands at the new EOF (offset 0) intact, or is lost in a
  sub-millisecond window (and still survives in the SQLite mirror). All readers
  (``read_all_escalations``, metabolic ``_count_escalations``, SQLite ``import``)
  skip blank/malformed lines and treat the file as a transient window, not a
  durable ledger.
- **Git coordination**: the canonical file is git-tracked. To avoid a working-
  tree-only truncate being resurrected from origin by a future fast-forward
  pull, ``--commit`` stages + commits the emptied file. Default is NO commit
  (operator/cron decides) to avoid sibling-checkout collisions (cicatrix
  W50/W51/W59 family) — when run as a daemon, prefer ``--no-commit`` and let the
  normal commit flow pick up the change, OR run only on the canonical node.

This script NEVER deletes the archive. It is idempotent and a no-op below
threshold.

Usage:
    python scripts/escalations_rotate.py --check                 # report only
    python scripts/escalations_rotate.py                         # rotate if over threshold
    python scripts/escalations_rotate.py --max-lines 5000        # custom threshold
    python scripts/escalations_rotate.py --file /tmp/copy.jsonl  # operate on a copy (testing)
    python scripts/escalations_rotate.py --force                 # rotate regardless of size
"""
from __future__ import annotations

import argparse
import gzip
import logging
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("escalations_rotate")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SHARED_DIR = _PROJECT_ROOT / "shared"
DEFAULT_ARCHIVE_DIR = Path.home() / ".agent" / "decisions"

_HOSTNAME_TO_MACHINE = {
    "Nuzantara": "pro",
    "Mini-Pro2": "pro",  # Mini writes to the pro file per _HOSTNAME_TO_MACHINE default
    "Nuzantara-9": "air",
    "Nuzantara-9.local": "air",
}

# Rotation thresholds. Either trips rotation.
DEFAULT_MAX_LINES = 5000
DEFAULT_MAX_BYTES = 1_048_576  # 1 MiB


def _current_machine() -> str:
    return _HOSTNAME_TO_MACHINE.get(socket.gethostname(), "pro")


def _canonical_path(machine: str | None) -> Path:
    machine = machine or _current_machine()
    return _SHARED_DIR / f"escalations_{machine}.jsonl"


def _count_lines_and_bytes(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    size = path.stat().st_size
    lines = 0
    with path.open("rb") as f:
        for _ in f:
            lines += 1
    return lines, size


def rotate(
    path: Path,
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
    max_lines: int = DEFAULT_MAX_LINES,
    max_bytes: int = DEFAULT_MAX_BYTES,
    force: bool = False,
    do_commit: bool = False,
) -> dict:
    """Rotate ``path`` if over threshold. Returns a result dict (always)."""
    result: dict = {
        "file": str(path),
        "rotated": False,
        "lines": 0,
        "bytes": 0,
        "archive": None,
        "committed": False,
        "reason": "",
    }
    lines, size = _count_lines_and_bytes(path)
    result["lines"] = lines
    result["bytes"] = size

    if not path.exists():
        result["reason"] = "file missing — nothing to rotate"
        return result
    if lines == 0:
        result["reason"] = "file empty — nothing to rotate"
        return result

    over = force or lines >= max_lines or size >= max_bytes
    if not over:
        result["reason"] = (
            f"under threshold (lines={lines}<{max_lines}, bytes={size}<{max_bytes})"
        )
        return result

    archive_dir.mkdir(parents=True, exist_ok=True)
    machine = path.stem.replace("escalations_", "") or "unknown"
    date_tag = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    out_path = archive_dir / f"escalations_archive_{machine}_{date_tag}.jsonl.gz"
    suffix = 1
    while out_path.exists():
        out_path = archive_dir / (
            f"escalations_archive_{machine}_{date_tag}_{suffix}.jsonl.gz"
        )
        suffix += 1

    # 1. Archive (durable) BEFORE truncating. Read the whole file, gzip, fsync.
    with path.open("r", encoding="utf-8") as src, gzip.open(
        out_path, "wt", encoding="utf-8"
    ) as gz:
        for line in src:
            gz.write(line if line.endswith("\n") else line + "\n")
    # Ensure the archive bytes are on disk before we destroy the source.
    with open(out_path, "rb") as fh:
        os.fsync(fh.fileno())

    # 2. Truncate the canonical file to 0 bytes. O_APPEND writers re-seek EOF, so
    #    this is race-safe (at worst one in-flight append lands intact at offset 0).
    fd = os.open(str(path), os.O_WRONLY | os.O_TRUNC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

    result["rotated"] = True
    result["archive"] = str(out_path)
    result["reason"] = f"rotated {lines} lines / {size} bytes → {out_path.name}"
    logger.info(result["reason"])

    # 3. Optional git commit so origin reflects the empty file (prevents FF-pull
    #    resurrection). Best-effort; never raises.
    if do_commit:
        result["committed"] = _git_commit_empty(path, lines)

    return result


def _git_commit_empty(path: Path, archived_lines: int) -> bool:
    """Stage + commit the emptied canonical file. Best-effort, never raises."""
    repo = path.resolve().parent.parent  # shared/ -> project root
    try:
        subprocess.run(
            ["git", "-C", str(repo), "add", str(path.relative_to(repo))],
            check=True, capture_output=True, timeout=30,
        )
        subprocess.run(
            [
                "git", "-C", str(repo), "commit", "-m",
                f"chore(ops): rotate {path.name} ({archived_lines} lines archived)",
            ],
            check=True, capture_output=True, timeout=30,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("git commit of rotated file failed (non-fatal): %s", exc)
        return False


def _main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument(
        "--file", type=Path, default=None,
        help="JSONL file to rotate (default: shared/escalations_<machine>.jsonl)",
    )
    p.add_argument("--machine", default=None, help="pro|air (default: inferred)")
    p.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR)
    p.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    p.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    p.add_argument("--force", action="store_true", help="rotate regardless of size")
    p.add_argument("--commit", dest="commit", action="store_true",
                   help="git add + commit the emptied file")
    p.add_argument("--check", action="store_true",
                   help="report size only, never rotate")
    args = p.parse_args(argv)

    path = args.file or _canonical_path(args.machine)

    if args.check:
        lines, size = _count_lines_and_bytes(path)
        over = lines >= args.max_lines or size >= args.max_bytes
        print(
            f"{path}: lines={lines} bytes={size} "
            f"over_threshold={'YES' if over else 'no'} "
            f"(max_lines={args.max_lines}, max_bytes={args.max_bytes})"
        )
        return 0

    result = rotate(
        path=path,
        archive_dir=args.archive_dir,
        max_lines=args.max_lines,
        max_bytes=args.max_bytes,
        force=args.force,
        do_commit=args.commit,
    )
    print(
        f"rotated={result['rotated']} lines={result['lines']} "
        f"bytes={result['bytes']} archive={result['archive']} "
        f"committed={result['committed']} — {result['reason']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(_main())
