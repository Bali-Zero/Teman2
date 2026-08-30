#!/usr/bin/env python3
"""AST lint: test-side `asyncpg.create_pool(...)` calls without `init=` (L12-PR1, 2026-08-29/30).

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

THE BASELINE (added 2026-08-30). The real test tree carries 26 pre-existing
bare pools this PR did not touch (outside its stated file list -- see
`infra/test-pool-parity/baseline.json`'s own `_meta.why`). Rather than
either (a) silently exempting a whole directory -- the blanket-exemption
anti-pattern `test_jsonb_double_encoding_class_guard.py`'s own header warns
against -- or (b) leaving the acceptance command permanently red, this lint
compares the RAW scan against an enumerated, per-file COUNT baseline. A file
matching its baseline count exactly is suppressed (pre-existing, tracked
debt); a file EXCEEDING its baseline count is a genuine new violation; a
file BELOW its baseline count (or a baseline entry naming a file that no
longer exists) is a STALE baseline -- also a failure, with a distinct
message, because a registry nobody is forced to shrink is a registry that
silently stops meaning anything. `--no-baseline` scans raw, ignoring the
file entirely, to prove the baseline is doing real suppression rather than
the findings having quietly vanished.

Exit 0: no findings (UNVERIFIABLE notes may still print). With a baseline
  active: no new violations AND no stale baseline entries.
Exit 1: at least one bare `create_pool` found beyond what the baseline
  covers, or the baseline itself is stale (see above); findings/messages
  printed to stdout with file:line and a remedy pointer.
Exit 2: usage/IO error -- a `--root` that does not exist, a file that could
  not be read, a file that failed to parse as Python, or a `--baseline`
  file that does not exist / does not parse as the expected shape. A scan
  that could not read a file must NEVER report exit 0 ("clean") -- that
  would be a blind scan mistaken for a green one (cicatrix superscar #2).
"""

from __future__ import annotations

import argparse
import ast
import json
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

_BASELINE_WHY = (
    "These are PRE-EXISTING bare asyncpg.create_pool() calls, discovered "
    "when scripts/lint_test_pool_codec_parity.py (L12-PR1, 2026-08-29) "
    "shipped -- outside that PR's stated file list, so it fixed the two "
    "files it named (apps/backend-rag/backend/tests/routers/) and enumerated "
    "the rest here rather than exempting a whole directory (the "
    "blanket-exemption anti-pattern test_jsonb_double_encoding_class_guard.py's "
    "own header warns against) or leaving the acceptance command permanently "
    "red. This list may only SHRINK: fixing a file's bare pool(s) and not "
    "lowering its count here is itself a lint failure (a stale baseline is "
    "how a registry rots) -- shrink or remove the entry in the SAME diff. A "
    "NEW bare pool in an already-listed file still fires, because the count "
    "is compared exactly, not just presence/absence."
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


def _default_baseline_path() -> Path:
    """`infra/test-pool-parity/baseline.json`, resolved relative to the repo
    root (this script lives at `<repo-root>/scripts/lint_test_pool_codec_parity.py`)."""
    return Path(__file__).resolve().parents[1] / "infra" / "test-pool-parity" / "baseline.json"


def build_baseline(findings: list[Finding]) -> dict[str, int]:
    """Repo-relative (or --root-relative -- see module docstring: the key is
    exactly the path STRING the scan produced, matching how this tool is
    always invoked, `--root` relative to the repo root) path -> count of
    bare `create_pool` calls in that file. Only files with count > 0 --
    an entry for a clean file would be noise no one asked for."""
    counts: dict[str, int] = {}
    for finding in findings:
        key = str(finding.path)
        counts[key] = counts.get(key, 0) + 1
    return counts


def write_baseline(path: Path, counts: dict[str, int], *, generated: str) -> None:
    payload = {
        "_meta": {
            "generated": generated,
            "generated_by": "scripts/lint_test_pool_codec_parity.py --write-baseline",
            "why": _BASELINE_WHY,
        },
    }
    payload.update(dict(sorted(counts.items())))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


class BaselineLoadError(Exception):
    """Baseline file missing, unreadable, or the wrong shape -- a usage/IO
    error (exit 2), never silently treated as an empty baseline."""


def load_baseline(path: Path) -> dict[str, int]:
    if not path.is_file():
        raise BaselineLoadError(f"baseline file not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineLoadError(f"cannot read/parse baseline file {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise BaselineLoadError(f"baseline file {path} must be a JSON object")
    counts: dict[str, int] = {}
    for key, value in raw.items():
        if key == "_meta":
            continue
        if not isinstance(value, int) or isinstance(value, bool):
            raise BaselineLoadError(
                f"baseline file {path}: entry {key!r} has non-integer count {value!r}"
            )
        counts[key] = value
    return counts


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lint_test_pool_codec_parity.py",
        description=(
            "AST lint: flags a test-side asyncpg.create_pool(...) call with no "
            "init= keyword -- such a pool encodes jsonb differently from every "
            "production pool, letting a test pass on a code path production "
            "never exercises (2026-08-27 GARUDA VOA incident). Compared against "
            "an enumerated, shrink-only baseline of pre-existing findings by "
            "default -- see infra/test-pool-parity/baseline.json."
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
    baseline_group = parser.add_mutually_exclusive_group()
    baseline_group.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help=(
            "Path to the shrink-only baseline JSON (default: "
            "infra/test-pool-parity/baseline.json, relative to the repo root)."
        ),
    )
    baseline_group.add_argument(
        "--no-baseline",
        action="store_true",
        help="Ignore the baseline entirely -- every finding is a violation.",
    )
    parser.add_argument(
        "--write-baseline",
        type=Path,
        default=None,
        help=(
            "Instead of checking, write a fresh baseline JSON (from the RAW "
            "scan of --root, ignoring any existing --baseline) to this path "
            "and exit 0. Use this to regenerate the baseline after a "
            "deliberate, reviewed shrink or an approved new exemption."
        ),
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

    if args.write_baseline is not None:
        counts = build_baseline(findings)
        write_baseline(args.write_baseline, counts, generated="2026-08-30")
        print(
            f"lint_test_pool_codec_parity: wrote baseline with {len(counts)} file(s) "
            f"({sum(counts.values())} total finding(s)) to {args.write_baseline}"
        )
        return 0

    for note in notes:
        print(note.render())

    if args.no_baseline:
        if not findings:
            print(
                f"✅ lint_test_pool_codec_parity: {scanned} file(s) scanned across "
                f"{len(args.roots)} root(s), no bare asyncpg.create_pool() found "
                "(--no-baseline)"
            )
            return 0
        print(
            f"❌ lint_test_pool_codec_parity: {len(findings)} violation(s) found "
            "(--no-baseline; baseline suppression disabled).\n"
        )
        for finding in findings:
            print(finding.render())
        return 1

    baseline_path = args.baseline if args.baseline is not None else _default_baseline_path()
    try:
        baseline = load_baseline(baseline_path)
    except BaselineLoadError as exc:
        print(f"lint_test_pool_codec_parity: {exc}", file=sys.stderr)
        return 2

    found_by_file: dict[str, list[Finding]] = {}
    for finding in findings:
        found_by_file.setdefault(str(finding.path), []).append(finding)

    growth_findings: list[Finding] = []
    stale_messages: list[str] = []
    suppressed_count = 0
    new_count = 0

    all_keys = sorted(set(found_by_file) | set(baseline))
    for key in all_keys:
        baseline_count = baseline.get(key)
        file_findings = found_by_file.get(key, [])
        found_count = len(file_findings)

        if baseline_count is None:
            # Not tracked at all. found_count == 0 is the overwhelming
            # common case (the vast majority of scanned files) and needs no
            # message; found_count > 0 is a brand-new, never-recorded
            # violation.
            if found_count > 0:
                growth_findings.extend(file_findings)
                new_count += found_count
            continue

        file_exists = Path(key).is_file()
        if not file_exists:
            stale_messages.append(
                f"{key}: baselined at {baseline_count} but the file no longer exists -- "
                f"remove this entry from {baseline_path}"
            )
            continue

        if found_count > baseline_count:
            growth_findings.extend(file_findings)
            new_count += found_count
            continue

        if found_count < baseline_count:
            stale_messages.append(
                f'{key}: baselined at {baseline_count} but only {found_count} found now -- '
                f'shrink the baseline in {baseline_path}: "{key}": {found_count}'
            )
            continue

        # found_count == baseline_count: pre-existing, tracked, suppressed.
        suppressed_count += found_count

    print(f"{suppressed_count} suppressed by baseline (pre-existing), {new_count} new")

    if growth_findings:
        print(
            f"\n❌ lint_test_pool_codec_parity: {len(growth_findings)} NEW "
            f"violation(s) beyond the baseline ({baseline_path}).\n"
        )
        for finding in sorted(growth_findings, key=lambda f: (str(f.path), f.lineno)):
            print(finding.render())

    if stale_messages:
        print(
            f"\n⚠️  lint_test_pool_codec_parity: baseline is STALE -- "
            f"{len(stale_messages)} entrie(s) need shrinking. Never let a stale "
            "baseline pass silently -- that is how a registry rots.\n"
        )
        for message in stale_messages:
            print(message)

    if not growth_findings and not stale_messages:
        print(
            "\n✅ lint_test_pool_codec_parity: baseline honored -- no new "
            "violations, no stale entries"
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
