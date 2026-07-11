"""
Tests for debug.verify_debug_access accepting a genuine admin JWT.

SCAR CONTEXT (found via live prod E2E 2026-07-08):
`verify_debug_access` advertised "API key OR JWT token" in its 401 message but
the JWT branch was a stub — it only re-checked `token == admin_api_key` (a
duplicate of the API-key branch above it). So a genuine Founder's JWT was
rejected with 401 on all 24 debug endpoints (/api/debug/*, used by
settings/system-pulse). Fix: validate the Bearer token as a JWT (same as
get_current_user) and grant access when the role is an admin role.

These tests drive verify_debug_access directly with forged tokens signed by
the configured jwt_secret_key, so they prove the gate by CONTENT.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials


def _settings():
    from backend.app.core.config import settings

    return settings


def _make_jwt(role: str, secret: str) -> str:
    from jose import jwt

    return jwt.encode(
        {"email": "u@balizero.com", "role": role, "type": "access"},
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
    key = "test-jwt-secret-for-debug-access"
    monkeypatch.setattr(s, "jwt_secret_key", key, raising=False)
    monkeypatch.setattr(s, "jwt_enforce_expiry", False, raising=False)
    # Non-production so the ADMIN_API_KEY-required guard doesn't short-circuit.
    monkeypatch.setattr(s, "environment", "development", raising=False)
    return key


def test_founder_jwt_grants_debug_access(secret) -> None:
    """GUILT: a Founder's JWT must be accepted (the regression: it was 401'd)."""
    from backend.app.routers.debug import verify_debug_access

    cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=_make_jwt("Founder", secret))
    assert verify_debug_access(credentials=cred, request=_Req()) is True


def test_admin_jwt_grants_debug_access(secret) -> None:
    """GUILT: role=admin also passes."""
    from backend.app.routers.debug import verify_debug_access

    cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=_make_jwt("admin", secret))
    assert verify_debug_access(credentials=cred, request=_Req()) is True


def test_regular_user_jwt_still_401(secret) -> None:
    """INNOCENCE: a non-admin JWT (role=user) must still be rejected — the fix
    must not open debug endpoints to every authenticated user."""
    from backend.app.routers.debug import verify_debug_access

    cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=_make_jwt("user", secret))
    with pytest.raises(HTTPException) as exc:
        verify_debug_access(credentials=cred, request=_Req())
    assert exc.value.status_code == 401


def test_no_credentials_still_401(secret) -> None:
    """INNOCENCE: no token at all → 401."""
    from backend.app.routers.debug import verify_debug_access

    with pytest.raises(HTTPException) as exc:
        verify_debug_access(credentials=None, request=_Req())
    assert exc.value.status_code == 401


def test_garbage_token_still_401(secret) -> None:
    """INNOCENCE: a bearer token that isn't a valid JWT (and isn't the API key)
    must not crash and must 401 — the except branch swallows the JWTError."""
    from backend.app.routers.debug import verify_debug_access

    cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-jwt")
    with pytest.raises(HTTPException) as exc:
        verify_debug_access(credentials=cred, request=_Req())
    assert exc.value.status_code == 401


def test_admin_api_key_still_works(secret, monkeypatch) -> None:
    """INNOCENCE: the pre-existing API-key path must keep working."""
    from backend.app.routers.debug import verify_debug_access

    s = _settings()
    monkeypatch.setattr(s, "admin_api_key", "super-secret-admin-key", raising=False)
    cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials="super-secret-admin-key")
    assert verify_debug_access(credentials=cred, request=_Req()) is True
