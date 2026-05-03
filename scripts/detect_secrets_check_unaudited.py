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
    if not BASELINE.exists():
        print(f"ERROR: {BASELINE} not found", file=sys.stderr)
        return 2

    baseline = json.loads(BASELINE.read_text())
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
