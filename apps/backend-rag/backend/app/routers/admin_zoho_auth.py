"""Admin Zoho Auth - Temporary endpoint to reconnect Zoho Invoice."""
import os

from fastapi import APIRouter, Header, HTTPException

from backend.app.core.config import settings

router = APIRouter()

@router.get("/admin/zoho/auth")
async def admin_zoho_auth(
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret")
):
    """
    Get Zoho OAuth URL for admin reconnection.

    Headers:
        X-Admin-Secret: Must match ADMIN_SECRET_KEY env var
    """
    expected_secret = os.environ.get("ADMIN_SECRET_KEY", "zantara-admin-2026")

    if not x_admin_secret or x_admin_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid admin secret")

    client_id = settings.zoho_client_id
    redirect_uri = settings.zoho_redirect_uri

    if not client_id:
        raise HTTPException(status_code=500, detail="Zoho not configured")

    # Zoho Invoice OAuth URL
    auth_url = (
        f"https://accounts.zoho.com/oauth/v2/auth?"
        f"client_id={client_id}&"
        f"response_type=code&"
        f"scope=ZohoInvoice.fullaccess.all,ZohoMail.messages.ALL&"
        f"redirect_uri={redirect_uri}&"
        f"access_type=offline&"
        f"prompt=consent&"
        f"state=7dfe56b2-ff63-4d40-b78b-90c018127a02"
    )

    return {
        "message": "Visit this URL to authenticate Zoho Invoice",
        "auth_url": auth_url,
        "instructions": [
            "1. Visit the auth_url in your browser",
            "2. Login with Zoho (zero@balizero.com)",
            "3. Accept ALL permissions (Invoice + Mail)",
            "4. After redirect, copy the 'code' from URL",
            "5. Call: GET /admin/zoho/callback?code=XXX&secret=zantara-admin-2026"
        ]
    }


@router.get("/admin/zoho/callback")
async def admin_zoho_callback(
    code: str,
    secret: str,
):
    """Handle Zoho OAuth callback."""
    expected_secret = os.environ.get("ADMIN_SECRET_KEY", "zantara-admin-2026")

    if secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid admin secret")

    import asyncpg

    from backend.services.integrations.zoho_oauth_service import ZohoOAuthService

    db_url = os.environ.get("DATABASE_URL")

    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)

        oauth_service = ZohoOAuthService(pool)

        # Exchange code for tokens
        result = await oauth_service.exchange_code(
            code=code,
            user_id="7dfe56b2-ff63-4d40-b78b-90c018127a02"
        )

        await pool.close()

        return {
            "success": True,
            "message": "Zoho Invoice reconnected successfully!",
            "account": result.get("email"),
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
