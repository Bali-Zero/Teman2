#!/usr/bin/env python3
"""W34 (2026-05-23) — asyncpg.PostgresError except-completeness linter.

Catches the silent-death trap that bit W29 (wr2_supervisor_watchdog),
W32 (pg-to-organism-bridge), and would have bit wr2_supervisor.py if
not patched in W34. asyncpg.InterfaceError is a SIBLING of PostgresError
(NOT a subclass), so an `except asyncpg.PostgresError:` clause does NOT
catch InterfaceError. When pg-proxy hiccups and a keep-alive raises
InterfaceError on a stale conn, the exception escapes the reconnect
loop and the daemon enters silent-death.

Rule: every `except` clause that contains `asyncpg.PostgresError` MUST
also contain `asyncpg.InterfaceError` in the same tuple. Bare singletons
`except asyncpg.PostgresError:` are flagged unless inside a function
that obviously isn't a reconnect loop (e.g. test files, one-shot scripts,
http handlers — see ALLOW_DIRS).

Exit 0 if clean. Exit 1 with diff-style report listing violations and
remediation hint.

Used by .github/workflows/asyncpg-lint.yml on every PR touching any .py
file under apps/ or scripts/ that imports asyncpg.

Scope policy:
- IN scope: scripts/*.py (daemons + cron entries), packages/*/*.py,
  apps/cell/, apps/organism/, apps/mata-garuda/
- OUT of scope (allowlisted): apps/backend-rag/backend/app/routers/
  (HTTP handlers — short-lived, request-scoped, no reconnect-loop class),
  apps/backend-rag/backend/agents/ (per-call agents, no daemon loop),
  any */tests/* (test fixtures legitimately catch PostgresError only),
  apps/backend-rag/backend/db/base_repository.py (per-query retry helper,
  caller responsible for reconnect).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


# Lines matching this pattern (greedily across the except clause) are checked.
# Captures the parenthesized exception tuple OR a bare exception class.
EXCEPT_RE = re.compile(
    r"^\s*except\s*(?:"
    r"(?P<tuple>\([^)]*\))"            # except (E1, E2, ...) as e:
    r"|"
    r"(?P<bare>[A-Za-z_][\w.]*)"        # except asyncpg.PostgresError as e:
    r")",
    re.MULTILINE,
)

POSTGRES_RE = re.compile(r"\basyncpg\.PostgresError\b")
INTERFACE_RE = re.compile(r"\basyncpg\.InterfaceError\b")

# Paths excluded from the check (see scope policy in docstring).
ALLOW_PREFIXES = (
    "apps/backend-rag/backend/app/routers/",
    "apps/backend-rag/backend/agents/",
    "apps/backend-rag/backend/db/base_repository.py",
    "apps/backend-rag/backend/db/migration_base.py",
    "apps/backend-rag/backend/services/portal/_mixins/billing.py",
    "apps/backend-rag/backend/services/",  # one-shot service calls
    "apps/backend-rag/backend/app/utils/postgres_debugger.py",
    "apps/backend-rag/backend/app/setup/service_initializer.py",
)
# Test directories (any path containing /tests/).
TEST_PATTERN = re.compile(r"(?:^|/)tests?/")
# Vendored/site-packages — never our code. Match either at path start
# (e.g. "node_modules/foo.py") or as path component (".../.venv/...").
VENV_PATTERN = re.compile(r"(?:^|/)(?:\.venv|venv|node_modules|site-packages)/")


def is_in_scope(path: Path, repo_root: Path) -> bool:
    rel = str(path.relative_to(repo_root))
    if VENV_PATTERN.search(rel):
        return False
    if TEST_PATTERN.search(rel):
        return False
    for prefix in ALLOW_PREFIXES:
        if rel.startswith(prefix):
            return False
    return True


def find_violations(path: Path) -> list[tuple[int, str]]:
    """Return list of (line_number, offending_line) for each except clause that
    mentions PostgresError but not InterfaceError."""
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if "asyncpg.PostgresError" not in src:
        return []
    violations: list[tuple[int, str]] = []
    for match in EXCEPT_RE.finditer(src):
        clause = match.group("tuple") or match.group("bare") or ""
        if not POSTGRES_RE.search(clause):
            continue
        if INTERFACE_RE.search(clause):
            continue
        # Compute line number from match.start()
        line_no = src[: match.start()].count("\n") + 1
        line = src.split("\n")[line_no - 1].rstrip()
        violations.append((line_no, line))
    return violations


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    targets: list[Path] = []
    if argv:
        targets = [repo_root / p for p in argv]
    else:
        # Default sweep: scripts/, apps/, packages/
        for root in ("scripts", "apps", "packages"):
            root_dir = repo_root / root
            if not root_dir.is_dir():
                continue
            targets.extend(root_dir.rglob("*.py"))

    bad: list[tuple[Path, int, str]] = []
    for path in targets:
        if not path.is_file():
            continue
        if not is_in_scope(path, repo_root):
            continue
        for line_no, line in find_violations(path):
            bad.append((path, line_no, line))

    if not bad:
        print("✅ asyncpg-lint: no violations — all `except asyncpg.PostgresError` "
              "clauses also catch InterfaceError")
        return 0

    print(
        f"❌ asyncpg-lint: {len(bad)} violation(s) found.\n"
        "Background: `asyncpg.InterfaceError` is a SIBLING of `PostgresError` "
        "(NOT a subclass).\n"
        "An `except asyncpg.PostgresError:` clause silently misses stale-conn errors\n"
        "(W29/W32/W34 silent-death pattern). Add InterfaceError to the tuple.\n"
        "\n"
        "Violations:\n"
    )
    for path, line_no, line in bad:
        rel = path.relative_to(repo_root)
        print(f"  {rel}:{line_no}: {line.strip()}")
    print(
        "\nFix template:\n"
        "  except (\n"
        "      asyncpg.PostgresError,\n"
        "      asyncpg.InterfaceError,  # sibling of PostgresError, NOT subclass\n"
        "      OSError,\n"
        "      asyncio.TimeoutError,\n"
        "  ) as exc:\n"
        "\n"
        "Allow-list policy: HTTP handlers, agents, test fixtures, and base_repository\n"
        "are exempt because they are not daemon reconnect loops. See lint script\n"
        "ALLOW_PREFIXES if a legitimate new path needs exemption."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
