#!/usr/bin/env python3
"""AST lint: test-side `asyncpg.create_pool(...)` calls without `init=` (L12-PR1, 2026-08-29).

WHY THIS EXISTS. Every production pool in this repo
(`backend/app/core/database.py::get_db_pool`, both pool paths in
`backend/app/setup/service_initializer.py`) registers `JSONB_ENCODER` on
every new connection via `init=init_asyncpg_connection`. A test pool built
with a bare `asyncpg.create_pool(dsn, min_size=1, max_size=4)` -- no `init=`
at all -- encodes jsonb DIFFERENTLY from production: it has no codec, so a
pre-serialized `json.dumps(...)` string passed straight through as JSON
text, while production's codec double-encodes that same string into a JSONB
string scalar (SQLSTATE 22023 on any `jsonb_array_length()`/`->>`/`?`
consumer). On 2026-08-27 that exact gap let `test_check_to_order_journey.py`
pass 10/10 against a real Postgres while GARUDA VOA's first customer action
answered HTTP 500 in production for every request shape -- see
`backend/tests/fixtures/prod_shaped_pool.py` for the full incident writeup.

WHAT THIS FLAGS. A real call to asyncpg's pool factory --
`asyncpg.create_pool(...)` (an `Attribute` call on a name bound to the
`asyncpg` module) or a bare `create_pool(...)` call (a `Name` bound via
`from asyncpg import create_pool`) -- that has no `init=` keyword argument.
Precise AST matching, not a text/regex search for the string
"create_pool" -- so a `patch("...asyncpg.create_pool")` string argument, a
`monkeypatch.setattr(mod.asyncpg, "create_pool", fake)` call, an
`AsyncMock`/`MagicMock` assignment, and a function merely NAMED
`fake_create_pool`/`_create_pool` are none of them a `Call` whose `func` is
literally `asyncpg.create_pool`/a `create_pool`-bound `Name` -- they are not
inspected at all, by construction, not via an allowlist.

WHAT THIS DOES NOT FLAG AS A HARD VIOLATION. A matched call that unpacks
`**kwargs` (`asyncpg.create_pool(dsn, **kwargs)`) cannot be statically
proven to omit `init=` -- the caller might inject it into `kwargs` at
runtime. That case is reported as a separate UNVERIFIABLE note (never
folded into the exit-1 violation count) so a human can check it by hand
without the lint crying wolf on every legitimately-dynamic call site.

Remedy for a real violation: use
`backend.tests.fixtures.prod_shaped_pool.create_prod_shaped_pool` instead
of a bare `asyncpg.create_pool(...)` -- it imports the SAME
`init_asyncpg_connection` production uses.

Exit 0: no findings (UNVERIFIABLE notes may still print).
Exit 1: at least one bare `create_pool` found; findings printed to stdout
  with file:line and a remedy pointer.
Exit 2: usage/IO error -- a `--root` that does not exist, a file that could
  not be read, or a file that failed to parse as Python. A scan that could
  not read a file must NEVER report exit 0 ("clean") -- that would be a
  blind scan mistaken for a green one (cicatrix superscar #2).
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_REMEDY = (
    "production registers a jsonb codec on every connection "
    "(backend/app/core/database.py::init_asyncpg_connection); use "
    "backend.tests.fixtures.prod_shaped_pool.create_prod_shaped_pool "
    "instead of a bare asyncpg.create_pool()."
)


@dataclass(frozen=True)
class Finding:
    path: Path
    lineno: int

    def render(self) -> str:
        return f"{self.path}:{self.lineno}: asyncpg.create_pool without init= -- {_REMEDY}"


@dataclass(frozen=True)
class Note:
    path: Path
    lineno: int
    reason: str

    def render(self) -> str:
        return f"{self.path}:{self.lineno}: UNVERIFIABLE -- {self.reason}"


def _is_pytest_importorskip_asyncpg(value: ast.expr) -> bool:
    """True for `pytest.importorskip("asyncpg")` (with or without a second
    `reason=`/`minversion=` argument) -- the idiom this test tree uses
    throughout `services/garuda_orders`, `garuda_portal`, and `garuda_ops`
    to make an asyncpg-requiring test skip cleanly instead of erroring when
    the dependency is missing.

    ``NAME = pytest.importorskip("asyncpg")`` binds NAME to the asyncpg
    module exactly as ``import asyncpg as NAME`` would; a scanner that only
    recognises `ast.Import`/`ast.ImportFrom` misses it entirely and reports
    every `NAME.create_pool(...)` call in that file as "no asyncpg import
    found" (silently not-a-match) rather than as a violation -- an
    under-match, the same class of bug as an over-match, just the opposite
    sign (cicatrix superscar #3).
    """
    if not (isinstance(value, ast.Call) and value.args):
        return False
    func = value.func
    is_importorskip = (
        isinstance(func, ast.Attribute)
        and func.attr == "importorskip"
        and isinstance(func.value, ast.Name)
        and func.value.id == "pytest"
    )
    if not is_importorskip:
        return False
    first_arg = value.args[0]
    return isinstance(first_arg, ast.Constant) and first_arg.value == "asyncpg"


def _import_aliases(tree: ast.Module) -> tuple[set[str], set[str]]:
    """Names bound to the `asyncpg` module itself, and names bound directly
    to `asyncpg.create_pool` via a `from asyncpg import create_pool` (with
    or without `as`). Walks the whole tree (not just module-level statements)
    so a lazy `import asyncpg` inside a fixture function, or a module-level
    `asyncpg = pytest.importorskip("asyncpg")`, is still tracked.
    """
    module_aliases: set[str] = set()
    bare_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "asyncpg":
                    module_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "asyncpg":
                for alias in node.names:
                    if alias.name == "create_pool":
                        bare_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and _is_pytest_importorskip_asyncpg(node.value)
            ):
                module_aliases.add(node.targets[0].id)
    return module_aliases, bare_aliases


def _has_keyword(call: ast.Call, name: str) -> bool:
    return any(kw.arg == name for kw in call.keywords)


def _has_double_star_unpacking(call: ast.Call) -> bool:
    """A `**kwargs`-style keyword unpacking is an `ast.keyword` with
    `arg=None` -- distinct from a named keyword like `init=...`."""
    return any(kw.arg is None for kw in call.keywords)


def _is_create_pool_call(node: ast.Call, module_aliases: set[str], bare_aliases: set[str]) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "create_pool":
        return isinstance(func.value, ast.Name) and func.value.id in module_aliases
    if isinstance(func, ast.Name):
        return func.id in bare_aliases
    return False


def scan_module(tree: ast.Module, path: Path) -> tuple[list[Finding], list[Note]]:
    module_aliases, bare_aliases = _import_aliases(tree)
    findings: list[Finding] = []
    notes: list[Note] = []
    if not module_aliases and not bare_aliases:
        return findings, notes
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_create_pool_call(node, module_aliases, bare_aliases):
            continue
        if _has_keyword(node, "init"):
            continue
        if _has_double_star_unpacking(node):
            notes.append(
                Note(
                    path=path,
                    lineno=node.lineno,
                    reason=(
                        "asyncpg.create_pool call unpacks **kwargs; cannot statically "
                        "confirm init= is absent -- verify by hand"
                    ),
                )
            )
            continue
        findings.append(Finding(path=path, lineno=node.lineno))
    return findings, notes


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lint_test_pool_codec_parity.py",
        description=(
            "AST lint: flags a test-side asyncpg.create_pool(...) call with no "
            "init= keyword -- such a pool encodes jsonb differently from every "
            "production pool, letting a test pass on a code path production "
            "never exercises (2026-08-27 GARUDA VOA incident)."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        action="append",
        required=True,
        dest="roots",
        help="Directory to scan for *.py files (repeatable).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    findings: list[Finding] = []
    notes: list[Note] = []
    errors: list[str] = []
    scanned = 0

    for root in args.roots:
        if not root.exists():
            errors.append(f"lint_test_pool_codec_parity: --root not found: {root}")
            continue
        if not root.is_dir():
            errors.append(f"lint_test_pool_codec_parity: --root is not a directory: {root}")
            continue
        for path in sorted(root.rglob("*.py")):
            if not path.is_file():
                continue
            try:
                src = path.read_text(encoding="utf-8")
            except OSError as exc:
                errors.append(f"lint_test_pool_codec_parity: cannot read {path}: {exc}")
                continue
            try:
                tree = ast.parse(src, filename=str(path))
            except SyntaxError as exc:
                errors.append(f"lint_test_pool_codec_parity: syntax error in {path}: {exc}")
                continue
            scanned += 1
            file_findings, file_notes = scan_module(tree, path)
            findings.extend(file_findings)
            notes.extend(file_notes)

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 2

    for note in notes:
        print(note.render())

    if not findings:
        print(
            f"✅ lint_test_pool_codec_parity: {scanned} file(s) scanned across "
            f"{len(args.roots)} root(s), no bare asyncpg.create_pool() found"
        )
        return 0

    print(f"❌ lint_test_pool_codec_parity: {len(findings)} violation(s) found.\n")
    for finding in findings:
        print(finding.render())
    return 1


if __name__ == "__main__":
    sys.exit(main())
