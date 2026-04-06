"""Tests for hardened JWT authentication — S03 Sprint 1."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from jose import jwt as jose_jwt


class TestSecurityConfig:
    """Test new security configuration fields."""

    def test_jwt_enforce_expiry_defaults_to_false(self):
        """JWT_ENFORCE_EXPIRY should default to False for safe rollout."""
        from backend.app.core.config import settings

        assert hasattr(settings, "jwt_enforce_expiry")
        assert settings.jwt_enforce_expiry is False

    def test_jwt_access_token_expire_hours_is_one(self):
        """Access token expiry should be 1 hour (down from 24)."""
        from backend.app.core.config import settings

        assert settings.jwt_access_token_expire_hours == 1


class TestTokenCreation:
    """Test that tokens include jti and type claims."""

    def test_access_token_has_jti(self):
        """Tokens must include a unique jti claim for revocation support."""
        from backend.app.routers.auth import create_access_token
        from backend.app.core.config import settings

        token = create_access_token(
            data={"sub": "user-1", "email": "test@balizero.com", "role": "admin"},
            expires_delta=timedelta(hours=1),
        )
        payload = jose_jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        assert "jti" in payload
        uuid.UUID(payload["jti"])

    def test_access_token_has_type_claim(self):
        """Tokens must include type=access claim."""
        from backend.app.routers.auth import create_access_token
        from backend.app.core.config import settings

        token = create_access_token(
            data={"sub": "user-1", "email": "test@balizero.com", "role": "admin"},
            expires_delta=timedelta(hours=1),
        )
        payload = jose_jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        assert payload.get("type") == "access"

    def test_access_token_has_iat(self):
        """Tokens must include iat (issued-at) claim."""
        from backend.app.routers.auth import create_access_token
        from backend.app.core.config import settings

        token = create_access_token(
            data={"sub": "user-1", "email": "test@balizero.com", "role": "admin"},
            expires_delta=timedelta(hours=1),
        )
        payload = jose_jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        assert "iat" in payload
