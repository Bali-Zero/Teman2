"""Tests for DB-backed API key resolution — S03 Sprint 1."""

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestAPIKeyDBResolution:
    """Test hybrid API key resolution: Redis -> DB -> legacy fallback."""

    def _hash_key(self, key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def test_legacy_role_inference_still_works(self):
        """Legacy name-based role inference continues to work as fallback."""
        from backend.app.services.api_key_auth import APIKeyAuth

        auth = APIKeyAuth()
        result = auth.validate_api_key("test_api_key_1")
        assert result is not None
        assert result["role"] == "user"

    def test_legacy_admin_inference_from_name(self):
        """Keys with 'admin' in name get admin role (legacy behavior)."""
        from backend.app.services.api_key_auth import APIKeyAuth

        auth = APIKeyAuth()
        auth.valid_keys["my_admin_key"] = {
            "role": "admin",
            "permissions": ["*"],
            "created_at": "2026-01-01T00:00:00Z",
            "description": "test",
        }
        auth.key_stats["my_admin_key"] = {"usage_count": 0, "last_used": None}

        result = auth.validate_api_key("my_admin_key")
        assert result["role"] == "admin"

    @pytest.mark.asyncio
    async def test_db_resolution_overrides_legacy(self):
        """DB record should override legacy name-based inference."""
        from backend.app.services.api_key_auth import APIKeyAuth

        auth = APIKeyAuth()

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "role": "readonly",
            "permissions": ["read"],
            "is_active": True,
        })

        result = await auth.resolve_role_from_db("test_api_key_1", mock_conn)
        assert result is not None
        assert result["role"] == "readonly"

    @pytest.mark.asyncio
    async def test_db_resolution_returns_none_when_not_found(self):
        """DB resolution returns None when key not in database."""
        from backend.app.services.api_key_auth import APIKeyAuth

        auth = APIKeyAuth()

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await auth.resolve_role_from_db("unknown_key", mock_conn)
        assert result is None

    @pytest.mark.asyncio
    async def test_auto_migrate_writes_to_db(self):
        """Auto-migration should insert a record into api_key_records."""
        from backend.app.services.api_key_auth import APIKeyAuth

        auth = APIKeyAuth()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        await auth.auto_migrate_key(
            "test_api_key_1", "user", ["read"], mock_conn
        )

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "INSERT INTO api_key_records" in call_args[0][0]
        assert call_args[0][2] == "migrated_test_api"  # first 8 chars of key as name

    @pytest.mark.asyncio
    async def test_enhanced_validation_uses_db_first(self):
        """Enhanced validation should try DB before legacy fallback."""
        from backend.app.services.api_key_auth import APIKeyAuth

        auth = APIKeyAuth()

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "role": "readonly",
            "permissions": ["read"],
            "is_active": True,
        })
        mock_conn.execute = AsyncMock()

        result = await auth.validate_api_key_enhanced("test_api_key_1", mock_conn)
        assert result is not None
        assert result["role"] == "readonly"  # DB role, not legacy name-based

    @pytest.mark.asyncio
    async def test_enhanced_validation_falls_back_to_legacy(self):
        """Enhanced validation falls back to legacy when DB returns nothing."""
        from backend.app.services.api_key_auth import APIKeyAuth

        auth = APIKeyAuth()

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()

        result = await auth.validate_api_key_enhanced("test_api_key_1", mock_conn)
        assert result is not None
        assert result["role"] == "user"  # legacy name-based role

    @pytest.mark.asyncio
    async def test_enhanced_validation_auto_migrates_on_fallback(self):
        """Enhanced validation triggers auto-migration when falling back to legacy."""
        from backend.app.services.api_key_auth import APIKeyAuth

        auth = APIKeyAuth()

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()

        await auth.validate_api_key_enhanced("test_api_key_1", mock_conn)

        # auto_migrate_key should have been called
        assert mock_conn.execute.call_count >= 1
        call_sql = mock_conn.execute.call_args[0][0]
        assert "INSERT INTO api_key_records" in call_sql

    @pytest.mark.asyncio
    async def test_enhanced_validation_works_without_conn(self):
        """Enhanced validation works without DB connection (pure legacy)."""
        from backend.app.services.api_key_auth import APIKeyAuth

        auth = APIKeyAuth()
        result = await auth.validate_api_key_enhanced("test_api_key_1", conn=None)
        assert result is not None
        assert result["role"] == "user"  # legacy path
