"""
JWT Authentication Router
Real email+PIN authentication using bcrypt and JWT tokens
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.dependencies import get_database_pool
from app.models import UserProfile
from app.utils.cookie_auth import clear_auth_cookies, set_auth_cookies
from app.utils.logging_utils import get_logger, log_error, log_warning

logger = get_logger(__name__)

# Configuration
JWT_SECRET_KEY = settings.jwt_secret_key
JWT_ALGORITHM = settings.jwt_algorithm
JWT_ACCESS_TOKEN_EXPIRE_HOURS = settings.jwt_access_token_expire_hours

router = APIRouter(prefix="/api/auth", tags=["authentication"])
security = HTTPBearer()

# ============================================================================
# Pydantic Models
# ============================================================================


class LoginRequest(BaseModel):
    """Login request model"""

    email: EmailStr
    pin: str | None = None
    password: str | None = None  # Alias for pin (backwards compatibility)

    @property
    def credentials(self) -> str:
        """Return pin or password, whichever is provided"""
        return self.pin or self.password or ""


class LoginResponse(BaseModel):
    """Login response model"""

    success: bool
    message: str
    data: dict[str, Any] | None = None


# ============================================================================
# Database Dependencies
# ============================================================================

# Use centralized database pool dependency

# ============================================================================
# Authentication Functions
# ============================================================================


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash"""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        log_error(logger, "Password verification failed", error=e)
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        if user_id is None or email is None:
            raise credentials_exception
    except JWTError as e:
        raise credentials_exception from e

    # Get user from database using connection pool
    async with db_pool.acquire() as conn:
        logger.debug(f"Validating user: {user_id}")
        query = """
            SELECT id::text, email, full_name as name, role, 'active' as status, NULL::jsonb as metadata, language as language_preference
            FROM team_members
            WHERE id::text = $1 AND email = $2 AND active = true
        """
        row = await conn.fetchrow(query, user_id, email)

        if not row:
            log_warning(logger, "User validation failed", user_id=user_id)
            raise credentials_exception

        logger.debug(f"User validated: {user_id}")
        return dict(row)


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    req: Request,
    response: Response,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    User login with email and PIN

    Returns JWT token and user profile on successful authentication.
    Also sets httpOnly cookie with JWT token and CSRF cookie.
    """
    from services.audit_service import get_audit_service

    audit_service = get_audit_service()
    if not audit_service.pool:
        await audit_service.connect()

    client_ip = req.client.host if req else None
    user_agent = req.headers.get("user-agent") if req else None

    try:
        async with db_pool.acquire() as conn:
            # Real database authentication using team_members
            query = """
                SELECT id, email, full_name as name, pin_hash as password_hash, role, 'active' as status, NULL::jsonb as metadata, language as language_preference, active
                FROM team_members
                WHERE email = $1
            """
            user = await conn.fetchrow(query, request.email)

            if not user:
                await audit_service.log_auth_event(
                    email=request.email,
                    action="failed_login",
                    success=False,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    failure_reason="User not found",
                )
                raise HTTPException(status_code=401, detail="Invalid email or PIN")

            if not user["active"]:
                await audit_service.log_auth_event(
                    email=request.email,
                    action="failed_login",
                    success=False,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    failure_reason="Account inactive",
                )
                raise HTTPException(status_code=401, detail="Account inactive")

            # Verify PIN
            if not verify_password(request.credentials, user["password_hash"]):
                await audit_service.log_auth_event(
                    email=request.email,
                    action="failed_login",
                    success=False,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    failure_reason="Invalid PIN",
                )
                raise HTTPException(status_code=401, detail="Invalid email or PIN")

            # Update last login
            await conn.execute(
                "UPDATE team_members SET last_login = NOW(), failed_attempts = 0 WHERE id = $1",
                user["id"],
            )

            # Create JWT token
            access_token_expires = timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS)
            access_token = create_access_token(
                data={"sub": str(user["id"]), "email": user["email"], "role": user["role"]},
                expires_delta=access_token_expires,
            )

            # Prepare user profile
            user_profile = {
                "id": str(user["id"]),
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
                "status": user["status"],
                "metadata": user.get("metadata"),
                "language_preference": user.get("language_preference", "en"),
            }

            # Log success
            await audit_service.log_auth_event(
                email=user["email"],
                action="login",
                success=True,
                ip_address=client_ip,
                user_agent=user_agent,
                user_id=str(user["id"]),
            )

            # Set httpOnly JWT cookie and CSRF cookie
            csrf_token = set_auth_cookies(
                response=response,
                jwt_token=access_token,
                max_age_hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS,
            )

            return LoginResponse(
                success=True,
                message="Login successful",
                data={
                    "token": access_token,  # Keep for backward compatibility (WebSocket, mobile)
                    "token_type": "Bearer",
                    "expiresIn": JWT_ACCESS_TOKEN_EXPIRE_HOURS * 3600,
                    "user": user_profile,
                    "csrfToken": csrf_token,  # For frontend CSRF protection
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "Login error", error=e, exc_info=True)
        await audit_service.log_auth_event(
            email=request.email,
            action="failed_login",
            success=False,
            ip_address=client_ip,
            user_agent=user_agent,
            failure_reason=f"System error: {str(e)}",
        )
        raise HTTPException(status_code=500, detail="Authentication service unavailable") from e


@router.get("/profile", response_model=UserProfile)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    return UserProfile(**current_user)


@router.post("/logout")
async def logout(
    response: Response,
    _current_user: dict = Depends(get_current_user),
):
    """
    Logout user and clear authentication cookies.

    Note: JWT tokens are stateless, so we only clear cookies.
    Client should also discard any stored tokens.
    """
    clear_auth_cookies(response)
    return {"success": True, "message": "Logout successful"}


@router.get("/check")
async def check_auth(current_user: dict = Depends(get_current_user)):
    """Check if current session is valid"""
    return {
        "valid": True,
        "user": {
            "id": current_user["id"],
            "email": current_user["email"],
            "role": current_user["role"],
        },
    }


@router.get("/csrf-token")
async def get_csrf_token():
    """
    Generate CSRF token and session ID for frontend security.
    Returns token in both JSON body and response headers.
    """
    import secrets

    # Generate CSRF token (32 bytes = 64 hex chars)
    csrf_token = secrets.token_hex(32)

    # Generate session ID
    from datetime import datetime, timezone

    session_id = (
        f"session_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{secrets.token_hex(16)}"
    )

    # Return in both JSON and headers
    response_data = {"csrfToken": csrf_token, "sessionId": session_id}

    # Note: FastAPI Response model doesn't support setting headers directly in decorator
    # Headers will be set in the endpoint function
    return response_data


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    response: Response,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Refresh JWT access token

    Generates a new access token for the authenticated user without requiring
    re-authentication. The user must provide a valid current token.
    Also updates the httpOnly cookie with the new token.
    """
    try:
        # Verify user is still active
        async with db_pool.acquire() as conn:
            query = """
                SELECT id, email, full_name as name, role, 'active' as status, NULL::jsonb as metadata, language as language_preference
                FROM team_members
                WHERE id::text = $1 AND email = $2 AND active = true
            """
            user = await conn.fetchrow(query, current_user["id"], current_user["email"])

            if not user:
                raise HTTPException(status_code=401, detail="User not found or inactive")

            # Create new JWT token
            access_token_expires = timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS)
            access_token = create_access_token(
                data={"sub": str(user["id"]), "email": user["email"], "role": user["role"]},
                expires_delta=access_token_expires,
            )

            # Prepare user profile
            user_profile = {
                "id": str(user["id"]),
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
                "status": user["status"],
                "metadata": user.get("metadata"),
                "language_preference": user.get("language_preference", "en"),
            }

            # Update httpOnly JWT cookie and CSRF cookie
            csrf_token = set_auth_cookies(
                response=response,
                jwt_token=access_token,
                max_age_hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS,
            )

            return LoginResponse(
                success=True,
                message="Token refreshed successfully",
                data={
                    "token": access_token,  # Keep for backward compatibility
                    "token_type": "Bearer",
                    "expiresIn": JWT_ACCESS_TOKEN_EXPIRE_HOURS * 3600,
                    "user": user_profile,
                    "csrfToken": csrf_token,  # For frontend CSRF protection
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "Token refresh error", error=e, exc_info=True)
        raise HTTPException(status_code=500, detail="Token refresh failed") from e


# ============================================================================
# JWT Only Authentication - No Mock Endpoints
# ============================================================================
