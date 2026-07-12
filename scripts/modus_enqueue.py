"""modus_enqueue.py — Unit 1 (Producer adapter) of the modus autonomous loop.

Normalizes any cron's discovered finding into the existing escalation queue
schema (scripts/sentinel_lib/escalations.py) and classifies it green vs
proposal. Idempotent: a job already pending in the queue is not re-enqueued
(relies on the queue's dedup_key, derived from 'job', plus a pre-write scan
of read_all_escalations() so the CLI/library stays honest even without the
SQLite mirror armed).

CLI:
    python scripts/modus_enqueue.py \
        --job regulatory-delta-2026-07-12 \
        --source regulatory-watcher \
        --mandate "Capture the PP-28 delta into research/regulatory/..." \
        --class green \
        --perimeter "research/regulatory/**" \
        [--severity normal]

Library:
    from scripts.modus_enqueue import enqueue_task
    enqueue_task(
        job="regulatory-delta-2026-07-12",
        source="regulatory-watcher",
        mandate="Capture the PP-28 delta into research/regulatory/...",
        klass="green",
        perimeter="research/regulatory/**",
    )

Kill switch: MODUS_AUTOLOOP_ENABLED (checked by downstream consumers of the
queue, e.g. the green-class gate — this producer always writes; gating on
whether the loop is armed happens at consumption time, per spec Unit 2/3).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from sentinel_lib import escalations  # noqa: E402

_logger = logging.getLogger("modus_enqueue")

_VALID_CLASSES = ("green", "proposal")


def enqueue_task(
    job: str,
    source: str,
    mandate: str,
    klass: str,
    perimeter: str,
    severity: str = "normal",
) -> None:
    """Deposit a discovered task into the existing escalation queue.

    'klass' is the Python parameter name (avoids shadowing the 'class'
    keyword); it is written under the JSON key 'class'.

    Raises:
        ValueError: if klass is not exactly "green" or "proposal".
    """
    if klass not in _VALID_CLASSES:
        raise ValueError(
            f"klass must be one of {_VALID_CLASSES!r}, got {klass!r}"
        )

    if _already_pending(job):
        _logger.info("job %r already pending in queue — skipping enqueue", job)
        return

    record = {
        "job": job,
        "source": source,
        "mandate": mandate,
        "class": klass,
        "perimeter": perimeter,
        "severity": severity,
        "status": "pending",
    }
    escalations.write_escalation(record)
    _logger.info("enqueued job=%r class=%r source=%r", job, klass, source)


def _already_pending(job: str) -> bool:
    """True if the queue already has a pending entry for this job."""
    for entry in escalations.read_all_escalations(include_resolved=False):
        if entry.get("job") == job and entry.get("status") == "pending":
            return True
    return False


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deposit a discovered task into the modus escalation queue."
    )
    parser.add_argument("--job", required=True, help="Unique job identifier (dedup key source).")
    parser.add_argument("--source", required=True, help="Name of the producing cron/agent.")
    parser.add_argument("--mandate", required=True, help="Free-text description of the task.")
    parser.add_argument(
        "--class",
        dest="klass",
        required=True,
        choices=list(_VALID_CLASSES),
        help="Task classification: green (auto-runnable) or proposal (needs Zero).",
    )
    parser.add_argument("--perimeter", required=True, help="Glob scope the task is allowed to touch.")
    parser.add_argument("--severity", default="normal", help="Severity label (default: normal).")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _build_arg_parser().parse_args(argv)
    try:
        enqueue_task(
            job=args.job,
            source=args.source,
            mandate=args.mandate,
            klass=args.klass,
            perimeter=args.perimeter,
            severity=args.severity,
        )
    except ValueError as exc:
        _logger.error("enqueue failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
