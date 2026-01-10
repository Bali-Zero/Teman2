from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from jose import jwt

from backend.app.modules.identity.models import User
from backend.app.modules.identity.service import IdentityService
from tests.conftest import create_mock_settings


class _DummyConn:
    def __init__(self, row=None, error=None):
        self.row = row
        self.error = error
        self.executed = []
        self.closed = False

    async def fetchrow(self, query, email):
        if self.error:
            raise self.error
        return self.row

    async def execute(self, query, *args):
        self.executed.append((query.strip(), args))

    async def close(self):
        self.closed = True


def _make_service(monkeypatch, db_url="postgres://test", jwt_secret="secret", jwt_alg="HS256"):
    # Ensure jwt_secret is at least 32 characters
    if len(jwt_secret) < 32:
        jwt_secret = jwt_secret + "_" * (32 - len(jwt_secret))
    mock_settings = create_mock_settings(
        database_url=db_url,
        jwt_secret_key=jwt_secret,
        jwt_algorithm=jwt_alg,
    )
    monkeypatch.setattr("backend.app.modules.identity.service.settings", mock_settings)
    return IdentityService()


def test_init_warns_on_default_secret(monkeypatch, caplog):
    mock_settings = create_mock_settings(
        database_url="db",
        jwt_secret_key="zantara_default_secret_key_2025_change_in_production",
        jwt_algorithm="HS256",
    )
    monkeypatch.setattr("backend.app.modules.identity.service.settings", mock_settings)

    IdentityService()

    assert "default or empty JWT secret key" in caplog.text


def test_password_hash_and_verify(monkeypatch):
    service = _make_service(monkeypatch)
    hashed = service.get_password_hash("1234")
    assert service.verify_password("1234", hashed) is True
    assert service.verify_password("0000", hashed) is False


def test_verify_password_invalid_hash(monkeypatch, caplog):
    service = _make_service(monkeypatch)
    assert service.verify_password("1234", "not-a-hash") is False
    assert "Bcrypt verification failed" in caplog.text


@pytest.mark.asyncio
async def test_get_db_connection_requires_url(monkeypatch):
    service = _make_service(monkeypatch, db_url=None)
    with pytest.raises(ValueError, match="DATABASE_URL not configured"):
        await service.get_db_connection()


@pytest.mark.asyncio
async def test_authenticate_user_invalid_pin(monkeypatch, caplog):
    service = _make_service(monkeypatch)

    result = await service.authenticate_user("user@example.com", "12")

    assert result is None
    assert "Invalid PIN format" in caplog.text


@pytest.mark.asyncio
async def test_authenticate_user_not_found(monkeypatch):
    service = _make_service(monkeypatch)
    dummy_conn = _DummyConn(row=None)
    monkeypatch.setattr(
        "backend.app.modules.identity.service.asyncpg.connect", AsyncMock(return_value=dummy_conn)
    )

    result = await service.authenticate_user("user@example.com", "1234")

    assert result is None
    assert dummy_conn.closed is True


@pytest.mark.asyncio
async def test_authenticate_user_locked(monkeypatch):
    service = _make_service(monkeypatch)
    row = {
        "id": "1",
        "name": "User",
        "email": "user@example.com",
        "pin_hash": service.get_password_hash("1234"),
        "role": "CEO",
        "department": "IT",
        "language": "en",
        "personalized_response": True,
        "is_active": True,
        "last_login": None,
        "failed_attempts": 0,
        "locked_until": datetime.now(timezone.utc) + timedelta(minutes=5),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    dummy_conn = _DummyConn(row=row)
    monkeypatch.setattr(
        "backend.app.modules.identity.service.asyncpg.connect", AsyncMock(return_value=dummy_conn)
    )

    result = await service.authenticate_user("user@example.com", "1234")

    assert result is None
    assert dummy_conn.closed is True


@pytest.mark.asyncio
async def test_authenticate_user_invalid_pin_increments(monkeypatch):
    service = _make_service(monkeypatch)
    row = {
        "id": "1",
        "name": "User",
        "email": "user@example.com",
        "pin_hash": service.get_password_hash("1234"),
        "role": "CEO",
        "department": "IT",
        "language": "en",
        "personalized_response": True,
        "is_active": True,
        "last_login": None,
        "failed_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    dummy_conn = _DummyConn(row=row)
    monkeypatch.setattr(
        "backend.app.modules.identity.service.asyncpg.connect", AsyncMock(return_value=dummy_conn)
    )
    service.verify_password = lambda *_args, **_kwargs: False

    result = await service.authenticate_user("user@example.com", "1234")

    assert result is None
    assert any("failed_attempts" in query for query, _ in dummy_conn.executed)


@pytest.mark.asyncio
async def test_authenticate_user_success(monkeypatch):
    service = _make_service(monkeypatch)
    row = {
        "id": "1",
        "name": "User",
        "email": "user@example.com",
        "pin_hash": service.get_password_hash("1234"),
        "role": "CEO",
        "department": "IT",
        "language": None,
        "personalized_response": None,
        "is_active": True,
        "last_login": None,
        "failed_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    dummy_conn = _DummyConn(row=row)
    monkeypatch.setattr(
        "backend.app.modules.identity.service.asyncpg.connect", AsyncMock(return_value=dummy_conn)
    )
    service.verify_password = lambda *_args, **_kwargs: True

    result = await service.authenticate_user("user@example.com", "1234")

    assert isinstance(result, User)
    assert result.email == "user@example.com"
    assert any("failed_attempts = 0" in query for query, _ in dummy_conn.executed)


@pytest.mark.asyncio
async def test_authenticate_user_exception(monkeypatch):
    service = _make_service(monkeypatch)
    dummy_conn = _DummyConn(error=RuntimeError("db error"))
    monkeypatch.setattr(
        "backend.app.modules.identity.service.asyncpg.connect", AsyncMock(return_value=dummy_conn)
    )

    result = await service.authenticate_user("user@example.com", "1234")

    assert result is None
    assert dummy_conn.closed is True


def test_create_access_token(monkeypatch):
    jwt_secret = "secret_at_least_32_chars_long_"
    service = _make_service(monkeypatch, jwt_secret=jwt_secret, jwt_alg="HS256")
    user = User(
        id="u1",
        name="User",
        email="user@example.com",
        pin_hash="hash",
        role="CEO",
        department="IT",
        language="en",
        personalized_response=False,
        is_active=True,
        last_login=None,
        failed_attempts=0,
        locked_until=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    token = service.create_access_token(user, session_id="s1")
    # Get the actual secret from the mocked settings module
    from backend.app.modules.identity import service as identity_service
    actual_secret = identity_service.settings.jwt_secret_key
    payload = jwt.decode(token, actual_secret, algorithms=["HS256"])

    assert payload["sub"] == "u1"
    assert payload["sessionId"] == "s1"


def test_permissions_for_role(monkeypatch):
    service = _make_service(monkeypatch)

    assert "admin" in service.get_permissions_for_role("CEO")
    assert service.get_permissions_for_role("unknown") == ["clients"]
