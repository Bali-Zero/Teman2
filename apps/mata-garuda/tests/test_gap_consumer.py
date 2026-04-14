"""Tests for gap consumer — reads nexus:gaps and dispatches agents."""
from __future__ import annotations

from unittest.mock import MagicMock

from mata_garuda.workers.gap_consumer import (
    GAP_DISPATCH,
    process_gap,
    run_gap_consumer,
)


def test_gap_dispatch_table_complete():
    """All 8 gap types from the design spec are mapped (1 to None for Phase 2)."""
    expected = {
        "gap.missing_nip",
        "gap.missing_lhkpn",
        "gap.missing_angkatan",
        "gap.stale_official",
        "gap.orphan_org",
        "gap.missing_office",
        "gap.kanim_struktur",
        "gap.missing_procurement",
    }
    assert set(GAP_DISPATCH.keys()) == expected
    # Phase 1: 7 gaps mapped to an agent, 1 unmapped (procurement)
    mapped = {k for k, v in GAP_DISPATCH.items() if v is not None}
    assert "gap.missing_procurement" not in mapped
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


def test_process_gap_dispatches_lhkpn_for_missing_nip():
    """gap.missing_nip → lhkpn_harvester."""
    fake_dispatch = MagicMock(return_value={"case_resolved": True})
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="3-0",
        gap_type="gap.missing_nip",
        payload={"person_name": "Budi"},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    fake_dispatch.assert_called_once()
    call_kwargs = fake_dispatch.call_args.kwargs
    assert call_kwargs["agent_name"] == "lhkpn_harvester"
    assert call_kwargs["payload"]["person_name"] == "Budi"
    assert call_kwargs["payload"]["_gap_type"] == "gap.missing_nip"
    assert result["status"] == "resolved"
    assert result["agent"] == "lhkpn_harvester"
    fake_xack.assert_called_once()


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

    assert fake_dispatch.call_args.kwargs["agent_name"] == "regulation_watcher"
    assert result["status"] == "resolved"


def test_process_gap_does_not_ack_on_case_not_resolved():
    """case_not_resolved: do NOT ack — let it redeliver."""
    fake_dispatch = MagicMock(return_value={"case_resolved": False, "reason": "403"})
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="5-0",
        gap_type="gap.missing_nip",
        payload={"person_name": "x"},
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
        gap_type="gap.missing_nip",
        payload={},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert result["status"] == "error"
    fake_xack.assert_not_called()


def test_run_gap_consumer_processes_batch():
    """run_gap_consumer reads N messages and processes each."""
    msgs = [
        {"id": "10-0", "data": {"type": "gap.missing_nip", "payload": '{"person_name": "A"}'}},
        {"id": "11-0", "data": {"type": "gap.stale_official", "payload": '{"nip": "123"}'}},
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
    assert stats["resolved"] == 2
    assert stats["failed"] == 0
    assert fake_dispatch.call_count == 2
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
        {"id": "12-0", "data": {"type": "gap.missing_nip", "payload": "not json {{{"}},
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
    assert payload == {"_gap_type": "gap.missing_nip"}
