"""
Internal API Authentication Dependency
Protects internal service endpoints with API key verification
"""

import logging

from fastapi import Header, HTTPException, status

from backend.app.services.api_key_auth import APIKeyAuth

logger = logging.getLogger(__name__)
api_key_auth = APIKeyAuth()


async def verify_internal_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")):
    """
    Dependency to verify API key for internal service endpoints.

    Usage:
        @router.post("/api/internal/endpoint")
        async def internal_endpoint(
            api_key_verified = Depends(verify_internal_api_key)
        ):
            # Endpoint logic here
    """
    if not x_api_key:
        logger.warning("Internal endpoint accessed without API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header.",
        )

    user_context = api_key_auth.validate_api_key(x_api_key)
    if not user_context:
        logger.warning(f"Invalid API key provided for internal endpoint: {x_api_key[:4]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    logger.debug(
        f"Internal endpoint accessed with valid API key: {user_context['role']}",
        extra={"auth_method": "api_key", "role": user_context["role"]},
    )

    return user_context
