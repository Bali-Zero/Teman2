"""Real-path coverage for invalid JWT handling at the five auth call sites."""

from __future__ import annotations

import secrets
import time
from types import SimpleNamespace

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.validation import validate_auth_token
from backend.app.core.config import settings
from backend.app.dependencies import get_database_pool
from backend.app.deps import auth as deps_auth
from backend.app.routers import auth as router_auth
from backend.services.garuda_portal import staff_auth
from backend.services.garuda_portal.staff_auth import _decode_staff_jwt

INVALID_SHAPES = (
    "forged_signature",
    "expired",
    "exp_absent",
    "exp_null",
    "garbage",
    "wrong_algorithm",
    "alg_none",
)


@pytest.fixture
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    """Install one generated test key everywhere the real call sites read it."""
    assert settings.jwt_algorithm == "HS256"
    secret = secrets.token_urlsafe(48)
    monkeypatch.setattr(settings, "jwt_secret_key", secret)
    monkeypatch.setattr(settings, "enable_token_revocation", True)
    monkeypatch.setattr(router_auth, "JWT_SECRET_KEY", secret)
    monkeypatch.setattr(router_auth, "JWT_ALGORITHM", settings.jwt_algorithm)
    return secret


def _token(shape: str, secret: str) -> str:
    now = int(time.time())
    claims = {
        "sub": "synthetic-user",
        "email": "synthetic@example.invalid",
        "role": "admin",
        "type": "access",
        "iat": now,
        "exp": now + 3600,
        "jti": "synthetic-jti",
    }

    if shape == "forged_signature":
        return jwt.encode(claims, secrets.token_urlsafe(48), algorithm="HS256")
    if shape == "expired":
        claims["exp"] = now - 60
    elif shape == "exp_absent":
        claims.pop("exp")
    elif shape == "exp_null":
        claims["exp"] = None
    elif shape == "garbage":
        return "not-a-jwt"
    elif shape == "wrong_algorithm":
        return jwt.encode(claims, secret, algorithm="HS512")
    elif shape == "alg_none":
        return jwt.encode(claims, key="", algorithm="none")
    return jwt.encode(claims, secret, algorithm="HS256")


def _router_client(*, bypass_auth_dependency: bool = False) -> TestClient:
    app = FastAPI()
    app.include_router(router_auth.router)
    pool = SimpleNamespace(acquire=lambda: None)
    app.dependency_overrides[get_database_pool] = lambda: pool
    if bypass_auth_dependency:
        app.dependency_overrides[router_auth.get_current_user] = lambda: {
            "id": "synthetic-user",
            "email": "synthetic@example.invalid",
            "role": "admin",
        }
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("shape", INVALID_SHAPES)
def test_router_get_current_user_maps_invalid_jwt_to_401(shape: str, jwt_secret: str) -> None:
    response = _router_client().get(
        "/api/auth/profile",
        headers={"Authorization": f"Bearer {_token(shape, jwt_secret)}"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("shape", INVALID_SHAPES)
def test_deps_get_current_user_maps_invalid_jwt_to_401(shape: str, jwt_secret: str) -> None:
    app = FastAPI()

    @app.get("/guarded")
    def guarded(user=Depends(deps_auth.get_current_user)):
        return user

    response = TestClient(app, raise_server_exceptions=False).get(
        "/guarded",
        headers={"Authorization": f"Bearer {_token(shape, jwt_secret)}"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("shape", INVALID_SHAPES)
def test_logout_maps_invalid_jwt_to_401(shape: str, jwt_secret: str) -> None:
    response = _router_client(bypass_auth_dependency=True).post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {_token(shape, jwt_secret)}"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("shape", INVALID_SHAPES)
@pytest.mark.asyncio
async def test_validation_returns_none_for_invalid_jwt(shape: str, jwt_secret: str) -> None:
    assert await validate_auth_token(_token(shape, jwt_secret)) is None


@pytest.fixture
def staff_revocation_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a reachable store the decoder fails closed to None after decoding,
    which would hide a decoder that accepted a bad token. Pin "not revoked"."""
    monkeypatch.setattr(staff_auth, "is_session_revoked_sync", lambda payload: False)


@pytest.mark.parametrize("shape", INVALID_SHAPES)
def test_staff_decoder_returns_none_for_invalid_jwt(
    shape: str, jwt_secret: str, staff_revocation_reachable: None
) -> None:
    assert _decode_staff_jwt(_token(shape, jwt_secret)) is None


def test_staff_decoder_accepts_the_valid_control_token(
    jwt_secret: str, staff_revocation_reachable: None
) -> None:
    payload = _decode_staff_jwt(_token("valid", jwt_secret))
    assert payload is not None
    assert payload["sub"] == "synthetic-user"
