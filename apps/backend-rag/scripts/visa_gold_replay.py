#!/usr/bin/env python3
"""Replay the 20 canonical Visa Oracle gold personas through the REAL
``evaluator.evaluate()`` and emit the G-b evidence artifact as JSON.

Acceptance flow for an INDEPENDENT grader (reviewer ≠ engine author):

    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/visa_gold_replay.py --out /tmp/gold-replay.json
    # exit code 0 iff zero divergences; the artifact's own "overall_pass"
    # and "divergences" fields say the same thing machine-readably.

Reproducibility: every field is a pure function of the checkout except
``generated_at``. For a byte-identical artifact across runs/machines pass
``--fixed-now`` (any tz-aware ISO-8601 instant); without it, diff two runs
with ``jq -S 'del(.generated_at)'`` (identical output = same engine, same
pack, same outcomes).

Dev-tool note: the canonical persona table lives in the test suite
(``backend.tests.services.visa_engine.test_evaluator_gold.PERSONAS``) and is
imported from there — single source of truth, never duplicated — so this
script must run inside the backend venv (that import transitively pulls in
pytest, which is always present there).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from backend.tests.services.visa_engine.gold_replay import build_report


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay the 20 canonical gold personas through the real visa_engine "
            "evaluator and write the G-b evidence artifact (JSON). Exit code 0 "
            "iff every persona replays with zero divergences."
        )
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="path to write the report JSON to (default: stdout)",
    )
    parser.add_argument(
        "--fixed-now",
        type=_parse_datetime,
        default=None,
        metavar="ISO8601",
        help=(
            "pin the artifact's generated_at to this tz-aware instant, making "
            "two runs on the same checkout byte-identical (for grader diffs)"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    generated_at = args.fixed_now if args.fixed_now is not None else datetime.now().astimezone()
    report = build_report(generated_at=generated_at)
    artifact = json.dumps(report, indent=2, sort_keys=True) + "\n"

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(artifact, encoding="utf-8")
        sys.stdout.write(f"wrote {args.out} -- overall_pass={report['overall_pass']}\n")
    else:
        sys.stdout.write(artifact)

    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
