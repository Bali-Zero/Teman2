"""Real-database integration tests for GarudaOrderRepository.

Requires a local throwaway Postgres reachable via `GARUDA_L3_TEST_DSN`
(defaults to the unix-socket default DB used during this lane's build —
see the PR description for the exact fixture SQL this test depends on:
migration 282's forward section, plus a minimal stand-in for L1's 281
widening of `visa_decision_retention_policies` with `policy_scope`).

Skips cleanly (not a failure) if the DSN is unreachable, so this file is
safe to collect in environments without a local Postgres.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_orders.errors import NoOpenLateCase
from backend.services.garuda_orders.idempotency import canonical_payload_sha256, scoped_key_sha256
from backend.services.garuda_orders.models import Applicant
from backend.services.garuda_orders.ports import ReviewedCheckSnapshot
from backend.services.garuda_orders.repository import GarudaOrderRepository
from backend.services.payments.port import (
    NormalizedFailureEvent,
    NormalizedPaidEvent,
    NormalizedRefundEvent,
)
from backend.services.payments.terminal_taxonomy import FailureOutcome, classify

_DSN = os.environ.get("GARUDA_L3_TEST_DSN", "postgresql://localhost/garuda_l3_test?host=/tmp")


class _FakeLookup:
    def __init__(self, case_type: CaseType = CaseType.ISSUANCE) -> None:
        self._case_type = case_type

    async def get_reviewed_check(self, result_id: str) -> ReviewedCheckSnapshot | None:
        return ReviewedCheckSnapshot(
            result_id=result_id, case_type=self._case_type, review_confirmed=True
        )


class _FakeProvider:
    def __init__(self) -> None:
        self.refund_calls: list[str] = []

    async def create_checkout_session(self, *, order_id, price_idr, idempotency_key):
        from backend.services.payments.port import CheckoutSession

        return CheckoutSession(
            provider_session_id=f"sess-{order_id}",
            checkout_url="https://sandbox.xendit.co/checkout/fake",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    def verify_signature(self, *, raw_body, headers):
        return None

    def parse_event(self, *, raw_body, headers):
        raise NotImplementedError

    async def confirm_no_successful_charge(self, *, provider_session_id: str) -> bool:
        return True

    async def refund(self, *, provider_charge_id: str, idempotency_key: str) -> str:
        self.refund_calls.append(provider_charge_id)
        return "refund-fake-1"


@pytest.fixture
async def pool():
    try:
        p = await asyncpg.create_pool(dsn=_DSN, min_size=1, max_size=2)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"no local Postgres reachable at {_DSN}: {exc}")
    async with p.acquire() as conn:
        await conn.execute(
            "TRUNCATE garuda_order_outbox, garuda_order_journal, garuda_payment_inbox, garuda_order_idempotency, garuda_orders CASCADE"
        )
    yield p
    await p.close()


@pytest.fixture
def repository(pool, monkeypatch):
    # Pricing freshness (G-FRESHNESS-FAIL-CLOSED) is garuda_flow's own tested
    # concern, not this lane's — the real catalogue in this checkout happens
    # to be >90 days stale as of "today", which correctly fails closed
    # (proving the guard works) but would fail every test in this file for a
    # reason unrelated to what they check. Pin a fixed, fresh price here.
    import backend.services.garuda_orders.repository as repository_module

    monkeypatch.setattr(
        repository_module.pricing,
        "price_for_case",
        lambda case_type, *, today: (790_000, "B1 Visa on Arrival (VOA)"),
    )
    return GarudaOrderRepository(
        pool, eligibility_lookup=_FakeLookup(), provider=_FakeProvider(), environment="PRODUCTION"
    )


def _applicant() -> Applicant:
    return Applicant(
        full_name="Test User", email="t@example.com", phone="+10000000", passport_number="P1234567"
    )


@pytest.mark.asyncio
async def test_create_order_happy_path_then_paid_then_duplicate_paid_is_noop(pool, repository):
    key_digest = scoped_key_sha256(
        actor="actor-1", operation="createOrderFromCheck", raw_key="idem-key-happy-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-1-0000000000", "applicant": {"e": 1}}
    )

    body, replayed = await repository.create_order_and_checkout(
        result_id="result-1-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    assert replayed is False
    assert body["order_state"] == "awaiting_payment"
    assert body["price_idr"] > 0
    order_id = body["order_id"]

    # Exact replay: no second order, cached response returned.
    body2, replayed2 = await repository.create_order_and_checkout(
        result_id="result-1-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    assert replayed2 is True
    assert body2["order_id"] == order_id
    count = await pool.fetchval("SELECT count(*) FROM garuda_orders WHERE order_id = $1", order_id)
    assert count == 1

    event = NormalizedPaidEvent(
        provider_event_id="evt-paid-1",
        provider_charge_id="charge-1",
        provider_session_id=f"sess-{order_id}",
        amount_idr=body["price_idr"],
        currency="IDR",
    )
    transition = await repository.handle_paid_event(event, canonical_payload_sha256=b"\x00" * 32)
    assert transition == "OP-02"
    state = await pool.fetchval("SELECT state FROM garuda_orders WHERE order_id = $1", order_id)
    assert state == "paid"

    # OP-09: exact duplicate webhook delivery (same provider_event_id) is a no-op.
    transition_dup = await repository.handle_paid_event(
        event, canonical_payload_sha256=b"\x00" * 32
    )
    assert transition_dup == "OP-09"
    journal_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_order_journal WHERE aggregate_id = $1 AND transition_id = 'OP-02'",
        order_id,
    )
    assert journal_count == 1  # not duplicated

    # OP-08: a genuinely distinct second charge on an already-paid order
    # is recorded and opens a remediation case, but state stays `paid`.
    second_charge_event = NormalizedPaidEvent(
        provider_event_id="evt-paid-2-distinct-charge",
        provider_charge_id="charge-2",
        provider_session_id=f"sess-{order_id}",
        amount_idr=body["price_idr"],
        currency="IDR",
    )
    transition_dup_charge = await repository.handle_paid_event(
        second_charge_event, canonical_payload_sha256=b"\x01" * 32
    )
    assert transition_dup_charge == "OP-08"
    state_after, late_open = await pool.fetchrow(
        "SELECT state, late_case_open FROM garuda_orders WHERE order_id = $1", order_id
    )
    assert state_after == "paid"
    assert late_open is True


@pytest.mark.asyncio
async def test_op_f04_late_paid_after_refund_keeps_refunded_and_opens_no_practice(pool, repository):
    key_digest = scoped_key_sha256(
        actor="actor-2", operation="createOrderFromCheck", raw_key="idem-key-f04-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-2-0000000000", "applicant": {"e": 2}}
    )
    body, _ = await repository.create_order_and_checkout(
        result_id="result-2-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    order_id = body["order_id"]

    # awaiting_payment -> refunded is OP-05 (a valid refund arriving before paid).
    refund_event = NormalizedRefundEvent(
        provider_event_id="evt-refund-1",
        provider_refund_id="refund-1",
        provider_charge_id="charge-x",
        provider_session_id=f"sess-{order_id}",
    )
    transition = await repository.handle_refund_event(
        refund_event, canonical_payload_sha256=b"\x02" * 32
    )
    assert transition == "OP-05"
    state = await pool.fetchval("SELECT state FROM garuda_orders WHERE order_id = $1", order_id)
    assert state == "refunded"

    # A LATE valid `paid` now arrives. This must NOT flip state back to paid —
    # the trigger would reject it anyway (bite-proofed at the SQL layer), but
    # the repository must handle it gracefully as OP-F04, not crash.
    late_paid_event = NormalizedPaidEvent(
        provider_event_id="evt-late-paid-1",
        provider_charge_id="charge-x",
        provider_session_id=f"sess-{order_id}",
        amount_idr=body["price_idr"],
        currency="IDR",
    )
    transition2 = await repository.handle_paid_event(
        late_paid_event, canonical_payload_sha256=b"\x03" * 32
    )
    assert transition2 == "OP-F04"
    state_after = await pool.fetchval(
        "SELECT state FROM garuda_orders WHERE order_id = $1", order_id
    )
    assert state_after == "refunded"  # unchanged — never flips back


@pytest.mark.asyncio
async def test_op_f05_late_paid_after_terminal_opens_remediation_then_resolve_honoured(
    pool, repository
):
    key_digest = scoped_key_sha256(
        actor="actor-3", operation="createOrderFromCheck", raw_key="idem-key-f05-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-3-0000000000", "applicant": {"e": 3}}
    )
    body, _ = await repository.create_order_and_checkout(
        result_id="result-3-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    order_id = body["order_id"]

    failure_event = NormalizedFailureEvent(
        provider_event_id="evt-fail-1",
        provider_session_id=f"sess-{order_id}",
        failure=classify(FailureOutcome.DECLINED_BY_ISSUER),
    )
    transition = await repository.handle_failure_event(
        failure_event, canonical_payload_sha256=b"\x04" * 32
    )
    assert transition == "OP-03"
    state = await pool.fetchval("SELECT state FROM garuda_orders WHERE order_id = $1", order_id)
    assert state == "failed"

    late_paid_event = NormalizedPaidEvent(
        provider_event_id="evt-late-paid-2",
        provider_charge_id="charge-late",
        provider_session_id=f"sess-{order_id}",
        amount_idr=body["price_idr"],
        currency="IDR",
    )
    transition2 = await repository.handle_paid_event(
        late_paid_event, canonical_payload_sha256=b"\x05" * 32
    )
    assert transition2 == "OP-F05"
    state_after, late_open = await pool.fetchrow(
        "SELECT state, late_case_open FROM garuda_orders WHERE order_id = $1", order_id
    )
    assert state_after == "failed"  # kept terminal, per Q10
    assert late_open is True

    # Q2: staff must resolve to exactly one of two outcomes. Try "honoured".
    resolve_key = scoped_key_sha256(
        actor="staff-1", operation="resolveLateOrder", raw_key="idem-key-resolve-0001"
    )
    resolve_payload = canonical_payload_sha256(
        {"order_id": order_id, "resolution": "honoured", "staff_reference": "case-42"}
    )
    resolution_body, replayed = await repository.resolve_late_order(
        order_id=order_id,
        resolution="honoured",
        staff_reference="case-42",
        idempotency_key_sha256=resolve_key,
        canonical_payload_sha256=resolve_payload,
    )
    assert replayed is False
    assert resolution_body["resolution"] == "honoured"
    late_open_after, resolution_col = await pool.fetchrow(
        "SELECT late_case_open, late_case_resolution FROM garuda_orders WHERE order_id = $1",
        order_id,
    )
    assert late_open_after is False
    assert resolution_col == "honoured"

    # A second resolve attempt on an already-closed case must fail — Q2's
    # "never neither" cuts both ways: it also never resolves the SAME case twice
    # under a fresh idempotency key.
    resolve_key_2 = scoped_key_sha256(
        actor="staff-1", operation="resolveLateOrder", raw_key="idem-key-resolve-0002"
    )
    resolve_payload_2 = canonical_payload_sha256(
        {"order_id": order_id, "resolution": "refunded_in_full", "staff_reference": "case-42-again"}
    )
    with pytest.raises(NoOpenLateCase):
        await repository.resolve_late_order(
            order_id=order_id,
            resolution="refunded_in_full",
            staff_reference="case-42-again",
            idempotency_key_sha256=resolve_key_2,
            canonical_payload_sha256=resolve_payload_2,
        )


@pytest.mark.asyncio
async def test_reconciliation_expires_unpaid_checkout(pool, repository):
    key_digest = scoped_key_sha256(
        actor="actor-4", operation="createOrderFromCheck", raw_key="idem-key-recon-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-4-0000000000", "applicant": {"e": 4}}
    )
    body, _ = await repository.create_order_and_checkout(
        result_id="result-4-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    order_id = body["order_id"]
    await pool.execute(
        "UPDATE garuda_orders SET checkout_expires_at = now() - interval '1 hour' WHERE order_id = $1",
        order_id,
    )

    from backend.services.garuda_orders.reconciliation import reconcile_expired_checkouts

    summary = await reconcile_expired_checkouts(pool, repository, limit=10)
    assert summary.candidates == 1
    assert summary.expired == 1
    state = await pool.fetchval("SELECT state FROM garuda_orders WHERE order_id = $1", order_id)
    assert state == "expired"


# --- The four tests below were added AFTER an independent cross-family
# refuter (Kimi K3) reviewed commit e1a0f708a and found four real defects.
# Each test proves the specific defect is fixed; none of these passed
# before the corresponding repository.py/migration edit.


@pytest.mark.asyncio
async def test_op_f04_opens_a_remediation_case_and_persists_the_late_charge_id(pool, repository):
    """Refuter finding (high): the OP-F04 branch previously journaled and
    paged but never set `late_case_open`, so `resolveLateOrder` could never
    act on exactly the orders it was paging staff about."""

    key_digest = scoped_key_sha256(
        actor="actor-5", operation="createOrderFromCheck", raw_key="idem-key-f04b-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-5-0000000000", "applicant": {"e": 5}}
    )
    body, _ = await repository.create_order_and_checkout(
        result_id="result-5-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    order_id = body["order_id"]

    refund_event = NormalizedRefundEvent(
        provider_event_id="evt-refund-2",
        provider_refund_id="refund-2",
        provider_charge_id="charge-original",
        provider_session_id=f"sess-{order_id}",
    )
    await repository.handle_refund_event(refund_event, canonical_payload_sha256=b"\x10" * 32)
    assert (
        await pool.fetchval("SELECT state FROM garuda_orders WHERE order_id = $1", order_id)
        == "refunded"
    )

    late_paid_event = NormalizedPaidEvent(
        provider_event_id="evt-late-paid-3",
        provider_charge_id="charge-the-late-one",
        provider_session_id=f"sess-{order_id}",
        amount_idr=body["price_idr"],
        currency="IDR",
    )
    transition = await repository.handle_paid_event(
        late_paid_event, canonical_payload_sha256=b"\x11" * 32
    )
    assert transition == "OP-F04"

    late_open, late_charge_id, state_after = await pool.fetchrow(
        "SELECT late_case_open, late_case_charge_id, state FROM garuda_orders WHERE order_id = $1",
        order_id,
    )
    assert late_open is True  # was False before the fix — resolveLateOrder is now reachable
    assert late_charge_id == "charge-the-late-one"  # never the original refunded charge
    assert state_after == "refunded"  # unchanged, per OP-F04


@pytest.mark.asyncio
async def test_resolve_late_order_refunds_the_late_charge_not_the_original(pool, repository):
    """Refuter finding (critical): `provider_charge_id` on a refunded order
    still names the ORIGINAL already-refunded charge. resolveLateOrder must
    refund `late_case_charge_id` (the late payment), never that one."""

    key_digest = scoped_key_sha256(
        actor="actor-6", operation="createOrderFromCheck", raw_key="idem-key-f04c-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-6-0000000000", "applicant": {"e": 6}}
    )
    body, _ = await repository.create_order_and_checkout(
        result_id="result-6-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    order_id = body["order_id"]

    await repository.handle_refund_event(
        NormalizedRefundEvent(
            provider_event_id="evt-refund-3",
            provider_refund_id="refund-3",
            provider_charge_id="charge-original-2",
            provider_session_id=f"sess-{order_id}",
        ),
        canonical_payload_sha256=b"\x12" * 32,
    )
    await repository.handle_paid_event(
        NormalizedPaidEvent(
            provider_event_id="evt-late-paid-4",
            provider_charge_id="charge-the-actually-late-one",
            provider_session_id=f"sess-{order_id}",
            amount_idr=body["price_idr"],
            currency="IDR",
        ),
        canonical_payload_sha256=b"\x13" * 32,
    )

    resolve_key = scoped_key_sha256(
        actor="staff-2", operation="resolveLateOrder", raw_key="idem-key-resolve-0003"
    )
    resolve_payload = canonical_payload_sha256(
        {"order_id": order_id, "resolution": "refunded_in_full", "staff_reference": "case-99"}
    )
    resolution_body, _ = await repository.resolve_late_order(
        order_id=order_id,
        resolution="refunded_in_full",
        staff_reference="case-99",
        idempotency_key_sha256=resolve_key,
        canonical_payload_sha256=resolve_payload,
    )
    assert resolution_body["resolution"] == "refunded_in_full"
    assert repository._provider.refund_calls == [
        "charge-the-actually-late-one"
    ]  # never "charge-original-2"


@pytest.mark.asyncio
async def test_paid_event_with_wrong_amount_is_quarantined_never_marks_paid(pool, repository):
    """Refuter finding (critical): a signed webhook proves WHO paid, never
    HOW MUCH. `handle_paid_event` must reconcile amount/currency against
    the frozen order price before flipping state to `paid`."""

    key_digest = scoped_key_sha256(
        actor="actor-7", operation="createOrderFromCheck", raw_key="idem-key-amt-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-7-0000000000", "applicant": {"e": 7}}
    )
    body, _ = await repository.create_order_and_checkout(
        result_id="result-7-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    order_id = body["order_id"]
    assert body["price_idr"] == 790_000

    wrong_amount_event = NormalizedPaidEvent(
        provider_event_id="evt-wrong-amount-1",
        provider_charge_id="charge-wrong-amount",
        provider_session_id=f"sess-{order_id}",
        amount_idr=1,  # far below the real 790.000 price
        currency="IDR",
    )
    transition = await repository.handle_paid_event(
        wrong_amount_event, canonical_payload_sha256=b"\x14" * 32
    )
    assert transition == "OP-F03"
    state = await pool.fetchval("SELECT state FROM garuda_orders WHERE order_id = $1", order_id)
    assert state == "awaiting_payment"  # never flipped to paid on a mismatched amount


@pytest.mark.asyncio
async def test_two_orders_for_the_same_check_are_rejected_at_the_db_layer(pool):
    """Refuter finding (medium-high): before the partial unique index, two
    createOrderFromCheck calls for the SAME check under two DIFFERENT
    Idempotency-Keys created two live orders — a double-charge path OP-08's
    same-session dedup cannot see. Proven directly against the schema
    (not through the repository, since the repository has no uniqueness
    check of its own — the DB constraint IS the fix)."""

    await pool.execute(
        """
        INSERT INTO garuda_orders (order_id, result_id_ref, case_type, applicant_full_name,
            applicant_email, applicant_phone, applicant_passport_number, price_idr, price_catalogue_key)
        VALUES ($1, 'result-8-0000000000', 'issuance', 'Test User', 't@example.com', '+10000000',
                'P1234567', 790000, 'B1 Visa on Arrival (VOA)')
        """,
        "order-dup-check-a-0000000",
    )
    with pytest.raises(asyncpg.exceptions.UniqueViolationError):
        await pool.execute(
            """
            INSERT INTO garuda_orders (order_id, result_id_ref, case_type, applicant_full_name,
                applicant_email, applicant_phone, applicant_passport_number, price_idr, price_catalogue_key)
            VALUES ($1, 'result-8-0000000000', 'issuance', 'Test User', 't@example.com', '+10000000',
                    'P1234567', 790000, 'B1 Visa on Arrival (VOA)')
            """,
            "order-dup-check-b-0000000",
        )
