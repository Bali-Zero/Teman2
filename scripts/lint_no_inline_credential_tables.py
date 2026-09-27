#!/usr/bin/env python3
"""lint_no_inline_credential_tables.py — catch the shape detect-secrets missed.

INCIDENT (2026-09-27): `apps/backend-rag/scripts/import_lkpm_q1_2026.py` carried
a literal `list[tuple[...]]` of 59 rows, 57 of them ending in two plaintext
strings holding a login and its counterpart — public on origin/main since
2026-04-07 (commit 38de0a686c). detect-secrets never flagged it: no single
high-entropy token, no dotenv-shaped line, no named-credential-variable
assignment of the shape this repo's own ban-prose lint already forbids
spelling out — just a repeated tuple shape whose LAST two fields are
strings, next to a comment or variable name that says
"password"/"credential"/"login".

This lint is narrow on purpose (family #3, guard-over-match/under-match — a
guard judges the ENTITY, not a substring): it does not flag every tuple that
happens to end in two strings (see the innocence fixture in
`scripts/tests/test_lint_no_inline_credential_tables.py` — a name/department
table is not a credential table). It flags a file only when BOTH hold:

  1. >= MIN_CREDENTIAL_ROWS lines match a single-line tuple/list literal whose
     last two elements are quoted strings (no nested parens on the line), and
  2. the file's content also contains a credential keyword (password, login,
     credential, secret, oss_user — case-insensitive) — the same signal a
     human reviewer would use to tell "coordinates" from "logins".

Exit code: 0 = clean, 1 = >=1 file flagged, 2 = operational error (git failure).
Usage:
    python3 scripts/lint_no_inline_credential_tables.py            # tracked *.py, repo-wide
    python3 scripts/lint_no_inline_credential_tables.py --files a.py b.py
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

MIN_CREDENTIAL_ROWS = 5

# A single-line tuple/list entry ending in two quoted string fields, e.g.:
#   (1, "Acme Corp", 42, "alice", "hunter2"),
#   ["alice", "hunter2"],
# Deliberately requires no nested "(" before the trailing pair, so it does not
# fire on multi-line or nested-call literals (those are out of scope here —
# same false-negative tradeoff detect-secrets already accepts for structure).
_TUPLE_TWO_TRAILING_STRINGS = re.compile(
    r'^\s*[\(\[][^()\[\]]*,\s*(["\'])[^"\']*\1\s*,\s*(["\'])[^"\']*\2\s*[\)\]],?\s*$',
)

_CREDENTIAL_KEYWORD = re.compile(
    r"password|credential|\blogin\b|secret|oss_user|oss_pass",
    re.IGNORECASE,
)


#: This guard's own test file embeds a GUILTY_SOURCE fixture — a credential-
#: shaped table, on purpose, as a Python string literal — to prove the scan
#: catches the shape. That string is not executable data (never assigned to
#: a module-level name, never imported), but this scanner works on raw text,
#: so it matches its own fixture the same way it would match a real table.
#: Excluding it here is the same "churn that carries no review risk"
#: philosophy `_is_size_term_excluded()` uses elsewhere in this repo — a
#: narrow, named, single-file exemption, not a directory-wide carve-out.
_SELF_TEST_FIXTURE_EXEMPT = "scripts/tests/test_lint_no_inline_credential_tables.py"


def _tracked_py_files() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "*.py"],
        capture_output=True, text=True, check=True,
    )
    return [
        f for f in out.stdout.splitlines()
        if f and f != _SELF_TEST_FIXTURE_EXEMPT
    ]


_WINDOW_BEFORE = 5  # lines to look back from a run's start for the declaring
                     # comment/variable name (the incident's keyword sat here)


def scan_file(path: Path) -> int:
    """Return the size of the largest LOCAL credential-shaped tuple run.

    Locality matters (family #3 discipline): a big test file can legitimately
    contain both a 20-row unrelated data table AND the word "secret" fifty
    lines away (e.g. an unrelated `WEBHOOK_SECRET` reference) — that pairing
    is a false positive, not a finding. Only a run of >= MIN_CREDENTIAL_ROWS
    trailing-string tuples that sits WITHIN its own declaration block (the
    run itself, plus a short look-back window for the introducing comment or
    variable name) counts.
    """
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return 0
    lines = text.splitlines()

    is_tuple = [bool(_TUPLE_TWO_TRAILING_STRINGS.match(line)) for line in lines]
    is_comment = [line.strip().startswith("#") for line in lines]

    best = 0
    i = 0
    n = len(lines)
    while i < n:
        if not is_tuple[i]:
            i += 1
            continue
        start = i
        count = 0
        while i < n and (is_tuple[i] or is_comment[i]):
            if is_tuple[i]:
                count += 1
            i += 1
        run_end = i  # exclusive
        if count >= MIN_CREDENTIAL_ROWS:
            window_start = max(0, start - _WINDOW_BEFORE)
            window = "\n".join(lines[window_start:run_end])
            if _CREDENTIAL_KEYWORD.search(window):
                best = max(best, count)
    return best


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="*", help="Scan only these files (relative to repo root)")
    args = parser.parse_args(argv)

    try:
        targets = args.files if args.files else _tracked_py_files()
    except subprocess.CalledProcessError as e:
        print(f"lint_no_inline_credential_tables: git ls-files failed: {e}", file=sys.stderr)
        return 2

    flagged: list[tuple[str, int]] = []
    for rel in targets:
        path = REPO_ROOT / rel
        hits = scan_file(path)
        if hits:
            flagged.append((rel, hits))

    if flagged:
        print("lint_no_inline_credential_tables: FOUND inline credential-shaped table(s):")
        for rel, hits in flagged:
            print(f"  - {rel}: {hits} password-shaped tuple/list literal(s)")
        print(
            "\nMove the username/password pairs to an untracked, gitignored "
            "local file loaded at runtime (see apps/backend-rag/scripts/"
            "import_lkpm_q1_2026.py::_load_oss_credentials for the pattern "
            "this incident produced, 2026-09-27).",
        )
        return 1

    print(f"lint_no_inline_credential_tables: clean ({len(targets)} tracked *.py file(s) scanned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
