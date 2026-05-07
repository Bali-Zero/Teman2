#!/usr/bin/env python3
"""SYMBIOSIS.md durability promise linter.

Scans SYMBIOSIS.md for lyrical promises about durability/recovery/never-loss and
verifies each is backed by a cited test file.

Pattern: lines containing keywords 'never lose', 'durable', 'always recover',
'replay', 'consumer groups', 'graceful degradation' must be either:
  (a) inside a markdown table cell that includes a 'Test' column citation, OR
  (b) followed within 10 lines by a 'Test:' / 'Validated by:' line citing a path

Exit 0 if all promises traced. Exit 1 with diff-style report otherwise.

Used by .github/workflows/symbiosis-lint.yml on every PR touching SYMBIOSIS.md.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PROMISE_PATTERNS = [
    r"\bnever\s+lose\b",
    r"\bdurabl(e|ity|ità)\b",
    r"\balways\s+recover\b",
    r"\breplay\b",
    r"\bconsumer\s+groups\b",
    r"\bgraceful\s+degradation\b",
    r"\bguarantee[ds]?\b",
    r"\bif\s+.*?\s+is\s+down\b",
]

TEST_CITATION_PATTERNS = [
    r"`apps/[^`]+/tests/[^`]+`",
    r"Test:\s*",
    r"Validated by:\s*",
    r"\|\s*Test\s*\|",  # markdown table column header
    r"resolution PR #\d+",  # cicatrix-resolution citation
    r"RESOLVED via PR #\d+",
]


def lint(symbiosis_path: Path) -> int:
    text = symbiosis_path.read_text()
    lines = text.splitlines()
    findings: list[tuple[int, str, str]] = []  # (line_no, claim, pattern)
    for i, line in enumerate(lines, 1):
        for pat in PROMISE_PATTERNS:
            if re.search(pat, line, flags=re.IGNORECASE):
                # Look in the same line plus 5 lines before / 10 after for citation.
                # The backward window catches table-row citations that the
                # surrounding prose then summarises (common SYMBIOSIS pattern).
                start = max(0, i - 6)
                end = min(i + 10, len(lines))
                window = "\n".join(lines[start:end])
                if not any(
                    re.search(p, window, flags=re.IGNORECASE)
                    for p in TEST_CITATION_PATTERNS
                ):
                    findings.append((i, line.strip()[:80], pat))
                break
    if findings:
        print(
            f"FAIL: {len(findings)} unverified durability promise(s) in {symbiosis_path}:"
        )
        for ln, claim, pat in findings:
            print(
                f"  L{ln}: {claim!r} (matched: /{pat}/) - no test citation in window"
            )
        return 1
    print(f"OK: All durability promises in {symbiosis_path} traced to test citations.")
    return 0


if __name__ == "__main__":
    sys.exit(lint(Path(sys.argv[1] if len(sys.argv) > 1 else "SYMBIOSIS.md")))
