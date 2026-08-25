"""HTTP-level ownership tests for `garuda_orders_router.py` (L3/L4 seam).

Two defects fixed together in the same PR, because fixing only the first
one ARMS the second:

1. `_require_magic_session_actor` had nothing wired to
   `app.state.garuda_magic_session_verifier` in production -- every
   authenticated route 401'd `SESSION_REQUIRED` unconditionally. Fixed by
   making the dependency `async def` (a real Postgres-backed verifier is
   async) and wiring `PostgresMagicLinkStore.verify_session` onto that
   attribute in `service_initializer.py`.

2. Once a session verifies, NOTHING compared the session's `result_id` to
   the order's `result_id_ref` -- any authenticated customer could read,
   write, or create against ANY other customer's order (an IDOR). Fixed by
   filtering every query/predicate on that pair.

Every test in this file is written to FAIL against the pre-fix code: the
cross-owner tests would have 401'd (not 404) before the verifier was wired,
and once a fake verifier is substituted to get past that 401, they would
have SUCCEEDED against someone else's order before the ownership predicate
existed. This file seeds two independent sessions/results/orders (A and B)
and asserts A can never observe or affect B's order, and vice versa via the
positive case.

Requires a real Postgres -- same DSN resolution as the sibling `garuda_orders`
/ `garuda_portal` integration suites (`INTAKE_TEST_DSN`, `GARUDA_L3_TEST_DSN`
optional local override), same CI-fails-loud-not-skip posture: a missing
Postgres in CI is a finding on this money-and-PII surface, never a quiet skip.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest

asyncpg = pytest.importorskip("asyncpg")

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.routers import garuda_orders_router
from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_orders.ports import ReviewedCheckSnapshot
from backend.services.garuda_orders.repository import GarudaOrderRepository
from backend.services.garuda_portal.magic_link_store import PostgresMagicLinkStore

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
)

_SESSION_COOKIE = "garuda_session"


@pytest.fixture(autouse=True)
def _garuda_public_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")


class _FakeLookup:
    async def get_reviewed_check(self, result_id: str) -> ReviewedCheckSnapshot | None:
        return ReviewedCheckSnapshot(
            result_id=result_id, case_type=CaseType.ISSUANCE, review_confirmed=True
        )


class _FakeProvider:
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
        return "refund-fake-1"


async def _ensure_garuda_order_test_policy(conn: asyncpg.Connection) -> str:
    """Same self-heal-first fixture as `test_repository_integration.py`'s
    `_ensure_garuda_order_test_policy` -- duplicated rather than imported
    because that module's fixtures are private, not a shared test-support
    surface (no `conftest.py` re-exports them). See that function's
    docstring for the full self-heal/no-backdate rationale; not re-derived
    here to avoid the two drifting apart.
    """
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_ORDER'
           AND upper(effective_period) IS NULL
        """
    )
    policy_version = f"l4-ownership-fixture-{uuid.uuid4().hex[:16]}"
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
                f"This is the gate for this file's ownership/IDOR tests; it must "
                f"never silently pass by skipping."
            )
        pytest.skip(f"no local Postgres reachable at {_DSN}: {exc}")
        # Unreachable: both pytest.fail and pytest.skip raise (Failed /
        # Skipped), so `p` is never read uninitialized below. CodeQL doesn't
        # model those as NoReturn -- this `raise` makes the termination
        # explicit to the analyser and re-propagates the original connection
        # error if that assumption ever stops being true.
        raise
    async with p.acquire() as conn:
        await conn.execute(
            "TRUNCATE garuda_order_outbox, garuda_order_journal, garuda_payment_inbox, "
            "garuda_order_idempotency, garuda_orders, garuda_account_sessions CASCADE"
        )
        policy_version = await _ensure_garuda_order_test_policy(conn)
    yield p
    async with p.acquire() as conn:
        await _close_garuda_order_test_policy(conn, policy_version)
    await p.close()


@pytest.fixture
def repository(pool, monkeypatch):
    # Same pricing-freshness pin as test_repository_integration.py's
    # `repository` fixture -- G-FRESHNESS-FAIL-CLOSED is garuda_flow's own
    # tested concern, not this file's.
    monkeypatch.setattr(
        "backend.services.garuda_orders.repository.pricing.price_for_case",
        lambda case_type, *, today: (790_000, "B1 Visa on Arrival (VOA)"),
    )
    return GarudaOrderRepository(
        pool, eligibility_lookup=_FakeLookup(), provider=_FakeProvider(), environment="TEST"
    )


@pytest.fixture
def magic_link_store(pool) -> PostgresMagicLinkStore:
    return PostgresMagicLinkStore(pool, environment="TEST")


@pytest.fixture
def app(repository: GarudaOrderRepository, pool, magic_link_store: PostgresMagicLinkStore) -> FastAPI:
    application = FastAPI()
    application.include_router(garuda_orders_router.router)
    application.state.garuda_order_repository = repository
    application.state.garuda_db_pool = pool
    application.state.garuda_magic_session_verifier = magic_link_store.verify_session
    return application


@pytest.fixture
def client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


def _hash_hex(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _seed_session(
    pool,
    *,
    raw_secret: str,
    result_id: str,
    email: str = "visitor@example.com",
    expires_at: datetime | None = None,
    created_at: datetime | None = None,
) -> None:
    # `garuda_account_sessions` CHECK requires `expires_at > created_at` --
    # a genuinely-expired row (expires_at in the past) needs created_at
    # pushed back further still, not left at its `statement_timestamp()`
    # default.
    resolved_expires_at = expires_at or (datetime.now(UTC) + timedelta(days=30))
    resolved_created_at = created_at or (resolved_expires_at - timedelta(days=30))
    await pool.execute(
        """
        INSERT INTO garuda_account_sessions
            (session_secret_hash, result_id, email, created_at, expires_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        _hash_hex(raw_secret),
        result_id,
        email,
        resolved_created_at,
        resolved_expires_at,
    )


async def _seed_order(
    pool, *, order_id: str, result_id_ref: str, price_idr: int = 790_000
) -> None:
    await pool.execute(
        """
        INSERT INTO garuda_orders (order_id, result_id_ref, case_type, applicant_full_name,
            applicant_email, applicant_phone, applicant_passport_number, price_idr,
            price_catalogue_key)
        VALUES ($1, $2, 'issuance', 'Order Owner', 'owner@example.com', '+10000000',
                'P0000001', $3, 'B1 Visa on Arrival (VOA)')
        """,
        order_id,
        result_id_ref,
        price_idr,
    )


def _idempotency_key(tag: str) -> str:
    return f"idem-{tag}-{secrets.token_hex(8)}"


# ============================================================
# Session verification (Defect 1)
# ============================================================


class TestSessionVerification:
    async def test_absent_cookie_is_rejected(self, client: AsyncClient) -> None:
        resp = await client.get("/api/visa/voa/orders/ord_absent_0000000000")
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "SESSION_REQUIRED"

    async def test_unknown_cookie_value_is_rejected(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/visa/voa/orders/ord_absent_0000000000",
            cookies={_SESSION_COOKIE: "not-a-real-session-secret"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "SESSION_REQUIRED"

    async def test_expired_session_is_rejected(
        self, pool, client: AsyncClient
    ) -> None:
        raw_secret = "expired-secret-0000000000000000000000000000"
        await _seed_session(
            pool,
            raw_secret=raw_secret,
            result_id="result-expired-00000000",
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        resp = await client.get(
            "/api/visa/voa/orders/ord_absent_0000000000",
            cookies={_SESSION_COOKIE: raw_secret},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "SESSION_REQUIRED"

    async def test_a_valid_session_reaches_past_the_401(
        self, pool, client: AsyncClient
    ) -> None:
        """Positive control: a live, unexpired session gets PAST the auth
        gate (a real ORDER_NOT_FOUND, never SESSION_REQUIRED) -- proves the
        401 tests above are testing the auth gate, not an unrelated 404."""
        raw_secret = "live-secret-00000000000000000000000000000"
        await _seed_session(pool, raw_secret=raw_secret, result_id="result-live-0000000000")
        resp = await client.get(
            "/api/visa/voa/orders/ord_absent_0000000000",
            cookies={_SESSION_COOKIE: raw_secret},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "ORDER_NOT_FOUND"


# ============================================================
# Ownership / IDOR (Defect 2)
# ============================================================


class TestGetOrderOwnership:
    async def test_a_session_cannot_read_another_customers_order(
        self, pool, client: AsyncClient
    ) -> None:
        raw_secret_a = "secret-a-get-000000000000000000000000000"
        await _seed_session(pool, raw_secret=raw_secret_a, result_id="result-a-get-000000000")
        await _seed_order(pool, order_id="ord_get_owned_by_b_0000", result_id_ref="result-b-get-000000000")

        resp = await client.get(
            "/api/visa/voa/orders/ord_get_owned_by_b_0000",
            cookies={_SESSION_COOKIE: raw_secret_a},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "ORDER_NOT_FOUND"

    async def test_a_session_can_read_its_own_order_and_only_the_frozen_fields(
        self, pool, client: AsyncClient
    ) -> None:
        raw_secret_a = "secret-a-get-own-00000000000000000000000"
        await _seed_session(pool, raw_secret=raw_secret_a, result_id="result-a-get-own-00000")
        await _seed_order(
            pool, order_id="ord_get_owned_by_a_0000", result_id_ref="result-a-get-own-00000"
        )

        resp = await client.get(
            "/api/visa/voa/orders/ord_get_owned_by_a_0000",
            cookies={_SESSION_COOKIE: raw_secret_a},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body == {
            "order_id": "ord_get_owned_by_a_0000",
            "order_state": "created",
            "price_idr": 790_000,
            "browser_observation": "browser_not_returned",
            "practice": None,
        }
        # No applicant PII in the response shape, today or after this fix.
        for pii_key in ("applicant_full_name", "applicant_email", "applicant_phone",
                        "applicant_passport_number"):
            assert pii_key not in body


class TestBrowserReturnObservationOwnership:
    async def test_a_session_cannot_write_an_observation_onto_another_customers_order(
        self, pool, client: AsyncClient
    ) -> None:
        raw_secret_a = "secret-a-obs-00000000000000000000000000"
        await _seed_session(pool, raw_secret=raw_secret_a, result_id="result-a-obs-000000000")
        await _seed_order(
            pool, order_id="ord_obs_owned_by_b_00000", result_id_ref="result-b-obs-000000000"
        )

        resp = await client.post(
            "/api/visa/voa/orders/ord_obs_owned_by_b_00000/browser-return-observations",
            cookies={_SESSION_COOKIE: raw_secret_a},
            headers={"Idempotency-Key": _idempotency_key("obs-deny")},
            json={"return_nonce": "n" * 20},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "ORDER_NOT_FOUND"

        row = await pool.fetchrow(
            "SELECT browser_observation, browser_return_nonce FROM garuda_orders WHERE order_id = $1",
            "ord_obs_owned_by_b_00000",
        )
        assert row["browser_observation"] == "browser_not_returned"
        assert row["browser_return_nonce"] is None

    async def test_a_session_can_write_an_observation_onto_its_own_order(
        self, pool, client: AsyncClient
    ) -> None:
        raw_secret_a = "secret-a-obs-own-0000000000000000000000"
        await _seed_session(pool, raw_secret=raw_secret_a, result_id="result-a-obs-own-00000")
        await _seed_order(
            pool, order_id="ord_obs_owned_by_a_00000", result_id_ref="result-a-obs-own-00000"
        )

        resp = await client.post(
            "/api/visa/voa/orders/ord_obs_owned_by_a_00000/browser-return-observations",
            cookies={_SESSION_COOKIE: raw_secret_a},
            headers={"Idempotency-Key": _idempotency_key("obs-allow")},
            json={"return_nonce": "n" * 20},
        )
        assert resp.status_code == 204, resp.text

        row = await pool.fetchrow(
            "SELECT browser_observation FROM garuda_orders WHERE order_id = $1",
            "ord_obs_owned_by_a_00000",
        )
        assert row["browser_observation"] == "browser_return_observed"


class TestCreateOrderOwnership:
    async def test_a_session_cannot_create_an_order_against_another_results_body(
        self, pool, client: AsyncClient
    ) -> None:
        raw_secret_a = "secret-a-create-000000000000000000000000"
        await _seed_session(pool, raw_secret=raw_secret_a, result_id="result-a-create-0000000")

        resp = await client.post(
            "/api/visa/voa/orders",
            cookies={_SESSION_COOKIE: raw_secret_a},
            headers={"Idempotency-Key": _idempotency_key("create-deny")},
            json={
                "result_id": "result-b-create-0000000",  # NOT session A's result_id
                "review_confirmed": True,
                "applicant": {
                    "full_name": "Someone Else",
                    "email": "someone@example.com",
                    "phone": "+10000001",
                    "passport_number": "P0000002",
                },
            },
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "RESULT_NOT_FOUND"

        count = await pool.fetchval(
            "SELECT count(*) FROM garuda_orders WHERE result_id_ref = $1", "result-b-create-0000000"
        )
        assert count == 0

    async def test_a_session_can_create_an_order_matching_its_own_result_id(
        self, pool, client: AsyncClient
    ) -> None:
        raw_secret_a = "secret-a-create-own-0000000000000000000"
        await _seed_session(pool, raw_secret=raw_secret_a, result_id="result-a-create-own-000")

        resp = await client.post(
            "/api/visa/voa/orders",
            cookies={_SESSION_COOKIE: raw_secret_a},
            headers={"Idempotency-Key": _idempotency_key("create-allow")},
            json={
                "result_id": "result-a-create-own-000",
                "review_confirmed": True,
                "applicant": {
                    "full_name": "Test User",
                    "email": "t@example.com",
                    "phone": "+10000000",
                    "passport_number": "P1234567",
                },
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["order_state"] == "awaiting_payment"

        count = await pool.fetchval(
            "SELECT count(*) FROM garuda_orders WHERE result_id_ref = $1",
            "result-a-create-own-000",
        )
        assert count == 1


# ============================================================
# db_pool degradation shape (gate finding, not in the original brief):
# `service_initializer.py` legitimately sets `app.state.db_pool = None`
# on a failed init -- the pool is nullable, not just sometimes-absent.
# `get_order_and_practice` used to read `request.app.state.garuda_db_pool`
# unguarded and call `.fetchrow(...)` on it: an ABSENT attribute and an
# explicit `None` both raised `AttributeError`, surfacing as an uncaught
# 500 -- while `get_repository` (same "nothing wired yet" condition, one
# function away) deliberately answers 503 SERVICE_UNAVAILABLE/retryable.
# Same cause, two different answers is the actual defect: fixed by
# `getattr(request.app.state, "garuda_db_pool", None)` + an explicit
# `is None` check, which collapses BOTH states into the SAME 503 shape.
# These two tests exercise them separately -- absent-attribute and
# explicit-None are distinct states and only one of them previously even
# reached the getattr default.
# ============================================================


class TestDbPoolDegradationIsFiveOhThreeNotFiveHundred:
    async def _client_with_session_but(
        self,
        pool,
        magic_link_store: PostgresMagicLinkStore,
        repository: GarudaOrderRepository,
        *,
        raw_secret: str,
        result_id: str,
        pool_state: str,  # "absent" or "none"
    ) -> AsyncClient:
        await _seed_session(pool, raw_secret=raw_secret, result_id=result_id)
        application = FastAPI()
        application.include_router(garuda_orders_router.router)
        # Auth still goes through the REAL, working verifier, and
        # `garuda_order_repository` is wired to a WORKING repository --
        # `get_repository`'s own 503 (an unrelated dependency, resolved by
        # FastAPI before the route body runs) must not be what makes this
        # test pass. Only `garuda_db_pool` is degraded; that is the one
        # thing under test.
        application.state.garuda_magic_session_verifier = magic_link_store.verify_session
        application.state.garuda_order_repository = repository
        if pool_state == "none":
            application.state.garuda_db_pool = None
        # else "absent": the attribute is never set on app.state at all.
        return AsyncClient(transport=ASGITransport(app=application), base_url="http://t")

    async def test_absent_garuda_db_pool_attribute_is_503_not_500(
        self, pool, magic_link_store: PostgresMagicLinkStore, repository: GarudaOrderRepository
    ) -> None:
        raw_secret = "secret-pool-absent-00000000000000000000"
        client = await self._client_with_session_but(
            pool,
            magic_link_store,
            repository,
            raw_secret=raw_secret,
            result_id="result-pool-absent-0000",
            pool_state="absent",
        )
        resp = await client.get(
            "/api/visa/voa/orders/ord_pool_absent_000000",
            cookies={_SESSION_COOKIE: raw_secret},
        )
        assert resp.status_code == 503, resp.text
        assert resp.json()["detail"]["code"] == "SERVICE_UNAVAILABLE"

    async def test_explicit_none_garuda_db_pool_is_503_not_500(
        self, pool, magic_link_store: PostgresMagicLinkStore, repository: GarudaOrderRepository
    ) -> None:
        raw_secret = "secret-pool-none-000000000000000000000"
        client = await self._client_with_session_but(
            pool,
            magic_link_store,
            repository,
            raw_secret=raw_secret,
            result_id="result-pool-none-00000",
            pool_state="none",
        )
        resp = await client.get(
            "/api/visa/voa/orders/ord_pool_none_0000000",
            cookies={_SESSION_COOKIE: raw_secret},
        )
        assert resp.status_code == 503, resp.text
        assert resp.json()["detail"]["code"] == "SERVICE_UNAVAILABLE"
