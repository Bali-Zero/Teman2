#!/usr/bin/env python3
"""The pytest DSN fail-closed guard must know EVERY env var the tests read.

THE DEFECT THIS EXISTS TO CATCH (measured 2026-07-28):

`backend/tests/conftest.py` refuses to run pytest against `nuzantara_dev` — the
database that carries the live local Intake/WhatsApp queue on Pro. The guard was
real, tested, and load-bearing. It watched exactly one variable,
`TEST_DATABASE_URL`.

Three intake tests resolve their DSN from a DIFFERENT variable,
`INTAKE_TEST_DSN`, whose module-level fallback was literally
`postgresql://localhost:5432/nuzantara_dev`. Nothing in the conftest set that
variable, so the fallback was live, and nothing in the guard inspected it, so
the refusal never fired. CI (`tests.yml`) and the pre-push hook each export a
safe value, which is why this never showed up as a red build — the uncovered
path was a bare manual `pytest`, which is precisely how a session runs them.

A guard that watches one door while the code walks through another is the same
shape as a scan surface that skips a file type (superscar #3, UNDER-match). The
per-instance fix is one more variable in the list; THIS file is the class fix,
because the next variable will be added by someone who never reads the conftest.

WHAT IT ASSERTS
  1. every env var used in a test module as the source of a `postgresql://` DSN
     is listed in the conftest's `TEST_DSN_ENV_VARS`;
  2. no test module carries a DSN default pointing at `nuzantara_dev`;
  3. the scanner found something at all — a scan that walked nothing must never
     report "clean" (W84).

Parsed with `ast`, never imported: importing that conftest sets ~20 environment
variables as a side effect, and a test that mutates the environment to check the
environment is its own kind of lie.

Run:  python3 scripts/tests/test_intake_dsn_guard_covers_every_var.py
      pytest scripts/tests/test_intake_dsn_guard_covers_every_var.py -q
"""

from __future__ import annotations

import ast
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "apps" / "backend-rag" / "backend" / "tests"
CONFTEST = TESTS_ROOT / "conftest.py"

_DSN_PREFIX = "postgresql://"
_OPERATIONAL_DB = "nuzantara_dev"


def covered_vars() -> set[str]:
    """`TEST_DSN_ENV_VARS` out of the conftest, by AST — no import."""
    tree = ast.parse(CONFTEST.read_text())
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for t in targets:
            if isinstance(t, ast.Name) and t.id == "TEST_DSN_ENV_VARS":
                value = node.value
                if isinstance(value, (ast.Tuple, ast.List)):
                    return {
                        e.value
                        for e in value.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)
                    }
    return set()


def dsn_reads() -> list[tuple[str, str, str, int]]:
    """(file, env_var, default_dsn, lineno) for every DSN-defaulted env read."""
    out: list[tuple[str, str, str, int]] = []
    for path in sorted(TESTS_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:  # pragma: no cover - a broken test file is another gate's job
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or len(node.args) != 2:
                continue
            fn = node.func
            # os.environ.get("X", "...") | os.getenv("X", "...")
            is_environ_get = (
                isinstance(fn, ast.Attribute)
                and fn.attr == "get"
                and isinstance(fn.value, ast.Attribute)
                and fn.value.attr == "environ"
            )
            is_getenv = isinstance(fn, ast.Attribute) and fn.attr == "getenv"
            if not (is_environ_get or is_getenv):
                continue
            name, default = node.args
            if not (isinstance(name, ast.Constant) and isinstance(name.value, str)):
                continue
            if not (isinstance(default, ast.Constant) and isinstance(default.value, str)):
                continue
            if not default.value.startswith(_DSN_PREFIX):
                continue
            out.append(
                (
                    str(path.relative_to(REPO_ROOT)),
                    name.value,
                    default.value,
                    node.lineno,
                )
            )
    return out


def test_every_dsn_env_var_is_covered_by_the_guard() -> None:
    reads = dsn_reads()
    # A scan that walked nothing is not a clean scan.
    assert reads, (
        "found ZERO env-var DSN defaults under backend/tests — the scanner is "
        "wrong, not the tree; this test would otherwise pass by being broken"
    )

    covered = covered_vars()
    assert covered, (
        "could not parse TEST_DSN_ENV_VARS out of backend/tests/conftest.py — if "
        "it was renamed, rename it here too rather than deleting this check"
    )

    uncovered = sorted({var for _f, var, _d, _l in reads} - covered)
    assert not uncovered, (
        f"these env vars carry a postgres DSN in a test module but the "
        f"fail-closed guard in backend/tests/conftest.py does not inspect them: "
        f"{uncovered}. Add them to TEST_DSN_ENV_VARS (and give them a safe "
        f"setdefault) — a guard that watches one variable while the code reads "
        f"another cannot refuse the operational database."
    )


def test_no_test_module_defaults_to_the_operational_database() -> None:
    offenders = [
        f"{f}:{line} {var} -> {dsn}"
        for f, var, dsn, line in dsn_reads()
        if dsn.split("?", 1)[0].rstrip("/").endswith(f"/{_OPERATIONAL_DB}")
    ]
    assert not offenders, (
        f"test modules default to the OPERATIONAL database {_OPERATIONAL_DB!r}, "
        f"which carries the live Intake/WhatsApp queue on Pro:\n  "
        + "\n  ".join(offenders)
        + "\nPoint the default at nuzantara_test. The conftest guard is the "
        "backstop, not the excuse: a module run without it (different rootdir, "
        "direct invocation) reads its own literal."
    )


if __name__ == "__main__":
    failures = 0
    for _name, fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   {_name}")
            except AssertionError as exc:
                failures += 1
                print(f"  FAIL {_name}\n       {exc}")
    print("PASS" if not failures else f"FAIL ({failures})")
    sys.exit(1 if failures else 0)
