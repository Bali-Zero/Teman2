import asyncio
import pytest
from unittest.mock import AsyncMock
from cell_observatory.collector import Collector


@pytest.mark.asyncio
async def test_bounded_queue_drops_oldest_on_overflow():
    """G1 fix: queue maxsize=10000, drop-oldest on overflow."""
    storage = AsyncMock()
    storage.insert_pulse_event = AsyncMock(return_value=True)
    classifier = AsyncMock()

    collector = Collector(storage=storage, classifier=classifier,
                          classifier_max_inflight=2, classifier_queue_maxsize=3)

    for i in range(10):
        collector._enqueue_for_classification({"outbox_id": i})

    # Queue should be capped at maxsize, oldest dropped
    assert collector._classification_queue.qsize() == 3


@pytest.mark.asyncio
async def test_outbox_replay_on_startup():
    """Replay unconsumed events_outbox rows on collector startup."""
    storage = AsyncMock()
    storage.insert_pulse_event = AsyncMock(return_value=True)
    classifier = AsyncMock()

    collector = Collector(storage=storage, classifier=classifier)

    # NOTE: column is `id` (per migration 144), NOT `outbox_id`. Python-side
    # variable name preserved for downstream contract.
    fake_conn_rows = [
        {
            "id": 1,
            "payload": '{"_outbox_id": 1, "event_version": "v1", "cell_id": "x", "cell_kind": "x", "pulse_id": "x", "pulse_timestamp": "2026-05-01T00:00:00Z", "phase": "x", "sensors": [], "pulse_result": {"classifier_self": "green"}, "homeostatic_state": {}, "scar_signals": [], "metadata": {}}'
        },
    ]

    fake_conn = AsyncMock()
    fake_conn.fetch = AsyncMock(return_value=fake_conn_rows)
    fake_conn.execute = AsyncMock()

    await collector._replay_outbox_unconsumed(fake_conn)

    storage.insert_pulse_event.assert_called_once()
    fake_conn.execute.assert_called()  # ack via consumed_at

    # Verify the SELECT uses `id`, not `outbox_id` (regression guard)
    select_call = fake_conn.fetch.call_args[0][0]
    assert "SELECT id, payload" in select_call, f"expected id col, got: {select_call}"
    assert "outbox_id" not in select_call.split("WHERE")[0], (
        "regression: SELECT must not reference outbox_id column"
    )
