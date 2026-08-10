"""Guilt + innocence for the shared run verdict, and a pin that all eight use it.

The fixtures below are not invented: `_NB3_LAST_RUN` and `_NB2_0110_RUN` are the
shapes measured on Pro on 2026-08-07, the night the NotebookLM credential was
found expired — twelve consecutive nb3 runs with `source_count: 0` reported as
"completed successfully", and nb2's 01:10 run halting on the breaker it had just
tripped while exiting 0.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.run_verdict import error_markers, verdict

MODULES = [
    "pipeline.py",
    "nb3_pipeline.py",
    "nb4_pipeline.py",
    "nb5_pipeline.py",
    "nb6_pipeline.py",
    "nb7_pipeline.py",
    "nb8_pipeline.py",
    "nb10_pipeline.py",
]
PKG = Path(__file__).resolve().parents[1]

# --- the two shapes that were exiting 0 (measured on Pro, 2026-08-07) --------

_NB2_0110_RUN = {
    "run_id": "836b4bc3",
    "phases": {"preflight": {"passed": True}, "l1": {"success": False, "error": "nlm exited with code 1"}},
    "halted_at": "l1_circuit_open",
    "degradation": "DEGRADED_L1",
    "claims_total": 4750,
}

_NB3_LAST_RUN = {
    "phases": {
        "preflight": {"passed": True},
        "integration": {
            "new_claims": 2,
            "total_claims": 170,
            "source_count": 0,
            "notebook": "NB-3: Company Setup Indonesia",
            "status": "error_nlm_add",
        },
    },
    "degradation": "NOMINAL",
    "claims_total": 170,
}


def test_a_run_halted_on_its_own_breaker_is_a_failure():
    code, reason = verdict(_NB2_0110_RUN)
    assert code == 1
    assert "l1_circuit_open" in reason


def test_a_run_that_ingested_nothing_and_said_NOMINAL_is_a_failure():
    code, reason = verdict(_NB3_LAST_RUN)
    assert code == 1
    assert "error_nlm_add" in reason


def test_the_error_marker_is_found_however_deeply_it_is_nested():
    """A fixed key path would pass one pipeline's layout and miss the other's."""
    deep = {"phases": {"a": {"b": [{"status": "error_nlm_add"}]}}}
    assert error_markers(deep) == ["phases.a.b[0].status=error_nlm_add"]


def test_preflight_failure_still_fails_and_now_names_its_cause():
    code, reason = verdict(
        {"phases": {"preflight": {"passed": False}}, "halted_at": "preflight", "halt_reason": "cb_nlm"}
    )
    assert code == 1
    assert "cb_nlm" in reason


def test_an_unusable_summary_fails_loud():
    assert verdict(None)[0] == 1
    assert verdict({})[0] == 1


# --- innocence: the shapes that must stay green -----------------------------


def test_a_clean_run_passes():
    code, reason = verdict(
        {"phases": {"preflight": {"passed": True}, "l1": {"success": True}}, "claims_total": 12}
    )
    assert (code, reason) == (0, "completed")


def test_the_weekend_skip_is_a_healthy_no_op():
    """It halts, but on purpose. Failing it would fabricate a death every Sunday."""
    code, reason = verdict(
        {"phases": {"preflight": {"passed": False}}, "halted_at": "preflight", "halt_reason": "weekend"}
    )
    assert code == 0
    assert "weekend" in reason


def test_a_single_tolerated_query_failure_does_NOT_fail_the_run():
    """DECLARED LIMIT, not an oversight: an L1 miss below the breaker threshold
    still lets real work happen downstream. Trading the false green for a false
    red would get this guard disarmed. When it matters the breaker trips, and
    that sets halted_at — which IS caught, above."""
    code, _ = verdict(
        {
            "phases": {"preflight": {"passed": True}, "l1": {"success": False, "error": "one miss"}},
            "claims_total": 12,
        }
    )
    assert code == 0


def test_a_status_that_merely_contains_error_elsewhere_is_not_a_marker():
    """`status: no_errors` must not read as a failure (match the entity, #3)."""
    assert error_markers({"phases": {"x": {"status": "no_errors"}}}) == []


# --- the pin: all eight modules must actually USE it ------------------------


@pytest.mark.parametrize("name", MODULES)
def test_every_pipeline_module_uses_the_shared_verdict(name):
    """Eight copies of a corrected line would drift; one rule cannot.

    This is the check that would have caught the original defect: it was the
    SAME wrong line in all eight files, so fixing seven of them would look
    finished (W107 — the cure that goes to one member of a class).
    """
    src = (PKG / name).read_text()
    assert "run_verdict" in src, f"{name} does not import the shared verdict"
    assert re.search(r"\bverdict\s*\(", src), f"{name} imports it but never calls it"
    assert not re.search(
        r'sys\.exit\(\s*0 if result\.get\("phases"', src
    ), f"{name} still decides its exit code from pre-flight alone"


@pytest.mark.parametrize("name", MODULES)
def test_every_pipeline_module_keeps_a_main_that_exits(name):
    """Parses AND still has the entry point the wiring edited.

    A bare `ast.parse()` here asserted nothing — the anti-reward-hacking linter
    caught that on the way in, correctly: a rewrite that deleted main() would
    have passed it.
    """
    tree = ast.parse((PKG / name).read_text())
    mains = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main"]
    assert mains, f"{name} lost its main()"
    exits = [
        n
        for n in ast.walk(mains[0])
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "exit"
    ]
    assert exits, f"{name}.main() no longer exits — nothing would set its exit code"
