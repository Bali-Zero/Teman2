"""A pipeline that deliberately did not run must not report a failure (2026-08-09).

TRAUMA. #3742 replaced eight copies of `sys.exit(0 if preflight passed else 1)`
with one shared `verdict()`, and taught it that an intentional calendar skip is
a healthy no-op. It wired the marker into **one** of the eight — `pipeline.py`
(nb2), the one that had bitten. Measured live on Pro the morning this was
written, both runs correct, one of them shouting:

    nb2, Sunday, weekend guard   -> WRAPPER_RC=0, zero Telegram sends
    nb3, Sunday, sunday guard    -> exit 1, P0 "NB-3 Company Setup pipeline
                                    FAILED (exit 1) — check <log>"

Before #3742 that same false exit fed the whole chain: on 2026-07-11 and
2026-07-18 — two Saturdays whose nb2 log contains nothing but "nlm CLI
available", all breakers CLOSED, "Weekend — pipeline skipped" — the DLQ
autopilot spent three repair attempts on a pipeline with nothing wrong with it
and then declared `TERMINAL`. Three alerts each Saturday for a healthy no-op.

The seven Sunday guards are cron-unreachable today (`45 2 * * 1-6` is Mon–Sat),
which is exactly why nobody noticed: the defect is latent until someone runs a
catch-up by hand, or moves one schedule to `* * *`. Latent is not absent.

This file is the class guard, not seven fixes: superscar #2/W107 — "I cured ONE
wrapper out of FIVE and called the disease closed". It reads the real modules,
so a ninth pipeline copied from any of these fails here until its skip is
marked with something `verdict()` actually honours.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.run_verdict import (
    SKIP_PREFIX,
    is_intentional_skip,
    verdict,
)

PKG = Path(__file__).resolve().parent.parent

#: Every module that owns a pipeline `run()`. Derived from disk rather than
#: hardcoded: a list is a thing you forget to extend, which is the defect.
PIPELINES = sorted(
    p.name
    for p in PKG.glob("*pipeline*.py")
    if "_preflight" in p.read_text() and "class " in p.read_text()
)


def _tree(name: str) -> ast.Module:
    return ast.parse((PKG / name).read_text(), filename=name)


def _skip_branch_reasons(tree: ast.Module) -> list[str | None]:
    """The literal assigned to `self._halt_reason` inside each calendar-skip
    branch — `None` where the branch sets nothing at all.

    Anchored on the `logger.*("... pipeline skipped")` call that IS the branch,
    not on a weekday expression: `weekday()`, `is_sunday` and `is_weekend` are
    three spellings of one intent, and matching the spelling is how a guard
    starts judging form instead of entity (superscar #3).
    """
    out: list[str | None] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
        announces_skip = any(
            isinstance(c.func, ast.Attribute)
            and c.args
            and isinstance(c.args[0], ast.Constant)
            and isinstance(c.args[0].value, str)
            and "pipeline skipped" in c.args[0].value
            for c in calls
        )
        if not announces_skip:
            continue
        reason: str | None = None
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Assign) or not isinstance(sub.value, ast.Constant):
                continue
            for tgt in sub.targets:
                if (
                    isinstance(tgt, ast.Attribute)
                    and tgt.attr == "_halt_reason"
                    and isinstance(tgt.value, ast.Name)
                    and tgt.value.id == "self"
                ):
                    reason = sub.value.value
        out.append(reason)
    return out


# ── the class: every pipeline, read from disk ────────────────────────────────


def test_the_class_is_not_empty():
    """A discovery bug that finds nothing would make every test below vacuous."""
    assert len(PIPELINES) >= 8, PIPELINES


@pytest.mark.parametrize("module", PIPELINES)
def test_every_calendar_skip_is_marked_and_the_verdict_honours_it(module):
    reasons = _skip_branch_reasons(_tree(module))
    assert reasons, f"{module}: no calendar-skip branch found — did the anchor move?"
    for reason in reasons:
        assert reason is not None, (
            f"{module}: its calendar-skip branch returns False without setting "
            f"self._halt_reason, so verdict() reads a deliberate no-op as a dead "
            f"run and the wrapper fires a P0 saying FAILED."
        )
        assert is_intentional_skip(reason), (
            f"{module}: marks its skip {reason!r}, which verdict() does not "
            f"honour — use the {SKIP_PREFIX!r} namespace."
        )


@pytest.mark.parametrize("module", PIPELINES)
def test_every_pipeline_carries_the_marker_into_its_summary(module):
    """Setting `_halt_reason` is useless if `run()` never puts it in the summary.

    verdict() only ever sees the summary; a module that marks the skip and drops
    it on the floor exits 1 exactly as before, and both halves look correct in
    isolation.
    """
    src = (PKG / module).read_text()
    assert '"halt_reason"' in src, (
        f"{module}: sets no summary['halt_reason'], so the marker never reaches verdict()"
    )


# ── the rule itself: guilt and innocence ─────────────────────────────────────


def _halted(reason):
    """The summary shape run() returns when pre-flight stops it."""
    return {"phases": {"preflight": {"passed": False}}, "halted_at": "preflight",
            "halt_reason": reason}


@pytest.mark.parametrize("reason", ["skip:sunday", "skip:weekend", "skip:holiday", "weekend"])
def test_an_intentional_skip_exits_zero(reason):
    code, why = verdict(_halted(reason))
    assert code == 0, why
    assert reason in why, "the verdict must name its own reason"


@pytest.mark.parametrize("reason", ["l1_circuit_open", "nlm_unavailable", "", None])
def test_a_real_halt_still_fails(reason):
    """Innocence. These are reasons this repo's pipelines genuinely emit, not
    strings invented here — an innocence check built from your own new objects
    confirms your convention, not reality (W116)."""
    code, why = verdict(_halted(reason))
    assert code == 1, why
    assert "pre-flight failed" in why


def test_a_skip_shaped_string_in_the_wrong_field_does_not_excuse_a_failure():
    """`skip:` is only meaningful as the halt_reason. A phase that happens to
    contain the word must not buy a green run."""
    summary = {"phases": {"preflight": {"passed": False}, "l1": {"note": "skip:sunday"}},
               "halted_at": "preflight"}
    assert verdict(summary)[0] == 1


def test_a_completed_run_is_unaffected():
    summary = {"phases": {"preflight": {"passed": True}}}
    assert verdict(summary) == (0, "completed")


def test_an_error_marker_still_beats_a_clean_preflight():
    summary = {"phases": {"preflight": {"passed": True}, "add": {"status": "error_nlm_add"}}}
    code, why = verdict(summary)
    assert code == 1 and "error_nlm_add" in why


def test_is_intentional_skip_rejects_non_strings():
    for value in (None, 0, 1, True, [], {}, object()):
        assert is_intentional_skip(value) is False
