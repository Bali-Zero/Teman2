"""Regression test for a gate finding on PR #4910 (garuda-voa L3/L4
ownership + auth wiring): production wiring for `garuda_portal_auth`'s
`MagicLinkStore` MUST live on `app.state`, never in
`app.dependency_overrides`.

Why this matters (team-lead review, 2026-08-25): `app.dependency_overrides`
is FastAPI's TEST mechanism -- one unscoped, process-wide dict, not scoped
per-test. `backend/tests/unit/routers/test_dashboard_coverage.py` already
calls `app.dependency_overrides.clear()` UNCONDITIONALLY in its teardown,
against the SAME `main_cloud.app` object production code shares. That call
is harmless today only because that test file never triggers
`initialize_services`, so it never has anything of this module's to clear
-- but a production wiring entry placed in `dependency_overrides` would be
exactly one unrelated test's indiscriminate teardown away from silently
reverting `/magic-links` and `/sessions` to `UnconfiguredMagicLinkStore`,
while `garuda_magic_session_verifier` (a separate, unaffected `app.state`
slot `service_initializer.py` sets alongside it) stayed live -- the
half-wired state (verifier live, minting dead) this whole PR exists to
avoid.

`get_garuda_magic_link_store` (`garuda_portal_auth.py`) now reads
`app.state.garuda_magic_link_store`, falling back to
`UnconfiguredMagicLinkStore`. This file proves both halves of that
contract: wiring survives the exact `dependency_overrides.clear()` gesture
found live in the tree, and the fail-closed default still holds when
nothing is wired at all.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import garuda_portal_auth as router_mod
from backend.services.garuda_portal.magic_link import IssueOutcome

_VALID_RESULT_ID = "r" * 22
_VALID_RESULT_SESSION = "s" * 43
_VALID_IDEMPOTENCY_KEY = "test-key-0123456789abcdef"


class _MarkerStore:
    """Distinguishable from `UnconfiguredMagicLinkStore` by OUTCOME, not by
    an identity check the test could get wrong: `issue()` always succeeds
    (202). `UnconfiguredMagicLinkStore` always raises
    `PersistencePolicyUnavailable` (503 `PERSISTENCE_POLICY_UNAVAILABLE`).
    If the router still reaches THIS store after the
    `dependency_overrides.clear()` below, the response is 202; if it
    silently fell back, it's 503 -- the observable difference this test
    checks."""

    async def issue(self, *, idempotency_key, result_id, email, result_session_secret):
        return IssueOutcome(idempotency_replayed=False)

    async def exchange(self, *, idempotency_key, token):  # pragma: no cover - not exercised
        raise AssertionError("exchange() is not exercised by this test")


class _AlwaysOwnsCheckStore:
    """A `CheckStore` double that recognises every (result_id,
    session_secret) pair.

    This file's whole point is isolating `MagicLinkStore`'s `app.state`
    wiring behaviour (PR #4910's gate finding). The ownership check added
    2026-08-30 (`garuda_portal_auth.request_magic_link`) runs BEFORE the
    magic-link store is ever reached, so every test below that wants to
    exercise the magic-link-store path must stub this port out of the way
    first -- otherwise every request would 503 at the ownership gate
    (`UnconfiguredCheckStore`) before saying anything about the thing this
    file actually tests. The check-store's OWN app.state/unconfigured
    behaviour is covered separately in `test_garuda_portal_auth.py`.
    """

    async def get(self, *, result_id, session_secret):
        return object()


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router_mod.router)
    return app


def _request_magic_link(client: TestClient):
    return client.post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": _VALID_RESULT_ID, "email": "visitor@example.com"},
        headers={"Idempotency-Key": _VALID_IDEMPOTENCY_KEY},
        cookies={"garuda_result_session": _VALID_RESULT_SESSION},
    )


@pytest.fixture(autouse=True)
def _enable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")


def test_app_state_wiring_survives_an_unrelated_dependency_overrides_clear() -> None:
    app = _app()

    # Production wiring shape (service_initializer.py, 2026-08-25 onward).
    app.state.garuda_magic_link_store = _MarkerStore()
    # Stub the ownership gate out of the way -- see _AlwaysOwnsCheckStore's
    # docstring; this test isolates the magic-link-store dimension only.
    app.state.garuda_check_store = _AlwaysOwnsCheckStore()

    # Simulate a COMPLETELY UNRELATED test file's indiscriminate teardown
    # against this same app object -- exactly
    # test_dashboard_coverage.py's `app.dependency_overrides.clear()`
    # gesture, reproduced verbatim, with nothing of this router's own in
    # the dict to begin with (this router's tests use
    # `app.dependency_overrides` too -- see test_garuda_portal_auth.py --
    # but production code never puts anything there to lose).
    app.dependency_overrides.clear()

    resp = _request_magic_link(TestClient(app))

    # A 503 here would mean the route silently fell back to
    # UnconfiguredMagicLinkStore -- the exact regression this test guards.
    assert resp.status_code == 202, resp.text


def test_absent_app_state_falls_back_to_unconfigured_fail_closed() -> None:
    """The other half of the contract: with the magic-link store NOTHING
    wired (today's actual state before `service_initializer.py` runs, or if
    that wiring block itself fails), the route must still fail closed with
    `PERSISTENCE_POLICY_UNAVAILABLE`, never a bare framework error. The
    check-store ownership gate is stubbed to always-own here (see
    `_AlwaysOwnsCheckStore`) so this test isolates the magic-link-store
    dimension specifically; the check-store's OWN unconfigured-fail-closed
    behaviour (also 503, different code: `SERVICE_UNAVAILABLE`) is covered
    in `test_garuda_portal_auth.py::test_request_with_no_check_store_wired_
    defaults_to_503_not_a_silent_202`."""
    app = _app()
    app.state.garuda_check_store = _AlwaysOwnsCheckStore()
    resp = _request_magic_link(TestClient(app))
    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "PERSISTENCE_POLICY_UNAVAILABLE"


def test_get_garuda_magic_link_store_prefers_the_dependency_override_when_present() -> None:
    """Tests may still override via `app.dependency_overrides` (FastAPI
    replaces the callable outright, so `get_garuda_magic_link_store`'s own
    body never runs) -- only the PRODUCTION wiring path moved to
    `app.state`. Confirms both mechanisms coexist without one masking the
    other in a way a future editor could mistake for a regression."""
    app = _app()
    app.state.garuda_magic_link_store = _MarkerStore()  # would answer 202
    app.state.garuda_check_store = _AlwaysOwnsCheckStore()  # clear the ownership gate

    class _AlwaysFailsStore:
        async def issue(self, **_kwargs):
            raise AssertionError("app.state store should not have been reached")

    app.dependency_overrides[router_mod.get_garuda_magic_link_store] = _AlwaysFailsStore
    resp = _request_magic_link(TestClient(app))
    # The override wins (FastAPI resolves it before the real dependency
    # function ever runs) -- surfaces as the router's own
    # exception-to-INTERNAL_ERROR mapping, not the app.state store's 202,
    # proving the override path is genuinely still live and distinct.
    assert resp.status_code != 202
