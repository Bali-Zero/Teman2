"""Every `job_type` production enqueues must have a handler — read from the AST.

WHY THIS TEST EXISTS AND WHY IT IS NOT A GREP
----------------------------------------------
The count of outbox job types was stated wrongly in three separate artifacts
(this module's own docstring twice, a ledger row, a plan document). Every one of
those counts was produced the same way: `grep 'job_type="'`. That pattern matches
a LITERAL, and `repository.py` has one call site that passes a VARIABLE::

    job_type = ("practice_release" if resolution == "honoured"
                else "late_refund_confirmation_email")
    await journal.enqueue_outbox(..., job_type=job_type)

`late_refund_confirmation_email` — a CUSTOMER-FACING email sent when a staff
member gives a duplicate charge back — was therefore invisible to every count.

The correction prescribed after the second miss was "grep `job_type=\"` across
ALL of `backend/services`, not just `repository.py`". That antidote carried the
very defect it was curing: widening the DIRECTORY changes nothing when the SHAPE
being matched is wrong. Widening from TEXT to SYNTAX is the fix — superscar #3,
under-match, where a guard watching one textual form goes quiet on the same fact
written differently.

So this test parses the AST. And, critically, it does NOT skip what it cannot
resolve: an unresolvable `job_type=` argument FAILS the test by name. A checker
that silently ignores the one shape that defeated three humans would reproduce
the original defect in executable form.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.services.garuda_orders.outbox_handlers import build_handlers

# parents: [0]=garuda_orders [1]=services [2]=tests [3]=backend. So [3]/"services"
# is `backend/services` — the production tree. An earlier draft used [4], which
# pointed at a directory that does not exist and made every walk return the empty
# set; `test_every_enqueued_job_type_has_a_handler` caught it because it asserts
# `types` is non-empty. Without that assert this file would have passed while
# checking nothing at all — the same failure mode it exists to prevent.
_SERVICES = Path(__file__).resolve().parents[3] / "services"


def _enqueue_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Attribute) and node.func.attr == "enqueue_outbox")
            or (isinstance(node.func, ast.Name) and node.func.id == "enqueue_outbox")
        )
    ]


def _constant_strings(node: ast.expr) -> list[str] | None:
    """Every string this expression can evaluate to, or None if not decidable.

    Deliberately narrow: a bare literal, or a conditional whose two branches are
    both literals. That is exactly the shape production uses today. Anything
    else returns None and the caller FAILS — never skips. Widen this only by
    adding a shape that actually appears, and only together with the call site
    that made it necessary.
    """

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):
        left = _constant_strings(node.body)
        right = _constant_strings(node.orelse)
        if left is None or right is None:
            return None
        return left + right
    return None


def _rebinds(node: ast.AST, name: str) -> bool:
    """Does this node bind `name` in a way `_resolve_name` cannot evaluate?

    FOUND BY ATTACKING THIS CHECKER, not by reviewing it. The first version
    looked only at `ast.Assign`, so `jt = "a"` followed by `jt += "b"` resolved
    to `["a"]` — SILENTLY, and with the wrong value: at runtime that call
    enqueues `"ab"`. Had `"a"` happened to have a handler and `"ab"` not, this
    checker would have gone green over precisely the defect it exists to catch.

    That is the one direction that must never happen. OVER-reporting is safe: an
    extra value merely demands a handler that is not needed, and fails loudly.
    UNDER-reporting a value the code really produces is the silent miss.

    So every binding form this module cannot evaluate is treated as "cannot
    decide": augmented assignment, annotated assignment, the walrus operator,
    `for` targets, `with ... as`, and comprehension targets. None of them appear
    at any call site today — the point is that if one ever does, this checker
    says so instead of guessing.
    """

    if isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
        target = node.target
        return isinstance(target, ast.Name) and target.id == name
    if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
        return any(
            isinstance(n, ast.Name) and n.id == name for n in ast.walk(node.target)
        )
    if isinstance(node, ast.withitem):
        var = node.optional_vars
        return var is not None and any(
            isinstance(n, ast.Name) and n.id == name for n in ast.walk(var)
        )
    return False


def _resolve_name(name: str, scope: ast.AST) -> list[str] | None:
    """Values assigned to `name` inside `scope`, if ALL of them are decidable.

    Returns None — meaning "the caller must fail, loudly" — when any binding of
    this name uses a form this checker cannot evaluate. See `_rebinds`.
    """

    for node in ast.walk(scope):
        if _rebinds(node, name):
            return None

    found: list[str] = []
    for node in ast.walk(scope):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                values = _constant_strings(node.value)
                if values is None:
                    return None
                found.extend(values)
    return found or None


def _enclosing_function(tree: ast.AST, call: ast.Call) -> ast.AST:
    best: ast.AST = tree
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= call.lineno and call.lineno <= (node.end_lineno or node.lineno):
                if getattr(best, "lineno", -1) <= node.lineno:
                    best = node
    return best


def _collect() -> tuple[set[str], list[str]]:
    """(job types enqueued anywhere in backend/services, unresolvable sites)."""

    types: set[str] = set()
    unresolved: list[str] = []
    for path in sorted(_SERVICES.rglob("*.py")):
        if "/tests/" in str(path):
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for call in _enqueue_calls(tree):
            arg = next((kw.value for kw in call.keywords if kw.arg == "job_type"), None)
            if arg is None:
                unresolved.append(f"{path}:{call.lineno} — enqueue_outbox with no job_type= kwarg")
                continue
            values = _constant_strings(arg)
            if values is None and isinstance(arg, ast.Name):
                values = _resolve_name(arg.id, _enclosing_function(tree, call))
            if values is None:
                unresolved.append(
                    f"{path}:{call.lineno} — job_type= is a {type(arg).__name__} this "
                    f"checker cannot resolve"
                )
                continue
            types.update(values)
    return types, unresolved


def test_no_enqueue_site_hides_its_job_type_from_this_checker() -> None:
    """The checker must never SKIP a call site — that is how the bug happened."""

    _, unresolved = _collect()
    assert not unresolved, (
        "An `enqueue_outbox` call site's job_type could not be resolved statically:\n  "
        + "\n  ".join(unresolved)
        + "\n\nDo NOT relax this into a skip. A literal-shaped grep is what missed "
        "`late_refund_confirmation_email` in three separate artifacts. Either make the "
        "call site pass a literal, or teach `_constant_strings` the new shape in the "
        "same PR that introduces it."
    )


def test_every_enqueued_job_type_has_a_handler() -> None:
    types, unresolved = _collect()
    assert not unresolved, "resolve the sites above first"
    assert types, "no enqueue_outbox call sites found — the walker is broken, not the code"

    handlers = build_handlers(
        pool=None,  # type: ignore[arg-type]
        sender=None,  # type: ignore[arg-type]
        staff_page_sender=object(),  # type: ignore[arg-type]
    )
    missing = sorted(types - set(handlers))
    assert not missing, (
        f"{len(missing)} job_type(s) are enqueued by production code with no handler in "
        f"build_handlers: {missing}. They would be reported `unroutable` on every drain "
        f"pass and never dispatched."
    )


def test_the_checker_actually_sees_the_variable_call_site() -> None:
    """Pin the specific shape that defeated three counts.

    Without this, `_constant_strings`/`_resolve_name` could regress to
    literal-only and the two tests above would still pass — they would simply
    stop seeing this type, exactly as every grep did.
    """

    types, _ = _collect()
    assert "late_refund_confirmation_email" in types, (
        "the AST walker no longer resolves repository.py's conditional job_type — "
        "it has regressed to the literal-only behaviour this whole file exists to replace"
    )
    assert "practice_release" in types


@pytest.mark.parametrize(
    "source",
    [
        "await j.enqueue_outbox(conn, job_type=some_call())",
        "await j.enqueue_outbox(conn, job_type=PREFIX + name)",
        "await j.enqueue_outbox(conn, job_type=mapping[key])",
    ],
)
def test_checker_refuses_shapes_it_cannot_prove(source: str) -> None:
    """Guilt side: an unresolvable shape must come back unresolvable, not empty."""

    tree = ast.parse(source)
    call = _enqueue_calls(tree)[0]
    arg = next(kw.value for kw in call.keywords if kw.arg == "job_type")
    assert _constant_strings(arg) is None


UNEVALUABLE_SHAPES = [
    # THE ONE THAT WAS SILENTLY WRONG. `jt = "a"; jt += "b"` enqueues "ab"; the
    # first version of `_resolve_name` reported ["a"] and accepted it.
    'async def f():\n    jt = "a"\n    jt += "b"\n    await j.enqueue_outbox(c, job_type=jt)\n',
    # Walrus, for-target, with-as, annotated assignment. None appear at a call
    # site today; each must be UNRESOLVABLE rather than guessed.
    'async def f():\n    await j.enqueue_outbox(c, job_type=(jt := "w"))\n',
    'async def f():\n    for jt in ("a", "b"):\n        await j.enqueue_outbox(c, job_type=jt)\n',
    'async def f():\n    with ctx() as jt:\n        await j.enqueue_outbox(c, job_type=jt)\n',
    'async def f():\n    jt: str = compute()\n    await j.enqueue_outbox(c, job_type=jt)\n',
    # A single undecidable assignment poisons the whole name.
    'async def f():\n    jt = compute()\n    jt = "a"\n    await j.enqueue_outbox(c, job_type=jt)\n',
]


@pytest.mark.parametrize("source", UNEVALUABLE_SHAPES)
def test_a_name_this_checker_cannot_evaluate_is_never_guessed(source: str) -> None:
    """The ONLY unacceptable outcome is a confident WRONG value.

    Over-reporting is safe — an extra value demands a handler that is not needed
    and fails loudly. Under-reporting a value the code can actually produce is
    the silent miss this whole file exists to prevent, and the augmented
    assignment case above did exactly that until the checker was attacked.
    """

    tree = ast.parse(source)
    call = _enqueue_calls(tree)[0]
    arg = next(kw.value for kw in call.keywords if kw.arg == "job_type")
    values = _constant_strings(arg)
    if values is None and isinstance(arg, ast.Name):
        values = _resolve_name(arg.id, _enclosing_function(tree, call))
    assert values is None, (
        f"resolved to {values!r} — a value this checker cannot prove the code "
        f"produces. It must report unresolvable and fail loudly instead."
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('await j.enqueue_outbox(conn, job_type="a")', ["a"]),
        ('await j.enqueue_outbox(conn, job_type="a" if x else "b")', ["a", "b"]),
    ],
)
def test_checker_resolves_shapes_it_can_prove(source: str, expected: list[str]) -> None:
    """Innocence side: the shapes production uses must resolve, not fail."""

    tree = ast.parse(source)
    call = _enqueue_calls(tree)[0]
    arg = next(kw.value for kw in call.keywords if kw.arg == "job_type")
    assert _constant_strings(arg) == expected
