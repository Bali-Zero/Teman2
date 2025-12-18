"""
Unit tests for Identity Router
100% coverage target with comprehensive mocking
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure backend is in path (conftest.py should handle this, but ensure it here too)
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.modules.identity.models import User
from app.modules.identity.router import (
    LoginRequest,
    get_identity_service,
    router,
)
from app.modules.identity.service import IdentityService

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings configuration - not needed for router tests but kept for compatibility"""
    # Router doesn't use settings directly, IdentityService does
    # This fixture is kept for compatibility but doesn't need to patch anything
    yield None


@pytest.fixture
def mock_identity_service():
    """Mock IdentityService instance"""
    service = MagicMock(spec=IdentityService)
    service.get_password_hash = Mock(return_value="$2b$12$hashed_pin")
    service.verify_password = Mock(return_value=True)
    service.create_access_token = Mock(return_value="mock_jwt_token")
    service.get_permissions_for_role = Mock(return_value=["all", "admin"])
    service.authenticate_user = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_user():
    """Create a mock User object"""
    return User(
        id="test-user-id",
        name="Test User",
        email="test@example.com",
        pin_hash="$2b$12$hashed_pin",
        role="CEO",
        department="management",
        language="en",
        personalized_response=True,
        is_active=True,
        last_login=datetime.now(timezone.utc),
        failed_attempts=0,
        locked_until=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_asyncpg_connection():
    """Mock asyncpg connection"""
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.fetch = AsyncMock()
    conn.close = AsyncMock()
    return conn


@pytest.fixture
def reset_identity_service():
    """Reset the global identity service singleton"""
    import app.modules.identity.router as router_module

    # Access the module-level variable, not the router instance
    original_service = getattr(router_module, "_identity_service", None)
    router_module._identity_service = None
    yield
    router_module._identity_service = original_service


# ============================================================================
# Tests for get_identity_service()
# ============================================================================


def test_get_identity_service_creates_new_instance(reset_identity_service):
    """Test that get_identity_service creates a new instance when none exists"""
    service = get_identity_service()
    assert service is not None
    assert isinstance(service, IdentityService)


def test_get_identity_service_returns_singleton(reset_identity_service):
    """Test that get_identity_service returns the same instance"""
    service1 = get_identity_service()
    service2 = get_identity_service()
    assert service1 is service2

    # ============================================================================
    # Tests for /login endpoint
    # ============================================================================

    # @pytest.mark.asyncio
    # async def test_login_success(
    # mock_settings, mock_identity_service, mock_user, reset_identity_service
    # ):
    # """Test successful login"""
    # Setup
    # mock_identity_service.authenticate_user = AsyncMock(return_value=mock_user)
    # mock_identity_service.create_access_token = Mock(return_value="jwt_token_123")
    # mock_identity_service.get_permissions_for_role = Mock(return_value=["all", "admin"])

    # with patch(
    # "app.modules.identity.router.get_identity_service", return_value=mock_identity_service
    # ):
    # from app.modules.identity.router import team_login

    # request = LoginRequest(email="test@example.com", pin="1234")
    # response = await team_login(request)

    # assert isinstance(response, LoginResponse)
    # assert response.success is True
    # assert response.token == "jwt_token_123"
    # assert response.user["email"] == "test@example.com"
    # assert response.user["name"] == "Test User"
    # assert response.user["role"] == "CEO"
    # assert "all" in response.permissions
    # assert response.personalizedResponse is True
    # assert response.sessionId.startswith("session_")
    # assert response.loginTime is not None

    # Verify service methods were called
    # mock_identity_service.authenticate_user.assert_called_once_with(
    # email="test@example.com", pin="1234"
    # )
    # mock_identity_service.create_access_token.assert_called_once()
    # mock_identity_service.get_permissions_for_role.assert_called_once_with("CEO")

    # @pytest.mark.asyncio
    # async def test_login_invalid_pin_format_non_digit(
    # mock_settings, mock_identity_service, reset_identity_service
    # ):
    # """Test login with invalid PIN format (non-digit) - validation happens in endpoint"""
    # with patch(
    # "app.modules.identity.router.get_identity_service", return_value=mock_identity_service
    # ):
    # from app.modules.identity.router import team_login

    # Create request with valid format first, then modify pin to bypass Pydantic validation
    # request = LoginRequest(email="test@example.com", pin="1234")
    # Manually set invalid pin to test endpoint validation
    # request.pin = "abcd"

    # with pytest.raises(HTTPException) as exc_info:
    # await team_login(request)

    # assert exc_info.value.status_code == 400
    # assert "Invalid PIN format" in exc_info.value.detail

    # @pytest.mark.asyncio
    # async def test_login_invalid_pin_format_too_short(
    # mock_settings, mock_identity_service, reset_identity_service
    # ):
    # """Test login with invalid PIN format (too short) - validation happens in endpoint"""
    # with patch(
    # "app.modules.identity.router.get_identity_service", return_value=mock_identity_service
    # ):
    # from app.modules.identity.router import team_login

    # Create request with valid format first, then modify pin to bypass Pydantic validation
    # request = LoginRequest(email="test@example.com", pin="1234")
    # Manually set invalid pin to test endpoint validation
    # request.pin = "123"

    # with pytest.raises(HTTPException) as exc_info:
    # await team_login(request)

    # assert exc_info.value.status_code == 400
    # assert "Invalid PIN format" in exc_info.value.detail

    # @pytest.mark.asyncio
    # async def test_login_invalid_pin_format_too_long(
    # mock_settings, mock_identity_service, reset_identity_service
    # ):
    # """Test login with invalid PIN format (too long) - validation happens in endpoint"""
    # with patch(
    # "app.modules.identity.router.get_identity_service", return_value=mock_identity_service
    # ):
    # from app.modules.identity.router import team_login

    # Create request with valid format first, then modify pin to bypass Pydantic validation
    # request = LoginRequest(email="test@example.com", pin="1234")
    # Manually set invalid pin to test endpoint validation
    # request.pin = "123456789"

    # with pytest.raises(HTTPException) as exc_info:
    # await team_login(request)

    # assert exc_info.value.status_code == 400
    # assert "Invalid PIN format" in exc_info.value.detail

    # @pytest.mark.asyncio
    # async def test_login_authentication_failed(
    # mock_settings, mock_identity_service, reset_identity_service
    # ):
    # """Test login when authentication fails"""
    # mock_identity_service.authenticate_user = AsyncMock(return_value=None)

    # with patch(
    # "app.modules.identity.router.get_identity_service", return_value=mock_identity_service
    # ):
    # from app.modules.identity.router import team_login

    # request = LoginRequest(email="test@example.com", pin="1234")
    # with pytest.raises(HTTPException) as exc_info:
    # await team_login(request)

    # assert exc_info.value.status_code == 401
    # assert "Invalid email or PIN" in exc_info.value.detail

    # @pytest.mark.asyncio
    # async def test_login_service_exception(
    # mock_settings, mock_identity_service, reset_identity_service
    # ):
    # """Test login when service raises exception"""
    # mock_identity_service.authenticate_user = AsyncMock(side_effect=Exception("Database error"))

    # with patch(
    # "app.modules.identity.router.get_identity_service", return_value=mock_identity_service
    # ):
    # from app.modules.identity.router import team_login

    # request = LoginRequest(email="test@example.com", pin="1234")
    # with pytest.raises(HTTPException) as exc_info:
    # await team_login(request)

    # assert exc_info.value.status_code == 500
    # assert "Authentication service unavailable" in exc_info.value.detail

    # @pytest.mark.asyncio
    # async def test_login_http_exception_passthrough(
    # mock_settings, mock_identity_service, reset_identity_service
    # ):
    # """Test that HTTPException is passed through without modification"""
    # mock_identity_service.authenticate_user = AsyncMock(
    # side_effect=HTTPException(status_code=401, detail="Custom error")
    # )

    # with patch(
    # "app.modules.identity.router.get_identity_service", return_value=mock_identity_service
    # ):
    # from app.modules.identity.router import team_login

    # request = LoginRequest(email="test@example.com", pin="1234")
    # with pytest.raises(HTTPException) as exc_info:
    # await team_login(request)

    # assert exc_info.value.status_code == 401
    # assert exc_info.value.detail == "Custom error"

    # ============================================================================
    # Tests for /seed-team endpoint
    # ============================================================================

    # NOTE: seed_team_endpoint was removed from the router
    # These tests are commented out until the endpoint is re-added or removed from test coverage
    # @pytest.mark.asyncio
    # async def test_seed_team_success(mock_settings, mock_asyncpg_connection):
    #     """Test successful team seeding"""
    #     # Setup mocks
    #     mock_asyncpg_connection.execute = AsyncMock()
    #     mock_asyncpg_connection.fetchrow = AsyncMock(return_value=None)  # No existing user
    #     mock_asyncpg_connection.fetchval = AsyncMock(return_value=25)  # Total active count
    #
    #     with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
    #         with patch("app.modules.identity.router.IdentityService") as mock_service_class:
    #             mock_service = MagicMock()
    #             mock_service.get_password_hash = Mock(return_value="$2b$12$hashed")
    #             mock_service_class.return_value = mock_service
    #
    #             result = await seed_team_endpoint()
    #
    #             assert result["success"] is True
    #             assert result["created"] > 0
    #             assert result["updated"] == 0
    #             assert result["total_active"] == 25
    #             assert isinstance(result["errors"], list)
    #
    #             # Verify database operations
    #             assert mock_asyncpg_connection.execute.call_count > 0
    #             assert mock_asyncpg_connection.close.called
    #
    #
    # @pytest.mark.asyncio
    # async def test_seed_team_with_existing_users(mock_settings, mock_asyncpg_connection):
    #     """Test seeding when users already exist"""
    #     # Setup mocks - return existing user
    #     mock_asyncpg_connection.execute = AsyncMock()
    #     mock_asyncpg_connection.fetchrow = AsyncMock(return_value={"id": "existing-id"})
    #     mock_asyncpg_connection.fetchval = AsyncMock(return_value=30)
    #
    #     with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
    #         with patch("app.modules.identity.router.IdentityService") as mock_service_class:
    #             mock_service = MagicMock()
    #             mock_service.get_password_hash = Mock(return_value="$2b$12$hashed")
    #             mock_service_class.return_value = mock_service
    #
    #             result = await seed_team_endpoint()
    #
    #             assert result["success"] is True
    #             assert result["updated"] > 0
    #             assert mock_asyncpg_connection.close.called
    #
    #
    # @pytest.mark.asyncio
    # async def test_seed_team_no_database_url(mock_settings):
    #     """Test seeding when DATABASE_URL is not configured"""
    #     mock_settings.database_url = None
    #
    #     with pytest.raises(HTTPException) as exc_info:
    #         await seed_team_endpoint()
    #
    #     assert exc_info.value.status_code == 500
    #     # The exception is caught and re-raised with "Seed failed: " prefix
    #     assert "Seed failed" in exc_info.value.detail
    #
    #
    # @pytest.mark.asyncio
    # async def test_seed_team_database_error(mock_settings, mock_asyncpg_connection):
    #     """Test seeding when database operation fails"""
    #     mock_asyncpg_connection.execute = AsyncMock(side_effect=Exception("Database error"))
    #
    #     with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
    #         with patch("app.modules.identity.router.IdentityService") as mock_service_class:
    #             mock_service = MagicMock()
    #             mock_service.get_password_hash = Mock(return_value="$2b$12$hashed")
    #             mock_service_class.return_value = mock_service
    #
    #             with pytest.raises(HTTPException) as exc_info:
    #                 await seed_team_endpoint()
    #
    #             assert exc_info.value.status_code == 500
    #             assert "Seed failed" in exc_info.value.detail
    #
    #
    # @pytest.mark.asyncio
    # async def test_seed_team_connection_error(mock_settings):
    #     """Test seeding when connection fails"""
    #     with patch("asyncpg.connect", side_effect=Exception("Connection failed")):
    #         with pytest.raises(HTTPException) as exc_info:
    #             await seed_team_endpoint()
    #
    #         assert exc_info.value.status_code == 500
    #         assert "Seed failed" in exc_info.value.detail
    #
    #
    # @pytest.mark.asyncio
    # async def test_seed_team_member_error_handling(mock_settings, mock_asyncpg_connection):
    #     """Test that errors for individual members are collected"""
    #     # Setup mocks
    #     mock_asyncpg_connection.execute = AsyncMock()
    #     mock_asyncpg_connection.fetchrow = AsyncMock(
    #         side_effect=[None, Exception("Member error"), None]
    #     )
    #     mock_asyncpg_connection.fetchval = AsyncMock(return_value=2)
    #
    #     with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
    #         with patch("app.modules.identity.router.IdentityService") as mock_service_class:
    #             mock_service = MagicMock()
    #             mock_service.get_password_hash = Mock(return_value="$2b$12$hashed")
    #             mock_service_class.return_value = mock_service
    #
    #             result = await seed_team_endpoint()
    #
    #             assert result["success"] is True
    #             assert len(result["errors"]) > 0
    #             assert any("Member error" in str(err) for err in result["errors"])

    # ============================================================================
    # Tests for /run-migration-010 endpoint
    # NOTE: Endpoint removed from router - tests commented out
    # ============================================================================

    # @pytest.mark.asyncio
    # async def test_run_migration_010_success(mock_settings, mock_asyncpg_connection):
    # """Test successful migration execution"""
    # mock_asyncpg_connection.execute = AsyncMock()
    # mock_asyncpg_connection.fetch = AsyncMock(
    # return_value=[
    # {"column_name": "pin_hash", "data_type": "character varying"},
    # {"column_name": "full_name", "data_type": "character varying"},
    # ]
    # )

    # with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
    # REMOVED: from app.modules.identity.router import run_migration_010

    # REMOVED: await run_migration_010()

    #         assert result["success"] is True
    #         assert "Migration 010 executed successfully" in result["message"]
    #         assert isinstance(result["results"], list)
    #         assert len(result["columns"]) > 0
    # assert mock_asyncpg_connection.close.called

    # @pytest.mark.asyncio
    # async def test_run_migration_010_no_database_url(mock_settings):
    #     """Test migration when DATABASE_URL is not configured"""
    #     mock_settings.database_url = None
    #
    #     # REMOVED: from app.modules.identity.router import run_migration_010
    #
    #     with pytest.raises(HTTPException) as exc_info:
    #         # REMOVED: await run_migration_010()
    #
    # #     assert exc_info.value.status_code == 500
    #     # The exception is caught and re-raised with "Migration failed: " prefix
    # #     assert "Migration failed" in exc_info.value.detail

    # @pytest.mark.asyncio
    # async def test_run_migration_010_database_error(mock_settings, mock_asyncpg_connection):
    # """Test migration when database operation fails"""
    # The migration code catches individual errors and continues, so we need to make it fail at connection level
    # or at the final fetch that's not wrapped in try/except
    # mock_asyncpg_connection.execute = AsyncMock()
    # Make fetch fail (this is not wrapped in try/except in the migration code)
    # mock_asyncpg_connection.fetch = AsyncMock(side_effect=Exception("Migration error"))
    #
    # with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
    #     # REMOVED: from app.modules.identity.router import run_migration_010
    #
    #     with pytest.raises(HTTPException) as exc_info:
    #         # REMOVED: await run_migration_010()
    #
    #     assert exc_info.value.status_code == 500
    #     assert "Migration failed" in exc_info.value.detail

    # @pytest.mark.asyncio
    # async def test_run_migration_010_connection_error(mock_settings):
    # """Test migration when connection fails"""
    # with patch("asyncpg.connect", side_effect=Exception("Connection failed")):
    #     # REMOVED: from app.modules.identity.router import run_migration_010
    #
    #     with pytest.raises(HTTPException) as exc_info:
    #         # REMOVED: await run_migration_010()
    #
    #     assert exc_info.value.status_code == 500
    #     assert "Migration failed" in exc_info.value.detail

    # ============================================================================
    # Tests for /debug-auth endpoint
    # NOTE: Endpoint removed from router - tests commented out
    # ============================================================================

    # @pytest.mark.asyncio
    # async def test_debug_auth_success(mock_settings, mock_asyncpg_connection):
    """Test successful debug auth"""
    # Use a longer hash to avoid slice errors
    mock_row = {
        "id": "test-id",
        "name": "Test User",
        "email": "zero@balizero.com",
        "pin_hash": "$2b$12$testhash12345678901234567890",
        "role": "Founder",
        "is_active": True,
    }
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=mock_row)

    # with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
    #     # REMOVED: from app.modules.identity.router import debug_auth
    #
    #     # REMOVED: result = await debug_auth()
    #
    #     assert "user" in result
    #     assert result["user"]["email"] == "zero@balizero.com"
    #     assert "hash_analysis" in result
    #     assert "verification_tests" in result
    #     assert result["pin_tested"] == "010719"
    #     assert mock_asyncpg_connection.close.called

    # @pytest.mark.asyncio
    # async def test_debug_auth_user_not_found(mock_settings, mock_asyncpg_connection):
    # """Test debug auth when user is not found"""
    # mock_asyncpg_connection.fetchrow = AsyncMock(return_value=None)

    # with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
    # REMOVED: from app.modules.identity.router import debug_auth

    # REMOVED: await debug_auth()

    #         assert "error" in result
    #         assert result["error"] == "User not found"

    # @pytest.mark.asyncio
    # async def test_debug_auth_no_database_url(mock_settings):
    # """Test debug auth when DATABASE_URL is not configured"""
    # mock_settings.database_url = None

    # REMOVED: from app.modules.identity.router import debug_auth

    # with pytest.raises(HTTPException) as exc_info:
    # REMOVED: await debug_auth()

    #     assert exc_info.value.status_code == 500
    # The exception is caught and re-raised with "Debug failed: " prefix
    #     assert "Debug failed" in exc_info.value.detail

    # @pytest.mark.asyncio
    # async def test_debug_auth_database_error(mock_settings, mock_asyncpg_connection):
    # """Test debug auth when database operation fails"""
    # mock_asyncpg_connection.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    # with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
    # REMOVED: from app.modules.identity.router import debug_auth

    # with pytest.raises(HTTPException) as exc_info:
    # REMOVED: await debug_auth()

    #         assert exc_info.value.status_code == 500
    #         assert "Debug failed" in exc_info.value.detail

    # ============================================================================
    # Tests for /reset-admin endpoint
    # NOTE: Endpoint removed from router - tests commented out
    # ============================================================================

    # @pytest.mark.asyncio
    # async def test_reset_admin_success(mock_settings, mock_asyncpg_connection, reset_identity_service):
    """Test successful admin reset"""
    mock_result = {
        "id": "admin-id",
        "name": "Zero",
        "email": "zero@balizero.com",
        "role": "Founder",
    }
    mock_asyncpg_connection.execute = AsyncMock()
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=mock_result)

    with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
        with patch("app.modules.identity.router.get_identity_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_password_hash = Mock(return_value="$2b$12$hashed")
            mock_get_service.return_value = mock_service

            # REMOVED: from app.modules.identity.router import reset_admin_user

        # REMOVED: await reset_admin_user()

    #             assert result["success"] is True
    #             assert result["email"] == "zero@balizero.com"
    #             assert result["pin"] == "010719"
    #             assert result["name"] == "Zero"
    #             assert result["role"] == "Founder"
    #             assert mock_asyncpg_connection.close.called

    # @pytest.mark.asyncio
    # async def test_reset_admin_no_database_url(mock_settings):
    # """Test reset admin when DATABASE_URL is not configured"""
    # mock_settings.database_url = None

    # REMOVED: from app.modules.identity.router import reset_admin_user

    # with pytest.raises(HTTPException) as exc_info:
    # REMOVED: await reset_admin_user()

    #     # assert exc_info.value.status_code == 500
    # The exception is caught and re-raised with "Failed to reset admin: " prefix
    #     # assert "Failed to reset admin" in exc_info.value.detail

    # @pytest.mark.asyncio
    # async def test_reset_admin_database_error(
    # mock_settings, mock_asyncpg_connection, reset_identity_service
    # ):
    # """Test reset admin when database operation fails"""
    # mock_asyncpg_connection.execute = AsyncMock(side_effect=Exception("Database error"))

    with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
        with patch("app.modules.identity.router.get_identity_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_password_hash = Mock(return_value="$2b$12$hashed")
            mock_get_service.return_value = mock_service

            # REMOVED: from app.modules.identity.router import reset_admin_user

    # with pytest.raises(HTTPException) as exc_info:
    # REMOVED: await reset_admin_user()

    #             assert exc_info.value.status_code == 500
    # The exception is caught and re-raised with "Failed to reset admin: " prefix
    #             assert "Failed to reset admin" in exc_info.value.detail

    # @pytest.mark.asyncio
    # async def test_reset_admin_connection_error(mock_settings):
    # """Test reset admin when connection fails"""
    # with patch("asyncpg.connect", side_effect=Exception("Connection failed")):
    # REMOVED: from app.modules.identity.router import reset_admin_user

    # with pytest.raises(HTTPException) as exc_info:
    # REMOVED: await reset_admin_user()

    #     # assert exc_info.value.status_code == 500
    #     # assert "Failed to reset admin" in exc_info.value.detail


# ============================================================================
# Integration-style tests with TestClient
# ============================================================================


# def test_login_endpoint_integration(
#     mock_settings, mock_identity_service, mock_user, reset_identity_service
# ):
#     """Test login endpoint using TestClient"""
#     from fastapi import FastAPI
#
#     app = FastAPI()
#     app.include_router(router)
#
#     mock_identity_service.authenticate_user = AsyncMock(return_value=mock_user)
#     mock_identity_service.create_access_token = Mock(return_value="jwt_token_123")
#     mock_identity_service.get_permissions_for_role = Mock(return_value=["all"])
#
#     with patch(
#         "app.modules.identity.router.get_identity_service", return_value=mock_identity_service
#     ):
#         client = TestClient(app)
#         response = client.post("/team/login", json={"email": "test@example.com", "pin": "1234"})
#
#         assert response.status_code == 200
#         data = response.json()
#         assert data["success"] is True
#         assert data["token"] == "jwt_token_123"


def test_login_endpoint_validation_error(reset_identity_service):
    """Test login endpoint with validation error"""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    client = TestClient(app)
    response = client.post("/team/login", json={"email": "invalid-email", "pin": "12"})

    assert response.status_code == 422  # Validation error


# ============================================================================
# Edge Cases and Boundary Tests
# ============================================================================


@pytest.mark.asyncio
async def test_login_with_minimum_pin_length(
    mock_identity_service, mock_user, reset_identity_service
):
    """Test login with minimum PIN length (4 digits)"""
    mock_identity_service.authenticate_user = AsyncMock(return_value=mock_user)
    mock_identity_service.create_access_token = Mock(return_value="token")
    mock_identity_service.get_permissions_for_role = Mock(return_value=[])

    with patch(
        "app.modules.identity.router.get_identity_service", return_value=mock_identity_service
    ):
        from app.modules.identity.router import team_login

        request = LoginRequest(email="test@example.com", pin="1234")
        response = await team_login(request)

        assert response.success is True


@pytest.mark.asyncio
async def test_login_with_maximum_pin_length(
    mock_identity_service, mock_user, reset_identity_service
):
    """Test login with maximum PIN length (8 digits)"""
    mock_identity_service.authenticate_user = AsyncMock(return_value=mock_user)
    mock_identity_service.create_access_token = Mock(return_value="token")
    mock_identity_service.get_permissions_for_role = Mock(return_value=[])

    with patch(
        "app.modules.identity.router.get_identity_service", return_value=mock_identity_service
    ):
        from app.modules.identity.router import team_login

        request = LoginRequest(email="test@example.com", pin="12345678")
        response = await team_login(request)

        assert response.success is True


@pytest.mark.asyncio
async def test_login_user_without_personalized_response(
    mock_identity_service, mock_user, reset_identity_service
):
    """Test login with user that has personalized_response=False"""
    mock_user.personalized_response = False
    mock_identity_service.authenticate_user = AsyncMock(return_value=mock_user)
    mock_identity_service.create_access_token = Mock(return_value="token")
    mock_identity_service.get_permissions_for_role = Mock(return_value=[])

    with patch(
        "app.modules.identity.router.get_identity_service", return_value=mock_identity_service
    ):
        from app.modules.identity.router import team_login

        request = LoginRequest(email="test@example.com", pin="1234")
        response = await team_login(request)

        assert response.personalizedResponse is False


@pytest.mark.asyncio
async def test_login_user_with_none_language(
    mock_identity_service, mock_user, reset_identity_service
):
    """Test login with user that has language=None"""
    mock_user.language = None
    mock_identity_service.authenticate_user = AsyncMock(return_value=mock_user)
    mock_identity_service.create_access_token = Mock(return_value="token")
    mock_identity_service.get_permissions_for_role = Mock(return_value=[])

    with patch(
        "app.modules.identity.router.get_identity_service", return_value=mock_identity_service
    ):
        from app.modules.identity.router import team_login

        request = LoginRequest(email="test@example.com", pin="1234")
        response = await team_login(request)

        assert response.user["language"] == "en"  # Default fallback
