#!/usr/bin/env python3
"""CLI doctor for the local-first voice concierge audio stack."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from backend.app.services.local_audio.readiness import build_local_audio_readiness_report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check local voice concierge audio readiness.",
    )
    parser.add_argument(
        "--mode",
        choices=("static", "deep"),
        default="static",
        help="static avoids model loading; deep runs runtime provider status checks on Pro/Mini.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON readiness report.",
    )
    args = parser.parse_args(argv)

    if args.json:
        with contextlib.redirect_stdout(sys.stderr):
            report = build_local_audio_readiness_report(mode=args.mode)
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        report = build_local_audio_readiness_report(mode=args.mode)
        print(report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
