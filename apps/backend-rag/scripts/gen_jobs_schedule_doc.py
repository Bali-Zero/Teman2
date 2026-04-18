#!/usr/bin/env python3
"""Regenerate docs/jobs-schedule.md from the jobs registry.

Usage:
    python scripts/gen_jobs_schedule_doc.py           # write the file
    python scripts/gen_jobs_schedule_doc.py --check   # exit 1 if file is stale

Invoked in CI to prevent the doc from drifting from the registry.
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Import the handlers package so register_job runs.
from backend.jobs import handlers  # noqa: E402, F401
from backend.jobs.registry import get_registry  # noqa: E402

DOC_PATH = ROOT / "docs" / "jobs-schedule.md"

HEADER = """# Backend Jobs Schedule

Generated from `backend/jobs/registry.py`. Do not edit by hand — run
`python scripts/gen_jobs_schedule_doc.py` to regenerate.

| Name | Cron | TZ | Timeout (s) | Max Attempts | Skip Middleware |
|------|------|----|-------------|--------------|-----------------|
"""


def render() -> str:
    rows = []
    for decl in sorted(get_registry().all(), key=lambda d: d.name):
        skip = ",".join(decl.skip_middleware) or "—"
        rows.append(
            f"| `{decl.name}` | `{decl.cron}` | {decl.timezone} | "
            f"{decl.timeout_seconds} | {decl.retry_policy.max_attempts} | {skip} |"
        )
    return HEADER + "\n".join(rows) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    generated = render()

    if args.check:
        current = DOC_PATH.read_text() if DOC_PATH.exists() else ""
        if current.strip() != generated.strip():
            diff = difflib.unified_diff(
                current.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile="on-disk",
                tofile="from-registry",
            )
            sys.stderr.write("".join(diff))
            sys.stderr.write("\n\ndocs/jobs-schedule.md is stale. Regenerate with:\n")
            sys.stderr.write("  python scripts/gen_jobs_schedule_doc.py\n")
            return 1
        print("docs/jobs-schedule.md is up to date.")
        return 0

    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(generated)
    print(f"wrote {DOC_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
