"""
Unified Authentication Validation Module
Consolidates auth validation logic from main_cloud.py, hybrid_auth.py, and auth.py

This module provides a single source of truth for authentication validation,
eliminating code duplication across the codebase.
"""

import logging
from typing import Any

from jose import JWTError, jwt

from app.core.config import settings
from app.services.api_key_auth import APIKeyAuth

logger = logging.getLogger(__name__)

# Initialize API key auth service
_api_key_auth = APIKeyAuth()


async def validate_api_key(api_key: str | None) -> dict[str, Any] | None:
    """
    Validate API key for service-to-service authentication.

    Returns a user payload when the API key is valid, otherwise None.

    Args:
        api_key: API key string to validate

    Returns:
        User context dict if valid, None otherwise
    """
    if not api_key:
        return None

    # Use the centralized API key auth service
    user_context = _api_key_auth.validate_api_key(api_key)
    if user_context:
        logger.info("✅ API key authentication successful")
        return user_context

    logger.warning(f"❌ Invalid API key: {api_key[:8]}... (masked)")
    return None


async def validate_auth_token(token: str | None) -> dict[str, Any] | None:
    """
    Validate JWT tokens locally using the shared secret.

    This is the primary JWT validation method used throughout the application.
    Validates JWT tokens locally (TypeScript backend removed).

    Args:
        token: JWT token string to validate

    Returns:
        User context dict if valid, None otherwise
    """
    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

        # Validate required fields
        user_id = payload.get("sub") or payload.get("userId")
        email = payload.get("email")

        if user_id and email:
            logger.info(f"✅ Local JWT validation successful for {email}")
            return {
                "id": user_id,
                "email": email,
                "role": payload.get("role", "member"),
                "name": payload.get("name", email.split("@")[0]),
                "auth_method": "jwt_local",
                "status": "active",
            }

    except JWTError as e:
        logger.debug(f"Local JWT validation failed: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error during local JWT validation: {e}")

    return None


async def validate_auth_mixed(
    authorization: str | None = None,
    auth_token: str | None = None,
    x_api_key: str | None = None,
) -> dict[str, Any] | None:
    """
    Enhanced authentication supporting both JWT and API keys.

    Priority order:
    1. Authorization: Bearer <JWT_TOKEN>
    2. auth_token parameter
    3. X-API-Key header

    Returns user profile when any authentication method succeeds.

    Args:
        authorization: Authorization header value (Bearer token)
        auth_token: Token parameter (alternative to Authorization header)
        x_api_key: X-API-Key header value

    Returns:
        User context dict if authenticated, None otherwise
    """
    # Try JWT token authentication first
    token_value = None
    if authorization:
        if not authorization.startswith("Bearer "):
            logger.warning("Invalid authorization header format")
        else:
            token_value = authorization.split(" ", 1)[1].strip()
    elif auth_token:
        token_value = auth_token.strip()

    if token_value:
        user = await validate_auth_token(token_value)
        if user:
            user["auth_method"] = "jwt"
            return user

    # Try API key authentication if JWT failed
    if x_api_key:
        user = await validate_api_key(x_api_key)
        if user:
            return user

    return None
