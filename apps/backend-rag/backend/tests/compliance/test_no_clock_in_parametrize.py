"""No decorator argument may read the clock.

Why this guard exists (2026-07-27): `backend/tests/routers/test_intake_review.py`
put `datetime.now(timezone.utc) + timedelta(minutes=5)` directly in a
`@pytest.mark.parametrize` list, as the "live lease" case for the intake claim
guard. A parametrize argument is evaluated ONCE, at collection — and pytest
collects the entire tree before running a single test. The lease was therefore
five minutes old the moment it was born, and stayed pinned to that instant while
the rest of the suite ran.

In CI the suite reached that file inside the window, so it was green. On a loaded
machine the full backend suite needs far longer, the "live" lease is expired by
the time the case runs, the guard correctly answers 409 — and three of the five
params fail asserting 403/400. The test's verdict depended on how long the suite
took to reach it, which is not a property of the code under test. Every local
push from that machine was blocked by a diff that touched none of it.

The cure is to keep absolute time inside the test body and parametrize an OFFSET.
This guard arms that rule for the whole tree. It found exactly one offender —
the one it was written for — and the tree is clean at zero after the fix, so it
starts life green rather than as a backlog.

Scope note: the ban is on decorator arguments only. Reading the clock inside a
test, a fixture, or a helper is normal and must keep passing.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

# `apps/backend-rag` — parents: compliance -> tests -> backend -> apps/backend-rag
_BACKEND_RAG_ROOT = Path(__file__).resolve().parents[3]

_TEST_ROOTS = (
    _BACKEND_RAG_ROOT / "backend" / "tests",
    _BACKEND_RAG_ROOT / "tests",
)

# `datetime.now()` / `datetime.utcnow()` / `date.today()` / `time.time()` /
# `time.monotonic()` / `time.perf_counter()`. Matched on the attribute name so a
# renamed import (`import datetime as dt`) is still caught.
_CLOCK_ATTRS = frozenset(
    {"now", "utcnow", "today", "time", "monotonic", "perf_counter"}
)


def _clock_calls_in_decorators(source: str) -> list[int]:
    """Line numbers of clock reads inside any decorator expression."""
    tree = ast.parse(source)
    found: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        for decorator in node.decorator_list:
            for sub in ast.walk(decorator):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr in _CLOCK_ATTRS
                ):
                    found.append(sub.lineno)
    return sorted(set(found))


def _iter_test_sources() -> list[Path]:
    files: list[Path] = []
    for root in _TEST_ROOTS:
        if not root.is_dir():
            continue
        files.extend(
            p
            for p in root.rglob("*.py")
            if "__pycache__" not in p.parts and "_obsolete" not in p.parts
        )
    return files


def test_guard_flags_a_frozen_timestamp_in_parametrize() -> None:
    """GUILT: the exact shape that blocked every push must be detected."""
    guilty = textwrap.dedent(
        """
        from datetime import datetime, timedelta, timezone

        import pytest

        @pytest.mark.parametrize(
            "lease_expires_at",
            [datetime.now(timezone.utc) + timedelta(minutes=5)],
        )
        def test_live_lease(lease_expires_at):
            assert lease_expires_at
        """
    )
    assert _clock_calls_in_decorators(guilty) == [8]


def test_guard_does_not_flag_the_clock_inside_a_test_or_fixture() -> None:
    """INNOCENCE: reading the clock at CALL time is the correct pattern.

    This is the post-fix shape of the very test that motivated the guard —
    parametrize carries an offset, the absolute instant is built in the body —
    plus a fixture that stamps a time. Neither may be flagged.
    """
    innocent = textwrap.dedent(
        """
        from datetime import datetime, timedelta, timezone

        import pytest

        @pytest.fixture
        def started_at():
            return datetime.now(timezone.utc)

        @pytest.mark.parametrize("lease_offset", [timedelta(minutes=5), None])
        def test_live_lease(lease_offset):
            expires = (
                None if lease_offset is None
                else datetime.now(timezone.utc) + lease_offset
            )
            assert expires is None or expires > datetime.now(timezone.utc)
        """
    )
    assert _clock_calls_in_decorators(innocent) == []


def test_no_test_decorator_reads_the_clock() -> None:
    """The real sweep over both collected test trees."""
    sources = _iter_test_sources()
    # A guard that walks zero files is blind, not green.
    assert len(sources) > 100, (
        f"expected to scan the whole backend test tree, found {len(sources)} "
        f"files under {[str(r) for r in _TEST_ROOTS]} — the roots are wrong"
    )

    offenders: list[str] = []
    for path in sources:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # pragma: no cover - unreadable file
            continue
        try:
            lines = _clock_calls_in_decorators(source)
        except SyntaxError:  # pragma: no cover - not this guard's job to police
            continue
        for line in lines:
            offenders.append(f"{path.relative_to(_BACKEND_RAG_ROOT)}:{line}")

    assert not offenders, (
        "a decorator argument is evaluated once at COLLECTION, so a timestamp "
        "frozen there ages while the rest of the suite runs and the case starts "
        "failing for how long the suite took (see this file's docstring). "
        "Parametrize an offset and build the absolute time inside the test:\n  "
        + "\n  ".join(offenders)
    )
