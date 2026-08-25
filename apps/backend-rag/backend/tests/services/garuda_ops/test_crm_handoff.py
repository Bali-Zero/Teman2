"""Bite-proof for `garuda_ops.crm_handoff.CrmHandoffService`, against fakes
implementing `ports.py` — the seam documented in `garuda_ops/__init__.py`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from backend.services.garuda_ops.crm_handoff import (
    GARUDA_VOA_PRACTICE_TYPE_CODE,
    CrmHandoffService,
    HandoffOutcome,
)
from backend.services.garuda_ops.ports import EventEnvelope, OrderSnapshot

_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)


def _pr01_event(*, event_id: str = "evt-pr01", aggregate_id: str = "practice-order-1") -> EventEnvelope:
    return EventEnvelope(
        schema_version="1.0.0",
        event_id=event_id,
        event_name="practice.received",
        occurred_at=_NOW,
        aggregate_type="practice",
        aggregate_id=aggregate_id,
        transition_id="PR-01",
        customer_visible=True,
    )


class FakeOrderSnapshots:
    def __init__(self, snapshots: dict[str, OrderSnapshot]) -> None:
        self._snapshots = snapshots

    async def get(self, order_aggregate_id: str) -> OrderSnapshot | None:
        return self._snapshots.get(order_aggregate_id)


class FakeCrmWriter:
    def __init__(self) -> None:
        self.by_event_id: dict[str, int] = {}
        self.created: list[tuple[OrderSnapshot, str, str]] = []
        self._next_id = 100

    async def find_practice_by_source_event(self, source_event_id: str) -> int | None:
        return self.by_event_id.get(source_event_id)

    async def create_client_and_practice(
        self, snapshot: OrderSnapshot, *, source_event_id: str, practice_type_code: str
    ) -> int:
        self._next_id += 1
        self.by_event_id[source_event_id] = self._next_id
        self.created.append((snapshot, source_event_id, practice_type_code))
        return self._next_id


def _snapshot(order_id: str = "practice-order-1") -> OrderSnapshot:
    return OrderSnapshot(
        order_aggregate_id=order_id,
        customer_email="traveller@example.com",
        case_type="issuance",
        purpose="tourism",
        nationality="AUS",
        entry_date=date(2026, 9, 1),
        price_idr=2_500_000,
        submit_by_date=date(2026, 8, 29),
    )


@pytest.mark.asyncio
async def test_creates_crm_practice_from_order_snapshot_with_zero_retyping() -> None:
    writer = FakeCrmWriter()
    service = CrmHandoffService(
        order_snapshots=FakeOrderSnapshots({"practice-order-1": _snapshot()}),
        crm_writer=writer,
    )
    result = await service.handle_practice_received(_pr01_event())
    assert result.outcome is HandoffOutcome.CREATED
    assert result.crm_practice_id is not None
    assert len(writer.created) == 1
    snapshot, source_event_id, practice_type_code = writer.created[0]
    assert source_event_id == "evt-pr01"
    assert practice_type_code == GARUDA_VOA_PRACTICE_TYPE_CODE
    assert snapshot.customer_email == "traveller@example.com"


@pytest.mark.asyncio
async def test_duplicate_pr01_delivery_never_creates_a_second_practice() -> None:
    """RED case this guards: an outbox retry of the SAME PR-01 event must be
    a no-op, not a second CRM practice (SM-G08)."""
    writer = FakeCrmWriter()
    service = CrmHandoffService(
        order_snapshots=FakeOrderSnapshots({"practice-order-1": _snapshot()}),
        crm_writer=writer,
    )
    first = await service.handle_practice_received(_pr01_event())
    second = await service.handle_practice_received(_pr01_event())

    assert first.outcome is HandoffOutcome.CREATED
    assert second.outcome is HandoffOutcome.ALREADY_HANDLED
    assert second.crm_practice_id == first.crm_practice_id
    assert len(writer.created) == 1  # the bite: still exactly one


@pytest.mark.asyncio
async def test_two_distinct_pr01_events_create_two_practices() -> None:
    """Green counterpart: proves the dedup key is the event id, not a
    blanket 'never create twice' that would also swallow real second
    practices."""
    writer = FakeCrmWriter()
    service = CrmHandoffService(
        order_snapshots=FakeOrderSnapshots(
            {"order-a": _snapshot("order-a"), "order-b": _snapshot("order-b")}
        ),
        crm_writer=writer,
    )
    first = await service.handle_practice_received(
        _pr01_event(event_id="evt-a", aggregate_id="order-a")
    )
    second = await service.handle_practice_received(
        _pr01_event(event_id="evt-b", aggregate_id="order-b")
    )
    assert first.outcome is HandoffOutcome.CREATED
    assert second.outcome is HandoffOutcome.CREATED
    assert first.crm_practice_id != second.crm_practice_id
    assert len(writer.created) == 2


@pytest.mark.asyncio
async def test_missing_order_snapshot_fails_closed_without_writing() -> None:
    writer = FakeCrmWriter()
    service = CrmHandoffService(
        order_snapshots=FakeOrderSnapshots({}),  # nothing resolvable
        crm_writer=writer,
    )
    result = await service.handle_practice_received(_pr01_event())
    assert result.outcome is HandoffOutcome.ORDER_SNAPSHOT_MISSING
    assert result.crm_practice_id is None
    assert writer.created == []


@pytest.mark.asyncio
async def test_rejects_any_transition_other_than_pr01() -> None:
    writer = FakeCrmWriter()
    service = CrmHandoffService(
        order_snapshots=FakeOrderSnapshots({"practice-order-1": _snapshot()}),
        crm_writer=writer,
    )
    non_pr01 = EventEnvelope(
        schema_version="1.0.0",
        event_id="evt-pr02",
        event_name="practice.in_review",
        occurred_at=_NOW,
        aggregate_type="practice",
        aggregate_id="practice-order-1",
        transition_id="PR-02",
        customer_visible=True,
    )
    with pytest.raises(ValueError, match="PR-01"):
        await service.handle_practice_received(non_pr01)
