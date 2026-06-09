#!/usr/bin/env python3
"""Falsifiable gate tests for the P6 parallelize-hypothesis gate.

Maps 1:1 to the falsifiable gates in
``research/operations/specs/P6-parallelize-gate.md`` §6:

* G1 — sequential / single-artifact task → SERIAL (not fan-out)
* G2 — revocability: shared artifact observed at runtime → re-serialize
* G3 — coder on the SAME artifact → rejected (serial)
* G4 — high merge cost (artifact overlap / no contract) → serial
* G5 — coder cap respected (streams > cap → serial)

Plus the headline invariants: the DEFAULT (no signal) is SERIAL, and the
orchestrator's ``route_after_checkpoint`` honours the hypothesis (single node
when serial, full fan-out when parallel).

Run (from scripts/, with the backend venv active)::

    PYTHONPATH=<repo>/apps/backend-rag:<repo>/scripts \\
        python -m pytest test_federation_parallelize_gate.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# scripts/ on path so the pure sibling module imports regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))
# apps/backend-rag on path so the orchestrator's optional observability import resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "backend-rag"))

import federation_parallelize as fp  # noqa: E402
from federation_parallelize import (  # noqa: E402
    DEFAULT_CODER_CAP,
    MergeCost,
    ParallelizeDecision,
    parallelizable_hypothesis,
    revoke_if_shared_artifact,
)


# ─────────────────────────────────────────────────────────────────────────────
# Headline invariant: the DEFAULT is SERIAL
# ─────────────────────────────────────────────────────────────────────────────
def test_default_no_signal_is_serial():
    """No classification signal at all → hypothesis False (serial default)."""
    d = parallelizable_hypothesis({}, "do something")
    assert d.hypothesis is False
    assert d.revocable is True


def test_single_specialist_is_serial():
    """One specialist is not parallelism — nothing to fan out → serial."""
    d = parallelizable_hypothesis({"needs_search": True}, "look up the KBLI code")
    assert d.hypothesis is False
    assert d.estimated_streams < fp.MIN_PARALLEL_STREAMS


# ─────────────────────────────────────────────────────────────────────────────
# G1 — sequential / single-artifact task → SERIAL
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "task",
    [
        "linear refactor of this file",
        "fix the typo in this function",
        "one-line fix with known cause",
        "rename this module's helper",
        "refactor a single file end to end",
    ],
)
def test_g1_single_artifact_tasks_serial(task):
    """A task described as a single linear artifact edit must be serial."""
    # Even if (wrongly) multiple flags are set, the single-artifact guard wins.
    classification = {"needs_search": True, "needs_explore": True}
    d = parallelizable_hypothesis(classification, task)
    assert d.hypothesis is False
    assert "G1" in d.reason or "single-artifact" in d.reason


# ─────────────────────────────────────────────────────────────────────────────
# G3 — coder on the SAME artifact → rejected (serial)
# ─────────────────────────────────────────────────────────────────────────────
def test_g3_same_artifact_twice_is_serial():
    """A task touching the SAME artifact twice → hypothesis False (the core G case).

    Two distinct streams that both resolve to the same file label → overlap →
    HIGH merge cost → serial. This is the 'coder on the same artifact' prohibition
    expressed through artifact overlap.
    """
    classification = {
        "needs_search": True,
        "needs_explore": True,
        "domains": [],  # no domain labels → file tokens are the only signal
    }
    # Both 'streams' would touch scripts/foo.py — the SAME artifact.
    task = "edit scripts/foo.py and also patch scripts/foo.py again"
    d = parallelizable_hypothesis(classification, task)
    assert d.hypothesis is False


def test_g3_explicit_same_file_phrase_serial():
    """'the same file' / single-artifact phrasing → serial regardless of flags."""
    d = parallelizable_hypothesis(
        {"needs_search": True, "needs_sandbox": True},
        "two changes to the same file",
    )
    assert d.hypothesis is False


# ─────────────────────────────────────────────────────────────────────────────
# G4 — high merge cost (overlap / no contract) → serial; net-positive → parallel
# ─────────────────────────────────────────────────────────────────────────────
def test_g4_overlapping_files_high_cost_serial():
    """Two streams colliding on one artifact → HIGH merge cost → serial."""
    cost = fp._estimate_merge_cost(
        ["file:a.py"], streams=2, has_explicit_contract=False
    )
    assert cost == MergeCost.HIGH


def test_g4_disjoint_with_contract_low_cost():
    """Disjoint artifacts + an explicit contract → LOW merge cost (composable)."""
    cost = fp._estimate_merge_cost(
        ["domain:visa", "domain:tax"], streams=2, has_explicit_contract=True
    )
    assert cost == MergeCost.LOW


def test_g4_disjoint_no_contract_med_cost():
    cost = fp._estimate_merge_cost(
        ["domain:visa", "domain:tax"], streams=2, has_explicit_contract=False
    )
    assert cost == MergeCost.MED


# ─────────────────────────────────────────────────────────────────────────────
# The positive case: breadth / disjoint specialists → PARALLEL (revocable)
# ─────────────────────────────────────────────────────────────────────────────
def test_breadth_research_is_parallel():
    """Breadth-first research (the +90.2% regime) → parallel hypothesis True."""
    d = parallelizable_hypothesis(
        {"needs_search": True, "needs_explore": True, "domains": ["visa", "tax"]},
        "research and compare approaches across multiple angles",
    )
    assert d.hypothesis is True
    assert d.revocable is True
    assert d.estimated_streams >= fp.MIN_PARALLEL_STREAMS


def test_disjoint_specialists_with_contract_parallel():
    """Role-distinct specialists on disjoint domains + contract → parallel."""
    classification = {
        "needs_search": True,
        "needs_explore": True,
        "domains": ["visa", "tax"],
    }
    d = parallelizable_hypothesis(
        classification, "gather visa rules and tax rules", has_explicit_contract=True
    )
    assert d.hypothesis is True
    assert d.estimated_merge_cost in (MergeCost.LOW, MergeCost.MED)


# ─────────────────────────────────────────────────────────────────────────────
# G5 — coder cap respected
# ─────────────────────────────────────────────────────────────────────────────
def test_g5_streams_over_cap_serial():
    """More disjoint streams than the cap → serial (cap is a ceiling, not a target)."""
    classification = {
        "needs_search": True,
        "needs_explore": True,
        "needs_sandbox": True,
        "domains": ["visa", "tax", "company"],
    }
    d = parallelizable_hypothesis(
        classification, "research three disjoint domains", coder_cap=2
    )
    assert d.hypothesis is False
    assert "cap" in d.reason.lower() or "G5" in d.reason


def test_g5_default_cap_value():
    """The prior cap is the Google 3-4 ceiling (4), per spec §3.3."""
    assert DEFAULT_CODER_CAP == 4


# ─────────────────────────────────────────────────────────────────────────────
# G2 — revocability: shared artifact observed at runtime → re-serialize
# ─────────────────────────────────────────────────────────────────────────────
def test_g2_revoke_on_contention():
    """A True hypothesis is downgraded to serial when a hot-zone is contended."""
    parallel = ParallelizeDecision(
        hypothesis=True,
        reason="ok",
        estimated_files_touched=["domain:visa", "domain:tax"],
        estimated_merge_cost=MergeCost.LOW,
        estimated_streams=2,
    )
    revoked = revoke_if_shared_artifact(parallel, ["scripts/shared.py"])
    assert revoked.hypothesis is False
    assert "REVOKED" in revoked.reason


def test_g2_no_contention_is_noop():
    """No contention → the decision is unchanged."""
    parallel = ParallelizeDecision(hypothesis=True, reason="ok", estimated_streams=2)
    assert revoke_if_shared_artifact(parallel, []) is parallel


def test_g2_revoke_never_upgrades_serial():
    """Revocation is one-directional: a serial decision stays serial."""
    serial = ParallelizeDecision(hypothesis=False, reason="serial")
    assert revoke_if_shared_artifact(serial, ["scripts/x.py"]) is serial


# ─────────────────────────────────────────────────────────────────────────────
# Serialisation of the decision (it crosses audit.jsonl / Telegram boundaries)
# ─────────────────────────────────────────────────────────────────────────────
def test_decision_fields_json_safe():
    """as_classification_fields() must emit JSON-safe primitives (enum → str)."""
    import json

    d = parallelizable_hypothesis(
        {"needs_search": True, "needs_explore": True, "domains": ["visa", "tax"]},
        "research multiple angles",
    )
    fields = d.as_classification_fields()
    json.dumps(fields)  # must not raise
    assert fields["parallelizable_hypothesis"] is True
    assert isinstance(fields["estimated_merge_cost"], str)
    assert fields["parallelizable_revocable"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator integration: route_after_checkpoint honours the hypothesis
# ─────────────────────────────────────────────────────────────────────────────
def test_route_serial_runs_single_node():
    """Serial default: multiple specialists requested → exactly ONE node routed."""
    import federation_orchestrator as fo

    classification = {
        "needs_search": True,
        "needs_explore": True,
        "parallelizable_hypothesis": False,
    }
    route = fo.route_after_checkpoint({"classification": classification})
    assert route == ["search"]  # single node, deterministic priority


def test_route_parallel_fans_out():
    """Parallel hypothesis True → full matched-specialist fan-out preserved."""
    import federation_orchestrator as fo

    classification = {
        "needs_search": True,
        "needs_explore": True,
        "needs_sandbox": True,
        "parallelizable_hypothesis": True,
    }
    route = fo.route_after_checkpoint({"classification": classification})
    assert route == ["search", "explore", "sandbox"]


def test_route_no_specialist_goes_to_assemble():
    import federation_orchestrator as fo

    route = fo.route_after_checkpoint({"classification": {}})
    assert route == ["assemble"]


def test_route_missing_hypothesis_defaults_serial():
    """If the hypothesis key is absent entirely, the route must still be serial."""
    import federation_orchestrator as fo

    classification = {"needs_search": True, "needs_explore": True}  # no hypothesis key
    route = fo.route_after_checkpoint({"classification": classification})
    assert len(route) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
