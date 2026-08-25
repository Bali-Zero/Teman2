"""Tests for GARUDA VOA magic-link authentication (L4).

Journey source: `products/garuda-voa/journeys/magic-link-security.feature`
(``@red-first``). Each guard here is proven to bite: the literal red produced
by breaking the guarded line and the literal green produced by restoring it
is recorded in the PR description for every test in this file (contract:
modus VERIFY discipline — see also `garuda_voa_public`'s own test-file
docstring, the precedent this file follows).

`UnconfiguredMagicLinkStore` (the only store this lane ships) always 503s —
by design, per LANES.md's persistence-policy prerequisite (see
`magic_link.py` module docstring). The journey scenarios below therefore
exercise a `_FakeStore` double, the exact same shape
`test_garuda_voa_public.py` uses for L2's identical situation: the ROUTER's
handling of an authorized/unauthorized/replayed outcome is what a red-first
test can prove today; a real store adapter is a follow-up PR once L1's
retention primitive covers this table too.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import garuda_portal_auth as router_mod
from backend.services.garuda_portal.magic_link import (
    ExchangeOutcome,
    IdempotencyConflict,
    IssueOutcome,
    PersistencePolicyUnavailable,
)

VALID_RESULT_ID = "r" * 22
VALID_RESULT_SESSION = "s" * 43
VALID_IDEMPOTENCY_KEY = "test-key-0123456789abcdef"
VALID_TOKEN = "t" * 43


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router_mod.router)
    return app


def _client() -> TestClient:
    return TestClient(_app())


class _FakeStore:
    """Minimal in-memory `MagicLinkStore` double — mirrors
    `test_garuda_voa_public.py::_FakeStore` for the identical reason (L2's
    persistence port is also fail-closed pending L1)."""

    def __init__(self) -> None:
        self.issued: list[dict[str, object]] = []
        self.tokens: dict[str, dict[str, object]] = {}
        self.exchanged_keys: dict[str, ExchangeOutcome] = {}
        self.raise_on_issue: Exception | None = None
        self.raise_on_exchange: Exception | None = None

    async def issue(
        self,
        *,
        idempotency_key: str,
        result_id: str,
        email: str,
        result_session_secret: str,
    ) -> IssueOutcome:
        if self.raise_on_issue is not None:
            raise self.raise_on_issue
        self.issued.append(
            {
                "idempotency_key": idempotency_key,
                "result_id": result_id,
                "email": email,
                "result_session_secret": result_session_secret,
            }
        )
        return IssueOutcome(idempotency_replayed=False)

    def seed_token(self, token: str, *, expired: bool, consumed: bool) -> None:
        self.tokens[token] = {"expired": expired, "consumed": consumed}

    async def exchange(self, *, idempotency_key: str, token: str) -> ExchangeOutcome:
        if self.raise_on_exchange is not None:
            raise self.raise_on_exchange

        if idempotency_key in self.exchanged_keys:
            original = self.exchanged_keys[idempotency_key]
            return ExchangeOutcome(
                authorized=original.authorized,
                security_counter=original.security_counter,
                result_id=original.result_id,
                account_session_secret=None,  # replay never re-exposes the cookie
                idempotency_replayed=True,
            )

        state = self.tokens.get(token)
        if state is None:
            outcome = ExchangeOutcome(authorized=False, security_counter="magic_link_invalid")
        elif state["expired"]:
            outcome = ExchangeOutcome(authorized=False, security_counter="magic_link_expired")
        elif state["consumed"]:
            outcome = ExchangeOutcome(authorized=False, security_counter="magic_link_replay")
        else:
            state["consumed"] = True
            outcome = ExchangeOutcome(
                authorized=True,
                security_counter="magic_link_authorized",
                result_id=VALID_RESULT_ID,
                account_session_secret="acct-" + token,
            )
        self.exchanged_keys[idempotency_key] = outcome
        return outcome


@pytest.fixture(autouse=True)
def _enable_flag(monkeypatch):
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")


@pytest.fixture
def fake_store():
    return _FakeStore()


def _client_with_store(store: _FakeStore) -> TestClient:
    app = _app()
    app.dependency_overrides[router_mod.get_garuda_magic_link_store] = lambda: store
    return TestClient(app)


# ============================================================
# Feature flag / idempotency plumbing (shared shape with L2)
# ============================================================


def test_disabled_flag_returns_404_garuda_public_disabled(monkeypatch):
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "false")
    resp = _client().post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": VALID_RESULT_ID, "email": "a@example.com"},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "GARUDA_PUBLIC_DISABLED"


def test_request_magic_link_missing_idempotency_key_400():
    resp = _client().post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": VALID_RESULT_ID, "email": "a@example.com"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_exchange_missing_idempotency_key_400():
    resp = _client().post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


# ============================================================
# requestMagicLink — non-enumeration
# ============================================================


def test_request_without_result_session_cookie_is_202_and_never_touches_store(fake_store):
    """No ResultSession cookie -> 202, and the store must never see the call
    (an absent cookie must be indistinguishable from "a link was queued")."""
    client = _client_with_store(fake_store)
    resp = client.post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": VALID_RESULT_ID, "email": "a@example.com"},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert resp.status_code == 202
    assert resp.json() == {}
    assert fake_store.issued == []


def test_request_with_valid_session_reaches_the_store(fake_store):
    client = _client_with_store(fake_store)
    resp = client.post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": VALID_RESULT_ID, "email": "a@example.com"},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
        cookies={"garuda_result_session": VALID_RESULT_SESSION},
    )
    assert resp.status_code == 202
    assert len(fake_store.issued) == 1
    assert fake_store.issued[0]["result_id"] == VALID_RESULT_ID


def test_request_persistence_unavailable_is_visible_503(fake_store):
    fake_store.raise_on_issue = PersistencePolicyUnavailable("no store")
    client = _client_with_store(fake_store)
    resp = client.post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": VALID_RESULT_ID, "email": "a@example.com"},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
        cookies={"garuda_result_session": VALID_RESULT_SESSION},
    )
    assert resp.status_code == 503
    assert resp.json()["code"] == "PERSISTENCE_POLICY_UNAVAILABLE"


def test_request_idempotency_conflict_409(fake_store):
    fake_store.raise_on_issue = IdempotencyConflict("bound to a different payload")
    client = _client_with_store(fake_store)
    resp = client.post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": VALID_RESULT_ID, "email": "a@example.com"},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
        cookies={"garuda_result_session": VALID_RESULT_SESSION},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "IDEMPOTENCY_CONFLICT"


# ============================================================
# exchangeMagicLink — the two @red-first scenarios, verbatim
# ============================================================


def test_expired_link_returns_identical_response_to_invalid(fake_store):
    """Scenario: An expired magic link cannot create a session.

    'authentication fails with the SAME non-enumerating response used for an
    invalid link. No account session ... is created.'
    """
    fake_store.seed_token(VALID_TOKEN, expired=True, consumed=False)
    client = _client_with_store(fake_store)

    resp = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )

    assert resp.status_code == 401
    assert resp.json() == {
        "code": "MAGIC_LINK_INVALID",
        "retryable": False,
        "message_key": "garuda_voa.error.magic_link_invalid",
    }
    assert "Set-Cookie" not in resp.headers

    # Prove it against an UNKNOWN token too, from the same client — byte
    # identical response is the whole point of DECISIONS.md Q1.
    resp_unknown = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": "z" * 43},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY + "-2"},
    )
    assert resp_unknown.status_code == resp.status_code
    assert resp_unknown.json() == resp.json()


def test_consumed_link_cannot_authenticate_twice(fake_store):
    """Scenario: A consumed magic link cannot authenticate twice.

    First consume -> one account session created, link atomically marked
    used. Replay (same or different idempotency key) -> non-enumerating
    401, no second session, no second Set-Cookie.
    """
    fake_store.seed_token(VALID_TOKEN, expired=False, consumed=False)
    client = _client_with_store(fake_store)

    first = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert first.status_code == 204
    assert "garuda_session" in first.cookies

    # Replay under a DIFFERENT idempotency key — the token itself is now
    # consumed at the store, so this must be denied, not treated as a fresh
    # request.
    replay = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY + "-replay"},
    )
    assert replay.status_code == 401
    assert replay.json()["code"] == "MAGIC_LINK_INVALID"
    assert "Set-Cookie" not in replay.headers


def test_exact_idempotency_replay_returns_original_204_no_second_cookie(fake_store):
    """Contract: 'An exact Idempotency-Key replay returns the original 204
    but creates no second session and emits no second Set-Cookie.'"""
    fake_store.seed_token(VALID_TOKEN, expired=False, consumed=False)
    client = _client_with_store(fake_store)

    first = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert first.status_code == 204
    assert first.headers["Idempotency-Replayed"] == "false"
    assert "garuda_session" in first.cookies

    replay = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert replay.status_code == 204
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert "Set-Cookie" not in replay.headers


async def test_router_suppresses_cookie_on_replay_even_if_store_misbehaves(fake_store):
    """Defense-in-depth: even if a future store adapter returns a non-None
    `account_session_secret` alongside `idempotency_replayed=True` (a bug at
    the store layer), the ROUTER must still never emit a second Set-Cookie —
    the contract's 'no second Set-Cookie' guarantee cannot depend on every
    adapter getting this right."""

    class _MisbehavingStore(_FakeStore):
        async def exchange(self, *, idempotency_key: str, token: str) -> ExchangeOutcome:
            return ExchangeOutcome(
                authorized=True,
                security_counter="magic_link_authorized",
                result_id=VALID_RESULT_ID,
                account_session_secret="should-never-be-sent",
                idempotency_replayed=True,
            )

    client = _client_with_store(_MisbehavingStore())
    resp = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert resp.status_code == 204
    assert "Set-Cookie" not in resp.headers


def test_exchange_persistence_unavailable_is_visible_503(fake_store):
    fake_store.raise_on_exchange = PersistencePolicyUnavailable("no store")
    client = _client_with_store(fake_store)
    resp = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert resp.status_code == 503
    assert resp.json()["code"] == "PERSISTENCE_POLICY_UNAVAILABLE"
