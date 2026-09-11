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

`_FakeCheckStore` plays the identical role for `garuda_flow.public_api.
CheckStore` — the ownership port `request_magic_link` now consults BEFORE
`store.issue` (security fix 2026-08-30, see that handler's inline comment).
Every test below that reaches the magic-link store must therefore also wire
a `_FakeCheckStore` that recognises the (result_id, session_secret) pair it
expects to succeed, via `_client_with_stores`; `UnconfiguredCheckStore`
(this router's default when no override is given) always raises
`PersistencePolicyUnavailable`, which is itself covered by
`test_request_check_store_persistence_unavailable_is_visible_503` below.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import garuda_portal_auth as router_mod
from backend.services.garuda_flow.public_api import (
    PersistencePolicyUnavailable as CheckStorePersistencePolicyUnavailable,
)
from backend.services.garuda_portal.magic_link import (
    ExchangeOutcome,
    IdempotencyConflict,
    IssueOutcome,
    PeekOutcome,
    PersistencePolicyUnavailable,
    RateLimited,
)

VALID_RESULT_ID = "r" * 22
#: A second, equally well-formed result_id the session cookie below does
#: NOT own -- the ownership-check tests request a magic link for THIS one
#: while presenting a cookie only valid for `VALID_RESULT_ID`.
OTHER_RESULT_ID = "o" * 22
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
        # Refuter finding #9: a real adapter binds an Idempotency-Key to the
        # CANONICAL REQUEST (here, the token) it was first used with — reusing
        # the same key with a different token must be IDEMPOTENCY_CONFLICT,
        # never treated as a replay of the first token's outcome.
        self._exchanged_key_tokens: dict[str, str] = {}
        self.raise_on_issue: Exception | None = None
        self.raise_on_exchange: Exception | None = None
        self.raise_on_peek: Exception | None = None

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

    def seed_token(
        self, token: str, *, expired: bool, consumed: bool, email: str = "visitor@example.com"
    ) -> None:
        self.tokens[token] = {"expired": expired, "consumed": consumed, "email": email}

    async def exchange(self, *, idempotency_key: str, token: str) -> ExchangeOutcome:
        if self.raise_on_exchange is not None:
            raise self.raise_on_exchange

        if idempotency_key in self.exchanged_keys:
            if self._exchanged_key_tokens[idempotency_key] != token:
                raise IdempotencyConflict(
                    f"key {idempotency_key!r} already bound to a different token"
                )
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
        self._exchanged_key_tokens[idempotency_key] = token
        return outcome

    async def peek(self, *, token: str) -> PeekOutcome:
        if self.raise_on_peek is not None:
            raise self.raise_on_peek
        state = self.tokens.get(token)
        if state is None or state["expired"] or state["consumed"]:
            return PeekOutcome(valid=False)
        return PeekOutcome(valid=True, email=state["email"])


class _FakeCheckStore:
    """Minimal in-memory `garuda_flow.public_api.CheckStore` double.

    `request_magic_link` now consults this port (security fix 2026-08-30)
    to re-verify that the caller's `garuda_result_session` cookie actually
    owns the `result_id` in the request body, BEFORE it may reach
    `MagicLinkStore.issue` -- mirrors `_FakeStore` above (and
    `test_garuda_voa_public.py`'s own fake) for the identical reason.
    """

    def __init__(self, *, owned: set[tuple[str, str]] | None = None) -> None:
        self._owned = set(owned or set())
        self.calls: list[tuple[str, str]] = []
        self.raise_on_get: Exception | None = None

    async def get(self, *, result_id: str, session_secret: str) -> object | None:
        self.calls.append((result_id, session_secret))
        if self.raise_on_get is not None:
            raise self.raise_on_get
        if (result_id, session_secret) not in self._owned:
            return None
        return object()  # the router only ever branches on None-ness


@pytest.fixture(autouse=True)
def _enable_flag(monkeypatch):
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")


@pytest.fixture
def fake_store():
    return _FakeStore()


def _client_with_store(
    store: _FakeStore, check_store: _FakeCheckStore | None = None
) -> TestClient:
    """`check_store` defaults to one that recognises the (result_id,
    session_secret) pair every pre-existing test in this file already used
    before the ownership check existed -- so the happy-path tests below
    keep proving what they always proved, and only the tests that care
    about a DIFFERENT ownership pair pass their own `_FakeCheckStore`."""
    resolved_check_store = check_store or _FakeCheckStore(
        owned={(VALID_RESULT_ID, VALID_RESULT_SESSION)}
    )
    app = _app()
    app.dependency_overrides[router_mod.get_garuda_magic_link_store] = lambda: store
    app.dependency_overrides[router_mod.get_garuda_check_store] = lambda: resolved_check_store
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


def test_request_malformed_idempotency_key_is_422_not_400():
    """Refuter finding #6: present-but-invalid must be 422 INVALID_REQUEST,
    the contract reserves 400 for an ABSENT key only."""
    resp = _client().post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": VALID_RESULT_ID, "email": "a@example.com"},
        headers={"Idempotency-Key": "too-short"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_REQUEST"


def test_exchange_malformed_idempotency_key_is_422_not_400():
    resp = _client().post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": "too-short"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_REQUEST"


# ============================================================
# requestMagicLink — non-enumeration
# ============================================================


def test_request_without_result_session_cookie_is_202_and_never_touches_store(fake_store):
    """No ResultSession cookie -> 202, and NEITHER store may see the call
    (an absent cookie must be indistinguishable from "a link was queued");
    the ownership check added 2026-08-30 short-circuits before it, same as
    it always did before that check existed."""
    check_store = _FakeCheckStore(owned={(VALID_RESULT_ID, VALID_RESULT_SESSION)})
    client = _client_with_store(fake_store, check_store)
    resp = client.post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": VALID_RESULT_ID, "email": "a@example.com"},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert resp.status_code == 202
    assert resp.json() == {}
    assert fake_store.issued == []
    assert check_store.calls == []


def test_request_with_valid_session_reaches_the_store(fake_store):
    """Innocence: a cookie that DOES own the requested result_id must still
    reach `MagicLinkStore.issue` exactly as before -- the ownership check
    added 2026-08-30 must not regress the happy path."""
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


def test_request_for_a_result_id_the_cookie_does_not_own_is_202_and_never_touches_the_magic_link_store(
    fake_store,
):
    """Guilt (security fix, 2026-08-30): a session cookie valid for result
    A must NOT unlock a magic link for a DIFFERENT result_id B. Before this
    fix, `garuda_result_session`'s mere presence was enough -- any caller
    who knew or guessed a result_id they did not own could have its magic
    link mailed to an email address THEY control, using only their own,
    unrelated session cookie. The response must be the SAME non-enumerating
    202 as an absent cookie / malformed id, and `MagicLinkStore.issue`
    (hence the email it triggers) must never be reached."""
    check_store = _FakeCheckStore(owned={(VALID_RESULT_ID, VALID_RESULT_SESSION)})
    client = _client_with_store(fake_store, check_store)

    resp = client.post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": OTHER_RESULT_ID, "email": "attacker@example.com"},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
        cookies={"garuda_result_session": VALID_RESULT_SESSION},
    )

    assert resp.status_code == 202
    assert resp.json() == {}
    assert resp.headers["Idempotency-Replayed"] == "false"
    assert fake_store.issued == []
    assert check_store.calls == [(OTHER_RESULT_ID, VALID_RESULT_SESSION)]


def test_request_check_store_persistence_unavailable_is_visible_503(fake_store):
    """A misconfigured/unwired `CheckStore` must surface as an OBSERVABLE
    503, never silently collapse into the enumeration-safe 202 above -- that
    would look identical to "no magic link is ever issued", with no signal
    that ownership could not even be checked. Mirrors the mapping
    `garuda_voa_public.get_eligibility_result` already uses for the same
    unconfigured-store state."""
    check_store = _FakeCheckStore()
    check_store.raise_on_get = CheckStorePersistencePolicyUnavailable("no check store")
    client = _client_with_store(fake_store, check_store)

    resp = client.post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": VALID_RESULT_ID, "email": "a@example.com"},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
        cookies={"garuda_result_session": VALID_RESULT_SESSION},
    )

    assert resp.status_code == 503
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"
    assert fake_store.issued == []


def test_request_with_no_check_store_wired_defaults_to_503_not_a_silent_202(fake_store):
    """With no `get_garuda_check_store` override at all, this router's own
    default (`UnconfiguredCheckStore`, wired via `get_garuda_check_store`)
    must make the configuration gap OBSERVABLE rather than either silently
    issuing an unverified magic link or silently pretending nothing was
    requested."""
    app = _app()
    app.dependency_overrides[router_mod.get_garuda_magic_link_store] = lambda: fake_store
    client = TestClient(app)

    resp = client.post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": VALID_RESULT_ID, "email": "a@example.com"},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
        cookies={"garuda_result_session": VALID_RESULT_SESSION},
    )

    assert resp.status_code == 503
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"
    assert fake_store.issued == []


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


def test_request_rate_limited_is_visible_429(fake_store):
    """Team-lead review, 2026-08-25: RATE_LIMITED was declared in the frozen
    contract for `requestMagicLink` but unreachable on every code path
    before `PostgresMagicLinkStore.issue` was given a reason to raise it.
    This proves the ROUTER side of the wire is not the blocker — once any
    store raises `RateLimited`, the handler surfaces it as the contract's
    429, not the generic 500 the pre-existing catch-all would have produced.
    """
    fake_store.raise_on_issue = RateLimited("more than 5 magic-links in 15 minutes")
    client = _client_with_store(fake_store)
    resp = client.post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": VALID_RESULT_ID, "email": "a@example.com"},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
        cookies={"garuda_result_session": VALID_RESULT_SESSION},
    )
    assert resp.status_code == 429
    assert resp.json()["code"] == "RATE_LIMITED"


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


def test_request_unexpected_store_exception_is_contract_shaped_500(fake_store):
    """Refuter finding #4: any exception the store raises beyond the two
    named ones must still come back as the frozen INTERNAL_ERROR shape, never
    a bare framework 500."""
    fake_store.raise_on_issue = RuntimeError("boom")
    client = _client_with_store(fake_store)
    resp = client.post(
        "/api/visa/voa/auth/magic-links",
        json={"result_id": VALID_RESULT_ID, "email": "a@example.com"},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
        cookies={"garuda_result_session": VALID_RESULT_SESSION},
    )
    assert resp.status_code == 500
    assert resp.json()["code"] == "INTERNAL_ERROR"


def test_exchange_unexpected_store_exception_is_contract_shaped_500(fake_store):
    fake_store.raise_on_exchange = RuntimeError("boom")
    client = _client_with_store(fake_store)
    resp = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert resp.status_code == 500
    assert resp.json()["code"] == "INTERNAL_ERROR"


def test_exchange_same_key_different_token_is_conflict_not_replay(fake_store):
    """Refuter finding #9: an Idempotency-Key is bound to the request that
    first used it — reusing it with a DIFFERENT token must never be treated
    as a replay of the first token's outcome."""
    fake_store.seed_token(VALID_TOKEN, expired=False, consumed=False)
    other_token = "u" * 43
    fake_store.seed_token(other_token, expired=False, consumed=False)
    client = _client_with_store(fake_store)

    first = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert first.status_code == 204

    second = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": other_token},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert second.status_code == 409
    assert second.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_exchange_impossible_outcome_fails_closed(fake_store):
    """Refuter finding #8: `authorized=True`, not a replay, and no session
    secret is an inconsistent adapter state — the router must refuse to
    honour it as a real 204 rather than silently establish no session."""

    class _InconsistentStore(_FakeStore):
        async def exchange(self, *, idempotency_key: str, token: str) -> ExchangeOutcome:
            return ExchangeOutcome(
                authorized=True,
                security_counter="magic_link_authorized",
                result_id=VALID_RESULT_ID,
                account_session_secret=None,
                idempotency_replayed=False,
            )

    client = _client_with_store(_InconsistentStore())
    resp = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert resp.status_code == 500
    assert resp.json()["code"] == "INTERNAL_ERROR"
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


# ============================================================
# previewMagicLink — non-consuming lookup (NOT in the frozen contract; see
# module docstring)
# ============================================================


def test_preview_valid_token_returns_masked_email_without_idempotency_key(fake_store):
    fake_store.seed_token(VALID_TOKEN, expired=False, consumed=False, email="johndoe@example.com")
    client = _client_with_store(fake_store)

    resp = client.post("/api/visa/voa/auth/magic-links/preview", json={"token": VALID_TOKEN})

    assert resp.status_code == 200
    assert resp.json() == {"masked_email": "jo***@example.com"}


def test_preview_never_reveals_the_raw_email(fake_store):
    fake_store.seed_token(VALID_TOKEN, expired=False, consumed=False, email="johndoe@example.com")
    client = _client_with_store(fake_store)

    resp = client.post("/api/visa/voa/auth/magic-links/preview", json={"token": VALID_TOKEN})

    assert "johndoe" not in resp.text


def test_preview_does_not_consume_the_token_then_exchange_still_succeeds(fake_store):
    """The load-bearing property this endpoint exists to prove: preview must
    never spend the credential it describes. Proven end to end -- preview,
    then a REAL exchange of the SAME token, must still succeed exactly as
    if preview had never run."""
    fake_store.seed_token(VALID_TOKEN, expired=False, consumed=False, email="johndoe@example.com")
    client = _client_with_store(fake_store)

    preview = client.post("/api/visa/voa/auth/magic-links/preview", json={"token": VALID_TOKEN})
    assert preview.status_code == 200

    exchange = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert exchange.status_code == 204
    assert "garuda_session" in exchange.cookies


def test_preview_expired_link_is_non_enumerating_401(fake_store):
    fake_store.seed_token(VALID_TOKEN, expired=True, consumed=False)
    client = _client_with_store(fake_store)

    resp = client.post("/api/visa/voa/auth/magic-links/preview", json={"token": VALID_TOKEN})

    assert resp.status_code == 401
    assert resp.json()["code"] == "MAGIC_LINK_INVALID"


def test_preview_consumed_link_is_indistinguishable_from_unknown(fake_store):
    """DECISIONS.md Q1 applies to preview exactly as it does to exchange: a
    consumed and an unknown token must be byte-identical to the caller."""
    fake_store.seed_token(VALID_TOKEN, expired=False, consumed=True)
    client = _client_with_store(fake_store)

    consumed_resp = client.post(
        "/api/visa/voa/auth/magic-links/preview", json={"token": VALID_TOKEN}
    )
    unknown_resp = client.post(
        "/api/visa/voa/auth/magic-links/preview", json={"token": "z" * 43}
    )

    assert consumed_resp.status_code == unknown_resp.status_code == 401
    assert consumed_resp.json() == unknown_resp.json()


def test_preview_disabled_flag_returns_404(monkeypatch):
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "false")
    resp = _client().post(
        "/api/visa/voa/auth/magic-links/preview", json={"token": VALID_TOKEN}
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "GARUDA_PUBLIC_DISABLED"


def test_preview_persistence_unavailable_is_visible_503(fake_store):
    fake_store.raise_on_peek = PersistencePolicyUnavailable("no store")
    client = _client_with_store(fake_store)
    resp = client.post("/api/visa/voa/auth/magic-links/preview", json={"token": VALID_TOKEN})
    assert resp.status_code == 503
    assert resp.json()["code"] == "PERSISTENCE_POLICY_UNAVAILABLE"


def test_preview_unexpected_store_exception_is_contract_shaped_500(fake_store):
    fake_store.raise_on_peek = RuntimeError("boom")
    client = _client_with_store(fake_store)
    resp = client.post("/api/visa/voa/auth/magic-links/preview", json={"token": VALID_TOKEN})
    assert resp.status_code == 500
    assert resp.json()["code"] == "INTERNAL_ERROR"


def test_preview_requires_no_idempotency_key():
    """Unlike issue/exchange, preview mutates nothing -- no Idempotency-Key
    header should ever be required."""
    store = _FakeStore()
    store.seed_token(VALID_TOKEN, expired=False, consumed=False)
    client = _client_with_store(store)
    resp = client.post("/api/visa/voa/auth/magic-links/preview", json={"token": VALID_TOKEN})
    assert resp.status_code == 200


def test_preview_rate_limit_class_matches_its_mounted_siblings():
    """No store-level throttle (see the handler's own docstring) -- the
    generic per-IP `/api/` bucket must still cover this path, the same one
    `/magic-links` and `/sessions` already answer under."""
    from backend.middleware.rate_limiter import RateLimitMiddleware

    rl = RateLimitMiddleware(app=object())
    preview_limit = rl._get_rate_limit("/api/visa/voa/auth/magic-links/preview")
    assert preview_limit == rl._get_rate_limit("/api/visa/voa/auth/sessions")
    assert preview_limit == (120, 60)


# ============================================================
# CodeQL py/clear-text-storage-sensitive-data (2026-08-25) — the account-
# session cookie must never be issued without `Secure` outside a genuinely-
# loopback-socket connection. `settings.environment` in this test process is
# "test" (`backend/tests/conftest.py`), i.e. NOT "production" — the shared
# `cookie_auth.get_cookie_secure()` would return `False` here, and the
# `TestClient` default host is "testserver", i.e. NOT loopback either. This
# is exactly the staging/preview/container shape the refuter flagged as
# reachable-over-a-real-network.
#
# ROUND 2 (same day): the first fix read `request.url.hostname`, which
# Starlette derives from the client-supplied `Host` header, not the socket —
# so a spoofed `Host: localhost` on a MITM'd staging request would have made
# the server drop `Secure`. `test_account_session_cookie_ignores_spoofed_host_header`
# below is the test that catches that: it sends `Host: localhost` to a
# non-loopback ASGI `server` socket and asserts `Secure` is still set. It was
# run RED against the round-1 fix (`request.url.hostname`-based) and GREEN
# against the round-2 fix (`request.scope["scheme"]`/`request.scope["server"]`
# -based, `_account_session_cookie_secure`) — pasted verbatim in the PR
# description. The genuine-localhost test also sends a mismatched Host header
# to prove the relaxation fires on the ASGI socket, not on anything the
# client can claim via a header.
# ============================================================


def test_account_session_cookie_is_secure_on_non_production_non_localhost_host(fake_store):
    """A non-production environment reached over a non-loopback host (the
    staging/preview/container shape) must still get `Secure` on the account-
    session cookie. This is the exact CodeQL
    `py/clear-text-storage-sensitive-data` regression at
    `_set_account_session_cookie` — asserting `Secure` is present is what
    would have caught it."""
    fake_store.seed_token(VALID_TOKEN, expired=False, consumed=False)
    client = _client_with_store(fake_store)

    resp = client.post(
        "/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )

    assert resp.status_code == 204
    set_cookie_headers = resp.headers.get_list("set-cookie")
    account_cookie = next(h for h in set_cookie_headers if h.startswith("garuda_session="))
    assert "Secure" in account_cookie, account_cookie


def test_account_session_cookie_ignores_spoofed_host_header(fake_store):
    """The Host header is client-supplied and must never drive this policy.
    Posting to a NON-loopback ASGI socket (`example.com`) with a spoofed
    `Host: localhost` header must still get `Secure` — this is the exact
    shape a MITM on a staging/preview deploy could exploit against a
    hostname-based check (measured: `Request(scope).url.hostname` reads
    'localhost' here even though `scope['server']` is `('example.com', 80)`).
    This test is RED against a `request.url.hostname`-based implementation
    and GREEN against one that reads `request.scope['server']`/`['scheme']`."""
    fake_store.seed_token(VALID_TOKEN, expired=False, consumed=False)
    client = _client_with_store(fake_store)

    resp = client.post(
        "http://example.com/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY, "Host": "localhost"},
    )

    assert resp.status_code == 204
    set_cookie_headers = resp.headers.get_list("set-cookie")
    account_cookie = next(h for h in set_cookie_headers if h.startswith("garuda_session="))
    assert "Secure" in account_cookie, account_cookie


def test_account_session_cookie_relaxes_only_on_genuine_localhost(fake_store):
    """The one legitimate relaxation: a request whose ASGI socket is
    genuinely loopback (real local dev, `uvicorn --host 127.0.0.1`, no TLS)
    may skip `Secure`. Sends a MISMATCHED Host header (`internal-lb`) to
    prove the relaxation is driven by the socket-level `server` tuple, not
    by anything the client's Host header claims — the exact opposite
    direction of the spoofed-Host test above."""
    fake_store.seed_token(VALID_TOKEN, expired=False, consumed=False)
    client = _client_with_store(fake_store)

    resp = client.post(
        "http://127.0.0.1/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY, "Host": "internal-lb"},
    )

    assert resp.status_code == 204
    set_cookie_headers = resp.headers.get_list("set-cookie")
    account_cookie = next(h for h in set_cookie_headers if h.startswith("garuda_session="))
    assert "Secure" not in account_cookie, account_cookie


def test_account_session_cookie_is_secure_on_loopback_https(fake_store):
    """An already-`https` connection is always `Secure=True`, even on a
    loopback socket — `Secure` costs nothing once the transport is already
    encrypted, and the one relaxation this policy grants is scoped to plain
    `http` on loopback only."""
    fake_store.seed_token(VALID_TOKEN, expired=False, consumed=False)
    client = _client_with_store(fake_store)

    resp = client.post(
        "https://127.0.0.1/api/visa/voa/auth/sessions",
        json={"token": VALID_TOKEN},
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )

    assert resp.status_code == 204
    set_cookie_headers = resp.headers.get_list("set-cookie")
    account_cookie = next(h for h in set_cookie_headers if h.startswith("garuda_session="))
    assert "Secure" in account_cookie, account_cookie


# ============================================================
# A blind catch-all cannot be diagnosed (2026-08-30, measured in production)
# ============================================================


class _PolicyProbeFailed(Exception):
    """Stands in for the class of store failure that took issuance down."""


def _assert_named_but_silent(caplog, *, expected_name: str, forbidden: str) -> None:
    records = [r for r in caplog.records if "unexpected error" in r.getMessage()]
    assert records, "the handler must still log the failure"
    message = records[-1].getMessage()
    assert expected_name in message, (
        "the exception's CLASS NAME must reach the log: on 2026-08-30 every call to this "
        "endpoint answered INTERNAL_ERROR and the log said only 'unexpected error', which "
        "cannot tell an absent SQL function from a bad cast from a dead pool"
    )
    assert forbidden not in message, "the exception MESSAGE must never be logged: it can quote a value"
    assert records[-1].exc_info is None, (
        "exc_info stays off — Sentry's LoggingIntegration turns it into a frame-locals dump, "
        "which is where the session secret lives and where key-based redaction cannot reach"
    )


def test_issue_failure_logs_the_exception_class_and_nothing_else(fake_store, caplog):
    fake_store.raise_on_issue = _PolicyProbeFailed("s3cret-session-value")
    client = _client_with_store(fake_store)

    with caplog.at_level("ERROR"):
        resp = client.post(
            "/api/visa/voa/auth/magic-links",
            json={"result_id": VALID_RESULT_ID, "email": "traveller@example.com"},
            headers={"Idempotency-Key": "11111111-1111-4111-8111-111111111111"},
            # `VALID_RESULT_SESSION`, not an arbitrary literal: since the
            # ownership check landed on this handler, a cookie the default
            # `_FakeCheckStore` does not recognise takes the non-enumerating
            # 202 path and `store.issue` — the thing THIS test is about — is
            # never reached. Written as the ownership constant so the two
            # facts stay coupled: this test asserts what the handler logs
            # when issuance fails FOR A LEGITIMATE OWNER.
            cookies={"garuda_result_session": VALID_RESULT_SESSION},
        )

    assert resp.status_code == 500
    assert resp.json()["code"] == "INTERNAL_ERROR"
    _assert_named_but_silent(
        caplog, expected_name="_PolicyProbeFailed", forbidden="s3cret-session-value"
    )


def test_exchange_failure_logs_the_exception_class_and_nothing_else(fake_store, caplog):
    fake_store.raise_on_exchange = _PolicyProbeFailed("s3cret-token-value")
    client = _client_with_store(fake_store)

    with caplog.at_level("ERROR"):
        resp = client.post(
            "/api/visa/voa/auth/sessions",
            json={"token": "T" * 43},
            headers={"Idempotency-Key": "22222222-2222-4222-8222-222222222222"},
        )

    assert resp.status_code == 500
    assert resp.json()["code"] == "INTERNAL_ERROR"
    _assert_named_but_silent(
        caplog, expected_name="_PolicyProbeFailed", forbidden="s3cret-token-value"
    )
