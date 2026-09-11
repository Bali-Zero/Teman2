"""L3 error envelope + privacy-header contract compliance (PR #4959 F2
follow-up).

`garuda_orders_router.py`'s 28 `raise HTTPException(status_code=X,
detail={"code": Y, "retryable": Z})` call sites used to produce FastAPI's
default `{"detail": {"code": ..., "retryable": ...}}` body — the contract
(`products/garuda-voa/contracts/errors.yaml`) declares a FLAT
`{"code", "retryable", "message_key"}` shape, exactly what `garuda_voa_public
.py`'s `_ContractErrorRoute` + `_error()` already produce for L2. The nested
shape also carried none of the three `_privacy_headers()` a success response
gets: raising builds a brand-new `Response` via FastAPI's own exception
handling, never the `response` object handlers mutate.

Three representative error paths, one per HTTP-status family the task asked
for (a validation 4xx, an authorization 4xx, and the 503), each proven
red-before / green-after against `garuda_orders_router.py`'s own
`_ContractErrorRoute` fix — NOT the sibling `garuda_voa_public.py`, which was
already correct. None of these need Postgres: every fixture here is a fake,
same shape as `test_garuda_staff_actor_async_verifier.py`'s.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.routers import garuda_orders_router

_SESSION_COOKIE = "garuda_session"
_ACTOR = "result-envelope-test-000000"


@pytest.fixture(autouse=True)
def _garuda_public_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")


async def _verifier_returns_fixed_actor(cookie: str) -> str | None:
    """Stand-in magic-link verifier — no Postgres, no `PostgresMagicLinkStore`.
    Accepts any non-empty cookie value and returns the same fixed actor."""
    return _ACTOR if cookie else None


class _NeverCalledRepository:
    """Fake `GarudaOrderRepository` for `Depends(get_repository)` — any
    method call is a test failure. Used only where the test's own error
    path must be reached BEFORE the repository is ever touched (matches
    `test_garuda_staff_actor_async_verifier.py`'s fixture of the same
    name/shape)."""

    async def create_order_and_checkout(self, **kwargs):  # pragma: no cover
        raise AssertionError(
            "create_order_and_checkout was called — the 422 body "
            "check did not reject the request before touching the "
            "repository"
        )


def _app(**state) -> FastAPI:
    application = FastAPI()
    application.include_router(garuda_orders_router.router)
    for key, value in state.items():
        setattr(application.state, key, value)
    return application


def _assert_privacy_headers(headers) -> None:
    assert headers.get("cache-control") == "no-store, private"
    assert headers.get("referrer-policy") == "no-referrer"
    assert headers.get("x-robots-tag") == "noindex, nofollow, noarchive"


class TestSessionRequiredEnvelope:
    """401 SESSION_REQUIRED — the authorization 4xx.

    No verifier wired at all (production's actual state until L4's session
    verifier is composed onto `app.state`), no cookie sent: `_require_magic_
    session_actor` raises before any `Depends()` (`get_repository`,
    `garuda_db_pool`) is ever touched, so this needs no fakes beyond the
    bare app.
    """

    async def test_envelope_is_flat_contract_shape(self) -> None:
        app = _app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.get("/api/visa/voa/orders/ord_envelope_test_0000")

        assert resp.status_code == 401, resp.text
        assert resp.json() == {
            "code": "SESSION_REQUIRED",
            "retryable": False,
            "message_key": "garuda_voa.error.session_required",
        }
        assert "detail" not in resp.json()

    async def test_privacy_headers_are_present(self) -> None:
        app = _app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.get("/api/visa/voa/orders/ord_envelope_test_0001")

        assert resp.status_code == 401, resp.text
        _assert_privacy_headers(resp.headers)


class TestInvalidRequestEnvelope:
    """422 INVALID_REQUEST — the validation 4xx.

    Verifier + repository both wired (a fake repository whose methods must
    NEVER be called — the malformed body must be rejected before the
    handler ever reaches `repository.create_order_and_checkout`), a valid
    session cookie and idempotency key, and a body that fails the
    `review_confirmed is not True` check.
    """

    async def test_envelope_is_flat_contract_shape(self) -> None:
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_order_repository=_NeverCalledRepository(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.post(
                "/api/visa/voa/orders",
                cookies={_SESSION_COOKIE: "any-nonempty-cookie-value"},
                headers={"Idempotency-Key": "envelope-test-invalid-request-0001"},
                json={"result_id": _ACTOR, "review_confirmed": False},
            )

        assert resp.status_code == 422, resp.text
        assert resp.json() == {
            "code": "INVALID_REQUEST",
            "retryable": False,
            "message_key": "garuda_voa.error.invalid_request",
        }
        assert "detail" not in resp.json()

    async def test_privacy_headers_are_present(self) -> None:
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_order_repository=_NeverCalledRepository(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.post(
                "/api/visa/voa/orders",
                cookies={_SESSION_COOKIE: "any-nonempty-cookie-value"},
                headers={"Idempotency-Key": "envelope-test-invalid-request-0002"},
                json={"result_id": _ACTOR, "review_confirmed": False},
            )

        assert resp.status_code == 422, resp.text
        _assert_privacy_headers(resp.headers)


class TestServiceUnavailableEnvelope:
    """503 SERVICE_UNAVAILABLE.

    A valid session (via the fake verifier — no Postgres) but no
    `garuda_db_pool` wired at all, exactly `TestDbPoolDegradationIsFiveOhThreeNotFiveHundred`'s
    "absent" case in `test_garuda_orders_ownership.py`, reused here without
    the Postgres-backed fixtures that file needs for its OTHER (ownership)
    assertions.
    """

    async def test_envelope_is_flat_contract_shape(self) -> None:
        app = _app(garuda_magic_session_verifier=_verifier_returns_fixed_actor)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.get(
                "/api/visa/voa/orders/ord_envelope_test_0002",
                cookies={_SESSION_COOKIE: "any-nonempty-cookie-value"},
            )

        assert resp.status_code == 503, resp.text
        assert resp.json() == {
            "code": "SERVICE_UNAVAILABLE",
            "retryable": True,
            "message_key": "garuda_voa.error.service_unavailable",
        }
        assert "detail" not in resp.json()

    async def test_privacy_headers_are_present(self) -> None:
        app = _app(garuda_magic_session_verifier=_verifier_returns_fixed_actor)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.get(
                "/api/visa/voa/orders/ord_envelope_test_0003",
                cookies={_SESSION_COOKIE: "any-nonempty-cookie-value"},
            )

        assert resp.status_code == 503, resp.text
        _assert_privacy_headers(resp.headers)
