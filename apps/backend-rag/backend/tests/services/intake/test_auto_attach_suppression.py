"""Guilt+innocence tests for the per-batch auto-attach suppression (R3-6).

The drive contact auto-create program reroutes docs whose CLIENT CARDS were
minted from those very docs — any LEVA gate "corroboration" against them is
circular. The suppression is keyed on the batch pipeline_version and enforced
at the ONE chokepoint where all three gates fire, so it holds even with every
worker killswitch armed (the live worker runs armed — verified 2026-07-19).
"""

from __future__ import annotations

import pytest

from backend.services.intake import auto_attach, routing


def _proposal(pipeline_version: str) -> dict:
    # MIRRORS build_routing_proposal's REAL payload shape: pipeline_version at
    # the TOP LEVEL, not inside `routing` (round-4 gate caught the first draft
    # testing a nested shape that never occurs in production — W99). The
    # end-to-end proof through route_stage lives in test_intake_routing.py.
    return {
        "pipeline_version": pipeline_version,
        "routing": {"client_id": None},
        "entity_resolution": {
            "decision": routing.DECISION_AUTO_ATTACH,
            "candidates": [],
        },
    }


@pytest.mark.asyncio
async def test_suppressed_pipeline_version_never_evaluates_gates(monkeypatch):
    """Guilt: a suppressed tag returns a skip verdict WITHOUT touching any
    gate, killswitches notwithstanding."""

    async def _must_not_run(*a, **kw):  # pragma: no cover - failure path
        raise AssertionError("attach gate evaluated despite suppression")

    monkeypatch.setattr(auto_attach, "try_auto_attach", _must_not_run)
    monkeypatch.setattr(auto_attach, "try_direct_phone_auto_attach", _must_not_run)
    monkeypatch.setattr(auto_attach, "try_nameid_auto_attach", _must_not_run)
    # Armed like the live worker — suppression must not depend on flags OFF.
    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "true")
    monkeypatch.setenv("INTAKE_AUTO_ATTACH_ENABLED", "true")
    monkeypatch.setenv("INTAKE_NAMEID_AUTO_ATTACH_ENABLED", "true")

    verdict = await routing._try_auto_attach_after_route(
        proposal_id=123,
        proposal=_proposal("v2.3-drive-autocreate"),
        pool=None,  # unused: suppression short-circuits before any DB access
        sender_phone=None,
        source_context=None,
        effective_status="review_pending",
    )

    assert verdict == {
        "skipped": "suppressed_pipeline_version",
        "pipeline_version": "v2.3-drive-autocreate",
    }


@pytest.mark.asyncio
async def test_normal_pipeline_version_still_reaches_gates(monkeypatch):
    """Innocence: a normal tag evaluates the gates exactly as before — the
    suppression must not disarm the live LEVA wire."""
    sentinel = {"committed": False, "skipped": "kill_switch_off"}
    calls: list[str] = []

    async def _gate(*a, **kw):
        calls.append("try_auto_attach")
        return sentinel

    monkeypatch.setattr(auto_attach, "try_auto_attach", _gate)

    verdict = await routing._try_auto_attach_after_route(
        proposal_id=124,
        proposal=_proposal("v2.2-m227-folder"),
        pool=None,
        sender_phone=None,
        source_context=None,
        effective_status="review_pending",
    )

    assert calls == ["try_auto_attach"]
    assert verdict is sentinel


@pytest.mark.asyncio
async def test_missing_pipeline_version_is_not_suppressed(monkeypatch):
    """Innocence (edge): an absent tag never matches the suppression set."""
    sentinel = {"committed": False, "skipped": "kill_switch_off"}

    async def _gate(*a, **kw):
        return sentinel

    monkeypatch.setattr(auto_attach, "try_auto_attach", _gate)

    proposal = _proposal("")
    del proposal["pipeline_version"]
    verdict = await routing._try_auto_attach_after_route(
        proposal_id=125,
        proposal=proposal,
        pool=None,
        sender_phone=None,
        source_context=None,
        effective_status="review_pending",
    )

    assert verdict is sentinel


@pytest.mark.asyncio
async def test_nested_routing_tag_also_suppresses(monkeypatch):
    """Tolerance: a hand-built payload carrying the tag inside `routing`
    (older draft shape) is still suppressed — belt for non-builder callers."""

    async def _must_not_run(*a, **kw):  # pragma: no cover - failure path
        raise AssertionError("attach gate evaluated despite suppression")

    monkeypatch.setattr(auto_attach, "try_auto_attach", _must_not_run)

    proposal = _proposal("")
    del proposal["pipeline_version"]
    proposal["routing"]["pipeline_version"] = "v2.3-drive-autocreate"
    verdict = await routing._try_auto_attach_after_route(
        proposal_id=126,
        proposal=proposal,
        pool=None,
        sender_phone=None,
        source_context=None,
        effective_status="review_pending",
    )

    assert verdict == {
        "skipped": "suppressed_pipeline_version",
        "pipeline_version": "v2.3-drive-autocreate",
    }


async def test_batch_qualified_tag_also_suppresses(monkeypatch):
    """R10-2a: the autocreate reroute stamps ``v2.3-drive-autocreate:<batch>``
    so a generation is attributable to ONE batch — the qualified tag must
    stay suppressed exactly like the bare one."""

    async def _must_not_run(*a, **kw):  # pragma: no cover - failure path
        raise AssertionError("attach gate evaluated despite suppression")

    monkeypatch.setattr(auto_attach, "try_auto_attach", _must_not_run)

    tag = "v2.3-drive-autocreate:w1-20260720-abcd1234"
    verdict = await routing._try_auto_attach_after_route(
        proposal_id=127,
        proposal=_proposal(tag),
        pool=None,
        sender_phone=None,
        source_context=None,
        effective_status="review_pending",
    )

    assert verdict == {
        "skipped": "suppressed_pipeline_version",
        "pipeline_version": tag,
    }


def test_similar_but_unqualified_tag_is_not_suppressed():
    """Innocence (guard family #3): only the exact tag or ``tag:batch`` is
    suppressed — a merely similar tag without the ``:`` separator is NOT."""
    assert routing._pipeline_version_suppressed("v2.3-drive-autocreate")
    assert routing._pipeline_version_suppressed("v2.3-drive-autocreate:w1-x")
    assert not routing._pipeline_version_suppressed("v2.3-drive-autocreate-other")
    assert not routing._pipeline_version_suppressed("v2.3-drive")
    assert not routing._pipeline_version_suppressed("")
