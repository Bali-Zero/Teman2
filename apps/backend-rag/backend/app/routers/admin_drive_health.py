"""
Admin endpoint per verificare stato Google Drive.
"""

from fastapi import APIRouter, HTTPException, Request
import asyncpg

router = APIRouter(prefix="/api/admin/drive", tags=["admin"])


@router.get("/health")
async def drive_health(request: Request):
    """Verifica stato token Google Drive (public endpoint)."""
    from backend.app.dependencies import get_database_pool
    pool = get_database_pool()
    
    async with pool.acquire() as conn:
        # Check table exists
        table_exists = await conn.fetchval(
            """SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'google_drive_tokens'
            )"""
        )
        
        if not table_exists:
            return {
                "status": "error",
                "message": "google_drive_tokens table not found"
            }
        
        # Check SYSTEM token
        token = await conn.fetchrow(
            """SELECT user_id, expires_at, refresh_token IS NOT NULL as has_refresh, updated_at
               FROM google_drive_tokens WHERE user_id = 'SYSTEM'"""
        )
        
        if not token:
            return {
                "status": "error", 
                "message": "SYSTEM token not found. Re-authorize required.",
                "auth_url": "/api/admin/google-drive/auth"
            }
        
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        expires = token['expires_at']
        
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        
        time_left = expires - now
        
        # Try actual Drive API call
        try:
            from backend.services.integrations.google_drive_service import GoogleDriveService
            drive = GoogleDriveService(pool)
            drive_token = await drive.get_valid_token("SYSTEM")
            api_working = drive_token is not None
        except Exception as e:
            api_working = False
        
        return {
            "status": "healthy" if time_left.total_seconds() > 0 and api_working else "warning",
            "token": {
                "user_id": token['user_id'],
                "expires_at": token['expires_at'].isoformat(),
                "has_refresh": token['has_refresh'],
                "updated_at": token['updated_at'].isoformat() if token['updated_at'] else None
            },
            "time_left_seconds": time_left.total_seconds(),
            "time_left_human": str(time_left),
            "api_working": api_working
        }
