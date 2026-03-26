"""
Admin Drive Auth - Temporary endpoint to authenticate system user.
Requires ADMIN_SECRET_KEY header.
"""

import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from backend.app.core.config import settings

router = APIRouter()


@router.get("/admin/google-drive/auth-system")
async def auth_system_user(
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
) -> dict[str, Any]:
    """
    Authenticate Google Drive system user.

    Headers:
        X-Admin-Secret: Must match ADMIN_SECRET_KEY env var

    Returns:
        Google OAuth URL to visit
    """
    admin_secret = os.environ.get("ADMIN_SECRET_KEY")
    if not admin_secret:
        raise HTTPException(status_code=500, detail="ADMIN_SECRET_KEY not configured")

    if not x_admin_secret or x_admin_secret != admin_secret:
        raise HTTPException(status_code=401, detail="Invalid admin secret")

    client_id = settings.google_drive_client_id
    redirect_uri = settings.google_drive_redirect_uri

    if not client_id:
        raise HTTPException(status_code=500, detail="Google Drive not configured")

    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=https://www.googleapis.com/auth/drive&"
        f"access_type=offline&"
        f"prompt=consent&"
        f"state=system"
    )

    return {
        "message": "Visit this URL to authenticate system user",
        "auth_url": auth_url,
        "instructions": [
            "1. Visit the auth_url in your browser",
            "2. Login with Google account",
            "3. Accept permissions",
            "4. You will be redirected - copy the 'code' from URL",
            "5. Call: GET /admin/google-drive/callback-system?code=XXX&secret=<your-admin-secret>",
        ],
    }


@router.get("/admin/google-drive/callback-system")
async def auth_callback_system(
    code: str,
    secret: str,
) -> dict[str, Any]:
    """
    Handle OAuth callback for system user.

    Query params:
        code: The authorization code from Google
        secret: Admin secret (same as X-Admin-Secret)
    """
    admin_secret = os.environ.get("ADMIN_SECRET_KEY")
    if not admin_secret:
        raise HTTPException(status_code=500, detail="ADMIN_SECRET_KEY not configured")

    if secret != admin_secret:
        raise HTTPException(status_code=401, detail="Invalid admin secret")

    from datetime import datetime, timedelta, timezone

    import asyncpg
    import httpx

    # Exchange code for tokens
    client_id = settings.google_drive_client_id
    client_secret = settings.google_drive_client_secret
    redirect_uri = settings.google_drive_redirect_uri

    conn = None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )

            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Token exchange failed: {resp.text}")

            data = resp.json()
            access_token = data["access_token"]
            refresh_token = data.get("refresh_token")
            expires_in = data.get("expires_in", 3600)

        # Save to database
        conn = await asyncpg.connect(os.environ["DATABASE_URL"])
        await conn.execute(
            """
            INSERT INTO google_drive_tokens (user_id, access_token, refresh_token, expires_at, updated_at)
            VALUES ('SYSTEM', $1, $2, $3, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = COALESCE(EXCLUDED.refresh_token, google_drive_tokens.refresh_token),
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
        """,
            access_token,
            refresh_token,
            datetime.now(tz=timezone.utc).replace(tzinfo=None) + timedelta(seconds=expires_in),
        )

        return {
            "success": True,
            "message": "System user authenticated successfully!",
            "expires_in": expires_in,
        }
    finally:
        if conn:
            await conn.close()
