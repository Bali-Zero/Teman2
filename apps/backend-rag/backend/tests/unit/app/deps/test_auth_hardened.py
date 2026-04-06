"""Tests for hardened JWT authentication — S03 Sprint 1."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
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


class TestJWTExpiryValidation:
    """Test JWT expiry enforcement in get_current_user."""

    def _make_token(self, exp_delta: timedelta, secret: str | None = None) -> str:
        """Helper: create a JWT with specific expiry."""
        if secret is None:
            from backend.app.core.config import settings
            secret = settings.jwt_secret_key
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-1",
            "email": "test@balizero.com",
            "role": "admin",
            "exp": now + exp_delta,
            "iat": now,
            "jti": "test-jti-001",
            "type": "access",
        }
        return jose_jwt.encode(payload, secret, algorithm="HS256")

    def _make_request(self) -> MagicMock:
        """Helper: create mock request without user in state."""
        request = MagicMock()
        request.state = MagicMock(spec=[])  # no 'user' attribute
        return request

    def _make_credentials(self, token: str) -> MagicMock:
        """Helper: create mock HTTPAuthorizationCredentials."""
        creds = MagicMock()
        creds.credentials = token
        return creds

    def _get_secret(self) -> str:
        from backend.app.core.config import settings
        return settings.jwt_secret_key

    def test_valid_token_passes(self):
        """A non-expired token should pass validation."""
        from backend.app.deps.auth import get_current_user

        token = self._make_token(exp_delta=timedelta(hours=1))
        request = self._make_request()
        creds = self._make_credentials(token)

        user = get_current_user(request, creds)
        assert user["email"] == "test@balizero.com"

    def test_expired_token_audit_mode_logs_warning(self):
        """When jwt_enforce_expiry=False, expired tokens pass but flag _warn_expired."""
        from backend.app.deps.auth import get_current_user

        token = self._make_token(exp_delta=timedelta(hours=-1))
        request = self._make_request()
        creds = self._make_credentials(token)
        real_secret = self._get_secret()

        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.jwt_secret_key = real_secret
            mock_settings.jwt_enforce_expiry = False

            user = get_current_user(request, creds)
            assert user["email"] == "test@balizero.com"
            assert user.get("_warn_expired") is True

    def test_expired_token_enforce_mode_raises_401(self):
        """When jwt_enforce_expiry=True, expired tokens raise 401."""
        from backend.app.deps.auth import get_current_user

        token = self._make_token(exp_delta=timedelta(hours=-1))
        request = self._make_request()
        creds = self._make_credentials(token)
        real_secret = self._get_secret()

        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.jwt_secret_key = real_secret
            mock_settings.jwt_enforce_expiry = True

            with pytest.raises(HTTPException) as exc_info:
                get_current_user(request, creds)
            assert exc_info.value.status_code == 401


class TestValidationModuleExpiry:
    """Test JWT expiry in auth/validation.py (used by HybridAuthMiddleware)."""

    def _make_token(self, exp_delta: timedelta) -> str:
        from backend.app.core.config import settings
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-1",
            "email": "test@balizero.com",
            "role": "admin",
            "exp": now + exp_delta,
            "iat": now,
            "jti": "test-jti-002",
            "type": "access",
        }
        return jose_jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")

    def _get_secret(self) -> str:
        from backend.app.core.config import settings
        return settings.jwt_secret_key

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        from backend.app.auth.validation import validate_auth_token
        token = self._make_token(exp_delta=timedelta(hours=1))
        result = await validate_auth_token(token)
        assert result is not None
        assert result["email"] == "test@balizero.com"

    @pytest.mark.asyncio
    async def test_expired_token_audit_mode_returns_user_with_flag(self):
        from backend.app.auth.validation import validate_auth_token
        token = self._make_token(exp_delta=timedelta(hours=-1))
        real_secret = self._get_secret()
        with patch("backend.app.auth.validation.settings") as mock_settings:
            mock_settings.jwt_secret_key = real_secret
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.jwt_enforce_expiry = False
            result = await validate_auth_token(token)
            assert result is not None
            assert result.get("_warn_expired") is True

    @pytest.mark.asyncio
    async def test_expired_token_enforce_mode_returns_none(self):
        from backend.app.auth.validation import validate_auth_token
        token = self._make_token(exp_delta=timedelta(hours=-1))
        real_secret = self._get_secret()
        with patch("backend.app.auth.validation.settings") as mock_settings:
            mock_settings.jwt_secret_key = real_secret
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.jwt_enforce_expiry = True
            result = await validate_auth_token(token)
            assert result is None


class TestDevSecretsRemoved:
    """Verify hardcoded dev secrets are not in production validators."""

    def test_jwt_validator_no_hardcoded_default(self):
        """JWT validator should not contain the old dev secret string."""
        import inspect
        from backend.app.core.config import Settings

        source = inspect.getsource(Settings.validate_jwt_secret)
        assert "zantara_dev_secret_key_change_in_production" not in source

    def test_api_keys_validator_no_hardcoded_default(self):
        """API keys validator should not contain the old dev key string."""
        import inspect
        from backend.app.core.config import Settings

        source = inspect.getsource(Settings.validate_api_keys)
        assert "dev_api_key_for_testing_only" not in source


class TestFullAuthFlowS03:
    """Integration: verify entire auth flow with S03 hardening."""

    def test_new_token_has_all_s03_claims(self):
        """Tokens created after S03 have exp, iat, jti, type claims."""
        from backend.app.routers.auth import create_access_token
        from backend.app.core.config import settings

        token = create_access_token(
            data={"sub": "u1", "email": "zero@balizero.com", "role": "admin"},
        )
        payload = jose_jwt.decode(
            token, settings.jwt_secret_key, algorithms=["HS256"],
        )

        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload
        assert payload["type"] == "access"

    def test_new_token_accepted_by_deps_auth(self):
        """Token from create_access_token passes get_current_user."""
        from backend.app.routers.auth import create_access_token
        from backend.app.deps.auth import get_current_user

        token = create_access_token(
            data={"sub": "u1", "email": "zero@balizero.com", "role": "admin"},
        )

        request = MagicMock()
        request.state = MagicMock(spec=[])
        creds = MagicMock()
        creds.credentials = token

        user = get_current_user(request, creds)
        assert user["email"] == "zero@balizero.com"
        assert user["role"] == "admin"
        assert user.get("_warn_expired") is None  # not expired

    def test_api_key_legacy_still_works(self):
        """Legacy API key validation unchanged by S03."""
        from backend.app.services.api_key_auth import APIKeyAuth

        auth = APIKeyAuth()
        result = auth.validate_api_key("test_api_key_1")
        assert result is not None
        assert result["auth_method"] == "api_key"


class TestSprint2Config:
    """Test Sprint 2 config fields."""

    def test_enable_token_revocation_defaults_to_false(self):
        """Token revocation should be off by default for safe rollout."""
        from backend.app.core.config import settings

        assert hasattr(settings, "enable_token_revocation")
        assert settings.enable_token_revocation is False


class TestTokenRevocationInAuth:
    """Test revocation config is accessible from auth deps."""

    def _make_token(self, jti: str = "test-jti-revoke") -> str:
        from backend.app.core.config import settings
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-1",
            "email": "test@balizero.com",
            "role": "admin",
            "exp": now + timedelta(hours=1),
            "iat": now,
            "jti": jti,
            "type": "access",
        }
        return jose_jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")

    def _make_request(self) -> MagicMock:
        request = MagicMock()
        request.state = MagicMock(spec=[])
        return request

    def _make_credentials(self, token: str) -> MagicMock:
        creds = MagicMock()
        creds.credentials = token
        return creds

    def test_revocation_disabled_passes_normally(self):
        """When enable_token_revocation=False, auth works normally."""
        from backend.app.deps.auth import get_current_user

        token = self._make_token()
        request = self._make_request()
        creds = self._make_credentials(token)

        user = get_current_user(request, creds)
        assert user["email"] == "test@balizero.com"


class TestLogoutRevocation:
    """Test that revoke-all endpoint exists."""

    def test_revoke_all_endpoint_exists(self):
        """The /api/auth/revoke-all endpoint should exist."""
        from backend.app.routers.auth import router

        paths = [route.path for route in router.routes]
        assert "/api/auth/revoke-all" in paths


class TestSprint3QuickFixes:
    """S03-S3: Quick fixes from code review."""

    def test_grace_period_removed(self):
        """jwt_grace_period_days should no longer exist in config."""
        from backend.app.core.config import settings
        assert not hasattr(settings, "jwt_grace_period_days")

    def test_scraper_key_no_hardcoded_default(self):
        """intel_scraper_api_key should not default to dev_scraper_key."""
        import inspect
        from backend.app.core.config import Settings
        source = inspect.getsource(Settings)
        assert 'default="dev_scraper_key"' not in source

    def test_identity_service_no_residual_secret(self):
        """identity/service.py should not contain known weak secret strings."""
        import inspect
        from backend.app.modules.identity.service import IdentityService
        source = inspect.getsource(IdentityService.__init__)
        assert "zantara_default_secret_key_2025" not in source

    def test_type_claim_validated_for_new_tokens(self):
        """Tokens with type=access should pass."""
        from backend.app.deps.auth import get_current_user
        from backend.app.core.config import settings
        now = datetime.now(timezone.utc)
        token = jose_jwt.encode(
            {"sub": "u1", "email": "t@b.com", "role": "admin",
             "exp": now + timedelta(hours=1), "type": "access"},
            settings.jwt_secret_key, algorithm="HS256",
        )
        request = MagicMock(); request.state = MagicMock(spec=[])
        creds = MagicMock(); creds.credentials = token
        user = get_current_user(request, creds)
        assert user["email"] == "t@b.com"

    def test_type_claim_rejects_refresh_tokens(self):
        """Tokens with type=refresh should be rejected."""
        from backend.app.deps.auth import get_current_user
        from backend.app.core.config import settings
        from fastapi import HTTPException
        now = datetime.now(timezone.utc)
        token = jose_jwt.encode(
            {"sub": "u1", "email": "t@b.com", "role": "admin",
             "exp": now + timedelta(hours=1), "type": "refresh"},
            settings.jwt_secret_key, algorithm="HS256",
        )
        request = MagicMock(); request.state = MagicMock(spec=[])
        creds = MagicMock(); creds.credentials = token
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request, creds)
        assert exc_info.value.status_code == 401

    def test_type_claim_absent_passes_backward_compat(self):
        """Pre-S03 tokens without type claim should still pass."""
        from backend.app.deps.auth import get_current_user
        from backend.app.core.config import settings
        now = datetime.now(timezone.utc)
        token = jose_jwt.encode(
            {"sub": "u1", "email": "t@b.com", "role": "admin",
             "exp": now + timedelta(hours=1)},
            settings.jwt_secret_key, algorithm="HS256",
        )
        request = MagicMock(); request.state = MagicMock(spec=[])
        creds = MagicMock(); creds.credentials = token
        user = get_current_user(request, creds)
        assert user["email"] == "t@b.com"
