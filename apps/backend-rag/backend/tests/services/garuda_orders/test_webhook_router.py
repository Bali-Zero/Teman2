"""HTTP-level bite-proof for `POST /api/visa/voa/webhooks/payment`.

Gate finding: the frozen contract's `$ref` on this operation attached the
generic `Idempotency-Key` header parameter to a route that is not a command
WE issue -- it is an inbound Xendit Invoices callback, authenticated by a
static `x-callback-token` (Xendit has no reason to send an Idempotency-Key
on a callback it originates). The router required that header anyway and
discarded its value, so in production the route 400'd before signature
verification ever ran: `handle_paid_event` never fired, the order sat in
`awaiting_payment` forever, and OP-04 reconciliation only logged a warning
(no page) about the real charge it could see but not act on.

There was no test anywhere that issued an HTTP request to this path -- that
missing coverage, not just the one `Header(...)` line, is the actual hole
this file closes.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest

asyncpg = pytest.importorskip("asyncpg")

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.routers import garuda_orders_router
from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_orders.ports import ReviewedCheckSnapshot
from backend.services.garuda_orders.repository import GarudaOrderRepository
from backend.services.payments.xendit import XenditFeeConfig, XenditPaymentProvider

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("TEST_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or "postgresql://localhost/garuda_l3_test?host=/tmp"
)
_CALLBACK_TOKEN = "test-webhook-callback-token"


@pytest.fixture(autouse=True)
def _garuda_public_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")


class _FakeLookup:
    async def get_reviewed_check(self, result_id: str) -> ReviewedCheckSnapshot | None:
        return ReviewedCheckSnapshot(
            result_id=result_id, case_type=CaseType.ISSUANCE, review_confirmed=True
        )


@pytest.fixture
async def pool():
    try:
        p = await asyncpg.create_pool(dsn=_DSN, min_size=1, max_size=2)
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            # Gate finding, round 3: a skip in a gate is a fail-open. This
            # file is the actual HTTP-level coverage for the payment webhook
            # -- it must never silently pass by skipping in CI.
            pytest.fail(
                f"CI has no reachable Postgres for GARUDA_L3_TEST_DSN/"
                f"TEST_DATABASE_URL/DATABASE_URL -- {_DSN!r} unreachable: {exc}."
            )
        pytest.skip(f"no local Postgres reachable at {_DSN}: {exc}")
    async with p.acquire() as conn:
        await conn.execute(
            "TRUNCATE garuda_order_outbox, garuda_order_journal, garuda_payment_inbox, garuda_order_idempotency, garuda_orders CASCADE"
        )
    yield p
    await p.close()


@pytest.fixture
def provider() -> XenditPaymentProvider:
    return XenditPaymentProvider(
        secret_key="xnd_development_fake_key_for_tests",
        callback_verification_token=_CALLBACK_TOKEN,
        success_redirect_url="https://example.com/success",
        failure_redirect_url="https://example.com/failure",
        fee_config=XenditFeeConfig(percentage_bps=350, fixed_idr=6000),
        client=httpx.AsyncClient(),
    )


@pytest.fixture
def repository(pool, provider: XenditPaymentProvider) -> GarudaOrderRepository:
    return GarudaOrderRepository(
        pool, eligibility_lookup=_FakeLookup(), provider=provider, environment="test"
    )


@pytest.fixture
def app(repository: GarudaOrderRepository, provider: XenditPaymentProvider) -> FastAPI:
    application = FastAPI()
    application.include_router(garuda_orders_router.router)
    application.state.garuda_order_repository = repository
    application.state.garuda_payment_provider = provider
    return application


@pytest.fixture
def client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _seed_awaiting_order(pool, *, order_id: str, session_id: str, price_idr: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO garuda_orders (order_id, result_id_ref, case_type, applicant_full_name,
                applicant_email, applicant_phone, applicant_passport_number, price_idr,
                price_catalogue_key, state, provider_session_id, checkout_expires_at)
            VALUES ($1, 'result-webhook-0000001', 'issuance', 'Webhook Test', 'wh@example.com',
                    '+10000000', 'P0000001', $2, 'B1 Visa on Arrival (VOA)', 'awaiting_payment',
                    $3, $4)
            """,
            order_id,
            price_idr,
            session_id,
            datetime.now(UTC) + timedelta(hours=1),
        )


def _sign(body: dict) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(body).encode()
    headers = {"x-callback-token": _CALLBACK_TOKEN, "content-type": "application/json"}
    return raw, headers


@pytest.mark.usefixtures("client")
class TestPaymentWebhook:
    async def test_the_provider_callback_does_not_need_our_client_idempotency_header(
        self, pool, client: AsyncClient
    ) -> None:
        """Guards the router against re-acquiring the gate defect: Xendit
        Invoices callbacks authenticate with `x-callback-token`, never our
        `Idempotency-Key` -- that header is a request-idempotency pattern
        for commands WE issue, not one an inbound provider callback carries.
        A real Xendit PAID callback sends no Idempotency-Key at all; this
        must still reach 204 and mark the order paid, not 400 before
        signature verification ever runs (the exact production defect)."""

        order_id = "ord_webhook_bite_1_0000000"
        session_id = "sess-webhook-bite-1"
        await _seed_awaiting_order(
            pool, order_id=order_id, session_id=session_id, price_idr=790_000
        )

        body = {
            "id": session_id,
            "status": "PAID",
            "payment_id": "charge-webhook-bite-1",
            "paid_amount": 790_000,
            "currency": "IDR",
        }
        raw, headers = _sign(body)
        # Deliberately NO Idempotency-Key header anywhere in this request.
        assert "idempotency-key" not in {k.lower() for k in headers}

        resp = await client.post("/api/visa/voa/webhooks/payment", content=raw, headers=headers)
        assert resp.status_code == 204, resp.text

        state = await pool.fetchval("SELECT state FROM garuda_orders WHERE order_id = $1", order_id)
        assert state == "paid"

    async def test_invalid_signature_is_rejected_before_any_state_change(
        self, pool, client: AsyncClient
    ) -> None:
        order_id = "ord_webhook_bite_2_0000000"
        session_id = "sess-webhook-bite-2"
        await _seed_awaiting_order(
            pool, order_id=order_id, session_id=session_id, price_idr=790_000
        )

        body = {
            "id": session_id,
            "status": "PAID",
            "payment_id": "charge-webhook-bite-2",
            "paid_amount": 790_000,
            "currency": "IDR",
        }
        raw = json.dumps(body).encode()
        bad_headers = {"x-callback-token": "wrong-token", "content-type": "application/json"}

        resp = await client.post("/api/visa/voa/webhooks/payment", content=raw, headers=bad_headers)
        assert resp.status_code == 401, resp.text

        state = await pool.fetchval("SELECT state FROM garuda_orders WHERE order_id = $1", order_id)
        assert state == "awaiting_payment"  # unchanged -- rejected before parse_event
