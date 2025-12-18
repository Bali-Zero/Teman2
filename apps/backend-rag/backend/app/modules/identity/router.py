"""
NUZANTARA PRIME - Identity Router
HTTP API endpoints for authentication
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field

from app.modules.identity.service import IdentityService
from app.utils.cookie_auth import set_auth_cookies

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/team", tags=["identity"])

# Service instance (singleton)
_identity_service: IdentityService | None = None


def get_identity_service() -> IdentityService:
    """Get or create IdentityService instance"""
    global _identity_service
    if _identity_service is None:
        _identity_service = IdentityService()
    return _identity_service


# ============================================================================
# Request/Response Models
# ============================================================================


class LoginRequest(BaseModel):
    """Login request model"""

    email: EmailStr = Field(..., description="User email address")
    pin: str = Field(..., min_length=4, max_length=8, description="User PIN (4-8 digits)")


class LoginResponse(BaseModel):
    """Login response model (matches Node.js format exactly)"""

    success: bool
    sessionId: str
    token: str  # JWT token (kept for backward compatibility)
    user: dict  # User object
    permissions: list[str]
    personalizedResponse: bool
    loginTime: str  # ISO timestamp
    csrfToken: str | None = None  # CSRF token for frontend protection


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/login", response_model=LoginResponse)
async def team_login(request: LoginRequest, response: Response) -> LoginResponse:
    """
    Team member login endpoint

    Replicates the exact behavior of Node.js /api/auth/team/login endpoint.

    - Validates email and PIN format
    - Authenticates user against database
    - Generates JWT token (7 days expiry)
    - Sets httpOnly cookie with JWT token
    - Returns user data and permissions

    Returns:
        LoginResponse with JWT token and user data
    """
    try:
        # Validate PIN format (4-8 digits, same as Node.js)
        if not request.pin.isdigit():
            raise HTTPException(status_code=400, detail="Invalid PIN format. Must be 4-8 digits.")

        if len(request.pin) < 4 or len(request.pin) > 8:
            raise HTTPException(status_code=400, detail="Invalid PIN format. Must be 4-8 digits.")

        # Get service instance
        identity_service = get_identity_service()

        # Authenticate user
        user = await identity_service.authenticate_user(email=request.email, pin=request.pin)

        if not user:
            logger.warning(f"Login failed for {request.email}")
            raise HTTPException(status_code=401, detail="Invalid email or PIN. Please try again.")

        # Generate session ID (same format as Node.js)
        session_id = f"session_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{user.id}"

        # Create JWT token
        token = identity_service.create_access_token(user, session_id)

        # Get permissions
        permissions = identity_service.get_permissions_for_role(user.role)

        # Set httpOnly JWT cookie and CSRF cookie (7 days = 168 hours)
        csrf_token = set_auth_cookies(
            response=response,
            jwt_token=token,
            max_age_hours=168,  # 7 days to match identity service token expiry
        )

        # Prepare response (matches Node.js format exactly)
        login_time = datetime.now(timezone.utc).isoformat()

        login_response = LoginResponse(
            success=True,
            sessionId=session_id,
            token=token,  # Keep for backward compatibility (WebSocket, mobile)
            user={
                "id": user.id,
                "name": user.name,
                "role": user.role,
                "department": user.department,
                "language": user.language or "en",
                "email": user.email,
            },
            permissions=permissions,
            personalizedResponse=user.personalized_response or False,
            loginTime=login_time,
            csrfToken=csrf_token,  # For frontend CSRF protection
        )

        logger.info(f"🔐 Team login successful: {user.name} ({user.role}) - Session: {session_id}")

        return login_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for {request.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication service unavailable") from None
