"""Real-database integration tests for GarudaOrderRepository.

Requires a real Postgres. DSN resolution (gate finding, round 3, corrected):
CI never set `GARUDA_L3_TEST_DSN` -- that name appears nowhere in
`.github/` -- so every test here was silently `pytest.skip`ping in the ONLY
run that gates the merge, on a suite that is nothing but the money paths
(amount reconciliation, double-charge, late-money remediation). A skip in a
gate is a fail-open.

Every other garuda lane reaches Postgres through `INTAKE_TEST_DSN` -- a
variable this repo already established and CI already sets (see
`.github/workflows/tests.yml`). This module now reads it the same way, so
it joins the pattern the rest of the product already uses instead of being
the one branch nobody wired. `GARUDA_L3_TEST_DSN` remains as an optional
override for a local throwaway database. In CI (`CI` env var set), a
connection failure now FAILS the test run instead of skipping it -- no
reachable database in CI is a finding, not a reason to pass.
"""

from __future__ import annotations

import os
import uuid
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
    ChargeConfirmation,
    NormalizedFailureEvent,
    NormalizedPaidEvent,
    NormalizedRefundEvent,
)
from backend.services.payments.terminal_taxonomy import FailureOutcome, classify
from backend.tests.fixtures.prod_shaped_pool import create_prod_shaped_pool

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
)


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
        # OP-F08: None keeps every existing test's behaviour (reconciliation
        # always confirms unpaid). Set this to make the provider answer "yes,
        # there is a charge" for the OP-F08 late-case-from-reconciliation tests.
        self.charge_confirmation_override: ChargeConfirmation | None = None

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

    async def confirm_no_successful_charge(self, *, provider_session_id: str) -> ChargeConfirmation:
        if self.charge_confirmation_override is not None:
            return self.charge_confirmation_override
        return ChargeConfirmation(confirmed_unpaid=True)

    async def refund(self, *, provider_charge_id: str, idempotency_key: str) -> str:
        self.refund_calls.append(provider_charge_id)
        return "refund-fake-1"


async def _ensure_garuda_order_test_policy(conn: asyncpg.Connection) -> str:
    """Install this suite's own Zero-approved GARUDA_ORDER retention policy fixture.

    SM-G01/OP-F07 (migration 284, `active_garuda_order_policy_available`) fails
    closed by construction -- migration 281 deliberately seeds NO policy row for
    ANY scope, GARUDA_ORDER included: a policy is a Zero-approved business
    decision, never a migration default (products/garuda-voa/DECISIONS.md).
    Every test in this file exercises `create_order_and_checkout`, which reads
    that gate, so the fixture -- not a migration -- installs the row this suite
    needs, exactly like `test_retention.py` / `test_garuda_voa_retention.py`
    already do for GARUDA_CHECK via `_insert_garuda_check_policy`.

    `environment='TEST'` matches the `repository` fixture below
    (`GarudaOrderRepository(..., environment="TEST")`) -- both were 'PRODUCTION'
    in an earlier draft (review finding: a row that says PRODUCTION is not
    self-evidently a test artifact from that column alone, unlike L1's own
    fixture, which already used 'TEST'). Nothing about the code under test
    requires 'PRODUCTION' specifically; the environment string is just the
    scoping key the DB function filters on.

    `policy_version` is a FRESH uuid4 per pool-fixture run, not a fixed
    string (review finding, round 2): `visa_decision_retention_policies` is
    genuinely append-only -- `guard_visa_decision_retention_policy_mutation`
    (migration 264) unconditionally raises on DELETE, and permits an UPDATE
    ONLY to close a still-open `effective_period` (verified against the
    trigger source, not assumed). A DELETE-based teardown is therefore not
    possible on this table by design, unlike a plain fixture table. The
    correspoding `_close_garuda_order_test_policy` (below) closes this run's
    row in the `pool` fixture's teardown -- the one mutation the guard
    allows -- so it stops satisfying `active_garuda_order_policy_available()`
    once the test run ends (review finding, scar W96: a fixture must not
    leave a live, usable policy in a database other test files/CI runs also
    write to) without violating the append-only invariant the table exists
    to enforce. Each run's fresh `policy_version` means a later run's INSERT
    never conflicts with an earlier run's now-closed row -- closed rows
    accumulate harmlessly as exactly the kind of policy-history audit trail
    this table is designed to keep. Bare `ON CONFLICT DO NOTHING` (no
    target) still guards the INSERT itself against a same-process retry
    racing on the same version (astronomically unlikely with a uuid4, but
    free); it does NOT swallow anything else -- CHECK/NOT NULL violations
    on this table (verified against migrations 264+281) are outside
    `ON CONFLICT`'s scope and still raise, so a genuinely different insert
    failure still fails this fixture (and every test using it) loudly.

    SELF-HEAL FIRST (round 2 finding, caught live): a fresh uuid version
    alone is not sufficient. The EXCLUDE constraint on
    `(environment, policy_scope, effective_period WITH &&)` allows at most
    ONE open-ended (upper bound NULL) policy per (environment, policy_scope)
    at a time REGARDLESS of policy_version -- that is its entire purpose
    (see `test_two_overlapping_garuda_check_policies_are_structurally_
    impossible` for the GARUDA_CHECK analog). If any earlier run's teardown
    never executed (crash, Ctrl-C, or -- reproduced live while building this
    fix -- a stale row left by an earlier, buggy version of this same
    fixture), that leftover OPEN row silently blocks this run's INSERT via
    the same bare `ON CONFLICT DO NOTHING`: the insert is skipped, no
    exception is raised, and every test in the file quietly runs against
    the STALE row's (possibly wrong) shape instead of the fresh one this
    call intended to install. So: close any dangling open GARUDA_ORDER/TEST
    row FIRST, unconditionally, using the same guard-permitted close this
    function's teardown counterpart uses -- a no-op if none exists (the
    UPDATE's WHERE matches zero rows), and otherwise self-heals the mess a
    crashed prior run left behind instead of silently reusing it.

    LOWER BOUND IS `clock_timestamp()`, NOT BACKDATED (round 2 finding,
    also caught live): L1's own `_insert_garuda_check_policy` backdates its
    lower bound by 1 day, because its sandbox is a THROWAWAY per-test
    database with no policy history to collide with. Copying that same
    backdate here reintroduced the exact overlap this self-heal exists to
    prevent: a policy just closed at `clock_timestamp()` still has a lower
    bound from up to a day earlier, so a fresh row starting "1 day ago"
    still overlaps it, and the EXCLUDE conflict (silently swallowed by
    `ON CONFLICT DO NOTHING`) recurred even with the self-heal in place --
    reproduced live, traced to this exact line. Nothing here needs a
    lookback window: the repository call this fixture serves reads
    `datetime.now(UTC)` in Python strictly AFTER this INSERT commits, and
    `clock_timestamp()` evaluated in a later statement on the same
    connection is guaranteed >= any earlier statement's close time. An
    unbackdated lower bound therefore never overlaps a prior row this same
    self-heal already closed, on this run or any before it.
    """
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_ORDER'
           AND upper(effective_period) IS NULL
        """
    )
    policy_version = f"l3-test-fixture-{uuid.uuid4().hex[:16]}"
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
    """Teardown counterpart to `_ensure_garuda_order_test_policy` (scar W96).

    Closes (never deletes -- see that function's docstring for why DELETE is
    structurally impossible here) exactly this run's row, scoped by its
    unique `policy_version`: never a bare scope/environment update, which
    could touch a row a different suite or a real approval also placed
    under GARUDA_ORDER. `WHERE upper(effective_period) IS NULL` makes this
    safe to call even if the row were somehow already closed -- the guard
    trigger rejects closing an already-closed row, so the predicate must
    exclude it rather than let the exception surface in teardown.
    """
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
        p = await create_prod_shaped_pool(_DSN, min_size=1, max_size=2)
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            # A skip in a gate is a fail-open (gate finding, round 3): every
            # test in this file is a money path. If CI cannot reach the
            # Postgres it advertises via INTAKE_TEST_DSN (or a
            # GARUDA_L3_TEST_DSN override), that is a red build, never a
            # quiet skip.
            pytest.fail(
                f"CI has no reachable Postgres for INTAKE_TEST_DSN "
                f"(or GARUDA_L3_TEST_DSN override) -- {_DSN!r} unreachable: {exc}. "
                f"This is the gate for this directory's money tests; it must "
                f"never silently pass by skipping."
            )
        pytest.skip(f"no local Postgres reachable at {_DSN}: {exc}")
        raise AssertionError("unreachable: pytest.skip always raises") from exc
    async with p.acquire() as conn:
        await conn.execute(
            "TRUNCATE garuda_order_outbox, garuda_order_journal, garuda_payment_inbox, garuda_order_idempotency, garuda_orders CASCADE"
        )
        policy_version = await _ensure_garuda_order_test_policy(conn)
    yield p
    async with p.acquire() as conn:
        await _close_garuda_order_test_policy(conn, policy_version)
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
        pool, eligibility_lookup=_FakeLookup(), provider=_FakeProvider(), environment="TEST"
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

    # ... and the REASON is on the record, not just the refusal (migration 298).
    # RED IF: `_quarantine` stops recording a cause, or records the wrong one.
    # Without this, the alarm that reads these rows can only say "1 event
    # quarantined, cause unknown" — and an amount mismatch, an unknown checkout
    # session and an unbound order are three different incidents with three
    # different cures.
    quarantine = await pool.fetchrow(
        "SELECT outcome, quarantine_reason FROM garuda_payment_inbox "
        "WHERE provider = 'xendit' AND provider_event_id = $1",
        "evt-wrong-amount-1",
    )
    assert quarantine["outcome"] == "quarantined"
    assert quarantine["quarantine_reason"] == "amount_mismatch"


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


@pytest.mark.asyncio
async def test_fresh_idempotency_key_against_a_still_live_order_does_not_crash(pool, repository):
    """Gate finding: a customer who reloads and issues a FRESH Idempotency-
    Key against a still-live `result_id_ref` used to hit `INSERT INTO
    garuda_orders` head-on into `uq_garuda_orders_result_id_ref_live` with no
    ON CONFLICT -- a raw asyncpg.UniqueViolationError -> 500 on the
    self-recovery path of a payment flow. The repository must instead find
    the live order and bind the new key to it, returning ITS real state."""

    key_digest_1 = scoped_key_sha256(
        actor="actor-9", operation="createOrderFromCheck", raw_key="idem-key-reload-0001"
    )
    payload_digest_1 = canonical_payload_sha256(
        {"result_id": "result-9-0000000000", "applicant": {"e": 9}}
    )
    body1, replayed1 = await repository.create_order_and_checkout(
        result_id="result-9-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest_1,
        canonical_payload_sha256=payload_digest_1,
    )
    assert replayed1 is False
    order_id = body1["order_id"]

    # A DIFFERENT (fresh) Idempotency-Key -- e.g. the customer reloaded the
    # checkout page and their client minted a new key -- against the SAME
    # still-live result_id_ref. This must not raise, and must resolve to
    # the SAME order rather than attempting (and failing) to create a second
    # live one.
    key_digest_2 = scoped_key_sha256(
        actor="actor-9", operation="createOrderFromCheck", raw_key="idem-key-reload-0002"
    )
    payload_digest_2 = canonical_payload_sha256(
        {"result_id": "result-9-0000000000", "applicant": {"e": 9}}
    )
    body2, replayed2 = await repository.create_order_and_checkout(
        result_id="result-9-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest_2,
        canonical_payload_sha256=payload_digest_2,
    )
    # Not a "replay" in the idempotency-cache sense (different key), but it
    # must resolve to the SAME live order, not a crash and not a duplicate.
    assert replayed2 is False
    assert body2["order_id"] == order_id
    assert body2["order_state"] == "awaiting_payment"

    count = await pool.fetchval(
        "SELECT count(*) FROM garuda_orders WHERE result_id_ref = 'result-9-0000000000'"
    )
    assert count == 1  # never a duplicate live order for the same check


@pytest.mark.asyncio
async def test_concurrent_order_creation_race_falls_back_to_the_winner_not_a_crash(
    pool, repository, monkeypatch
):
    """Gate finding: the live-order lookup and the INSERT are two separate
    statements, not one atomic unit -- two concurrent requests with two
    fresh keys and no live order can both read `existing=None` and both
    attempt the insert. Reproduces the LOSER's exact race window by forcing
    its own lookup to return None (as if it ran BEFORE the winner's insert
    committed), so its INSERT hits the REAL unique-constraint violation the
    winner already created -- and asserts it recovers by binding to the
    winner's order instead of raising."""

    winner_body, _ = await repository.create_order_and_checkout(
        result_id="result-10-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=scoped_key_sha256(
            actor="actor-10", operation="createOrderFromCheck", raw_key="idem-key-race-winner-01"
        ),
        canonical_payload_sha256=canonical_payload_sha256(
            {"result_id": "result-10-0000000000", "applicant": {"e": 10}}
        ),
    )
    winner_order_id = winner_body["order_id"]

    # Force the LOSER's live-order lookup to see `existing=None` exactly
    # once, as if it executed before the winner's INSERT committed. Patched
    # at the level actually invoked through `pool.acquire()`
    # (PoolConnectionProxy.fetchrow calls self._execute directly -- it does
    # NOT delegate to Connection.fetchrow, so that is the wrong patch point).
    real_fetchrow = asyncpg.pool.PoolConnectionProxy.fetchrow
    state = {"suppressed": False}

    async def _patched_fetchrow(self, query, *args, **kwargs):
        if (
            not state["suppressed"]
            and "SELECT order_id FROM garuda_orders" in query
            and "state IN ('created', 'awaiting_payment', 'paid')" in query
        ):
            state["suppressed"] = True
            return None
        return await real_fetchrow(self, query, *args, **kwargs)

    monkeypatch.setattr(asyncpg.pool.PoolConnectionProxy, "fetchrow", _patched_fetchrow)

    loser_body, replayed = await repository.create_order_and_checkout(
        result_id="result-10-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=scoped_key_sha256(
            actor="actor-10", operation="createOrderFromCheck", raw_key="idem-key-race-loser-01"
        ),
        canonical_payload_sha256=canonical_payload_sha256(
            {"result_id": "result-10-0000000000", "applicant": {"e": 10}}
        ),
    )
    assert replayed is False
    assert loser_body["order_id"] == winner_order_id  # falls back to the real winner, no crash

    count = await pool.fetchval(
        "SELECT count(*) FROM garuda_orders WHERE result_id_ref = 'result-10-0000000000'"
    )
    assert count == 1  # the loser never created a second live order


# --- OP-F08: reconciliation finds a charge no webhook ever delivered ------


@pytest.mark.asyncio
async def test_op_f08_opens_a_late_case_when_reconciliation_finds_a_charge_and_no_webhook_ever_came(
    pool, repository
):
    """Before this existed, `expire_if_unpaid` only logged a warning when the
    provider reported a charge -- the order stayed `awaiting_payment` and no
    human was ever told. OP-F08 makes that case a visible, refundable late
    case instead of a silent log line."""

    key_digest = scoped_key_sha256(
        actor="actor-11", operation="createOrderFromCheck", raw_key="idem-key-f08a-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-11-0000000000", "applicant": {"e": 11}}
    )
    body, _ = await repository.create_order_and_checkout(
        result_id="result-11-0000000000",
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
    repository._provider.charge_confirmation_override = ChargeConfirmation(
        confirmed_unpaid=False, provider_charge_id="charge-op-f08-1", provider_status="SETTLED"
    )

    from backend.services.garuda_orders.reconciliation import reconcile_expired_checkouts

    summary = await reconcile_expired_checkouts(pool, repository, limit=10)
    assert summary.expired == 0
    assert summary.late_cases_opened == 1
    assert summary.left_for_webhook == 0

    state, late_open, late_charge_id = await pool.fetchrow(
        "SELECT state, late_case_open, late_case_charge_id FROM garuda_orders WHERE order_id = $1",
        order_id,
    )
    assert state == "awaiting_payment"  # only a signed webhook may write `paid`
    assert late_open is True
    assert late_charge_id == "charge-op-f08-1"

    journal_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_order_journal "
        "WHERE aggregate_id = $1 AND event_name = 'payment.charge_detected_without_webhook' "
        "AND transition_id = 'OP-F08'",
        order_id,
    )
    assert journal_count == 1
    outbox_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_order_outbox o "
        "JOIN garuda_order_journal j ON j.event_id = o.journal_event_id "
        "WHERE o.order_id = $1 AND o.job_type = 'staff_page_charge_without_webhook'",
        order_id,
    )
    assert outbox_count == 1


@pytest.mark.asyncio
async def test_op_f08_pages_once_per_case_not_once_per_scheduler_tick(pool, repository):
    """Idempotency proof, at BOTH layers, because they defend differently.

    The sweep's SELECT now excludes an order whose late case is open, so
    ticks 2 and 3 never reach the repository at all (that is the cure for
    re-asking the provider about the same order forever). The repository's
    compare-and-set is the layer BELOW it, and a filter that stops
    exercising the CAS would quietly retire the guard it was written for —
    so this test calls `expire_if_unpaid` directly afterwards, which is the
    path a concurrent tick or a manual replay still takes.
    """

    key_digest = scoped_key_sha256(
        actor="actor-12", operation="createOrderFromCheck", raw_key="idem-key-f08b-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-12-0000000000", "applicant": {"e": 12}}
    )
    body, _ = await repository.create_order_and_checkout(
        result_id="result-12-0000000000",
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
    repository._provider.charge_confirmation_override = ChargeConfirmation(
        confirmed_unpaid=False, provider_charge_id="charge-op-f08-2", provider_status="SETTLED"
    )

    from backend.services.garuda_orders.reconciliation import reconcile_expired_checkouts

    for _ in range(3):
        await reconcile_expired_checkouts(pool, repository, limit=10)

    late_open = await pool.fetchval(
        "SELECT late_case_open FROM garuda_orders WHERE order_id = $1", order_id
    )
    assert late_open is True
    journal_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_order_journal "
        "WHERE aggregate_id = $1 AND event_name = 'payment.charge_detected_without_webhook'",
        order_id,
    )
    assert journal_count == 1  # not once per tick
    outbox_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_order_outbox o "
        "JOIN garuda_order_journal j ON j.event_id = o.journal_event_id "
        "WHERE o.order_id = $1 AND o.job_type = 'staff_page_charge_without_webhook'",
        order_id,
    )
    assert outbox_count == 1

    swept = await pool.fetchval(
        """
        SELECT count(*) FROM garuda_orders
         WHERE order_id = $1
           AND state = 'awaiting_payment'
           AND checkout_expires_at < now()
           AND late_case_open = FALSE
           AND late_case_resolution IS NULL
        """,
        order_id,
    )
    assert swept == 0  # the sweep's own predicate no longer selects it

    # The layer below: a direct call (what a concurrent tick does) must still
    # find the CAS closed against it.
    direct_outcome = await repository.expire_if_unpaid(
        order_id=order_id, provider_session_id=f"sess-{order_id}"
    )
    assert direct_outcome.expired is False
    assert direct_outcome.late_case_opened is False
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM garuda_order_journal "
            "WHERE aggregate_id = $1 AND event_name = 'payment.charge_detected_without_webhook'",
            order_id,
        )
        == 1
    )


@pytest.mark.asyncio
async def test_reconciliation_still_expires_an_order_the_provider_confirms_unpaid(pool, repository):
    """Innocence control for OP-F08: when the provider confirms no charge
    exists, reconciliation still reaches OP-04 as before -- no late case, no
    OP-F08 journal event."""

    key_digest = scoped_key_sha256(
        actor="actor-13", operation="createOrderFromCheck", raw_key="idem-key-f08c-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-13-0000000000", "applicant": {"e": 13}}
    )
    body, _ = await repository.create_order_and_checkout(
        result_id="result-13-0000000000",
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
    # repository._provider.charge_confirmation_override left at its default
    # (None -> ChargeConfirmation(confirmed_unpaid=True)): the provider
    # confirms no accepted charge, exactly OP-04's happy path.

    from backend.services.garuda_orders.reconciliation import reconcile_expired_checkouts

    summary = await reconcile_expired_checkouts(pool, repository, limit=10)
    assert summary.expired == 1

    state, late_open = await pool.fetchrow(
        "SELECT state, late_case_open FROM garuda_orders WHERE order_id = $1", order_id
    )
    assert state == "expired"
    assert late_open is False
    journal_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_order_journal "
        "WHERE aggregate_id = $1 AND event_name = 'payment.charge_detected_without_webhook'",
        order_id,
    )
    assert journal_count == 0


@pytest.mark.asyncio
async def test_op_f08_does_not_open_a_case_on_an_order_the_webhook_already_paid(pool, repository):
    """Guilt test for the `state = 'awaiting_payment'` predicate (Codex
    gpt-5.6-sol finding, BLOCKING). Only `late_case_open` was checked before
    this: reconciliation selects an order, then the real webhook can land
    before the CAS UPDATE runs, opening a late case on an order that
    meanwhile reached `paid` -- and `resolve_late_order` does not re-check
    state before refunding, so a legitimate, fully reconciled payment became
    refundable.

    `reconcile_expired_checkouts` only SELECTs `awaiting_payment` rows, so
    driving the race through it would only prove the SELECT's own filter,
    not the UPDATE's guard. This calls `repository.expire_if_unpaid`
    directly on an order already `paid` -- the exact shape of the race
    window, where nothing upstream has filtered the order out yet -- so it
    is the UPDATE's own `state = 'awaiting_payment'` predicate under test."""

    key_digest = scoped_key_sha256(
        actor="actor-14", operation="createOrderFromCheck", raw_key="idem-key-f08d-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-14-0000000000", "applicant": {"e": 14}}
    )
    body, _ = await repository.create_order_and_checkout(
        result_id="result-14-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    order_id = body["order_id"]

    paid_event = NormalizedPaidEvent(
        provider_event_id="evt-f08-race-paid",
        provider_charge_id="charge-f08-race",
        provider_session_id=f"sess-{order_id}",
        amount_idr=body["price_idr"],
        currency="IDR",
    )
    transition = await repository.handle_paid_event(
        paid_event, canonical_payload_sha256=b"\x20" * 32
    )
    assert transition == "OP-02"
    assert (
        await pool.fetchval("SELECT state FROM garuda_orders WHERE order_id = $1", order_id)
        == "paid"
    )

    # The provider still reports a charge (it is the SAME charge the webhook
    # just recorded) -- reconciliation catching up to a payment it does not
    # yet know landed, the real race this predicate guards against.
    repository._provider.charge_confirmation_override = ChargeConfirmation(
        confirmed_unpaid=False, provider_charge_id="charge-f08-race", provider_status="SETTLED"
    )
    outcome = await repository.expire_if_unpaid(
        order_id=order_id, provider_session_id=f"sess-{order_id}"
    )
    assert outcome.expired is False
    # and NOT because a case was opened instead: the webhook won, so neither
    # branch fired. The bare bool this replaced could not tell those apart.
    assert outcome.late_case_opened is False

    state, late_open = await pool.fetchrow(
        "SELECT state, late_case_open FROM garuda_orders WHERE order_id = $1", order_id
    )
    assert state == "paid"  # unchanged -- and never became refundable
    assert late_open is False
    journal_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_order_journal "
        "WHERE aggregate_id = $1 AND event_name = 'payment.charge_detected_without_webhook'",
        order_id,
    )
    assert journal_count == 0


@pytest.mark.asyncio
async def test_op_f08_does_not_reopen_a_case_staff_already_resolved(pool, repository):
    """Guilt test for the `late_case_resolution IS NULL` predicate (Codex
    gpt-5.6-sol finding, MAJOR). After staff close a case as `honoured` the
    order KEEPS `awaiting_payment` (OP-F08 never writes `paid`) and the
    provider keeps answering "there is a charge", so an unguarded UPDATE
    would try to reopen it on the very next tick -- and migration 284's CHECK
    forbids `(late_case_open = TRUE, late_case_resolution IS NOT NULL)`, so
    that is not a duplicate page, it is a `check_violation` on EVERY tick
    forever, silently swallowed by the caller's `except Exception: continue`.
    """

    key_digest = scoped_key_sha256(
        actor="actor-15", operation="createOrderFromCheck", raw_key="idem-key-f08e-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-15-0000000000", "applicant": {"e": 15}}
    )
    body, _ = await repository.create_order_and_checkout(
        result_id="result-15-0000000000",
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
    repository._provider.charge_confirmation_override = ChargeConfirmation(
        confirmed_unpaid=False, provider_charge_id="charge-f08-resolved", provider_status="SETTLED"
    )

    from backend.services.garuda_orders.reconciliation import reconcile_expired_checkouts

    await reconcile_expired_checkouts(pool, repository, limit=10)
    assert (
        await pool.fetchval(
            "SELECT late_case_open FROM garuda_orders WHERE order_id = $1", order_id
        )
        is True
    )

    resolve_key = scoped_key_sha256(
        actor="staff-2", operation="resolveLateOrder", raw_key="idem-key-f08-resolve-0001"
    )
    resolve_payload = canonical_payload_sha256(
        {"order_id": order_id, "resolution": "honoured", "staff_reference": "case-f08-1"}
    )
    _resolution_body, replayed = await repository.resolve_late_order(
        order_id=order_id,
        resolution="honoured",
        staff_reference="case-f08-1",
        idempotency_key_sha256=resolve_key,
        canonical_payload_sha256=resolve_payload,
    )
    assert replayed is False
    late_open_after, resolution_col = await pool.fetchrow(
        "SELECT late_case_open, late_case_resolution FROM garuda_orders WHERE order_id = $1",
        order_id,
    )
    assert late_open_after is False
    assert resolution_col == "honoured"

    # The order is STILL awaiting_payment (resolve_late_order never writes
    # `state`) and the provider is STILL answering "there is a charge" --
    # exactly the shape that would retrigger the tick forever without the
    # resolution predicate. This must raise no exception.
    summary = await reconcile_expired_checkouts(pool, repository, limit=10)
    # STRONGER than "the write was refused": the sweep's own SELECT no longer
    # selects a resolved order at all, so the provider is never asked about it
    # again. Without that filter this order stays a candidate for the rest of
    # its life -- one provider call per tick, forever, and with `limit` rows
    # taken oldest-first, enough of them eventually crowd out real candidates.
    assert summary.candidates == 0
    assert summary.expired == 0
    assert summary.late_cases_opened == 0
    assert summary.left_for_webhook == 0

    late_open_final, resolution_final = await pool.fetchrow(
        "SELECT late_case_open, late_case_resolution FROM garuda_orders WHERE order_id = $1",
        order_id,
    )
    assert late_open_final is False
    assert resolution_final == "honoured"  # unchanged by the second tick

    journal_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_order_journal "
        "WHERE aggregate_id = $1 AND event_name = 'payment.charge_detected_without_webhook'",
        order_id,
    )
    assert journal_count == 1  # still exactly one -- the resolved tick added none


@pytest.mark.asyncio
async def test_a_late_case_is_closed_as_honoured_by_the_webhook_that_finally_arrives(
    pool, repository
):
    """GUILT for the mirror-image race (Codex `gpt-5.6-sol`, BLOCKING).

    OP-F08 opens a case on an order that is still LIVE -- that is what makes
    it different from OP-F04/F05, which only ever fire on terminal orders.
    So the webhook it is complaining about can still arrive: the callback URL
    gets registered, Xendit replays, OP-02 marks the order `paid` and mints
    the practice. Before this cure the case SURVIVED that: the order read
    `paid`, with a practice running, and an open `late_case_open` beside it --
    and `resolve_late_order` does not re-check `state` before calling
    `provider.refund`. A staff member working the page would have refunded a
    payment that had already bought the service.

    The close rides in OP-02's own transaction, so there is no window where
    the order is paid and the case is still open.
    """

    key_digest = scoped_key_sha256(
        actor="actor-16", operation="createOrderFromCheck", raw_key="idem-key-f08f-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-16-0000000000", "applicant": {"e": 16}}
    )
    body, _ = await repository.create_order_and_checkout(
        result_id="result-16-0000000000",
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
    repository._provider.charge_confirmation_override = ChargeConfirmation(
        confirmed_unpaid=False, provider_charge_id="inv-f08-late", provider_status="PAID"
    )

    from backend.services.garuda_orders.reconciliation import reconcile_expired_checkouts

    await reconcile_expired_checkouts(pool, repository, limit=10)
    assert (
        await pool.fetchval(
            "SELECT late_case_open FROM garuda_orders WHERE order_id = $1", order_id
        )
        is True
    )

    transition = await repository.handle_paid_event(
        NormalizedPaidEvent(
            provider_event_id="evt-paid-f08-late",
            provider_charge_id="inv-f08-late",
            provider_session_id=f"sess-{order_id}",
            amount_idr=body["price_idr"],
            currency="IDR",
        ),
        canonical_payload_sha256=b"\x16" * 32,
    )
    assert transition == "OP-02"

    state, late_open, resolution = await pool.fetchrow(
        "SELECT state, late_case_open, late_case_resolution FROM garuda_orders WHERE order_id = $1",
        order_id,
    )
    assert state == "paid"
    assert late_open is False
    assert resolution == "honoured"


@pytest.mark.asyncio
async def test_a_paid_order_that_never_had_a_late_case_records_no_resolution(pool, repository):
    """INNOCENCE control for the close above: `CASE WHEN late_case_open` reads
    the OLD row, so an order that never had a case must not come out of OP-02
    wearing a resolution for a case that never existed -- migration 284's CHECK
    admits `(open FALSE, resolution NOT NULL)` only as the shape of a case that
    was really closed."""

    key_digest = scoped_key_sha256(
        actor="actor-17", operation="createOrderFromCheck", raw_key="idem-key-f08g-0001"
    )
    payload_digest = canonical_payload_sha256(
        {"result_id": "result-17-0000000000", "applicant": {"e": 17}}
    )
    body, _ = await repository.create_order_and_checkout(
        result_id="result-17-0000000000",
        applicant=_applicant(),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    order_id = body["order_id"]

    transition = await repository.handle_paid_event(
        NormalizedPaidEvent(
            provider_event_id="evt-paid-no-case",
            provider_charge_id="inv-no-case",
            provider_session_id=f"sess-{order_id}",
            amount_idr=body["price_idr"],
            currency="IDR",
        ),
        canonical_payload_sha256=b"\x17" * 32,
    )
    assert transition == "OP-02"

    state, late_open, resolution = await pool.fetchrow(
        "SELECT state, late_case_open, late_case_resolution FROM garuda_orders WHERE order_id = $1",
        order_id,
    )
    assert state == "paid"
    assert late_open is False
    assert resolution is None
