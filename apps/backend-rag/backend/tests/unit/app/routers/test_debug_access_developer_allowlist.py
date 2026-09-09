"""Tests for the DEVELOPER_EMAILS perimeter on `debug.verify_debug_access`.

WHY THIS EXISTS (2026-09-10): the runtime observability endpoints
(`/api/debug/*`, `/api/admin/logs/*`) were reachable only by an admin-role JWT
or by `ADMIN_API_KEY`. A senior developer debugging production is neither: his
`team_members.role` is an ordinary team role, and the two ways to let him in
were both wrong. Making him a CRM admin hands him the entire client book, and
`ADMIN_API_KEY` is one shared secret that cannot be revoked for one person.
Hence a separate, explicit, per-address allowlist.

Being a GUARD (it accepts or rejects a principal), it ships with guilt AND
innocence — `.claude/rules/cicatrix-superscar.md` #3 — and the innocence half
carries the OVER-match cases, because an allowlist compared as a substring or
a domain suffix is exactly how that family bites.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

DEVELOPER = "subhi@balizero.com"


def _settings():
    from backend.app.core.config import settings

    return settings


def _make_jwt(secret: str, *, email: str, role: str = "member", token_type: str = "access") -> str:
    from jose import jwt

    return jwt.encode(
        {
            "email": email,
            "role": role,
            "type": token_type,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        secret,
        algorithm="HS256",
    )


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


@pytest.fixture()
def with_developer(monkeypatch):
    monkeypatch.setattr(_settings(), "developer_emails", DEVELOPER, raising=False)


def _check(token: str):
    from backend.app.routers.debug import verify_debug_access

    return verify_debug_access(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
        request=_Req(),
    )


# --------------------------------------------------------------- GUILT


def test_listed_developer_with_ordinary_team_role_is_granted(secret, with_developer) -> None:
    """The whole point: role=member, but the address is on the list."""
    assert _check(_make_jwt(secret, email=DEVELOPER)) is True


def test_listed_developer_is_matched_case_insensitively(secret, with_developer) -> None:
    """A JWT minted with a capitalised address is the same person."""
    assert _check(_make_jwt(secret, email="Subhi@BaliZero.com")) is True


# ----------------------------------------------------------- INNOCENCE


def test_same_developer_is_rejected_when_the_list_is_unset(secret, monkeypatch) -> None:
    """LOAD-BEARING: proves the grant comes from the LIST, not from the role.

    Without this the guilt test above would pass just as well if the code had
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
        "evil+subhi@balizero.com",  # listed address as a substring of a longer local part
        "subhi@balizero.com.attacker.io",  # listed address as a prefix of another domain
        "notsubhi@balizero.com",
        "subhi@balizero.co",  # one character short of the listed domain
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


def test_token_without_an_email_claim_is_rejected(secret, with_developer) -> None:
    """The empty string must never match a list entry."""
    with pytest.raises(HTTPException) as exc:
        _check(_make_jwt(secret, email=""))
    assert exc.value.status_code == 401


def test_developer_perimeter_does_not_make_a_crm_admin(with_developer) -> None:
    """The grant must stay INSIDE observability.

    `is_crm_admin` is what opens the whole client book (it drops the
    `assigned_to` filter on every CRM list endpoint). Reading logs must not
    imply reading the book — this is the containment the separate allowlist
    exists to provide.
    """
    from backend.app.utils.crm_utils import is_crm_admin

    assert is_crm_admin({"email": DEVELOPER, "role": "member"}) is False


# ------------------------------------------- THE CONSUMER, OVER REAL HTTP
#
# The tests above drive the dependency directly. These two drive the ENDPOINT
# Subhi actually opens, over a real request through the real router, with only
# the database faked — because a gate that passes as a function and still 401s
# behind its own route would be a gate that works nowhere that matters.


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
def logs_client(secret):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.dependencies import get_database_pool
    from backend.app.routers import admin_logs

    app = FastAPI()
    app.include_router(admin_logs.router)
    app.dependency_overrides[get_database_pool] = lambda: _FakePool()
    return TestClient(app)


def test_listed_developer_opens_the_logs_endpoint(logs_client, secret, with_developer) -> None:
    """GUILT, over HTTP: role=member + listed address → the log summary opens."""
    token = _make_jwt(secret, email=DEVELOPER)
    response = logs_client.get(
        "/api/admin/logs/summary/today",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


def test_unlisted_member_is_401_on_the_logs_endpoint(logs_client, secret, monkeypatch) -> None:
    """INNOCENCE, over HTTP: the same request with the list unset is refused."""
    monkeypatch.setattr(_settings(), "developer_emails", None, raising=False)
    token = _make_jwt(secret, email=DEVELOPER)
    response = logs_client.get(
        "/api/admin/logs/summary/today",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401, response.text
