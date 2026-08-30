"""Regression test for the staff-actor auth-bypass landmine (adversarial
review finding on PR #4910, 2026-08-25).

`_require_staff_actor` in `garuda_orders_router.py` is the twin of
`_require_magic_session_actor` (the customer-facing seam fixed earlier in
this PR). It was left a plain sync `def` calling `verifier(authorization)`
un-awaited. `garuda_staff_session_verifier` is wired nowhere in production
today, so the route 401s unconditionally and nothing is exploitable yet --
but the defect is what the NEXT lane does: the moment a real *async*
verifier is wired onto that `app.state` slot without also converting this
function, calling it without `await` returns a coroutine object rather than
running the lookup. A coroutine is never `None`, so `if actor is None` is
False and the request proceeds AUTHENTICATED for any non-empty
`Authorization` header -- a full auth bypass on the staff late-resolution
endpoint. No exception is raised; the only symptom is a
`RuntimeWarning: coroutine ... was never awaited` in logs.

This test simulates exactly that future state -- an async verifier wired
onto `app.state.garuda_staff_session_verifier` that returns `None` (i.e. an
unrecognized/invalid `Authorization` value) -- and asserts 401. Against the
pre-fix sync `_require_staff_actor` this test FAILS: the un-awaited
coroutine is truthy, `actor is None` is False, and the route proceeds past
auth (observable here as anything other than 401 -- a 422/500 further down
the body, never the desired 401 SESSION_REQUIRED). That is the red-first
proof, and it is what stops anyone from silently un-fixing this later by
reverting `_require_staff_actor` back to `def`/un-awaited.

No Postgres required: `get_repository` (a `Depends`) is satisfied by a fake
repository whose `resolve_late_order` raises if ever called, proving the
auth check runs and rejects BEFORE any repository access is attempted.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.routers import garuda_orders_router


@pytest.fixture(autouse=True)
def _garuda_public_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")


class _NeverCalledRepository:
    """Fake `GarudaOrderRepository` -- any method call is a test failure,
    because auth must reject before the route ever reaches the repository.
    """

    async def resolve_late_order(self, **kwargs):  # pragma: no cover - must not run
        raise AssertionError(
            "resolve_late_order was called -- the staff-actor auth check did "
            "not reject the request before reaching the repository"
        )


async def _async_verifier_returns_none(authorization: str) -> str | None:
    """Stand-in for a real (future) async staff-session verifier that does
    not recognize this `Authorization` value.
    """
    return None


def _make_app(*, verifier) -> FastAPI:
    app = FastAPI()
    app.include_router(garuda_orders_router.router)
    app.state.garuda_order_repository = _NeverCalledRepository()
    if verifier is not None:
        app.state.garuda_staff_session_verifier = verifier
    return app


class TestStaffActorAsyncVerifierIsAwaited:
    async def test_async_verifier_returning_none_is_rejected_with_401(self) -> None:
        """Red-first proof: against the pre-fix sync `_require_staff_actor`,
        `verifier(authorization)` returns an un-awaited coroutine object --
        truthy, so `actor is None` is False and the request proceeds past
        auth instead of getting 401. This is what would let it slip through
        as authenticated.
        """
        app = _make_app(verifier=_async_verifier_returns_none)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/visa/voa/staff/orders/ord_test_0000000000/late-resolution",
                headers={
                    "Authorization": "Bearer whatever-nonempty-value",
                    "Idempotency-Key": "staff-late-resolution-key-0001",
                },
                json={"resolution": "honoured", "staff_reference": "ref-1"},
            )
        assert resp.status_code == 401
        assert resp.json()["code"] == "SESSION_REQUIRED"

    async def test_no_verifier_wired_is_still_401(self) -> None:
        """Baseline: today's actual production state (nothing wired) must
        keep 401ing -- this PR must not change that behavior.
        """
        app = _make_app(verifier=None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/visa/voa/staff/orders/ord_test_0000000000/late-resolution",
                headers={
                    "Authorization": "Bearer whatever-nonempty-value",
                    "Idempotency-Key": "staff-late-resolution-key-0002",
                },
                json={"resolution": "honoured", "staff_reference": "ref-1"},
            )
        assert resp.status_code == 401
        assert resp.json()["code"] == "SESSION_REQUIRED"

    async def test_missing_authorization_header_is_401(self) -> None:
        app = _make_app(verifier=_async_verifier_returns_none)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/visa/voa/staff/orders/ord_test_0000000000/late-resolution",
                headers={"Idempotency-Key": "staff-late-resolution-key-0003"},
                json={"resolution": "honoured", "staff_reference": "ref-1"},
            )
        assert resp.status_code == 401
        assert resp.json()["code"] == "SESSION_REQUIRED"
