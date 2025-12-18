"""
Cookie-based authentication utilities for httpOnly JWT tokens.

This module provides secure cookie management for authentication:
- httpOnly JWT cookie (prevents XSS token theft)
- CSRF cookie (readable by JS for double-submit pattern)
- Environment-aware domain configuration
"""

import logging
import secrets
from pathlib import Path

from fastapi import Request, Response

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cookie names
JWT_COOKIE_NAME = "nz_access_token"
CSRF_COOKIE_NAME = "nz_csrf_token"


def get_cookie_domain() -> str | None:
    """
    Return domain for cross-subdomain cookies.

    Returns:
        - ".balizero.com" in production (allows zantara.balizero.com <-> api.balizero.com)
        - None for localhost (browser handles it automatically)
    """
    if settings.environment == "production":
        # Use configured domain or default to .balizero.com
        return getattr(settings, "cookie_domain", None) or ".balizero.com"
    return None  # localhost doesn't need domain


def get_cookie_secure() -> bool:
    """
    Return whether cookies should use Secure flag.

    Returns:
        - True in production (HTTPS only)
        - False in development (allows http://localhost)
    """
    if settings.environment == "production":
        return getattr(settings, "cookie_secure", True)
    return False  # localhost uses http


def get_samesite_policy() -> str:
    """
    Return SameSite policy for cookies.

    Returns:
        - "none" in production for cross-subdomain (zantara.balizero.com <-> api.balizero.com)
        - "lax" in development (localhost same-origin)
    """
    # Cross-subdomain requires SameSite=none (with Secure=true)
    # Even though they share .balizero.com, fetch requests are treated as cross-site
    if settings.environment == "production":
        return "none"
    return "lax"


def set_auth_cookies(
    response: Response,
    jwt_token: str,
    max_age_hours: int | None = None,
) -> str:
    """
    Set httpOnly JWT cookie and readable CSRF cookie.

    Args:
        response: FastAPI Response object
        jwt_token: JWT token string
        max_age_hours: Cookie lifetime in hours (defaults to JWT expiry setting)

    Returns:
        CSRF token string (to include in response body for frontend)
    """
    domain = get_cookie_domain()
    secure = get_cookie_secure()
    samesite = get_samesite_policy()

    if max_age_hours is None:
        max_age_hours = settings.jwt_access_token_expire_hours
    max_age = max_age_hours * 3600

    # Generate CSRF token
    csrf_token = secrets.token_hex(32)

    # Set JWT cookie (httpOnly - JS cannot read this)
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=jwt_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=max_age,
        path="/",
        domain=domain,
    )

    # Set CSRF cookie (JS readable for double-submit pattern)
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,  # Must be readable by frontend JavaScript
        secure=secure,
        samesite=samesite,
        max_age=max_age,
        path="/",
        domain=domain,
    )

    logger.debug(
        f"Auth cookies set: domain={domain}, secure={secure}, samesite={samesite}, max_age={max_age}s"
    )

    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    """
    Clear authentication cookies on logout.

    Args:
        response: FastAPI Response object
    """
    domain = get_cookie_domain()
    secure = get_cookie_secure()
    samesite = get_samesite_policy()

    # Delete both cookies
    for cookie_name in [JWT_COOKIE_NAME, CSRF_COOKIE_NAME]:
        response.delete_cookie(
            key=cookie_name,
            path="/",
            domain=domain,
            secure=secure,
            samesite=samesite,
        )

    logger.debug(f"Auth cookies cleared: domain={domain}")


def get_jwt_from_cookie(request: Request) -> str | None:
    """
    Extract JWT token from httpOnly cookie.

    Args:
        request: FastAPI Request object

    Returns:
        JWT token string or None if not present
    """
    return request.cookies.get(JWT_COOKIE_NAME)


def get_csrf_from_cookie(request: Request) -> str | None:
    """
    Extract CSRF token from cookie.

    Args:
        request: FastAPI Request object

    Returns:
        CSRF token string or None if not present
    """
    return request.cookies.get(CSRF_COOKIE_NAME)


def validate_csrf(request: Request) -> bool:
    """
    Validate CSRF token for state-changing requests.

    The CSRF token in the X-CSRF-Token header must match the cookie value.
    This implements the double-submit cookie pattern.

    Args:
        request: FastAPI Request object

    Returns:
        True if CSRF validation passes, False otherwise
    """
    cookie_csrf = get_csrf_from_cookie(request)
    header_csrf = request.headers.get("X-CSRF-Token")

    if not cookie_csrf or not header_csrf:
        logger.debug(
            f"CSRF validation failed: cookie={bool(cookie_csrf)}, header={bool(header_csrf)}"
        )
        return False

    # Use constant-time comparison to prevent timing attacks
    is_valid = secrets.compare_digest(cookie_csrf, header_csrf)

    if not is_valid:
        logger.warning(f"CSRF token mismatch for {request.url.path}")

    return is_valid


def is_csrf_exempt(request: Request) -> bool:
    """
    Check if request is exempt from CSRF validation.

    GET, HEAD, OPTIONS requests are safe and don't need CSRF protection.

    Args:
        request: FastAPI Request object

    Returns:
        True if exempt from CSRF validation
    """
    safe_methods = {"GET", "HEAD", "OPTIONS"}
    return request.method.upper() in safe_methods
