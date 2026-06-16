"""Run the safe Skill Coach cycle as one OpenClaw-friendly job.

This runner wires the existing propose-only learning loop:

1. aggregate successful Genome trajectories into skill-creation proposals;
2. evaluate those proposals into redacted Skill Coach evidence cards.

It never records active skills and never publishes HGT events. Zero still
decides which evidence card becomes a real Skill Registry entry.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from backend.scripts.experience_to_skill_aggregator import main as aggregate_main
from backend.scripts.skill_coach_evaluate_proposals import main as evaluate_main
from backend.services.skill_coach.service import (
    DEFAULT_DB_PATH,
    SKILL_COACH_EVIDENCE_PATH,
    SKILL_CREATION_PROPOSALS_PATH,
)

logger = logging.getLogger(__name__)


def run_skill_coach_cycle(
    *,
    db_path: str = DEFAULT_DB_PATH,
    proposals_path: str = SKILL_CREATION_PROPOSALS_PATH,
    evidence_path: str = SKILL_COACH_EVIDENCE_PATH,
    min_cluster_size: int = 10,
    window_days: int = 7,
    min_support: int = 3,
    run_aggregator: bool = True,
) -> dict[str, Any]:
    """Run one safe learning cycle and return a structured summary."""
    _validate_positive("min_cluster_size", min_cluster_size)
    _validate_positive("window_days", window_days)
    _validate_positive("min_support", min_support)

    if run_aggregator:
        _ensure_parent(proposals_path)
        aggregate_rc = aggregate_main(
            [
                "--db-path",
                db_path,
                "--out",
                proposals_path,
                "--min-cluster-size",
                str(min_cluster_size),
                "--window-days",
                str(window_days),
            ]
        )
        if aggregate_rc != 0:
            raise RuntimeError(f"experience_to_skill_aggregator failed rc={aggregate_rc}")

    _ensure_parent(evidence_path)
    evaluate_rc = evaluate_main(
        [
            "--db-path",
            db_path,
            "--proposals",
            proposals_path,
            "--out",
            evidence_path,
            "--min-support",
            str(min_support),
        ]
    )
    if evaluate_rc != 0:
        raise RuntimeError(f"skill_coach_evaluate_proposals failed rc={evaluate_rc}")

    evidence_rows = _read_jsonl(evidence_path)
    status_counts = Counter(str(row.get("status", "unknown")) for row in evidence_rows)
    summary = {
        "status": "ok",
        "aggregator_ran": run_aggregator,
        "db_path": db_path,
        "proposals_path": proposals_path,
        "evidence_path": evidence_path,
        "proposals_written": _count_jsonl(proposals_path),
        "evidence_written": len(evidence_rows),
        "evidence_by_status": dict(sorted(status_counts.items())),
        "min_cluster_size": min_cluster_size,
        "window_days": window_days,
        "min_support": min_support,
    }
    logger.info(
        "skill-coach OpenClaw cycle ok: proposals=%d evidence=%d",
        summary["proposals_written"],
        summary["evidence_written"],
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--proposals", default=SKILL_CREATION_PROPOSALS_PATH)
    parser.add_argument("--out", default=SKILL_COACH_EVIDENCE_PATH)
    parser.add_argument("--min-cluster-size", type=int, default=10)
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--min-support", type=int, default=3)
    parser.add_argument(
        "--skip-aggregator",
        action="store_true",
        help="Refresh evidence from an existing proposals file without regenerating it.",
    )
    args = parser.parse_args(argv)

    try:
        summary = run_skill_coach_cycle(
            db_path=args.db_path,
            proposals_path=args.proposals,
            evidence_path=args.out,
            min_cluster_size=args.min_cluster_size,
            window_days=args.window_days,
            min_support=args.min_support,
            run_aggregator=not args.skip_aggregator,
        )
    except Exception as exc:
        logger.exception("skill-coach OpenClaw cycle failed")
        error_summary = {
            "status": "error",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        sys.stdout.write(json.dumps(error_summary, sort_keys=True) + "\n")
        return 1

    sys.stdout.write(json.dumps(summary, sort_keys=True) + "\n")
    return 0


def _validate_positive(name: str, value: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be >= 1")


def _ensure_parent(path: str) -> None:
    Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def _count_jsonl(path: str) -> int:
    return len(_read_jsonl(path))


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with file_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
