"""The whole funnel, over HTTP, with Xendit as the ONLY thing that is faked.

WHY THIS FILE EXISTS. Every step of GARUDA VOA had coverage; the walk from one
step to the next did not. `test_check_to_order_journey.py` proves the
check<->order seam but stops at the service layer and uses `_FakeProvider`.
`test_webhook_router.py` proves the webhook over HTTP but SEEDS the order row
directly, so `create_checkout_session` is never reached through a route.
`test_garuda_voa_public.py` overrides the store with an in-memory fake. So the
one thing a customer actually does -- answer four questions, buy, get tracked --
had never been executed end to end by anything.

That gap is not academic. Two production defects lived inside it and shipped
green: PR #5098 (the stores were wired only on the process that does not mount
these routers -> 503 on the first action) and PR #5108 (`reason_codes` was
double-encoded against the pool's own jsonb codec -> 500 on every single
request, while the integration suite passed 10/10).

This file catches the SECOND one and not the first, and the distinction is
worth stating rather than blurring. Measured 2026-08-27: with `check_store.py`
reverted to its pre-#5108 form, four of these tests go red with production's
exact SQLSTATE 22023. The #5098 class it CANNOT catch -- this file mounts both
routers on one app and wires `app.state` itself, so a process-group wiring
inversion is invisible to it by construction. That class has its own guard,
`backend/tests/setup/test_api_process_wires_the_state_its_routers_read.py`, and
neither file substitutes for the other: one asks "does the journey work", the
other asks "is it wired on the process that serves it".

WHAT IS REAL, AND WHAT IS NOT -- stated exactly, because this file's value
depends entirely on the answer:

  REAL: `PostgresCheckStore`, `PostgresEligibilityCheckLookup`,
        `GarudaOrderRepository`, both HTTP routers with their real router-level
        feature-flag dependency, the retention trigger, migration 286's CHECK
        constraints, the outbox rows, and a prod-shaped pool
        (`prod_shaped_pool.py` -- NOT an inline pool; an inline pool is exactly
        what hid #5108).
  REAL: `XenditPaymentProvider` itself -- the real class, the real sandbox-key
        guard, the real `verify_signature`, the real `parse_event`.
  FAKED: exactly one thing -- the HTTP transport underneath it, i.e. Xendit's
         own servers. Plus the magic-link session verifier, which has its own
         suite and whose contract here is one line (see the `app` fixture).

The mock transport ASSERTS the outbound request shape rather than ignoring it,
which makes this file double as the written record of the contract we will send
to the real Xendit sandbox on day one. Measured 2026-08-27: nothing in this repo
reaches a real Xendit endpoint, so when a live key first rejects something, the
diff between these assertions and Xendit's docs is where to look.

Requires a real Postgres with migrations applied through 286. Follows
`test_check_to_order_journey.py`'s DSN resolution and its CI-must-not-skip
rule: a skip inside a gate is a fail-open.
"""

from __future__ import annotations

import json
import os
import pathlib
import uuid
from datetime import timedelta
from http.cookies import SimpleCookie

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

asyncpg = pytest.importorskip("asyncpg")

from backend.app.routers import garuda_orders_router, garuda_voa_public
from backend.services.garuda_flow.check_store import PostgresCheckStore
from backend.services.garuda_flow.civil_clock import garuda_today
from backend.services.garuda_orders.eligibility_lookup import PostgresEligibilityCheckLookup
from backend.services.garuda_orders.repository import GarudaOrderRepository
from backend.services.payments.xendit import XenditFeeConfig, XenditPaymentProvider
from backend.tests.fixtures.prod_shaped_pool import create_prod_shaped_pool

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
)

# Deliberately NOT module-level constants. `garuda_today()` at import time
# freezes an answer the backend recomputes per request from Asia/Makassar, so
# an import just before midnight WITA and requests just after would evaluate
# the fixture against a different "today" than it was built for.
#
# Measured 2026-08-27 before choosing the offset: this payload ACCEPTs at every
# entry offset from +1 to +89 days (price 790.000 throughout), so a one-day
# drift cannot flip the verdict either way. The per-call derivation below is
# therefore about removing the stale-clock SHAPE, not about a live flake — and
# the +14 offset sits far from both ends of that measured range on purpose.
_ENTRY_OFFSET_DAYS = 14
_PASSPORT_VALID_DAYS = 400

_CALLBACK_TOKEN = "test-callback-token-not-a-secret"
_FAKE_INVOICE_ID = "inv_e2e_fake_0000000001"
_FAKE_CHECKOUT_URL = "https://checkout-staging.xendit.co/web/inv_e2e_fake_0000000001"
_RESULT_SESSION_COOKIE = "garuda_result_session"

# Synthetic throughout. `.invalid` is reserved by RFC 2606 and can never route,
# and no field here is derived from any real person: this file is committed to a
# PUBLIC repo, so a plausible-looking applicant would be a UU PDP problem even
# in a test fixture.
_APPLICANT = {
    "full_name": "Test Traveller",
    "email": "voa-e2e@example.invalid",
    "phone": "+390000000000",
    "passport_number": "SYNTHETIC000",
}


def _check_payload() -> dict[str, object]:
    """A shape a real tourist produces: issuance, one traveller, ACCEPT-bound.

    Measured live against production 2026-08-27 (the probe that proved #5108
    fixed): this exact shape answers 201 ACCEPT at 790.000 IDR.
    """
    today = garuda_today()  # fresh per call; see _ENTRY_OFFSET_DAYS above
    entry_date = today + timedelta(days=_ENTRY_OFFSET_DAYS)
    return {
        "case_type": "issuance",
        "nationality": "ITA",
        "entry_date": entry_date.isoformat(),
        "passport_expiry_date": (entry_date + timedelta(days=_PASSPORT_VALID_DAYS)).isoformat(),
        "purpose": "tourism",
        "travellers": 1,
        "self_pay": True,
        "extension_already_used": False,
        "retention_notice_acknowledged": True,
    }


def _result_id_of(response: httpx.Response) -> str:
    """The result id is in the `Location` header, NOT in the body.

    Verified against the live 201 body, which carries only `verdict`,
    `reason_codes`, `published_filing_deadline` and `price_idr`. A test that
    read `body["result_id"]` would KeyError and look like a routing failure.
    """
    location = response.headers.get("location")
    assert location, "a 201 with no Location header gives the client no result to re-read"
    return location.rsplit("/", 1)[-1]


def _session_secret_of(response: httpx.Response) -> str:
    """Read the session cookie off the header, not out of the httpx jar.

    `_set_result_session_cookie` sets `domain=get_cookie_domain()` and
    `secure=` per transport. Either can stop httpx from storing or sending the
    cookie against an ASGI base URL, which would make the GET below fail as
    RESULT_NOT_FOUND -- a false red pointing at the store instead of at the jar.
    """
    for raw in response.headers.get_list("set-cookie"):
        jar: SimpleCookie = SimpleCookie()
        jar.load(raw)
        if _RESULT_SESSION_COOKIE in jar:
            return jar[_RESULT_SESSION_COOKIE].value
    raise AssertionError(
        f"no {_RESULT_SESSION_COOKIE} cookie on the 201 -- the customer cannot re-read "
        "their own verdict"
    )


class _XenditServerDouble:
    """Stands in for Xendit's HTTP endpoint, and CHECKS what we send it.

    Deliberately assertive. A transport that returns 200 to anything would let
    a malformed invoice payload pass here and fail on the first real key, which
    is the failure mode this whole file is built to prevent.
    """

    def __init__(self) -> None:
        self.bodies: list[dict[str, object]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.method == "POST", request.method
        assert request.url.path == "/v2/invoices", str(request.url)
        # Xendit authenticates with HTTP Basic, secret key as username and an
        # empty password. If this stops holding, a live key fails 401 and the
        # cause is here, not in our routing.
        assert request.headers.get("authorization", "").startswith("Basic "), (
            "Xendit expects HTTP Basic auth with the secret key as username"
        )
        assert request.headers.get("Idempotency-Key"), (
            "an invoice create without an Idempotency-Key can double-charge on retry"
        )
        body = json.loads(request.content)
        self.bodies.append(body)
        return httpx.Response(
            200,
            json={
                "id": _FAKE_INVOICE_ID,
                "invoice_url": _FAKE_CHECKOUT_URL,
                "status": "PENDING",
                "external_id": body["external_id"],
                "amount": body["amount"],
            },
        )


async def _seed_policy(conn: asyncpg.Connection, *, scope: str) -> str:
    """Zero-approved TEST policy for one scope.

    Closes a dangling open row first and closes-not-deletes on teardown --
    this table is append-only. Mirrors `test_check_to_order_journey.py`'s
    `_seed_policy` deliberately: a second, subtly different copy would drift,
    and then one of the two suites would silently stop proving what it claims.
    """
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = $1
           AND upper(effective_period) IS NULL
        """,
        scope,
    )
    policy_version = f"funnel-e2e-{scope.lower()}-{uuid.uuid4().hex[:16]}"
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
            'zero-test-approver', 'ZERO-FUNNEL-E2E-APPROVAL'
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


@pytest.fixture(autouse=True)
def public_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both routers carry `dependencies=[Depends(_require_flag)]`.

    Without this the dark-launch guard answers 404 to every request below and
    the whole file passes vacuously green -- an empty proof of exactly the kind
    this file exists to eliminate.
    """
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")


@pytest.fixture
async def pool():
    try:
        p = await create_prod_shaped_pool(_DSN, min_size=1, max_size=4)
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            pytest.fail(
                f"CI has no reachable Postgres for INTAKE_TEST_DSN "
                f"(or GARUDA_L3_TEST_DSN) -- {_DSN!r} unreachable: {exc}. This file is the "
                f"only end-to-end proof of the funnel and must never skip in CI."
            )
        pytest.skip(f"no local Postgres reachable at {_DSN}: {exc}")
        # Unreachable in practice: pytest.fail/skip are NoReturn, so `p` is
        # always bound below. CodeQL can't see that through the pytest API;
        # this `raise` terminates the branch provably and re-raises the
        # connection error if that assumption ever stops being true.
        raise

    async with p.acquire() as conn:
        await conn.execute(
            "TRUNCATE garuda_order_outbox, garuda_order_journal, garuda_payment_inbox, "
            "garuda_order_idempotency, garuda_orders CASCADE"
        )
        await conn.execute(
            "TRUNCATE garuda_voa_check_idempotency, garuda_voa_check_results CASCADE"
        )
        check_policy = await _seed_policy(conn, scope="GARUDA_CHECK")
        order_policy = await _seed_policy(conn, scope="GARUDA_ORDER")
    yield p
    async with p.acquire() as conn:
        await _close_policy(conn, scope="GARUDA_CHECK", policy_version=check_policy)
        await _close_policy(conn, scope="GARUDA_ORDER", policy_version=order_policy)
    await p.close()


@pytest.fixture
def xendit() -> _XenditServerDouble:
    return _XenditServerDouble()


@pytest.fixture
def provider(xendit: _XenditServerDouble) -> XenditPaymentProvider:
    """The REAL provider. Only its transport is a double.

    The `xnd_development_` prefix is not cosmetic: the provider refuses any key
    without it, which is the guard that stops a live key reaching this build.
    """
    return XenditPaymentProvider(
        secret_key="xnd_development_fake_key_for_tests",
        callback_verification_token=_CALLBACK_TOKEN,
        public_base_url="https://example.invalid",
        fee_config=XenditFeeConfig(percentage_bps=350, fixed_idr=6000),
        client=httpx.AsyncClient(transport=httpx.MockTransport(xendit.handler)),
    )


@pytest.fixture
def app(pool, provider: XenditPaymentProvider) -> FastAPI:
    """Both routers on one app, wired the way the orchestrator wires them.

    The magic-session verifier is the one seam stubbed above the transport
    layer: the magic-link exchange has its own suite, and its contract here is
    narrow and explicit -- the session's actor IS the result_id
    (`garuda_orders_router._require_magic_session_actor`). Holding that
    contract in one line makes a future change to it fail loudly here.
    """
    application = FastAPI()
    application.include_router(garuda_voa_public.router)
    application.include_router(garuda_orders_router.router)

    application.state.garuda_check_store = PostgresCheckStore(pool, environment="TEST")
    application.state.garuda_db_pool = pool
    application.state.garuda_payment_provider = provider
    application.state.garuda_order_repository = GarudaOrderRepository(
        pool,
        eligibility_lookup=PostgresEligibilityCheckLookup(pool),
        provider=provider,
        environment="TEST",
    )

    application.state._e2e_actor = None

    async def _verify_session(token: str) -> str | None:
        return application.state._e2e_actor

    application.state.garuda_magic_session_verifier = _verify_session
    return application


@pytest.fixture
def client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost")


def _key() -> str:
    return uuid.uuid4().hex


async def _accepted_check(client: AsyncClient) -> tuple[str, dict, httpx.Response]:
    """Walk steps 1-2 and hand back what step 3 needs."""
    created = await client.post(
        "/api/visa/voa/eligibility-checks",
        json=_check_payload(),
        headers={"Idempotency-Key": _key()},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["verdict"] == "ACCEPT", (
        f"the fixture payload declined ({body}); this file's buy leg needs an ACCEPT, so "
        "either the rules changed or _check_payload() went stale -- fix the payload, do "
        "not skip"
    )
    return _result_id_of(created), body, created


class TestTheFunnelAVisitorActuallyWalks:
    async def test_four_questions_produce_a_persisted_verdict_with_one_price(
        self, client: AsyncClient, pool
    ) -> None:
        """Steps 1-2. This is the request that answered 500 in production for
        three days while every gate was green (PR #5098, then #5108)."""
        result_id, body, created = await _accepted_check(client)
        assert body["price_idr"] > 0
        assert body["published_filing_deadline"], "an ACCEPT with no deadline sells nothing"

        # The row really landed, and `reason_codes` is a JSON ARRAY -- not the
        # scalar string #5108's double-encoding produced. Asserting
        # `jsonb_typeof` rather than the decoded value is deliberate: the
        # decoded value looks identical either way, which is exactly why the
        # defect survived a real-Postgres suite.
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT decision, jsonb_typeof(reason_codes) AS kind, price_idr "
                "FROM garuda_voa_check_results WHERE result_id = $1",
                result_id,
            )
        assert row is not None, "the verdict was returned to the customer but never persisted"
        assert row["kind"] == "array", (
            f"reason_codes is {row['kind']!r}, not 'array' -- the jsonb codec is "
            "double-encoding again (PR #5108)"
        )
        assert row["price_idr"] == body["price_idr"], (
            "the price shown to the customer is not the price we stored"
        )

        reread = await client.get(
            f"/api/visa/voa/eligibility-checks/{result_id}",
            headers={"Cookie": f"{_RESULT_SESSION_COOKIE}={_session_secret_of(created)}"},
        )
        assert reread.status_code == 200, reread.text
        assert reread.json()["price_idr"] == body["price_idr"]

    async def test_buying_reaches_xendit_with_the_contract_we_think_we_send(
        self, client: AsyncClient, app: FastAPI, xendit: _XenditServerDouble
    ) -> None:
        """Step 3. The first time an order is created THROUGH A ROUTE."""
        result_id, body, _ = await _accepted_check(client)

        app.state._e2e_actor = result_id
        order = await client.post(
            "/api/visa/voa/orders",
            json={"result_id": result_id, "review_confirmed": True, "applicant": _APPLICANT},
            headers={"Idempotency-Key": _key(), "Cookie": "garuda_session=e2e"},
        )
        assert order.status_code == 201, order.text
        assert order.json()["checkout_url"] == _FAKE_CHECKOUT_URL

        assert len(xendit.bodies) == 1, f"expected one invoice create, got {len(xendit.bodies)}"
        sent = xendit.bodies[0]
        assert sent["currency"] == "IDR"
        assert sent["payment_methods"] == ["CREDIT_CARD"]
        # The provider fee is ABSORBED (owner decision 1, tier (a)): what we ask
        # Xendit to charge must equal the catalogue price, never price + fee.
        assert sent["amount"] == body["price_idr"], (
            "the amount sent to Xendit differs from the price shown to the customer -- "
            "the all-inclusive promise is broken"
        )
        assert sent["success_redirect_url"] == sent["failure_redirect_url"], (
            "one return route, no success/failure split (Dissent #3, 2026-08-25)"
        )
        assert sent["external_id"], "no external_id means the callback cannot find the order"

    async def test_a_paid_callback_moves_the_order_and_enqueues_the_work(
        self, client: AsyncClient, app: FastAPI, pool
    ) -> None:
        """Steps 4-5: the paid webhook, then what the customer is owed next."""
        result_id, body, _ = await _accepted_check(client)

        app.state._e2e_actor = result_id
        order = await client.post(
            "/api/visa/voa/orders",
            json={"result_id": result_id, "review_confirmed": True, "applicant": _APPLICANT},
            headers={"Idempotency-Key": _key(), "Cookie": "garuda_session=e2e"},
        )
        assert order.status_code == 201, order.text
        order_id = order.json()["order_id"]

        callback = {
            "id": _FAKE_INVOICE_ID,
            "status": "PAID",
            "paid_amount": body["price_idr"],
            "currency": "IDR",
            "payment_id": "pay_e2e_fake_0001",
        }
        paid = await client.post(
            "/api/visa/voa/webhooks/payment",
            content=json.dumps(callback).encode(),
            headers={"x-callback-token": _CALLBACK_TOKEN, "content-type": "application/json"},
        )
        assert paid.status_code == 204, paid.text

        async with pool.acquire() as conn:
            # The column is `state`, not `status`, and its CHECK pins the
            # vocabulary to created/awaiting_payment/paid/failed/expired/refunded
            # -- so `paid` is assertable exactly, rather than "not the bad one".
            state = await conn.fetchval(
                "SELECT state FROM garuda_orders WHERE order_id = $1", order_id
            )
            jobs = await conn.fetch(
                "SELECT job_type, jsonb_typeof(payload) AS kind FROM garuda_order_outbox "
                "WHERE order_id = $1",
                order_id,
            )
        assert state == "paid", (
            f"a PAID callback left the order in {state!r} -- `awaiting_payment` here is "
            "exactly the state the missing-Idempotency-Key regression produced in "
            "production, where the charge was real and the order never moved"
        )
        assert jobs, "payment was accepted and nothing was enqueued: the customer gets silence"
        # Named, not just counted. A non-empty outbox proves something was
        # enqueued; only the job types prove the RIGHT things were -- the
        # customer is owed a receipt and a way into the portal, and an outbox
        # holding neither is silence with a row in it.
        job_types = {r["job_type"] for r in jobs}
        assert "payment_paid_email" in job_types, (
            f"paid, but no receipt job enqueued (got {sorted(job_types)})"
        )
        assert "portal_invite" in job_types, (
            f"paid, but no portal invite enqueued -- the customer has nowhere to upload "
            f"documents (got {sorted(job_types)})"
        )

    async def test_outbox_payloads_are_currently_json_strings_pinning_an_open_defect(
        self, client: AsyncClient, app: FastAPI, pool
    ) -> None:
        """Pins the latent half of #5108 as it ACTUALLY is today.

        This was an `xfail(strict=True)` naming the codec defect as its reason.
        An adversarial review falsified that encoding: `xfail` without `raises=`
        treats ANY failure as expected, and it demonstrated the test still
        reporting `xfailed` when the feature flag was off -- i.e. for a 404
        routing failure, not the defect the reason named. A probe that cannot
        distinguish its own cause is not a probe.

        So it is a characterization test instead: the funnel walk below is
        asserted NORMALLY (a routing or wiring break is a real red, named), and
        the storage shape is pinned as `string`. When the codec decision lands
        (`.claude/skills/modus/PENDING-ARMS.md`: `journal.py:53,78` pre-serialize
        with `json.dumps(default=str)` against a codec whose encoder is a bare
        `json.dumps`), THIS test goes red and says so -- invert it to `object`
        and delete this paragraph.

        Nothing is broken TODAY: `outbox_consumer.py:165` reads
        `json.loads(raw) if isinstance(raw, str)`, and that compensation is
        itself asserted in the test below. It still matters:
        `payload->>'k'` in SQL returns NULL against a scalar string, and the
        next reader written against the declared jsonb type gets a `str` where
        its annotation promises `dict[str, Any]`.
        """
        result_id, body, _ = await _accepted_check(client)
        app.state._e2e_actor = result_id
        order = await client.post(
            "/api/visa/voa/orders",
            json={"result_id": result_id, "review_confirmed": True, "applicant": _APPLICANT},
            headers={"Idempotency-Key": _key(), "Cookie": "garuda_session=e2e"},
        )
        assert order.status_code == 201, order.text
        paid = await client.post(
            "/api/visa/voa/webhooks/payment",
            content=json.dumps(
                {
                    "id": _FAKE_INVOICE_ID,
                    "status": "PAID",
                    "paid_amount": body["price_idr"],
                    "currency": "IDR",
                    "payment_id": "pay_e2e_fake_0002",
                }
            ).encode(),
            headers={"x-callback-token": _CALLBACK_TOKEN, "content-type": "application/json"},
        )
        assert paid.status_code == 204, paid.text

        async with pool.acquire() as conn:
            kinds = [
                r["kind"]
                for r in await conn.fetch(
                    "SELECT jsonb_typeof(payload) AS kind FROM garuda_order_outbox "
                    "WHERE order_id = $1",
                    order.json()["order_id"],
                )
            ]
        assert kinds, "no outbox rows to judge"
        assert all(k == "string" for k in kinds), (
            f"outbox payloads have jsonb_typeof {kinds}. If they are now 'object', the "
            "codec double-encoding is FIXED: flip this assertion to 'object', drop the "
            "PENDING-ARMS row, and remove the compensating read this file pins below. "
            "Any other value means something new."
        )

    async def test_the_only_current_reader_absorbs_the_double_encoding(
        self, client: AsyncClient, app: FastAPI, pool
    ) -> None:
        """Pins WHY the xfail above is not a customer-facing outage.

        If someone removes `outbox_consumer.py`'s `isinstance(raw, str)`
        compensation while the storage shape is still a scalar string, this
        goes red and names the consequence -- which is the whole reason the
        other test is allowed to stay xfail instead of blocking this PR.
        """
        result_id, body, _ = await _accepted_check(client)
        app.state._e2e_actor = result_id
        order = await client.post(
            "/api/visa/voa/orders",
            json={"result_id": result_id, "review_confirmed": True, "applicant": _APPLICANT},
            headers={"Idempotency-Key": _key(), "Cookie": "garuda_session=e2e"},
        )
        assert order.status_code == 201, order.text
        paid = await client.post(
            "/api/visa/voa/webhooks/payment",
            content=json.dumps(
                {
                    "id": _FAKE_INVOICE_ID,
                    "status": "PAID",
                    "paid_amount": body["price_idr"],
                    "currency": "IDR",
                    "payment_id": "pay_e2e_fake_0003",
                }
            ).encode(),
            headers={"x-callback-token": _CALLBACK_TOKEN, "content-type": "application/json"},
        )
        assert paid.status_code == 204, paid.text

        from backend.services.garuda_orders import outbox_consumer

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, order_id, journal_event_id, job_type, payload, attempts "
                "FROM garuda_order_outbox WHERE order_id = $1",
                order.json()["order_id"],
            )
        assert rows, "no outbox rows to read"
        for row in rows:
            raw = row["payload"]
            decoded = json.loads(raw) if isinstance(raw, str) else (raw or {})
            assert isinstance(decoded, dict), (
                f"job {row['job_type']!r} decodes to {type(decoded).__name__}, not dict -- "
                "the consumer's compensating read no longer recovers the payload"
            )
        # And the compensation is still physically present in the reader, not
        # merely reproduced by this test's own copy of the expression.
        source = pathlib.Path(outbox_consumer.__file__).read_text()
        assert "isinstance(raw, str)" in source, (
            "outbox_consumer no longer compensates for the scalar-string payload while "
            "the storage shape is still a scalar string -- the paid-customer delivery "
            "path is now broken; fix the codec (PENDING-ARMS) before removing this"
        )

    async def test_an_invalid_callback_token_changes_nothing(
        self, client: AsyncClient, pool
    ) -> None:
        """The guard's guilt case.

               Near-sibling, kept deliberately: `test_webhook_router.py`'s
               `test_invalid_signature_is_rejected_before_any_state_change` covers the
               same endpoint and the same 401, but asserts on `garuda_orders.state`
               while this one asserts on `garuda_payment_inbox`. Neither is the
               other's superset -- an unauthenticated caller must move NEITHER table,
               and deleting "the duplicate" silently drops one of those two halves.
        Innocence is covered above; without this,
               'the webhook accepted it' and 'the webhook verified it' are the same
               observation."""
        rejected = await client.post(
            "/api/visa/voa/webhooks/payment",
            content=json.dumps(
                {"id": _FAKE_INVOICE_ID, "status": "PAID", "paid_amount": 1}
            ).encode(),
            headers={"x-callback-token": "wrong-token", "content-type": "application/json"},
        )
        assert rejected.status_code == 401, rejected.text
        async with pool.acquire() as conn:
            inbox = await conn.fetchval("SELECT count(*) FROM garuda_payment_inbox")
        assert inbox == 0, "a rejected callback still wrote to the payment inbox"


class TestWhatTheSandboxKeyWillTestForTheFirstTime:
    def test_the_provider_refuses_a_live_key(self) -> None:
        """The one guard standing between this build and a real charge.

        Not a formality: `WHEN-THE-PAYMENT-KEYS-ARRIVE.md` exists because live
        keys must be a deliberate code change, never a secrets change.
        """
        with pytest.raises(ValueError):
            XenditPaymentProvider(
                secret_key="xnd_production_looks_real",
                callback_verification_token=_CALLBACK_TOKEN,
                public_base_url="https://example.invalid",
                fee_config=XenditFeeConfig(percentage_bps=350, fixed_idr=6000),
                client=httpx.AsyncClient(),
            )

    def test_this_file_never_reaches_the_real_xendit(self) -> None:
        """Says out loud what the mock transport means, so nobody reads a green
        run here as proof that Xendit accepts our payload. Measured
        2026-08-27: nothing in this repo talks to Xendit. The invoice contract,
        the callback token format and the return redirect are all first
        exercised by the first real sandbox purchase.
        """
        double = _XenditServerDouble()
        provider = XenditPaymentProvider(
            secret_key="xnd_development_fake_key_for_tests",
            callback_verification_token=_CALLBACK_TOKEN,
            public_base_url="https://example.invalid",
            fee_config=XenditFeeConfig(percentage_bps=350, fixed_idr=6000),
            client=httpx.AsyncClient(transport=httpx.MockTransport(double.handler)),
        )
        assert isinstance(provider._client._transport, httpx.MockTransport)
