"""Real-database integration tests for `PracticeRepository` (L4).

Requires a real Postgres. Same DSN resolution as the sibling
`garuda_orders`/`garuda_portal` integration suites (`INTAKE_TEST_DSN`,
`GARUDA_L3_TEST_DSN` optional override), same CI-fails-loud-not-skip
posture as `test_repository_integration.py`: this is a money-and-PII-
adjacent surface (it reads/creates rows for a paid order), never a quiet
skip in CI.

Drives real orders through `GarudaOrderRepository` (create -> paid) exactly
like `test_repository_integration.py` does, so these tests exercise
`PracticeRepository` against the SAME shape of `garuda_orders` /
`garuda_order_journal` rows production code produces -- never a hand-rolled
INSERT that could drift from what OP-00/OP-02 actually write.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_orders.idempotency import canonical_payload_sha256, scoped_key_sha256
from backend.services.garuda_orders.models import Applicant
from backend.services.garuda_orders.ports import ReviewedCheckSnapshot
from backend.services.garuda_orders.repository import GarudaOrderRepository
from backend.services.garuda_portal.practice import PracticeRepository
from backend.services.payments.port import CheckoutSession, NormalizedPaidEvent

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
)


class _FakeLookup:
    async def get_reviewed_check(self, result_id: str) -> ReviewedCheckSnapshot | None:
        return ReviewedCheckSnapshot(
            result_id=result_id, case_type=CaseType.ISSUANCE, review_confirmed=True
        )


class _FakeProvider:
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
        raise NotImplementedError


async def _ensure_garuda_order_test_policy(conn: asyncpg.Connection) -> str:
    """Verbatim copy of `test_repository_integration.py`'s own helper (scar
    W96: a policy row is a Zero-approved business decision, never a
    migration default -- migration 281 seeds none; see that file for the
    full self-heal reasoning this mirrors byte-for-byte rather than
    re-deriving from the schema by hand). `create_order_and_checkout` reads
    this gate, so every test here needs it too, even though this file's own
    subject (`PracticeRepository`) never reads it directly -- `garuda_
    practices` deliberately has no independent retention-policy check
    (287's own header explains why: it rides the already-authorized
    order's policy, never a second gate)."""
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_ORDER'
           AND upper(effective_period) IS NULL
        """
    )
    policy_version = f"l4-practice-test-fixture-{uuid.uuid4().hex[:16]}"
    await conn.execute(
        """
        INSERT INTO public.visa_decision_retention_policies (
            environment, policy_scope, policy_version, retention_interval,
            idempotency_retention_interval, legal_hold_review_interval,
            retention_anchor, effective_period, approved_by, approval_reference
        ) VALUES (
            'TEST', 'GARUDA_ORDER', $1, INTERVAL '90 days',
            INTERVAL '1 hour', INTERVAL '30 days',
            'CREATED_AT', tstzrange(clock_timestamp(), NULL, '[)'),
            'zero-test-approver', 'ZERO-GARUDA-ORDER-RETENTION-TEST-APPROVAL'
        )
        ON CONFLICT DO NOTHING
        """,
        policy_version,
    )
    return policy_version


async def _close_garuda_order_test_policy(conn: asyncpg.Connection, policy_version: str) -> None:
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE policy_scope = 'GARUDA_ORDER'
           AND policy_version = $1
           AND upper(effective_period) IS NULL
        """,
        policy_version,
    )


@pytest.fixture
async def pool():
    try:
        p = await asyncpg.create_pool(dsn=_DSN, min_size=1, max_size=2)
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            pytest.fail(
                f"CI has no reachable Postgres for INTAKE_TEST_DSN "
                f"(or GARUDA_L3_TEST_DSN override) -- {_DSN!r} unreachable: {exc}. "
                f"This surface creates rows for a paid order; it must never "
                f"silently pass by skipping."
            )
        pytest.skip(f"no local Postgres reachable at {_DSN}: {exc}")
    async with p.acquire() as conn:
        await conn.execute(
            "TRUNCATE garuda_practices, garuda_order_outbox, garuda_order_journal, "
            "garuda_payment_inbox, garuda_order_idempotency, garuda_orders CASCADE"
        )
        policy_version = await _ensure_garuda_order_test_policy(conn)
    yield p
    async with p.acquire() as conn:
        await _close_garuda_order_test_policy(conn, policy_version)
    await p.close()


@pytest.fixture
def order_repository(pool, monkeypatch):
    import backend.services.garuda_orders.repository as repository_module

    monkeypatch.setattr(
        repository_module.pricing,
        "price_for_case",
        lambda case_type, *, today: (790_000, "B1 Visa on Arrival (VOA)"),
    )
    return GarudaOrderRepository(
        pool, eligibility_lookup=_FakeLookup(), provider=_FakeProvider(), environment="TEST"
    )


@pytest.fixture
def practice_repository(pool) -> PracticeRepository:
    return PracticeRepository(pool)


def _applicant() -> Applicant:
    return Applicant(
        full_name="Test User", email="t@example.com", phone="+10000000", passport_number="P1234567"
    )


async def _create_and_pay_order(order_repository, *, result_id: str, provider_event_id: str) -> str:
    """Drives one order from creation through OP-02 (paid), returning its
    order_id -- the real production path PracticeRepository must observe,
    never a hand-rolled `garuda_orders` row."""
    key_digest = scoped_key_sha256(
        actor=result_id, operation="createOrderFromCheck", raw_key=f"idem-{provider_event_id}"
    )
    payload_digest = canonical_payload_sha256({"result_id": result_id, "applicant": {"e": 1}})
    body, _replayed = await order_repository.create_order_and_checkout(
        result_id=result_id,
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    order_id = body["order_id"]
    event = NormalizedPaidEvent(
        provider_event_id=provider_event_id,
        provider_charge_id=f"charge-{provider_event_id}",
        provider_session_id=f"sess-{order_id}",
        amount_idr=body["price_idr"],
        currency="IDR",
    )
    transition = await order_repository.handle_paid_event(
        event, canonical_payload_sha256=b"\x00" * 32
    )
    assert transition == "OP-02"
    return order_id


@pytest.mark.asyncio
async def test_unpaid_order_has_no_practice(pool, order_repository, practice_repository):
    key_digest = scoped_key_sha256(
        actor="result-unpaid-000000000", operation="createOrderFromCheck", raw_key="idem-unpaid-1"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-unpaid-000000000", "applicant": {"e": 1}}
    )
    body, _ = await order_repository.create_order_and_checkout(
        result_id="result-unpaid-000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    order_id = body["order_id"]

    view = await practice_repository.get_order_and_practice_view(
        order_id=order_id, result_id_ref="result-unpaid-000000000"
    )
    assert view is not None
    assert view["order_state"] == "awaiting_payment"
    assert view["practice"] is None

    count = await pool.fetchval("SELECT count(*) FROM garuda_practices")
    assert count == 0


@pytest.mark.asyncio
async def test_a_paid_order_gets_a_received_practice_on_first_read(
    pool, order_repository, practice_repository
):
    order_id = await _create_and_pay_order(
        order_repository, result_id="result-paid-0000000000", provider_event_id="evt-p1"
    )

    view = await practice_repository.get_order_and_practice_view(
        order_id=order_id, result_id_ref="result-paid-0000000000"
    )
    assert view is not None
    assert view["order_state"] == "paid"
    assert view["practice"] == {
        "practice_id": view["practice"]["practice_id"],
        "state": "Received",
        "artifact_available": False,
    }
    assert view["practice"]["practice_id"].startswith("practice_")

    # Never leak staff-only/internal columns onto the wire shape.
    for forbidden_key in ("private_staff_note", "resume_target", "artifact_id", "artifact_digest"):
        assert forbidden_key not in view["practice"]

    row = await pool.fetchrow(
        "SELECT state, source_paid_journal_event_id FROM garuda_practices WHERE order_id = $1",
        order_id,
    )
    assert row["state"] == "Received"

    journal_row = await pool.fetchrow(
        "SELECT event_id FROM garuda_order_journal "
        "WHERE aggregate_type = 'practice' AND transition_id = 'PR-01' AND aggregate_id = $1",
        view["practice"]["practice_id"],
    )
    assert journal_row is not None

    outbox_row = await pool.fetchrow(
        "SELECT job_type FROM garuda_order_outbox WHERE order_id = $1 AND job_type = 'practice_received_email'",
        order_id,
    )
    assert outbox_row is not None


@pytest.mark.asyncio
async def test_second_read_is_idempotent_no_duplicate_practice_or_journal_event(
    pool, order_repository, practice_repository
):
    order_id = await _create_and_pay_order(
        order_repository, result_id="result-paid2-000000000", provider_event_id="evt-p2"
    )

    view1 = await practice_repository.get_order_and_practice_view(
        order_id=order_id, result_id_ref="result-paid2-000000000"
    )
    view2 = await practice_repository.get_order_and_practice_view(
        order_id=order_id, result_id_ref="result-paid2-000000000"
    )
    assert view1["practice"]["practice_id"] == view2["practice"]["practice_id"]

    practice_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_practices WHERE order_id = $1", order_id
    )
    assert practice_count == 1

    journal_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_order_journal WHERE aggregate_type = 'practice' AND transition_id = 'PR-01'"
    )
    assert journal_count == 1

    outbox_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_order_outbox WHERE order_id = $1 AND job_type = 'practice_received_email'",
        order_id,
    )
    assert outbox_count == 1


@pytest.mark.asyncio
async def test_ownership_filter_hides_practice_from_a_different_result_id(
    pool, order_repository, practice_repository
):
    """The same ownership predicate #4910 closed on the order query must
    hold on the practice read too -- a paid order's practice is never
    observable through a `result_id_ref` that does not own it."""
    order_id = await _create_and_pay_order(
        order_repository, result_id="result-owner-00000000000", provider_event_id="evt-p3"
    )

    view = await practice_repository.get_order_and_practice_view(
        order_id=order_id, result_id_ref="result-intruder-000000000"
    )
    assert view is None

    # And the intruding read must not have side-effected a practice into
    # existence for an order it cannot even see.
    count = await pool.fetchval("SELECT count(*) FROM garuda_practices WHERE order_id = $1", order_id)
    assert count == 0


@pytest.mark.asyncio
async def test_concurrent_reads_of_a_paid_order_never_duplicate_pr01(
    pool, order_repository, practice_repository
):
    """Two racing reads of the same freshly-paid order must both observe
    the SAME practice_id, never mint two -- `source_paid_journal_event_id`'s
    UNIQUE constraint (migration 287) is what makes this structural, not
    just usually-true under a single-threaded test."""
    import asyncio

    order_id = await _create_and_pay_order(
        order_repository, result_id="result-race-0000000000", provider_event_id="evt-p4"
    )

    results = await asyncio.gather(
        *(
            practice_repository.get_order_and_practice_view(
                order_id=order_id, result_id_ref="result-race-0000000000"
            )
            for _ in range(5)
        )
    )
    practice_ids = {r["practice"]["practice_id"] for r in results}
    assert len(practice_ids) == 1

    practice_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_practices WHERE order_id = $1", order_id
    )
    assert practice_count == 1
    journal_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_order_journal WHERE aggregate_type = 'practice' AND transition_id = 'PR-01'"
    )
    assert journal_count == 1


@pytest.mark.asyncio
async def test_nonexistent_order_returns_none(pool, practice_repository):
    view = await practice_repository.get_order_and_practice_view(
        order_id="ord_does_not_exist_00000", result_id_ref="result-whatever-00000000"
    )
    assert view is None


@pytest.mark.asyncio
async def test_paid_order_with_no_op02_journal_event_fails_safe_not_500(
    pool, order_repository, practice_repository
):
    """Defensive-branch coverage (bite-proof self-review finding, ROUND 2
    after the first attempt below was itself wrong): a `paid` order with no
    matching OP-02 `garuda_order_journal` row should be structurally
    unreachable in production (`handle_paid_event` writes `state='paid'`
    and appends `payment.paid` in the SAME transaction, SM-G07).

    The first version of this test tried to force the anomaly with a
    `DELETE FROM garuda_order_journal` after a real payment -- that raised
    `CheckViolationError: garuda_order_journal is append-only` from
    migration 284's own guard trigger, which forbids UPDATE/DELETE
    unconditionally. That failure is itself the finding: the "should be
    unreachable" claim in `_create_received_practice`'s docstring is
    actually enforced by the DATABASE, not merely true by construction of
    the application code paths -- a stronger guarantee than assumed, and
    a genuine reason this branch cannot be exercised through the public
    `PracticeRepository` surface at all with a real Postgres. Covered
    instead as a narrow unit test directly against `_create_received_
    practice` with a query stub, so the "logs and returns None rather than
    raising" behavior still has a red/green test even though the schema
    makes the scenario it defends against unreachable end-to-end."""

    class _NoOp02JournalConnection:
        """Answers `SELECT event_id FROM garuda_order_journal ...` (the
        OP-02 lookup) with no row, and fails loudly on anything else --
        this stub exists to exercise exactly one branch, not to fake a
        real connection's full surface."""

        def transaction(self):
            class _Txn:
                async def __aenter__(self_inner):
                    return None

                async def __aexit__(self_inner, *exc):
                    return False

            return _Txn()

        async def fetchrow(self, query: str, *args):
            if "FROM garuda_order_journal" in query:
                return None
            raise AssertionError(f"unexpected fetchrow in stub: {query}")

    from backend.services.garuda_portal.practice import PracticeRepository

    repo = PracticeRepository(pool=None)  # never used -- this call takes conn directly
    result = await repo._create_received_practice(
        _NoOp02JournalConnection(), order_id="ord_stub_no_op02_000"
    )
    assert result is None
