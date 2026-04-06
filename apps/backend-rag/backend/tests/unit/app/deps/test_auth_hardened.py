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
