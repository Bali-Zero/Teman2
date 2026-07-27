#!/usr/bin/env python3
"""Every test dependency CI installs INLINE must also be declared in
apps/backend-rag/requirements-test.txt.

WHY (measured 2026-07-27, cicatrix-superscar.md family #2 "esiste ≠ armato"):
`.github/workflows/tests.yml` installs the suite's test-runtime deps as a bare
inline list —

    uv pip install --system pytest pytest-cov pytest-asyncio pytest-mock fakeredis

— while `requirements-test.txt` knew about only one of them. An inline workflow
list is not a manifest: nothing in the tree stated that the suite needs
`fakeredis`, so a fleet machine provisioned from the repo could not reproduce
CI's environment. Mini's venv duly lacked it; two test files ERRORed at
COLLECTION; and the pre-push gate blocked two branches that do not touch those
files at all — a red owned by the machine, reported as a verdict on the diff.

Declaring the deps fixes today. This test is what keeps it fixed: the next
person who adds a package to that inline list gets a failure here unless they
also declare it. Direction matters — the manifest must COVER the installer, not
the reverse: requirements-test.txt is allowed extra entries (mypy, testcontainers
are dev-only and deliberately not in the Backend Tests job).

Run:  python3 scripts/tests/test_test_deps_declared.py
      pytest scripts/tests/test_test_deps_declared.py -q
"""
from __future__ import annotations

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
MANIFEST = REPO_ROOT / "apps" / "backend-rag" / "requirements-test.txt"

# Flags/arguments that mean "this token is not a plain package name".
_NON_PACKAGE_PREFIXES = ("-", "$", "{", '"', "'")


def _normalise(name: str) -> str:
    """Canonical comparison form: PEP 503 name, extras and specifiers stripped.

    `pytest-cov`, `pytest_cov`, `PyTest-Cov`, `testcontainers[postgres]>=4.0.0`
    must all compare as their base distribution name.
    """
    base = re.split(r"[\[<>=!~;]", name, maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", base).strip().lower()


def inline_installed_packages() -> set[str]:
    """Bare package names installed by `pip/uv pip install` lines in tests.yml.

    Only tokens that are plain names count: `-r requirements.lock.txt`,
    `-e ../../packages/cell-core`, `--system`, `--upgrade` and shell/expression
    tokens are all excluded — this test is about packages named nowhere else,
    not about requirement files (which are manifests already).

    Anchored on the COMMAND, not on the substring: an `install` must open the
    shell line (or follow `&&` / `;`), and comment lines are dropped first.
    The first cut of this parser searched for `pip install` anywhere in the
    line and duly harvested 40-odd English words out of the workflow's own
    comments about pip installs — over-match on form instead of entity, the
    same defect this repo files under cicatrix-superscar.md family #3, written
    here by the person quoting it.
    """
    text = WORKFLOW.read_text()
    found: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = re.search(r"(?:^|&&\s*|;\s*)(?:uv\s+pip|pip3?)\s+install\b(.*)$", stripped)
        if not m:
            continue
        tail = m.group(1)
        # A `-r`/`-e`/`--requirement` argument consumes its value; drop both.
        tokens = tail.split()
        skip_next = False
        for tok in tokens:
            if skip_next:
                skip_next = False
                continue
            if tok in ("-r", "-e", "--requirement", "--editable", "-c", "--constraint"):
                skip_next = True
                continue
            if tok.startswith(_NON_PACKAGE_PREFIXES):
                continue
            if "/" in tok or tok.endswith(".txt"):
                continue
            if tok in ("pip", "uv"):  # bootstrap of the installer itself
                continue
            found.add(_normalise(tok))
    return found


def declared_packages() -> set[str]:
    out: set[str] = set()
    for raw in MANIFEST.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        out.add(_normalise(line))
    return out


def test_workflow_is_readable() -> None:
    """Fail LOUD rather than vacuously pass if either file moves.

    An empty inline-package set would make the coverage assertion below
    trivially true — the blind-scan failure mode (superscar #2 / W84): zero
    items traversed is not the same as nothing to find.
    """
    assert WORKFLOW.is_file(), f"missing {WORKFLOW}"
    assert MANIFEST.is_file(), f"missing {MANIFEST}"
    assert inline_installed_packages(), (
        f"no inline-installed packages parsed out of {WORKFLOW} — the install "
        "step was renamed or reformatted, and this test would silently pass "
        "against an empty set. Re-anchor the parser."
    )


def test_every_inline_installed_dep_is_declared() -> None:
    """GUILT: an inline-installed package absent from the manifest fails."""
    missing = sorted(inline_installed_packages() - declared_packages())
    assert not missing, (
        "these packages are installed by .github/workflows/tests.yml but are "
        f"declared in no manifest: {missing}. Add them to "
        "apps/backend-rag/requirements-test.txt — otherwise no machine can "
        "rebuild CI's test env from the repo, and the local suite fails with "
        "collection ERRORs that look like a defect in whatever diff is being "
        "pushed (measured on Mini, 2026-07-27)."
    )


def test_manifest_may_declare_extras() -> None:
    """INNOCENCE: manifest-only entries are legitimate, not a violation.

    `mypy` and `testcontainers` are dev/pre-commit tooling that the Backend
    Tests job deliberately does not install. A check written in the other
    direction would fail on them and teach people to delete real declarations.
    """
    extras = declared_packages() - inline_installed_packages()
    assert extras, (
        "expected requirements-test.txt to declare more than the CI inline "
        "list (mypy/testcontainers at minimum); if that is no longer true, "
        "this test's premise changed — re-read it, don't delete it."
    )
    assert "mypy" in declared_packages()


def test_the_dep_that_bit_us_is_declared() -> None:
    """SCAR PIN: fakeredis specifically. Two test files import it at module
    level (`import fakeredis.aioredis`, no importorskip), so its absence is a
    collection ERROR, not a skip."""
    assert "fakeredis" in declared_packages()


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
