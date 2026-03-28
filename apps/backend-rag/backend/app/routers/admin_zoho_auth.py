"""Admin Zoho Auth - Temporary endpoint to reconnect Zoho Invoice."""

import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from backend.app.core.config import settings

router = APIRouter()


@router.get("/admin/zoho/auth")
async def admin_zoho_auth(
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
) -> dict[str, Any]:
    """
    Get Zoho OAuth URL for admin reconnection.

    Headers:
        X-Admin-Secret: Must match ADMIN_SECRET_KEY env var
    """
    admin_secret = os.environ.get("ADMIN_SECRET_KEY")
    if not admin_secret:
        raise HTTPException(status_code=500, detail="ADMIN_SECRET_KEY not configured")

    if not x_admin_secret or x_admin_secret != admin_secret:
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
            "2. Login with Zoho",
            "3. Accept ALL permissions (Invoice + Mail)",
            "4. After redirect, copy the 'code' from URL",
            "5. Call: GET /admin/zoho/callback?code=XXX&secret=<your-admin-secret>",
        ],
    }


@router.get("/admin/zoho/callback")
async def admin_zoho_callback(
    code: str,
    secret: str,
) -> dict[str, Any]:
    """Handle Zoho OAuth callback."""
    import logging

    logger = logging.getLogger(__name__)

    admin_secret = os.environ.get("ADMIN_SECRET_KEY")
    if not admin_secret:
        raise HTTPException(status_code=500, detail="ADMIN_SECRET_KEY not configured")

    if secret != admin_secret:
        raise HTTPException(status_code=401, detail="Invalid admin secret")

    import asyncpg

    from backend.services.integrations.zoho_oauth_service import ZohoOAuthService

    db_url = os.environ.get("DATABASE_URL")
    pool = None

    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)

        oauth_service = ZohoOAuthService(pool)

        # Exchange code for tokens
        result = await oauth_service.exchange_code(
            code=code, user_id="7dfe56b2-ff63-4d40-b78b-90c018127a02",
        )

        return {
            "success": True,
            "message": "Zoho Invoice reconnected successfully!",
            "account": result.get("email"),
        }
    except Exception as e:
        logger.error(f"Zoho OAuth callback failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Zoho OAuth failed: {str(e)}") from e
    finally:
        if pool:
            await pool.close()


@router.get("/admin/zoho/debug-callback")
async def admin_zoho_debug_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Any:
    """
    Debug endpoint to capture OAuth callback parameters.
    Use this when normal callback fails. It displays the code for easy copy-paste.
    """
    import logging

    logger = logging.getLogger(__name__)

    logger.info(
        f"Zoho OAuth Debug - code: {code[:50] if code else 'None'}..., state: {state}, error: {error}",
    )

    if code:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Zoho OAuth - Code Captured</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
                .code-box {{ background: #f4f4f4; padding: 15px; border-radius: 5px; word-break: break-all; font-family: monospace; }}
                .btn {{ background: #4CAF50; color: white; padding: 10px 20px; border: none; cursor: pointer; margin: 10px 5px; }}
                .btn-copy {{ background: #2196F3; }}
                .success {{ color: green; }}
            </style>
        </head>
        <body>
            <h1>Zoho Authorization Code Captured</h1>
            <p class="success">The authorization code has been captured successfully.</p>

            <h3>Authorization Code:</h3>
            <div class="code-box" id="auth-code">{code}</div>
            <button class="btn btn-copy" onclick="copyCode()">Copy Code</button>

            <h3>Next Step:</h3>
            <p>Call the callback endpoint with this code and your admin secret.</p>

            <script>
                function copyCode() {{
                    const code = document.getElementById('auth-code').innerText;
                    navigator.clipboard.writeText(code);
                    alert('Code copied to clipboard!');
                }}
            </script>
        </body>
        </html>
        """
        from fastapi.responses import HTMLResponse

        return HTMLResponse(content=html_content)

    if error:
        return {"error": error, "message": "OAuth failed"}

    return {"message": "No code provided"}
