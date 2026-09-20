#!/usr/bin/env python3
"""
Check .secrets.baseline for unaudited findings.

Reproduces the intent of `detect-secrets audit --fail-on-unaudited`
(which does not exist as a CLI flag in detect-secrets 1.5.0). Called
from .github/workflows/security.yml as the post-scan gate.

Exit 0 if all findings have an `is_secret` decision (true or false).
Exit 1 if any finding is unaudited — prints the top 20 and the total.

Companion: scripts/detect_secrets_auto_triage.py pre-marks known false
positives by path pattern; run it whenever the scan surfaces a new
residue that looks like a false positive from a known location.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASELINE = Path(".secrets.baseline")


def main() -> int:
    # `--baseline PATH` reads a COPY instead of the tracked file, so a caller
    # can ask what a scan WOULD say without touching the repo's own baseline.
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--baseline" or (i > 0 and argv[i - 1] == "--baseline"):
            continue
        print(f"ERROR: unexpected argument {a!r} (known: --baseline PATH)", file=sys.stderr)
        return 2
    if "--baseline" in argv:
        i = argv.index("--baseline")
        if i + 1 >= len(argv):
            print("ERROR: --baseline needs a path", file=sys.stderr)
            return 2
        path = Path(argv[i + 1])
    else:
        path = BASELINE

    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 2

    baseline = json.loads(path.read_text())
    results = baseline.get("results", {})

    unaudited: list[tuple[str, int, str]] = []
    total = 0
    for fn, hits in results.items():
        for hit in hits:
            total += 1
            if "is_secret" not in hit:
                unaudited.append(
                    (fn, hit.get("line_number", 0), hit.get("type", "?"))
                )

    if unaudited:
        print(f"❌ {len(unaudited)} unaudited findings (of {total} total):")
        for f, line, t in unaudited[:20]:
            print(f"   {f}:{line}  {t}")
        if len(unaudited) > 20:
            print(f"   ... and {len(unaudited) - 20} more")
        print(
            "\n  Run `python scripts/detect_secrets_auto_triage.py --report` "
            "to see which ones are covered by auto-triage rules."
        )
        return 1

    print(f"✅ All findings audited ({total} total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
