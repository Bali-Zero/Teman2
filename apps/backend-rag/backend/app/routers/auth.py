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

from backend.app.core.config import settings
from backend.app.dependencies import get_database_pool
from backend.app.models import UserProfile
from backend.app.utils.cookie_auth import clear_auth_cookies, set_auth_cookies
from backend.app.utils.logging_utils import get_logger, log_error, log_warning
from backend.services.common.background import spawn

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


class MagicLinkRequest(BaseModel):
    """Request body for passwordless magic-link login (FASE 6)."""

    email: EmailStr


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


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> Any:
    """Create JWT access token with jti, type, and iat claims (S03 hardening)."""
    import uuid

    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "type": "access",
        }
    )
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # S03: Two-phase JWT expiry enforcement
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"verify_exp": getattr(settings, "jwt_enforce_expiry", False)},
        )
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        if user_id is None or email is None:
            raise credentials_exception
    except JWTError as e:
        raise credentials_exception from e

    # Get user from database using connection pool
    async with db_pool.acquire() as conn:
        logger.debug("Validating user: %s", user_id)
        query = """
            SELECT id::text, email, full_name as name, role, 'active' as status, NULL::jsonb as metadata, language as language_preference, avatar
            FROM team_members
            WHERE id::text = $1 AND email = $2 AND active = true
        """
        row = await conn.fetchrow(query, user_id, email)

        if not row:
            log_warning(logger, "User validation failed", user_id=user_id)
            raise credentials_exception

        logger.debug("User validated: %s", user_id)
        return dict(row)


# ============================================================================
# PANOPTICON: Auto Clock-In
# ============================================================================

_CLIENT_ROLES = frozenset({"client"})


async def _auto_clockin_if_needed(
    pool: asyncpg.Pool,
    user_id: str,
    email: str,
    role: str,
) -> bool:
    """Auto-clock-in team member on first login of the day. Never raises."""
    if role in _CLIENT_ROLES or not email.endswith("@balizero.com"):
        return False
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchval(
                """
                SELECT count(*) FROM team_timesheet
                WHERE user_id = $1
                  AND action_type = 'clock_in'
                  AND timestamp AT TIME ZONE 'Asia/Makassar' >= (NOW() AT TIME ZONE 'Asia/Makassar')::date
                """,
                user_id,
            )
            if existing > 0:
                return False
            await conn.execute(
                """
                INSERT INTO team_timesheet (user_id, email, action_type, metadata)
                VALUES ($1, $2, 'clock_in', '{"source": "auto_login"}'::jsonb)
                """,
                user_id,
                email,
            )
            logger.info("🟢 Auto clock-in: %s (from login)", email)
            return True
    except Exception as e:
        logger.warning("⚠️ Auto clock-in failed for %s: %s", email, e)
        return False


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    req: Request,
    response: Response,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> LoginResponse:
    """
    User login with email and PIN

    Returns JWT token and user profile on successful authentication.
    Also sets httpOnly cookie with JWT token and CSRF cookie.
    """
    from backend.services.monitoring.audit_service import get_audit_service

    audit_service = get_audit_service()
    if not audit_service.pool:
        await audit_service.connect()

    client_ip = req.client.host if req else None
    user_agent = req.headers.get("user-agent") if req else None

    try:
        # S03-S3: Brute force detection
        brute_force = None
        try:
            from backend.core.redis_manager import RedisManager
            from backend.services.security.brute_force import BruteForceDetector

            redis_client = RedisManager.get_instance().get_async_client()
            brute_force = BruteForceDetector(redis_client=redis_client)

            if await brute_force.is_blocked(client_ip or "", request.email):
                logger.warning(
                    f"S03: Login blocked (brute force) ip={client_ip} email={request.email}"
                )
                raise HTTPException(
                    status_code=429,
                    detail="Too many failed attempts. Please try again later.",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.debug("S03: Brute force check skipped: %s", e)

        async with db_pool.acquire() as conn:
            # Real database authentication using team_members
            # Use case-insensitive query to handle email case variations
            query = """
                SELECT id, email,
                       COALESCE(full_name, name) as name,
                       pin_hash as password_hash, role,
                       'active' as status, NULL::jsonb as metadata, language as language_preference,
                       active, avatar
                FROM team_members
                WHERE LOWER(email) = LOWER($1)
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
                if brute_force:
                    try:
                        await brute_force.record_failure(client_ip or "", request.email)
                    except Exception as exc:
                        # UU PDP audit: failure to record a brute-force attempt
                        # must not hide the underlying error, even though the
                        # 401 path still proceeds (graceful degradation).
                        logger.warning(
                            "auth.brute_force_record_failed",
                            extra={
                                "error_type": type(exc).__name__,
                                "client_ip": client_ip or "unknown",
                            },
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
                if brute_force:
                    try:
                        await brute_force.record_failure(client_ip or "", request.email)
                    except Exception as exc:
                        # UU PDP audit: failure to record a brute-force attempt
                        # must not hide the underlying error, even though the
                        # 401 path still proceeds (graceful degradation).
                        logger.warning(
                            "auth.brute_force_record_failed",
                            extra={
                                "error_type": type(exc).__name__,
                                "client_ip": client_ip or "unknown",
                            },
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
                if brute_force:
                    try:
                        await brute_force.record_failure(client_ip or "", request.email)
                    except Exception as exc:
                        # UU PDP audit: failure to record a brute-force attempt
                        # must not hide the underlying error, even though the
                        # 401 path still proceeds (graceful degradation).
                        logger.warning(
                            "auth.brute_force_record_failed",
                            extra={
                                "error_type": type(exc).__name__,
                                "client_ip": client_ip or "unknown",
                            },
                        )
                raise HTTPException(status_code=401, detail="Invalid email or PIN")

            # Update last login
            await conn.execute(
                "UPDATE team_members SET last_login = NOW(), failed_attempts = 0 WHERE id = $1",
                user["id"],
            )

            # S03-S3: Clear brute force counter on success
            if brute_force:
                try:
                    await brute_force.clear_on_success(client_ip or "", request.email)
                except Exception as exc:
                    # UU PDP audit: failing to clear the counter only inflates
                    # lockout risk on the next attempt; login itself proceeds.
                    logger.warning(
                        "auth.brute_force_clear_failed",
                        extra={
                            "error_type": type(exc).__name__,
                            "client_ip": client_ip or "unknown",
                        },
                    )

            # Create JWT token with role-specific data
            jwt_data = {
                "sub": str(user["id"]),
                "email": user["email"],
                "role": user["role"],
            }

            # For client users, include linked_client_id in JWT
            # linked_client_id logic disabled due to schema mismatch
            # if user["role"] == "client" and user.get("linked_client_id"):
            #    jwt_data["client_id"] = user["linked_client_id"]

            access_token_expires = timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS)
            access_token = create_access_token(
                data=jwt_data,
                expires_delta=access_token_expires,
            )

            # Determine redirect based on role
            # Clients go to portal, team members go to dashboard
            redirect_to = "/portal" if user["role"] == "client" else "/dashboard"

            # Prepare user profile
            user_profile = {
                "id": str(user["id"]),
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
                "status": user["status"],
                "avatar": user.get("avatar"),
                "metadata": user.get("metadata"),
                "language_preference": user.get("language_preference", "en"),
            }

            # Add client-specific fields
            if user["role"] == "client":
                # client specific logic temporarily disabled due to schema mismatch
                pass

            # Log success
            await audit_service.log_auth_event(
                email=user["email"],
                action="login",
                success=True,
                ip_address=client_ip,
                user_agent=user_agent,
                user_id=str(user["id"]),
            )

            # PANOPTICON: Auto clock-in on team login
            if user["role"] != "client":
                spawn(
                    _auto_clockin_if_needed(db_pool, str(user["id"]), user["email"], user["role"]),
                    name=f"auto-clockin:{user['email']}",
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
                    "redirectTo": redirect_to,  # Role-based redirect for frontend
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
            failure_reason=f"System error: {e!s}",
        )
        raise HTTPException(status_code=500, detail="Authentication service unavailable") from e


# ============================================================================
# Passwordless magic-link login (FASE 6)
# ============================================================================


async def _send_magic_link_email(to_email: str, name: str | None, link_url: str) -> bool:
    """Send the magic-link email via Brevo (from=zantara@balizero.com — fixed rule).

    Returns True on success; never raises (a send failure must not change the
    enumeration-safe HTTP response).
    """
    import os

    import httpx

    greeting = f"Hello {name}," if name else "Hello,"
    html_body = (
        f"{greeting}<br><br>"
        "Use the secure link below to sign in to your Bali Zero client portal. "
        f"This link works once and expires in 15 minutes.<br><br>"
        f'<a href="{link_url}">Sign in to my.balizero.com</a><br><br>'
        "If you didn't request this, you can safely ignore this email — your "
        "account stays protected.<br><br>"
        "— Bali Zero"
    )
    api_url = os.getenv(
        "INTERNAL_EMAIL_API_URL",
        "https://nuzantara-rag.fly.dev/api/notifications/send-email",
    )
    api_key = os.getenv("NUZANTARA_API_KEY", "")
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            resp = await http_client.post(
                api_url,
                headers={"X-API-Key": api_key},
                json={
                    "to": to_email,
                    "subject": "Your Bali Zero portal sign-in link",
                    "body": html_body,
                },
            )
            resp.raise_for_status()
        logger.info("📧 Magic-link email dispatched via Brevo")
        return True
    except Exception as e:
        logger.warning("Magic-link email send failed: %s", e)
        return False


@router.post("/request-magic-link")
async def request_magic_link(
    body: MagicLinkRequest,
    req: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Request a passwordless sign-in link for a registered portal client.

    Enumeration-safe: the response is identical whether or not the email maps to
    a portal account. A link is emailed only when the email IS an active portal
    client (and is not rate-limited).
    """
    from backend.services.portal.magic_link_service import MagicLinkService

    client_ip = req.client.host if req and req.client else None
    service = MagicLinkService(db_pool)

    try:
        result = await service.request_magic_link(body.email, created_ip=client_ip)
    except Exception as e:
        # Don't leak internals; still answer with the generic message.
        log_error(logger, "Magic-link request error", error=e)
        result = {"token": None}

    raw_token = result.get("token")
    if raw_token:
        import os

        base = os.getenv("PORTAL_BASE_URL", "https://my.balizero.com").rstrip("/")
        link_url = f"{base}/portal/magic?token={raw_token}"
        spawn(
            _send_magic_link_email(result["email"], result.get("name"), link_url),
            name="magic-link-email",
        )

    # Always the same body — never reveal account existence.
    return {
        "success": True,
        "message": "If an account exists for that email, a sign-in link is on its way.",
    }


@router.get("/verify-magic/{token}", response_model=LoginResponse)
async def verify_magic_link(
    token: str,
    req: Request,
    response: Response,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> LoginResponse:
    """
    Verify a magic-link token and establish a portal session.

    On success issues the SAME JWT + httpOnly cookie + CSRF token as a PIN login,
    so the client lands authenticated. The token is single-use and consumed here.
    """
    from backend.services.monitoring.audit_service import get_audit_service
    from backend.services.portal.magic_link_service import MagicLinkService

    client_ip = req.client.host if req and req.client else None
    user_agent = req.headers.get("user-agent") if req else None

    service = MagicLinkService(db_pool)
    user = await service.verify_magic_link(token)

    audit_service = get_audit_service()
    if not audit_service.pool:
        try:
            await audit_service.connect()
        except Exception:
            pass

    if not user:
        try:
            await audit_service.log_auth_event(
                email="unknown",
                action="failed_login",
                success=False,
                ip_address=client_ip,
                user_agent=user_agent,
                failure_reason="Invalid or expired magic link",
            )
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="This sign-in link is invalid or expired.")

    # Issue the session — mirror the PIN-login path exactly.
    jwt_data = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
    }
    access_token = create_access_token(
        data=jwt_data,
        expires_delta=timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS),
    )

    try:
        await audit_service.log_auth_event(
            email=user["email"],
            action="login",
            success=True,
            ip_address=client_ip,
            user_agent=user_agent,
            user_id=str(user["id"]),
        )
    except Exception:
        pass

    csrf_token = set_auth_cookies(
        response=response,
        jwt_token=access_token,
        max_age_hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS,
    )

    return LoginResponse(
        success=True,
        message="Login successful",
        data={
            "token": access_token,
            "token_type": "Bearer",
            "expiresIn": JWT_ACCESS_TOKEN_EXPIRE_HOURS * 3600,
            "user": {
                "id": str(user["id"]),
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
            },
            "csrfToken": csrf_token,
            "redirectTo": "/portal",
        },
    )


@router.get("/profile", response_model=UserProfile)
async def get_profile(current_user: dict = Depends(get_current_user)) -> UserProfile:
    """Get current user profile"""
    return UserProfile(**current_user)


@router.post("/logout")
async def logout(
    response: Response,
    _current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Logout user and clear authentication cookies.

    Note: JWT tokens are stateless, so we only clear cookies.
    Client should also discard any stored tokens.
    """
    clear_auth_cookies(response)
    return {"success": True, "message": "Logout successful"}


@router.get("/check")
async def check_auth(current_user: dict = Depends(get_current_user)) -> dict[str, Any]:
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
async def get_csrf_token() -> Any:
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
    return {"csrfToken": csrf_token, "sessionId": session_id}

    # Note: FastAPI Response model doesn't support setting headers directly in decorator
    # Headers will be set in the endpoint function


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    response: Response,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> LoginResponse:
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
                SELECT id, email,
                       COALESCE(full_name, name) as name,
                       role, 'active' as status,
                       NULL::jsonb as metadata, language as language_preference,
                       linked_client_id, portal_access, avatar
                FROM team_members
                WHERE id::text = $1 AND email = $2 AND active = true
            """
            user = await conn.fetchrow(query, current_user["id"], current_user["email"])

            if not user:
                raise HTTPException(status_code=401, detail="User not found or inactive")

            # Create JWT token with role-specific data
            jwt_data = {
                "sub": str(user["id"]),
                "email": user["email"],
                "role": user["role"],
            }

            # For client users, include linked_client_id in JWT
            if user["role"] == "client" and user.get("linked_client_id"):
                jwt_data["client_id"] = user["linked_client_id"]

            access_token_expires = timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS)
            access_token = create_access_token(
                data=jwt_data,
                expires_delta=access_token_expires,
            )

            # Determine redirect based on role
            redirect_to = "/portal" if user["role"] == "client" else "/dashboard"

            # Prepare user profile
            user_profile = {
                "id": str(user["id"]),
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
                "status": user["status"],
                "avatar": user.get("avatar"),
                "metadata": user.get("metadata"),
                "language_preference": user.get("language_preference", "en"),
            }

            # Add client-specific fields
            if user["role"] == "client":
                user_profile["client_id"] = user.get("linked_client_id")
                user_profile["portal_access"] = user.get("portal_access", False)

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
                    "redirectTo": redirect_to,  # Role-based redirect
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "Token refresh error", error=e, exc_info=True)
        raise HTTPException(status_code=500, detail="Token refresh failed") from e


@router.post("/revoke-all")
async def revoke_all_sessions(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Revoke all active sessions for the current user (S03-S2).

    Sets a user-level revocation key in Redis. All tokens for this
    user will be rejected until the key expires (24h).
    """
    from backend.app.core.config import settings

    user_email = current_user.get("email", "")
    client_ip = request.client.host if request.client else None

    if settings.enable_token_revocation:
        try:
            from backend.core.redis_manager import RedisManager
            from backend.services.security.token_revocation import TokenRevocationService

            redis_client = RedisManager.get_instance().get_async_client()
            revocation_svc = TokenRevocationService(redis_client=redis_client)
            await revocation_svc.revoke_all_user_tokens(user_email, reason="user_requested")
        except Exception as e:
            logger.warning("S03-S2: Revoke-all failed for %s: %s", user_email, e)

    # Audit log
    try:
        async with db_pool.acquire() as conn:
            from backend.services.security.audit_service import SecurityAuditService

            audit = SecurityAuditService()
            await audit.log_event(
                conn=conn,
                action="revoke_all",
                user_email=user_email,
                ip_address=client_ip,
                success=True,
                details={"reason": "user_requested"},
            )
    except Exception as e:
        logger.warning("S03-S2: Audit log failed for revoke-all: %s", e)

    return {"success": True, "message": "All sessions revoked"}


# ============================================================================
# JWT Only Authentication - No Mock Endpoints
# ============================================================================
