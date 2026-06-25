"""Tests for gap consumer — reads nexus:gaps and dispatches agents."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from mata_garuda.workers.gap_consumer import (
    GAP_DISPATCH,
    _extract_terminal_case_status,
    _default_dispatch_agent,
    process_gap,
    run_gap_consumer,
)
from mata_garuda.workers.gap_legacy import consume_unmapped_counter


@pytest.fixture(autouse=True)
def _reset_unmapped_counter():
    """Counter state must not leak across consumer tests."""
    consume_unmapped_counter()
    yield
    consume_unmapped_counter()


def test_gap_dispatch_agent_names_match_registry():
    """Every non-None GAP_DISPATCH value must be a name in the agent registry.

    Regression guard for C.6 (2026-05-16): GAP_DISPATCH had "regulation_watcher"
    while the registry name was "Regulation Watcher" — every gap routed to
    that agent failed silently with "agent not registered". Symptom only
    surfaced AFTER C.5 fixed the parser; before C.5 the routing never ran.
    """
    import mata_garuda.agents  # noqa: F401 — populate @register_agent registry
    from mata_garuda.registry import get_agent

    for gap_type, agent_name in GAP_DISPATCH.items():
        if agent_name is None:
            continue  # Phase 2 deferred or DLQ — no agent expected
        agent = get_agent(agent_name)
        assert agent is not None, (
            f"GAP_DISPATCH[{gap_type!r}] = {agent_name!r} but no agent with "
            f"that name is registered. Either register the agent or fix the "
            f"name in GAP_DISPATCH to match @register_agent(name=...)."
        )


def test_gap_dispatch_table_complete():
    """8 canonical gap types + 2 explicit DLQ slots (C.4 2026-05-16)."""
    expected = {
        # Canonical agent-targeted
        "gap.missing_nip",
        "gap.missing_lhkpn",
        "gap.missing_angkatan",
        "gap.stale_official",
        "gap.orphan_org",
        "gap.missing_office",
        "gap.kanim_struktur",
        "gap.missing_procurement",
        # C.4 explicit DLQ — no agent target by design
        "gap.dlq:phone",
        "gap.dlq:profile",
    }
    assert set(GAP_DISPATCH.keys()) == expected
    # 7 routable, 3 None (1 phase-2 deferred + 2 DLQ)
    mapped = {k for k, v in GAP_DISPATCH.items() if v is not None}
    assert "gap.missing_procurement" not in mapped
    assert "gap.dlq:phone" not in mapped
    assert "gap.dlq:profile" not in mapped
    assert len(mapped) == 7


def test_process_gap_skips_unmapped_phase2():
    """Unmapped gap (Phase 2) is skipped + acked."""
    fake_dispatch = MagicMock()
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="1-0",
        gap_type="gap.missing_procurement",
        payload={"x": 1},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert result == {"status": "skipped", "agent": None}
    fake_dispatch.assert_not_called()
    fake_xack.assert_called_once()


def test_process_gap_unknown_type_skips_with_ack():
    """Unknown gap type is logged and acked (no infinite loop)."""
    fake_dispatch = MagicMock()
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="2-0",
        gap_type="gap.totally_unknown",
        payload={},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert result["status"] == "unknown"
    fake_dispatch.assert_not_called()
    fake_xack.assert_called_once()


def test_terminal_case_status_ignores_intermediate_false_payload():
    """Tool payloads with case_resolved=False are not terminal success."""
    messages = [
        {"role": "tool", "content": "[harvest] {'case_resolved': False}"},
        {"role": "tool", "content": "Case not resolved. Reason: no NIP. Insight: stop"},
    ]

    resolved, reason = _extract_terminal_case_status(messages)

    assert resolved is False
    assert "Case not resolved" in reason


def test_terminal_case_status_requires_explicit_status_tool():
    """A run without case_resolved/case_not_resolved is a failure signal."""
    resolved, reason = _extract_terminal_case_status([
        {"role": "assistant", "content": "I stopped without calling a status tool."}
    ])

    assert resolved is False
    assert reason == "missing_terminal_case_status"


def test_process_gap_skips_lhkpn_missing_nip_without_dispatch():
    """gap.missing_nip is structurally unresolvable in the current KPK portal."""
    fake_dispatch = MagicMock()
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="3-0",
        gap_type="gap.missing_nip",
        payload={"person_name": "Budi"},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    fake_dispatch.assert_not_called()
    fake_xack.assert_called_once()
    assert result["status"] == "skipped"
    assert result["agent"] == "lhkpn_harvester"
    assert result["reason"] == "lhkpn_portal_search_does_not_return_nip"


def test_process_gap_skips_lhkpn_missing_lhkpn_without_nip():
    """gap.missing_lhkpn needs a NIP before it is worth dispatching."""
    fake_dispatch = MagicMock()
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="3-1",
        gap_type="gap.missing_lhkpn",
        payload={"entity_name": "redacted", "entity_nip": ""},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    fake_dispatch.assert_not_called()
    fake_xack.assert_called_once()
    assert result["status"] == "skipped"
    assert result["reason"] == "lhkpn_profile_fetch_requires_existing_nip"


def test_process_gap_skips_lhkpn_missing_lhkpn_without_name():
    """The current KPK portal searches by name, not by NIP alone."""
    fake_dispatch = MagicMock()
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="3-2",
        gap_type="gap.missing_lhkpn",
        payload={"entity_nip": "123"},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    fake_dispatch.assert_not_called()
    assert result["status"] == "skipped"
    assert result["reason"] == "lhkpn_portal_search_requires_person_name"
    fake_xack.assert_called_once()


def test_process_gap_resolves_lhkpn_known_person_directly(monkeypatch):
    """Name + NIP LHKPN gaps use the local scraper tool, not the LLM dispatch."""
    fake_dispatch = MagicMock()
    fake_xack = MagicMock()

    def fake_harvest_lhkpn_for_person(name: str, nip: str) -> dict[str, object]:
        assert name == "Redacted Official"
        assert nip == "123"
        return {"case_resolved": True, "msg_id": "raw-1"}

    monkeypatch.setattr(
        "mata_garuda.agents.lhkpn_harvester.harvest_lhkpn_for_person",
        fake_harvest_lhkpn_for_person,
    )

    result = process_gap(
        msg_id="3-4",
        gap_type="gap.missing_lhkpn",
        payload={"entity_name": "Redacted Official", "entity_nip": "123"},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    fake_dispatch.assert_not_called()
    fake_xack.assert_called_once()
    assert result["status"] == "resolved"
    assert result["agent"] == "lhkpn_harvester"


def test_process_gap_lhkpn_direct_failure_does_not_ack(monkeypatch):
    """A failed direct LHKPN lookup must remain pending for retry/audit."""
    fake_dispatch = MagicMock()
    fake_xack = MagicMock()

    monkeypatch.setattr(
        "mata_garuda.agents.lhkpn_harvester.harvest_lhkpn_for_person",
        lambda name, nip: {"case_resolved": False, "reason": "no search results"},
    )

    result = process_gap(
        msg_id="3-5",
        gap_type="gap.missing_lhkpn",
        payload={"entity_name": "Redacted Official", "entity_nip": "123"},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    fake_dispatch.assert_not_called()
    fake_xack.assert_not_called()
    assert result["status"] == "failed"
    assert result["reason"] == "no search results"


def test_process_gap_skips_lhkpn_missing_angkatan():
    """Current LHKPN source cannot derive angkatan, so avoid retry loops."""
    fake_dispatch = MagicMock()
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="3-3",
        gap_type="gap.missing_angkatan",
        payload={"entity_name": "redacted", "entity_nip": "123"},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    fake_dispatch.assert_not_called()
    fake_xack.assert_called_once()
    assert result["status"] == "skipped"
    assert result["reason"] == "lhkpn_portal_does_not_expose_angkatan"


def test_default_dispatch_forces_non_frontier_model(monkeypatch):
    """Automated gap dispatch must not inherit Claude defaults from agents."""
    import importlib

    from mata_garuda.types import Agent, Response

    captured: dict[str, Agent] = {}
    registry_agent = Agent(name="Regulation Watcher", model="claude")

    class _FakeKB:
        def close(self):
            pass

    def fake_get_agent(name: str) -> Agent:
        assert name == "Regulation Watcher"
        return registry_agent

    def fake_run_with_lamarckian_feedback(agent: Agent, query: str, **kwargs) -> Response:
        captured["agent"] = agent
        return Response(messages=[{"role": "tool", "content": "Case resolved. The result is: ok"}])

    registry_module = importlib.import_module("mata_garuda.registry")
    knowledge_module = importlib.import_module("mata_garuda.runtime.knowledge")
    lamarckian_module = importlib.import_module("mata_garuda.runtime.lamarckian")

    monkeypatch.setattr(registry_module, "get_agent", fake_get_agent)
    monkeypatch.setattr(knowledge_module, "KnowledgeBase", _FakeKB)
    monkeypatch.setattr(
        lamarckian_module,
        "run_with_lamarckian_feedback",
        fake_run_with_lamarckian_feedback,
    )

    result = _default_dispatch_agent("Regulation Watcher", {"_gap_type": "gap.stale_official"})

    assert result["case_resolved"] is True
    assert captured["agent"].model == "ollama:qwen3.5:9b"
    assert registry_agent.model == "claude"


def test_process_gap_dispatches_regulation_watcher_for_stale_official():
    """gap.stale_official → regulation_watcher."""
    fake_dispatch = MagicMock(return_value={"case_resolved": True})
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="4-0",
        gap_type="gap.stale_official",
        payload={"nip": "123"},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    # GAP_DISPATCH must use the canonical registry name (with capital + space),
    # not the snake_case alias. Mismatch caused 8h of "agent not registered"
    # failures on 2026-05-16 — see C.6 commit message.
    assert fake_dispatch.call_args.kwargs["agent_name"] == "Regulation Watcher"
    assert result["status"] == "resolved"


def test_process_gap_does_not_ack_on_case_not_resolved():
    """case_not_resolved: do NOT ack — let it redeliver."""
    fake_dispatch = MagicMock(return_value={"case_resolved": False, "reason": "403"})
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="5-0",
        gap_type="gap.missing_lhkpn",
        payload={"entity_name": "redacted", "entity_nip": "123"},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert result["status"] == "failed"
    fake_xack.assert_not_called()


def test_process_gap_dispatch_exception_caught_no_ack():
    """Exception from dispatcher is caught and logged — no crash, no ack."""
    fake_dispatch = MagicMock(side_effect=RuntimeError("boom"))
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="6-0",
        gap_type="gap.stale_official",
        payload={"entity_nip": "123"},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert result["status"] == "error"
    fake_xack.assert_not_called()


def test_run_gap_consumer_processes_batch():
    """run_gap_consumer reads N messages and processes each."""
    msgs = [
        {"id": "10-0", "data": {
            "id": "uuid-10", "type": "gap.missing_lhkpn", "source": "gap_detector",
            "timestamp": "2026-04-16T00:00:00+08:00", "priority": "3",
            "payload": '{"entity_nip": "123"}',
        }},
        {"id": "11-0", "data": {
            "id": "uuid-11", "type": "gap.stale_official", "source": "gap_detector",
            "timestamp": "2026-04-16T00:00:00+08:00", "priority": "3",
            "payload": '{"nip": "123"}',
        }},
    ]

    fake_read = MagicMock(return_value=msgs)
    fake_dispatch = MagicMock(return_value={"case_resolved": True})
    fake_xack = MagicMock()

    stats = run_gap_consumer(
        max_items=10,
        stream_read=fake_read,
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert stats["read"] == 2
    assert stats["resolved"] == 1
    assert stats["skipped"] == 1
    assert stats["failed"] == 0
    assert fake_dispatch.call_count == 1
    assert fake_xack.call_count == 2


def test_run_gap_consumer_empty_stream_no_op():
    """If stream is empty, return zero stats."""
    fake_read = MagicMock(return_value=[])
    fake_dispatch = MagicMock()
    fake_xack = MagicMock()

    stats = run_gap_consumer(
        max_items=10,
        stream_read=fake_read,
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert stats["read"] == 0
    fake_dispatch.assert_not_called()
    fake_xack.assert_not_called()


def test_run_gap_consumer_handles_invalid_json_payload():
    """Invalid JSON in payload field → empty dict, still processes."""
    msgs = [
        {"id": "12-0", "data": {
            "id": "uuid-12", "type": "gap.stale_official", "source": "gap_detector",
            "timestamp": "2026-04-16T00:00:00+08:00", "priority": "3",
            "payload": "not json {{{",
        }},
    ]
    fake_read = MagicMock(return_value=msgs)
    fake_dispatch = MagicMock(return_value={"case_resolved": True})
    fake_xack = MagicMock()

    stats = run_gap_consumer(
        max_items=10,
        stream_read=fake_read,
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert stats["read"] == 1
    assert stats["resolved"] == 1
    # dispatch was called even with empty payload (only _gap_type added)
    fake_dispatch.assert_called_once()
    payload = fake_dispatch.call_args.kwargs["payload"]
    assert payload == {"_gap_type": "gap.stale_official"}


# ── legacy stream end-to-end (coerce + dispatch) ───────────────────────


def test_run_gap_consumer_skips_legacy_missing_nip_without_dispatch():
    """Legacy entry (gap_type=missing_attribute, attribute=nip) reaches
    a terminal LHKPN skip because KPK search no longer returns NIP."""
    msgs = [
        {
            "id": "100-0",
            "data": {
                "request_id": "abc",
                "gap_type": "missing_attribute",
                "attribute": "nip",
                "entity_type": "Official",
                "entity_name": "redacted",
                "entity_nip": "",
                "priority": "2",
                "ttl_seconds": "86400",
                "created_at": "2026-04-10T02:54:14",
            },
        },
    ]
    fake_read = MagicMock(return_value=msgs)
    fake_dispatch = MagicMock(return_value={"case_resolved": True})
    fake_xack = MagicMock()

    stats = run_gap_consumer(
        max_items=10,
        stream_read=fake_read,
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert stats["read"] == 1
    assert stats["skipped"] == 1
    fake_dispatch.assert_not_called()
    fake_xack.assert_called_once()


def test_run_gap_consumer_drains_unmappable_legacy_with_ack():
    """Legacy entry with no canonical mapping is acked + counted as skipped."""
    msgs = [
        {
            "id": "101-0",
            "data": {
                "request_id": "xyz",
                "gap_type": "missing_attribute",
                "attribute": "profile",
                "entity_name": "Foo",
            },
        },
    ]
    fake_read = MagicMock(return_value=msgs)
    fake_dispatch = MagicMock()
    fake_xack = MagicMock()

    stats = run_gap_consumer(
        max_items=10,
        stream_read=fake_read,
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert stats["read"] == 1
    assert stats["skipped"] == 1
    assert stats["resolved"] == 0
    fake_dispatch.assert_not_called()
    fake_xack.assert_called_once_with("nexus:gaps", "gap-consumer", "101-0")


def test_run_gap_consumer_mixed_canonical_and_legacy_batch():
    """Batch with both shapes: each routed correctly."""
    msgs = [
        # canonical
        {"id": "200-0", "data": {
            "id": "uuid-1", "type": "gap.stale_official", "source": "gap_detector",
            "timestamp": "2026-04-16T00:00:00+08:00", "priority": "3",
            "payload": '{"nip": "999"}',
        }},
        # legacy mappable
        {"id": "201-0", "data": {
            "gap_type": "missing_attribute", "attribute": "lhkpn",
            "entity_nip": "123", "priority": "2",
        }},
        # legacy drained
        {"id": "202-0", "data": {
            "gap_type": "missing_relation", "from": "X", "to": "Y",
        }},
    ]
    fake_read = MagicMock(return_value=msgs)
    fake_dispatch = MagicMock(return_value={"case_resolved": True})
    fake_xack = MagicMock()

    stats = run_gap_consumer(
        max_items=10,
        stream_read=fake_read,
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert stats["read"] == 3
    assert stats["resolved"] == 1  # canonical regulation gap
    assert stats["skipped"] == 2   # LHKPN without name + drained legacy
    assert fake_dispatch.call_count == 1
    # All three entries got acked (1 resolve, 2 skip/drain)
    assert fake_xack.call_count == 3


# ── C.2 — unmapped persistence ──────────────────────────────────────────


def test_run_gap_consumer_persists_unmapped_snapshot():
    """Drained legacy entries must be persisted to knowledge.db at cycle end."""
    msgs = [
        {"id": "300-0", "data": {
            "gap_type": "totally_invented", "attribute": "x",
        }},
        {"id": "300-1", "data": {
            "gap_type": "totally_invented", "attribute": "x",
        }},
        {"id": "300-2", "data": {
            "gap_type": "another_unknown",
        }},
    ]
    fake_read = MagicMock(return_value=msgs)
    fake_xack = MagicMock()

    captured_stores: list[dict] = []

    class _FakeKB:
        def store(self, **kwargs):
            captured_stores.append(kwargs)
            return 1

        def close(self):
            pass

    with patch(
        "mata_garuda.runtime.knowledge.KnowledgeBase", return_value=_FakeKB()
    ):
        stats = run_gap_consumer(
            max_items=10,
            stream_read=fake_read,
            xack=fake_xack,
        )

    assert stats["skipped"] == 3
    # Two distinct unmapped tuples → two persistence rows
    assert len(captured_stores) == 2
    types_seen = {c["entry_type"] for c in captured_stores}
    assert types_seen == {"unmapped_gap"}
    agents_seen = {c["agent"] for c in captured_stores}
    assert agents_seen == {"gap_consumer"}


def test_run_gap_consumer_no_persistence_when_zero_unmapped():
    """If all entries are mapped, no audit row is written."""
    msgs = [
        {"id": "400-0", "data": {
            "gap_type": "missing_attribute", "attribute": "nip",
            "entity_name": "OK",
        }},
    ]
    fake_read = MagicMock(return_value=msgs)
    fake_dispatch = MagicMock(return_value={"case_resolved": True})
    fake_xack = MagicMock()

    captured_stores: list[dict] = []

    class _FakeKB:
        def store(self, **kwargs):
            captured_stores.append(kwargs)
            return 1

        def close(self):
            pass

    with patch(
        "mata_garuda.runtime.knowledge.KnowledgeBase", return_value=_FakeKB()
    ):
        run_gap_consumer(
            max_items=10,
            stream_read=fake_read,
            dispatch_agent=fake_dispatch,
            xack=fake_xack,
        )

    assert captured_stores == []


def test_run_gap_consumer_persistence_failure_does_not_break_cycle():
    """A crash in the audit persister must not poison the consumer cycle."""
    msgs = [
        {"id": "500-0", "data": {"gap_type": "totally_invented", "attribute": "x"}},
    ]
    fake_read = MagicMock(return_value=msgs)
    fake_xack = MagicMock()

    class _BrokenKB:
        def store(self, **kwargs):
            raise RuntimeError("disk full")

        def close(self):
            pass

    with patch(
        "mata_garuda.runtime.knowledge.KnowledgeBase", return_value=_BrokenKB()
    ):
        stats = run_gap_consumer(
            max_items=10,
            stream_read=fake_read,
            xack=fake_xack,
        )

    # Consumer still completed its work; only the audit step swallowed.
    assert stats["skipped"] == 1
    fake_xack.assert_called_once()
