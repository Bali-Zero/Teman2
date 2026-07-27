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

Extended 2026-07-27 to cover the clock's twin: random/UUID values in the same
position. Found while probing pytest-xdist for `backend/tests/` — the same
mechanism (evaluated once at collection) breaks a DIFFERENT thing for a
random source than for a clock. A frozen timestamp ages; a frozen UUID is
merely wrong-but-stable within a single process, so it never bit the
single-process suite. It bites `-n auto`: each xdist worker is a separate
process, so a `uuid.uuid4()` read at collection mints a different value per
worker, giving each worker a different generated test ID for the same
logical test — pytest-xdist refuses the entire run with "Different tests
were collected between gwN and gwM" before executing a single test. See
`_NONDETERMINISTIC_NAMES` below for the guard's own docstring on this half.
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

# The clock's twin (2026-07-27, found while probing pytest-xdist): a decorator
# argument that mints a RANDOM value is non-deterministic in the same way a
# clock read is, and it breaks something the clock case did not. pytest-xdist
# requires every worker to collect a byte-identical test list; each worker is a
# separate Python process, so a `uuid.uuid4()` in a parametrize list produces a
# different value — and therefore a different generated test ID — per worker.
# xdist then refuses the whole run with "Different tests were collected between
# gw2 and gw3", before executing a single test. Measured live: three sites in
# backend/tests/routers/test_intake_review.py, 22 differing collection lines
# across two plain processes.
#
# Matched on BOTH a bare name (`uuid4()` after `from uuid import uuid4`) and an
# attribute (`uuid.uuid4()`), unlike the clock set above which only matches the
# attribute form — these names are distinctive enough that a bare call is not
# plausibly a local helper, whereas a bare `time()` could be.
_NONDETERMINISTIC_NAMES = frozenset(
    {
        "uuid1",
        "uuid4",
        "random",
        "randint",
        "randrange",
        "choice",
        "shuffle",
        "sample",
        "getrandbits",
        "token_hex",
        "token_bytes",
        "token_urlsafe",
    }
)


def _nondeterministic_calls_in_decorators(source: str) -> list[int]:
    """Line numbers of random-value reads inside any decorator expression."""
    tree = ast.parse(source)
    found: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        for decorator in node.decorator_list:
            for sub in ast.walk(decorator):
                if not isinstance(sub, ast.Call):
                    continue
                name = None
                if isinstance(sub.func, ast.Attribute):
                    name = sub.func.attr
                elif isinstance(sub.func, ast.Name):
                    name = sub.func.id
                if name in _NONDETERMINISTIC_NAMES:
                    found.append(sub.lineno)
    return sorted(set(found))


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


def test_guard_flags_a_random_uuid_in_parametrize() -> None:
    """GUILT: the exact shape that broke pytest-xdist collection.

    Live case, `backend/tests/routers/test_intake_review.py`: a bare
    `f"...{uuid.uuid4()}"` inside a parametrize list. Minted once per Python
    process at collection time — a different value (and therefore a
    different generated test ID) in every xdist worker.
    """
    guilty = textwrap.dedent(
        """
        import uuid

        import pytest

        @pytest.mark.parametrize(
            "release_url",
            [f"/api/intake/review/42/release?claim_token={uuid.uuid4()}"],
        )
        def test_release(release_url):
            assert release_url
        """
    )
    assert _nondeterministic_calls_in_decorators(guilty) == [8]


def test_guard_flags_a_bare_import_of_the_random_call() -> None:
    """GUILT (bare-name form): `from uuid import uuid4` then a naked call."""
    guilty = textwrap.dedent(
        """
        from uuid import uuid4

        import pytest

        @pytest.mark.parametrize("token", [str(uuid4())])
        def test_token(token):
            assert token
        """
    )
    assert _nondeterministic_calls_in_decorators(guilty) == [6]


def test_guard_does_not_flag_random_values_inside_a_test_or_fixture() -> None:
    """INNOCENCE: minting a fresh UUID per test run is the correct pattern.

    This is the post-fix shape of the live offender — parametrize carries a
    FIXED constant (still a syntactically valid, deliberately-wrong token,
    so semantics are preserved), the fresh one is built inside the test body
    where it is re-evaluated for every worker/run and never poisons
    collection.
    """
    innocent = textwrap.dedent(
        """
        import uuid

        import pytest

        @pytest.fixture
        def claim_token():
            return uuid.uuid4()

        @pytest.mark.parametrize(
            "release_url",
            ["/api/intake/review/42/release?claim_token=00000000-0000-0000-0000-000000000000"],
        )
        def test_release(release_url, claim_token):
            assert release_url
            assert claim_token
        """
    )
    assert _nondeterministic_calls_in_decorators(innocent) == []


def test_no_test_decorator_reads_a_random_value() -> None:
    """The real sweep over both collected test trees, random-value twin."""
    sources = _iter_test_sources()
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
            lines = _nondeterministic_calls_in_decorators(source)
        except SyntaxError:  # pragma: no cover - not this guard's job to police
            continue
        for line in lines:
            offenders.append(f"{path.relative_to(_BACKEND_RAG_ROOT)}:{line}")

    assert not offenders, (
        "a decorator argument is evaluated once at COLLECTION — a random/UUID "
        "value minted there is a different value (and therefore a different "
        "generated test ID) in every process, which is exactly what makes "
        "pytest-xdist refuse the run with 'Different tests were collected "
        "between gwN and gwM'. Use a fixed constant in parametrize and mint "
        "the real random value inside the test body:\n  "
        + "\n  ".join(offenders)
    )
