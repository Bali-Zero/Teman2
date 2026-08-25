"""The seam that has never once executed: a check created through L2's real
``PostgresCheckStore`` fetched by L3's real ``PostgresEligibilityCheckLookup``
and turned into an order.

Composition-lane journey test (migration 286 wires this). Every prior L2/L3
suite exercised each lane against a fake counterpart
(``test_garuda_voa_public.py`` overrides ``CheckStore`` with an in-memory
fake; ``test_repository_integration.py`` overrides ``EligibilityCheckLookup``
with ``_FakeLookup``). Neither ever ran the REAL adapter on both sides of the
`result_id` handoff against a real Postgres. This file is that run.

Requires a real Postgres with migrations applied through 286 -- see
``test_repository_integration.py``'s module docstring for the DSN
resolution and CI-must-not-skip rationale; this file follows the identical
convention.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.services.garuda_flow.check_store import PostgresCheckStore
from backend.services.garuda_flow.civil_clock import garuda_today
from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_flow.public_api import EligibilityCheckOutcome, IdempotencyConflict
from backend.services.garuda_orders.eligibility_lookup import PostgresEligibilityCheckLookup
from backend.services.garuda_orders.errors import OrderNotReady, ResultNotFound
from backend.services.garuda_orders.idempotency import canonical_payload_sha256, scoped_key_sha256
from backend.services.garuda_orders.models import Applicant
from backend.services.garuda_orders.repository import GarudaOrderRepository
from backend.services.payments.port import CheckoutSession

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
)

_TODAY = garuda_today()
_ENTRY_DATE = _TODAY + timedelta(days=7)
_PASSPORT_EXPIRY = _ENTRY_DATE + timedelta(days=200)


class _FakeProvider:
    """Sandbox-free payment provider double -- this file's concern is the
    check<->order seam, not the payment leg L3's own suite already covers."""

    async def create_checkout_session(self, *, order_id, price_idr, idempotency_key):
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
        return "refund-fake"


async def _seed_policy(conn: asyncpg.Connection, *, scope: str) -> str:
    """Zero-approved test policy fixture for one scope. Self-heals a
    dangling open row first (see test_repository_integration.py's
    ``_ensure_garuda_order_test_policy`` for the full reasoning this
    mirrors) and closes-not-deletes on teardown (append-only table)."""

    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = $1
           AND upper(effective_period) IS NULL
        """,
        scope,
    )
    policy_version = f"journey-test-{scope.lower()}-{uuid.uuid4().hex[:16]}"
    await conn.execute(
        """
        INSERT INTO public.visa_decision_retention_policies (
            environment, policy_scope, policy_version, retention_interval,
            idempotency_retention_interval, legal_hold_review_interval,
            retention_anchor, effective_period, approved_by, approval_reference
        ) VALUES (
            'TEST', $1, $2, INTERVAL '90 days',
            INTERVAL '1 hour', INTERVAL '30 days',
            'CREATED_AT', tstzrange(clock_timestamp(), NULL, '[)'),
            'zero-test-approver', 'ZERO-JOURNEY-TEST-APPROVAL'
        )
        ON CONFLICT DO NOTHING
        """,
        scope,
        policy_version,
    )
    return policy_version


async def _close_policy(conn: asyncpg.Connection, *, scope: str, policy_version: str) -> None:
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE policy_scope = $1 AND policy_version = $2
           AND upper(effective_period) IS NULL
        """,
        scope,
        policy_version,
    )


@pytest.fixture
async def pool():
    try:
        p = await asyncpg.create_pool(dsn=_DSN, min_size=1, max_size=4)
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            pytest.fail(
                f"CI has no reachable Postgres for INTAKE_TEST_DSN "
                f"(or GARUDA_L3_TEST_DSN override) -- {_DSN!r} unreachable: {exc}. "
                f"This journey test proves the L2<->L3 seam and must never skip in CI."
            )
        pytest.skip(f"no local Postgres reachable at {_DSN}: {exc}")

    async with p.acquire() as conn:
        await conn.execute(
            "TRUNCATE garuda_order_outbox, garuda_order_journal, garuda_payment_inbox, "
            "garuda_order_idempotency, garuda_orders CASCADE"
        )
        await conn.execute("TRUNCATE garuda_voa_check_idempotency, garuda_voa_check_results CASCADE")
        check_policy_version = await _seed_policy(conn, scope="GARUDA_CHECK")
        order_policy_version = await _seed_policy(conn, scope="GARUDA_ORDER")
    yield p
    async with p.acquire() as conn:
        await _close_policy(conn, scope="GARUDA_CHECK", policy_version=check_policy_version)
        await _close_policy(conn, scope="GARUDA_ORDER", policy_version=order_policy_version)
    await p.close()


@pytest.fixture
def check_store(pool):
    return PostgresCheckStore(pool, environment="TEST")


@pytest.fixture
def lookup(pool):
    return PostgresEligibilityCheckLookup(pool)


@pytest.fixture
def repository(pool, lookup, monkeypatch):
    import backend.services.garuda_orders.repository as repository_module

    monkeypatch.setattr(
        repository_module.pricing,
        "price_for_case",
        lambda case_type, *, today: (790_000, "B1 Visa on Arrival (VOA)"),
    )
    return GarudaOrderRepository(
        pool, eligibility_lookup=lookup, provider=_FakeProvider(), environment="TEST"
    )


def _accept_canonical_request(*, case_type: str = "issuance") -> dict[str, object]:
    return {
        "case_type": case_type,
        "nationality": "USA",
        "entry_date": _ENTRY_DATE.isoformat(),
        "passport_expiry_date": _PASSPORT_EXPIRY.isoformat(),
        "voa_expiry_date": None,
        "purpose": "tourism",
        "travellers": 1,
        "self_pay": True,
        "extension_already_used": False,
        "retention_notice_acknowledged": True,
    }


def _accept_outcome() -> EligibilityCheckOutcome:
    return EligibilityCheckOutcome(
        accepted=True,
        reason_codes=[],
        published_filing_deadline=_TODAY + timedelta(days=1),
        price_idr=790_000,
        price_source="B1 Visa on Arrival (VOA)",
    )


def _applicant() -> Applicant:
    return Applicant(
        full_name="Journey Tester",
        email="journey@example.com",
        phone="+10000000",
        passport_number="P9998887",
    )


@pytest.mark.asyncio
async def test_a_check_created_through_l2_can_be_fetched_by_l3_and_turned_into_an_order(
    pool, check_store, repository
) -> None:
    stored = await check_store.create(
        idempotency_key="journey-create-key-0000000001",
        canonical_request=_accept_canonical_request(),
        outcome=_accept_outcome(),
    )
    assert stored.idempotency_replayed is False
    assert stored.session_secret is not None
    result_id = stored.result_id

    # L2's own GET, over the real store, proves the session-scoped read works
    # end-to-end before L3 ever touches it.
    fetched = await check_store.get(result_id=result_id, session_secret=stored.session_secret)
    assert fetched is not None
    assert fetched.outcome.accepted is True
    assert fetched.session_secret is None  # never re-exposed on replay/get

    key_digest = scoped_key_sha256(
        actor=result_id, operation="createOrderFromCheck", raw_key="order-key-0000000001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": result_id, "applicant": {"e": "journey@example.com"}}
    )
    body, replayed = await repository.create_order_and_checkout(
        result_id=result_id,
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    assert replayed is False
    assert body["order_state"] == "awaiting_payment"
    assert body["price_idr"] == 790_000

    order_row = await pool.fetchrow(
        "SELECT case_type, result_id_ref FROM garuda_orders WHERE order_id = $1", body["order_id"]
    )
    assert order_row["case_type"] == CaseType.ISSUANCE.value
    assert order_row["result_id_ref"] == result_id


@pytest.mark.asyncio
async def test_create_replay_is_a_true_replay_not_a_second_check(check_store) -> None:
    request = _accept_canonical_request()
    outcome = _accept_outcome()
    first = await check_store.create(
        idempotency_key="journey-replay-key-0000001", canonical_request=request, outcome=outcome
    )
    second = await check_store.create(
        idempotency_key="journey-replay-key-0000001", canonical_request=request, outcome=outcome
    )
    assert second.idempotency_replayed is True
    assert second.result_id == first.result_id
    assert second.session_secret is None  # never re-minted on replay


@pytest.mark.asyncio
async def test_create_conflict_same_key_different_payload_raises(check_store) -> None:
    outcome = _accept_outcome()
    await check_store.create(
        idempotency_key="journey-conflict-key-0000001",
        canonical_request=_accept_canonical_request(case_type="issuance"),
        outcome=outcome,
    )
    with pytest.raises(IdempotencyConflict):
        await check_store.create(
            idempotency_key="journey-conflict-key-0000001",
            canonical_request=_accept_canonical_request(case_type="extension")
            | {"voa_expiry_date": _TODAY.isoformat()},
            outcome=outcome,
        )


@pytest.mark.asyncio
async def test_a_result_id_that_does_not_exist_produces_the_contracts_non_enumerating_shape(
    repository,
) -> None:
    key_digest = scoped_key_sha256(
        actor="ghost-result-id-000000", operation="createOrderFromCheck", raw_key="k-ghost-001"
    )
    payload_digest = canonical_payload_sha256({"result_id": "ghost", "applicant": {}})
    with pytest.raises(ResultNotFound):
        await repository.create_order_and_checkout(
            result_id="ghost-result-id-000000",
            applicant=_applicant(),
            review_confirmed=True,
            idempotency_key_sha256=key_digest,
            canonical_payload_sha256=payload_digest,
        )


@pytest.mark.asyncio
async def test_a_declined_check_cannot_become_an_order(check_store, repository) -> None:
    declined_outcome = EligibilityCheckOutcome(
        accepted=False,
        reason_codes=[],
        published_filing_deadline=None,
        price_idr=None,
        price_source=None,
    )
    # DECLINE reason_codes must be non-empty per the 286 CHECK constraint —
    # any real DeclineCode value exercises the same path.
    from backend.services.garuda_flow.eligibility import DeclineCode

    declined_outcome = EligibilityCheckOutcome(
        accepted=False,
        reason_codes=[DeclineCode.NATIONALITY_NOT_ELIGIBLE],
        published_filing_deadline=None,
        price_idr=None,
        price_source=None,
    )
    stored = await check_store.create(
        idempotency_key="journey-decline-key-0000001",
        canonical_request=_accept_canonical_request(),
        outcome=declined_outcome,
    )

    key_digest = scoped_key_sha256(
        actor=stored.result_id, operation="createOrderFromCheck", raw_key="k-decline-001"
    )
    payload_digest = canonical_payload_sha256({"result_id": stored.result_id, "applicant": {}})
    with pytest.raises(OrderNotReady):
        await repository.create_order_and_checkout(
            result_id=stored.result_id,
            applicant=_applicant(),
            review_confirmed=True,
            idempotency_key_sha256=key_digest,
            canonical_payload_sha256=payload_digest,
        )


@pytest.mark.asyncio
async def test_get_with_the_wrong_session_secret_is_non_enumerating(check_store) -> None:
    stored = await check_store.create(
        idempotency_key="journey-wrong-secret-key-001",
        canonical_request=_accept_canonical_request(),
        outcome=_accept_outcome(),
    )
    assert await check_store.get(result_id=stored.result_id, session_secret="not-the-real-secret") is None
    assert await check_store.get(result_id="totally-malformed-id", session_secret="whatever") is None


@pytest.mark.asyncio
async def test_lookup_returns_none_for_malformed_or_absent_result_id(lookup) -> None:
    assert await lookup.get_reviewed_check("") is None
    assert await lookup.get_reviewed_check("does-not-exist-anywhere-00") is None


@pytest.mark.asyncio
async def test_self_service_delete_removes_the_row_and_is_idempotent(check_store, pool) -> None:
    stored = await check_store.create(
        idempotency_key="journey-delete-key-0000001",
        canonical_request=_accept_canonical_request(),
        outcome=_accept_outcome(),
    )
    deleted = await check_store.delete(
        result_id=stored.result_id,
        session_secret=stored.session_secret,
        idempotency_key="journey-delete-idem-key-01",
    )
    assert deleted is True
    remaining = await pool.fetchval(
        "SELECT count(*) FROM garuda_voa_check_results WHERE result_id = $1", stored.result_id
    )
    assert remaining == 0

    # Idempotent replay of the SAME delete command: no error, no re-delete.
    replayed_deleted = await check_store.delete(
        result_id=stored.result_id,
        session_secret=stored.session_secret,
        idempotency_key="journey-delete-idem-key-01",
    )
    assert replayed_deleted is False

    # And a lookup afterward correctly reports gone, not "wrong owner".
    assert await check_store.get(result_id=stored.result_id, session_secret=stored.session_secret) is None
