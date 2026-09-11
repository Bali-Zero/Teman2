"""Bite-proof for `garuda_ops.crm_handoff.CrmHandoffService`, against fakes
implementing `ports.py` — the seam documented in `garuda_ops/__init__.py`.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import date, datetime, timezone

import pytest

from backend.services.garuda_ops.crm_handoff import (
    PRACTICE_TYPE_CODE_BY_CASE_TYPE,
    CrmHandoffService,
    HandoffOutcome,
    UnmappedCaseType,
)
from backend.services.garuda_ops.ports import EventEnvelope, IdempotencyIdentity, OrderSnapshot

_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)


def _idempotency(seed: str) -> IdempotencyIdentity:
    """Stands in for the contract-named "committed payment.paid journal
    event identity" (events.yaml `x-idempotency-source` for
    `PracticeReceived`) — the key `crm_handoff.py` actually dedups on, NOT
    the `practice.received` event's own `event_id` (ports.py docstring)."""
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return IdempotencyIdentity(
        kind="DOMAIN_EVENT", key_digest=digest, canonical_payload_digest=digest
    )


def _pr01_event(
    *,
    event_id: str = "evt-pr01",
    aggregate_id: str = "practice-order-1",
    paid_event_identity_seed: str | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        schema_version="1.0.0",
        event_id=event_id,
        event_name="practice.received",
        occurred_at=_NOW,
        aggregate_type="practice",
        aggregate_id=aggregate_id,
        transition_id="PR-01",
        customer_visible=True,
        idempotency_identity=_idempotency(paid_event_identity_seed or event_id),
    )


class FakeOrderSnapshots:
    def __init__(self, snapshots: dict[str, OrderSnapshot]) -> None:
        self._snapshots = snapshots

    async def get(self, order_aggregate_id: str) -> OrderSnapshot | None:
        return self._snapshots.get(order_aggregate_id)


class FakeCrmWriter:
    def __init__(self) -> None:
        self.by_idempotency_key: dict[str, int] = {}
        self.created: list[tuple[OrderSnapshot, str, str]] = []
        self._next_id = 100

    async def find_practice_by_source_idempotency_key(self, source_idempotency_key: str) -> int | None:
        return self.by_idempotency_key.get(source_idempotency_key)

    async def _create_client_and_practice_uncontrolled(
        self, snapshot: OrderSnapshot, *, source_idempotency_key: str, practice_type_code: str
    ) -> int:
        """The write itself — a real INSERT is a DB round-trip, so a real
        adapter's write genuinely suspends the coroutine before it commits.
        Two concurrency-fake subclasses below build on this: one leaves the
        window open (races), one closes it with a lock (a stand-in for a DB
        unique constraint)."""
        await asyncio.sleep(0)
        self._next_id += 1
        self.by_idempotency_key[source_idempotency_key] = self._next_id
        self.created.append((snapshot, source_idempotency_key, practice_type_code))
        return self._next_id

    async def create_client_and_practice(
        self, snapshot: OrderSnapshot, *, source_idempotency_key: str, practice_type_code: str
    ) -> int:
        return await self._create_client_and_practice_uncontrolled(
            snapshot, source_idempotency_key=source_idempotency_key, practice_type_code=practice_type_code
        )


class AtomicFakeCrmWriter(FakeCrmWriter):
    """Models the concurrency contract documented on `ports.CrmWriter`: a
    real adapter's `create_client_and_practice` must itself be the atomic
    idempotency authority (DB unique constraint + upsert), not merely look
    idempotent under a single-threaded caller. This fake enforces that with
    an `asyncio.Lock` around its check-and-write, standing in for what a
    `UNIQUE(source_event_id)` constraint plus `INSERT ... ON CONFLICT ...
    RETURNING` gives you for free at the database — held across the same
    `asyncio.sleep(0)` the base class's write incurs, the way a real
    Postgres transaction holds its row lock across the network round-trip.
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = asyncio.Lock()

    async def create_client_and_practice(
        self, snapshot: OrderSnapshot, *, source_idempotency_key: str, practice_type_code: str
    ) -> int:
        async with self._lock:
            existing = self.by_idempotency_key.get(source_idempotency_key)
            if existing is not None:
                return existing
            return await self._create_client_and_practice_uncontrolled(
                snapshot, source_idempotency_key=source_idempotency_key, practice_type_code=practice_type_code
            )


def _snapshot(order_id: str = "practice-order-1", case_type: str = "issuance") -> OrderSnapshot:
    return OrderSnapshot(
        order_aggregate_id=order_id,
        customer_email="traveller@example.com",
        case_type=case_type,
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
    event = _pr01_event()
    result = await service.handle_practice_received(event)
    assert result.outcome is HandoffOutcome.CREATED
    assert result.crm_practice_id is not None
    assert len(writer.created) == 1
    snapshot, source_idempotency_key, practice_type_code = writer.created[0]
    assert source_idempotency_key == event.idempotency_identity.key_digest
    assert practice_type_code == "visa_b1_voa"
    assert snapshot.customer_email == "traveller@example.com"


@pytest.mark.asyncio
async def test_journal_level_retry_with_a_fresh_event_id_still_dedups() -> None:
    """RED-if-wrong (refuter finding 2): before the fix, dedup keyed on the
    `practice.received` event's own `event_id` — which only catches an
    outbox redelivery of ONE committed event. A journal-level PR-01 retry
    (worker crash after journal append, before ack) mints a SECOND
    `practice.received` event, with a FRESH `event_id`, for the SAME order.
    The contract-correct key is `idempotency_identity.key_digest` (the paid
    journal event identity, per events.yaml's `x-idempotency-source` for
    `PracticeReceived`), which is identical across both deliveries here."""
    writer = FakeCrmWriter()
    service = CrmHandoffService(
        order_snapshots=FakeOrderSnapshots({"practice-order-1": _snapshot()}),
        crm_writer=writer,
    )
    first_delivery = _pr01_event(event_id="evt-pr01-attempt-1", paid_event_identity_seed="paid-evt-shared")
    second_delivery = _pr01_event(event_id="evt-pr01-attempt-2", paid_event_identity_seed="paid-evt-shared")
    assert first_delivery.event_id != second_delivery.event_id  # genuinely different wire events

    first = await service.handle_practice_received(first_delivery)
    second = await service.handle_practice_received(second_delivery)

    assert first.outcome is HandoffOutcome.CREATED
    assert second.outcome is HandoffOutcome.ALREADY_HANDLED
    assert len(writer.created) == 1  # the bite: one practice, not two


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
        idempotency_identity=_idempotency("evt-pr02"),
    )
    with pytest.raises(ValueError, match="PR-01"):
        await service.handle_practice_received(non_pr01)


class _BarrierFindFakeCrmWriter(FakeCrmWriter):
    """A real `find_practice_by_source_idempotency_key` is a DB round-trip — it
    genuinely suspends the coroutine, which is exactly the window a race
    needs. The plain in-process `FakeCrmWriter` never suspends (a dict
    lookup returns without yielding to the event loop), so a single
    `asyncio.sleep(0)` is not reliably enough to force the interleaving
    asyncio's scheduler happens to choose. This fake uses a barrier: `find`
    blocks until exactly `expected_racers` callers have reached it, so
    BOTH concurrent deliveries are guaranteed to observe "no existing row"
    before either one proceeds to `create` — deterministically reproducing
    the race a real DB round-trip could produce non-deterministically.
    """

    def __init__(self, *, expected_racers: int = 2) -> None:
        super().__init__()
        self._pending = expected_racers
        self._release = asyncio.Event()

    async def find_practice_by_source_idempotency_key(self, source_idempotency_key: str) -> int | None:
        self._pending -= 1
        if self._pending <= 0:
            self._release.set()
        else:
            await self._release.wait()
        return await super().find_practice_by_source_idempotency_key(source_idempotency_key)


class _BarrierFindAtomicCrmWriter(AtomicFakeCrmWriter):
    def __init__(self, *, expected_racers: int = 2) -> None:
        super().__init__()
        self._pending = expected_racers
        self._release = asyncio.Event()

    async def find_practice_by_source_idempotency_key(self, source_idempotency_key: str) -> int | None:
        self._pending -= 1
        if self._pending <= 0:
            self._release.set()
        else:
            await self._release.wait()
        return await super().find_practice_by_source_idempotency_key(source_idempotency_key)


@pytest.mark.asyncio
async def test_naive_writer_races_under_true_concurrency() -> None:
    """RED, by construction: `CrmHandoffService.handle_practice_received`
    is check-then-act (find, then create as two separate awaits). With a
    writer whose `find` genuinely suspends (as a real DB call would), two
    truly concurrent deliveries of the SAME PR-01 event CAN both observe no
    existing row and both create one. This is not a bug in
    `CrmHandoffService`; it is the exact gap `ports.CrmWriter`'s docstring
    requires a real adapter to close at the database. Asserting the race
    actually happens here — rather than hoping it doesn't — is what proves
    the next test's fix is load-bearing, not accidental."""
    writer = _BarrierFindFakeCrmWriter()
    service = CrmHandoffService(
        order_snapshots=FakeOrderSnapshots({"practice-order-1": _snapshot()}),
        crm_writer=writer,
    )

    await asyncio.gather(
        service.handle_practice_received(_pr01_event()),
        service.handle_practice_received(_pr01_event()),
    )
    assert len(writer.created) == 2  # the race: two practices for one PR-01 event


@pytest.mark.asyncio
async def test_atomic_writer_closes_the_race_under_true_concurrency() -> None:
    """GREEN counterpart: swap in a writer whose `create_client_and_practice`
    is itself the atomic idempotency authority (this fake's lock stands in
    for a DB `UNIQUE(source_event_id)` + upsert) — the same two concurrent
    deliveries, with the same latent `find`, now produce exactly one
    practice."""
    writer = _BarrierFindAtomicCrmWriter()
    service = CrmHandoffService(
        order_snapshots=FakeOrderSnapshots({"practice-order-1": _snapshot()}),
        crm_writer=writer,
    )

    await asyncio.gather(
        service.handle_practice_received(_pr01_event()),
        service.handle_practice_received(_pr01_event()),
    )
    assert len(writer.created) == 1


# --------------------------------------------------------------------------
# The practice type is DERIVED FROM THE ORDER, not hardcoded (Zero, 2026-08-26)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case_type", "expected_code"),
    [("issuance", "visa_b1_voa"), ("extension", "ext_b1_voa")],
)
@pytest.mark.asyncio
async def test_each_case_type_writes_its_own_catalogue_service(
    case_type: str, expected_code: str
) -> None:
    """RED-if-wrong: the version this replaces passed ONE constant
    (`"garuda_voa"`) for both case types. Issuance and extension are separate
    products at separate prices in `practice_types` — Rp 750,000 vs
    Rp 850,000 (221 seeded issuance at 750,000; migration 302 moved it to
    790,000 and migration 303 moved it back, per the owner's 2026-08-31
    ruling) — so a shared code prices, reports and routes
    them as one service. Parametrized precisely so re-hardcoding either side
    reddens exactly one case, not the pair."""
    writer = FakeCrmWriter()
    service = CrmHandoffService(
        order_snapshots=FakeOrderSnapshots(
            {"practice-order-1": _snapshot(case_type=case_type)}
        ),
        crm_writer=writer,
    )
    result = await service.handle_practice_received(_pr01_event())
    assert result.outcome is HandoffOutcome.CREATED
    _, _, practice_type_code = writer.created[0]
    assert practice_type_code == expected_code


def test_the_two_case_types_do_not_share_one_code() -> None:
    """Guards the shape, not one value: a future edit that collapses both
    rows onto a single code reddens here even if each row still "looks"
    populated."""
    codes = set(PRACTICE_TYPE_CODE_BY_CASE_TYPE.values())
    assert len(codes) == len(PRACTICE_TYPE_CODE_BY_CASE_TYPE) == 2


@pytest.mark.asyncio
async def test_an_unmapped_case_type_raises_and_writes_nothing() -> None:
    """A paid order whose case_type has no CRM service must NOT be retired
    green. `drain_once` reads a returned value as success and marks the job
    dispatched; only a raise keeps the job visible. The second assertion is
    the one that matters — no half-written practice."""
    writer = FakeCrmWriter()
    service = CrmHandoffService(
        order_snapshots=FakeOrderSnapshots(
            {"practice-order-1": _snapshot(case_type="renewal")}
        ),
        crm_writer=writer,
    )
    with pytest.raises(UnmappedCaseType):
        await service.handle_practice_received(_pr01_event())
    assert writer.created == []


@pytest.mark.asyncio
async def test_the_unmapped_error_leaks_no_order_identifier_or_case_value() -> None:
    """SM-G03 bans order/account identifiers as log fields, and this message
    reaches a log through the raise. RED if someone "helpfully" interpolates
    the case_type or the aggregate id into the text."""
    service = CrmHandoffService(
        order_snapshots=FakeOrderSnapshots(
            {"practice-order-1": _snapshot(case_type="renewal")}
        ),
        crm_writer=FakeCrmWriter(),
    )
    with pytest.raises(UnmappedCaseType) as excinfo:
        await service.handle_practice_received(_pr01_event())
    text = str(excinfo.value)
    assert "renewal" not in text
    assert "practice-order-1" not in text
    assert "traveller@example.com" not in text
