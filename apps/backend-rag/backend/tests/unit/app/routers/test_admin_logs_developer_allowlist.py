"""Tests for `admin_logs.verify_log_read_access` — the DEVELOPER_EMAILS gate.

WHY THIS EXISTS (2026-09-10): the runtime log endpoints (`/api/admin/logs/*`)
were reachable only by an admin-role JWT or by `ADMIN_API_KEY`. A senior
developer debugging production is neither, and the two ways of letting him in
were both wrong: making him a CRM admin hands him the whole client book, and
`ADMIN_API_KEY` is one shared secret that cannot be revoked per person.

WHY THE GRANT IS NOT ON `verify_debug_access` (adversarial review,
codex-gpt-5.6-sol, verdict REJECT on the first cut; verified on disk before
being accepted): that dependency guards every route in `debug.py`, including
`POST /api/debug/postgres/query`, which runs a caller-supplied SQL statement
against production. Adding the allowlist there would have granted arbitrary
SELECT over the client book — strictly more than CRM admin, and the exact
outcome the separate perimeter exists to prevent. The containment tests at the
bottom of this file are the proof that it did not happen.

Being a GUARD, it ships with guilt AND innocence
(`.claude/rules/cicatrix-superscar.md` #3), and the innocence half carries the
OVER-match cases, because an allowlist compared as a substring or a domain
suffix is how that family bites.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

DEVELOPER = "dev.seat@balizero.com"


def _settings():
    from backend.app.core.config import settings

    return settings


_OMIT = object()


def _make_jwt(
    secret: str,
    *,
    email: object = _OMIT,
    role: str = "member",
    token_type: str | None = "access",
) -> str:
    """`email` / `token_type` accept `_OMIT` / `None` to LEAVE THE CLAIM OUT.

    An absent claim and a claim holding the empty string are two different
    tokens, and a test named for one while minting the other proves neither
    (adversarial review, kimi-code/k3, round 1, finding 10).
    """
    from jose import jwt

    claims: dict[str, object] = {
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    if email is not _OMIT:
        claims["email"] = email
    if token_type is not None:
        claims["type"] = token_type
    return jwt.encode(claims, secret, algorithm="HS256")


class _Req:
    """Minimal stand-in for fastapi Request (only .headers is read)."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}


@pytest.fixture()
def secret(monkeypatch) -> str:
    s = _settings()
    key = "test-jwt-secret-for-developer-allowlist"
    monkeypatch.setattr(s, "jwt_secret_key", key, raising=False)
    # Non-production so the ADMIN_API_KEY-required guard doesn't short-circuit.
    monkeypatch.setattr(s, "environment", "development", raising=False)
    monkeypatch.setattr(s, "admin_api_key", None, raising=False)
    return key


@pytest.fixture(autouse=True)
def live_session(monkeypatch):
    """Every test below assumes the session is NOT revoked, unless it says so.

    Without this the whole file 503s: revocation is enabled by default and the
    store is Redis, which no unit test has. That 503 is the gate failing CLOSED
    and is itself asserted in `test_revocation_store_outage_fails_closed_with_503`
    — here it would only be noise drowning the property under test. The three
    revocation tests re-patch this in their own body, which wins over an
    autouse fixture.
    """
    import backend.services.security.token_revocation as revocation

    monkeypatch.setattr(revocation, "is_session_revoked_sync", lambda _payload: False)


@pytest.fixture()
def with_developer(monkeypatch):
    monkeypatch.setattr(_settings(), "developer_emails", DEVELOPER, raising=False)


def _check(token: str):
    from backend.app.routers.admin_logs import verify_log_read_access

    return verify_log_read_access(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
        request=_Req(),
    )


# --------------------------------------------------------------- GUILT


def test_listed_developer_with_ordinary_team_role_is_granted(secret, with_developer) -> None:
    """The whole point: role=member, but the address is on the list."""
    assert _check(_make_jwt(secret, email=DEVELOPER)) is True


def test_listed_developer_is_matched_case_insensitively(secret, with_developer) -> None:
    """A JWT minted with a capitalised address is the same person."""
    assert _check(_make_jwt(secret, email="Dev.Seat@BaliZero.com")) is True


# ----------------------------------------------------------- INNOCENCE


def test_same_developer_is_rejected_when_the_list_is_unset(secret, monkeypatch) -> None:
    """LOAD-BEARING: proves the grant comes from the LIST, not from the role.

    Without this the guilt tests would pass just as well if the code had
    accidentally started accepting every `member` JWT.
    """
    monkeypatch.setattr(_settings(), "developer_emails", None, raising=False)
    with pytest.raises(HTTPException) as exc:
        _check(_make_jwt(secret, email=DEVELOPER))
    assert exc.value.status_code == 401


def test_blank_list_grants_nobody(secret, monkeypatch) -> None:
    """`DEVELOPER_EMAILS=" , "` parses to an empty set, not to a wildcard."""
    monkeypatch.setattr(_settings(), "developer_emails", " , ", raising=False)
    with pytest.raises(HTTPException) as exc:
        _check(_make_jwt(secret, email=DEVELOPER))
    assert exc.value.status_code == 401


def test_unlisted_team_member_is_rejected(secret, with_developer) -> None:
    with pytest.raises(HTTPException) as exc:
        _check(_make_jwt(secret, email="someone.else@balizero.com"))
    assert exc.value.status_code == 401


@pytest.mark.parametrize(
    "impostor",
    [
        "evil+dev.seat@balizero.com",  # listed address inside a longer local part
        "dev.seat@balizero.com.attacker.io",  # listed address as a domain prefix
        "notdev.seat@balizero.com",
        "dev.seat@balizero.co",  # one character short of the listed domain
    ],
)
def test_over_match_impostors_are_rejected(secret, with_developer, impostor: str) -> None:
    """Superscar #3: the allowlist is an ENTITY comparison, not a substring one."""
    with pytest.raises(HTTPException) as exc:
        _check(_make_jwt(secret, email=impostor))
    assert exc.value.status_code == 401


def test_refresh_token_of_a_listed_developer_is_rejected(secret, with_developer) -> None:
    """A refresh token is not an access token, listed address or not."""
    with pytest.raises(HTTPException) as exc:
        _check(_make_jwt(secret, email=DEVELOPER, token_type="refresh"))
    assert exc.value.status_code == 401


def test_token_with_no_type_claim_is_rejected(secret, with_developer) -> None:
    """STRICTER THAN `verify_debug_access` ON PURPOSE.

    That gate accepts `type` missing OR "access", a tolerance the adversarial
    review flagged: another token family signed with the same key and carrying
    a listed email would inherit the grant. This gate requires the claim to be
    exactly "access".
    """
    with pytest.raises(HTTPException) as exc:
        _check(_make_jwt(secret, email=DEVELOPER, token_type=None))
    assert exc.value.status_code == 401


def test_token_with_an_empty_email_claim_is_rejected(secret, with_developer) -> None:
    """The empty string must never match a list entry."""
    with pytest.raises(HTTPException) as exc:
        _check(_make_jwt(secret, email=""))
    assert exc.value.status_code == 401


def test_token_with_no_email_claim_at_all_is_rejected(secret, with_developer) -> None:
    """A MISSING claim, not an empty one — the case the old name promised."""
    with pytest.raises(HTTPException) as exc:
        _check(_make_jwt(secret))
    assert exc.value.status_code == 401


def test_non_string_email_claim_is_rejected(secret, with_developer) -> None:
    """`email` is attacker-influenced data; a list or an int must fail closed,
    not raise 500 out of the gate."""
    for hostile in (["dev.seat@balizero.com"], 42, {"x": 1}):
        with pytest.raises(HTTPException) as exc:
            _check(_make_jwt(secret, email=hostile))
        assert exc.value.status_code == 401


@pytest.mark.parametrize("raw", [f"  {DEVELOPER.upper()}  ", f"{DEVELOPER},{DEVELOPER}", f"{DEVELOPER},"])
def test_env_side_normalisation_of_the_list(secret, monkeypatch, raw: str) -> None:
    """The ENV half of the comparison, which round 1 noted was untested:
    surrounding whitespace, an uppercase entry, a duplicate and a trailing
    comma must all still grant exactly the one listed person."""
    monkeypatch.setattr(_settings(), "developer_emails", raw, raising=False)
    assert _check(_make_jwt(secret, email=DEVELOPER)) is True
    with pytest.raises(HTTPException):
        _check(_make_jwt(secret, email="someone.else@balizero.com"))


def test_expired_token_of_a_listed_developer_is_rejected(secret, with_developer) -> None:
    """`verify_exp` pinned by a red test, not by trust in python-jose
    (adversarial review, kimi-code/k3, round 2, finding 6)."""
    from jose import jwt

    expired = jwt.encode(
        {
            "email": DEVELOPER,
            "role": "member",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        _check(expired)
    assert exc.value.status_code == 401


def test_token_without_an_exp_claim_is_rejected(secret, with_developer) -> None:
    """`require_exp` — a token that never expires must not be accepted."""
    from jose import jwt

    no_exp = jwt.encode(
        {"email": DEVELOPER, "role": "member", "type": "access"},
        secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        _check(no_exp)
    assert exc.value.status_code == 401


def test_token_signed_with_another_key_is_rejected(secret, with_developer) -> None:
    with pytest.raises(HTTPException) as exc:
        _check(_make_jwt("a-different-secret", email=DEVELOPER))
    assert exc.value.status_code == 401


def test_garbage_token_is_rejected(secret, with_developer) -> None:
    with pytest.raises(HTTPException) as exc:
        _check("not-a-jwt")
    assert exc.value.status_code == 401


def test_no_credentials_is_rejected(secret, with_developer) -> None:
    from backend.app.routers.admin_logs import verify_log_read_access

    with pytest.raises(HTTPException) as exc:
        verify_log_read_access(credentials=None, request=_Req())
    assert exc.value.status_code == 401


# ------------------------------------------- THE ADMIN PATHS, UNCHANGED


def test_admin_jwt_still_opens_the_logs(secret, monkeypatch) -> None:
    """Delegation to `verify_debug_access` must not have narrowed anything."""
    monkeypatch.setattr(_settings(), "developer_emails", None, raising=False)
    assert _check(_make_jwt(secret, email="boss@balizero.com", role="Founder")) is True


def test_admin_api_key_still_opens_the_logs(secret, with_developer, monkeypatch) -> None:
    monkeypatch.setattr(_settings(), "admin_api_key", "super-secret-admin-key", raising=False)
    assert _check("super-secret-admin-key") is True


# ------------------------------------------------------- CONTAINMENT
#
# The finding that sent the first cut back: the grant must reach the LOGS and
# nothing else. `verify_debug_access` guards `POST /api/debug/postgres/query`
# (arbitrary SQL against production), `DELETE /api/debug/traces` and
# `POST /api/debug/profile`. A listed developer must be refused by it.


def test_listed_developer_is_still_refused_by_the_debug_gate(secret, with_developer) -> None:
    from backend.app.routers.debug import verify_debug_access

    cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=_make_jwt(secret, email=DEVELOPER))
    with pytest.raises(HTTPException) as exc:
        verify_debug_access(credentials=cred, request=_Req())
    assert exc.value.status_code == 401


# A `test_developer_perimeter_does_not_make_a_crm_admin` used to sit here,
# asserting `is_crm_admin(...) is False`. It was VACUOUS and has been removed:
# `is_crm_admin` never reads `developer_emails`, so it passed under any
# implementation of this diff — including the round-1 one that DID leak
# arbitrary SQL (adversarial review, kimi-code/k3, round 2, finding 10). A test
# that cannot fail is worse than no test, because it reads as proof. The real
# containment proof is `test_listed_developer_cannot_run_sql_over_http` below,
# which fails if the perimeter breaks.


# ------------------------------------------- THE CONSUMERS, OVER REAL HTTP


class _FakeConn:
    async def fetch(self, *_args, **_kwargs):
        return []


class _FakeAcquire:
    async def __aenter__(self):
        return _FakeConn()

    async def __aexit__(self, *_exc):
        return False


class _FakePool:
    def acquire(self):
        return _FakeAcquire()


@pytest.fixture()
def app_client(secret):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.dependencies import get_database_pool
    from backend.app.routers import admin_logs, debug

    app = FastAPI()
    app.include_router(admin_logs.router)
    app.include_router(debug.router)
    app.dependency_overrides[get_database_pool] = lambda: _FakePool()
    return TestClient(app)


def _get_logs(client, token: str):
    return client.get(
        "/api/admin/logs/summary/today",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_listed_developer_opens_the_logs_endpoint(app_client, secret, with_developer) -> None:
    """GUILT, over HTTP: role=member + listed address → the log summary opens."""
    response = _get_logs(app_client, _make_jwt(secret, email=DEVELOPER))
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


def test_unlisted_member_is_401_on_the_logs_endpoint(app_client, secret, monkeypatch) -> None:
    """INNOCENCE, over HTTP: the same request with the list unset is refused."""
    monkeypatch.setattr(_settings(), "developer_emails", None, raising=False)
    response = _get_logs(app_client, _make_jwt(secret, email=DEVELOPER))
    assert response.status_code == 401, response.text


def test_listed_developer_cannot_run_sql_over_http(app_client, secret, with_developer) -> None:
    """CONTAINMENT, over HTTP — the case that failed the first cut.

    The same token that opens the log summary must be refused by the arbitrary
    SQL endpoint, because that one is behind the untouched admin-only gate.
    """
    token = _make_jwt(secret, email=DEVELOPER)
    assert _get_logs(app_client, token).status_code == 200

    response = app_client.post(
        "/api/debug/postgres/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "SELECT email FROM clients", "limit": 5},
    )
    assert response.status_code == 401, response.text


def test_production_without_admin_api_key_refuses_even_a_listed_developer(
    secret, with_developer, monkeypatch
) -> None:
    """The environment-level refusal is not a "not an admin" 401.

    `verify_debug_access` raises 403 when environment == production and
    ADMIN_API_KEY is unset — "debug endpoints are not available here at all".
    The log gate must propagate that, not swallow it and then grant on the
    allowlist (adversarial review, kimi-code/k3, round 2).
    """
    monkeypatch.setattr(_settings(), "environment", "production", raising=False)
    monkeypatch.setattr(_settings(), "admin_api_key", None, raising=False)
    with pytest.raises(HTTPException) as exc:
        _check(_make_jwt(secret, email=DEVELOPER))
    assert exc.value.status_code == 403


# --------------------------------------------------- SESSION REVOCATION
#
# Both review seats raised this independently: a signed, unexpired token is not
# a live session. Without the check, a developer who logged out — or whose
# access was revoked — keeps reading production logs until the token expires.


def test_revoked_session_of_a_listed_developer_is_rejected(
    secret, with_developer, monkeypatch
) -> None:
    """GUILT for the revocation check: listed, valid signature, revoked → 401."""
    import backend.services.security.token_revocation as revocation

    monkeypatch.setattr(revocation, "is_session_revoked_sync", lambda _payload: True)
    with pytest.raises(HTTPException) as exc:
        _check(_make_jwt(secret, email=DEVELOPER))
    assert exc.value.status_code == 401


def test_live_session_of_a_listed_developer_is_granted(
    secret, with_developer, monkeypatch
) -> None:
    """INNOCENCE: the check must not reject a session that is NOT revoked."""
    import backend.services.security.token_revocation as revocation

    monkeypatch.setattr(revocation, "is_session_revoked_sync", lambda _payload: False)
    assert _check(_make_jwt(secret, email=DEVELOPER)) is True


def test_revocation_store_outage_fails_closed_with_503(
    secret, with_developer, monkeypatch
) -> None:
    """A store that cannot answer must NOT be indistinguishable from a bad
    token: 503, the same shape `get_current_user` raises, never a silent 401
    and never a grant."""
    import backend.services.security.token_revocation as revocation

    def _unavailable(_payload):
        raise revocation.RevocationStoreUnavailable("store down")

    monkeypatch.setattr(revocation, "is_session_revoked_sync", _unavailable)
    with pytest.raises(HTTPException) as exc:
        _check(_make_jwt(secret, email=DEVELOPER))
    assert exc.value.status_code == 503
