#!/usr/bin/env python3
"""Refresh Google Drive OAuth token."""
import asyncio
import asyncpg
import os
import httpx

async def refresh():
    try:
        conn = await asyncpg.connect(os.environ['DATABASE_URL'])
        
        # Get current token
        row = await conn.fetchrow(
            "SELECT user_id, refresh_token FROM google_drive_tokens WHERE user_id = 'SYSTEM'"
        )
        
        if not row:
            print("❌ No SYSTEM token found")
            await conn.close()
            return
        
        refresh_token = row['refresh_token']
        print(f"Found refresh token for SYSTEM")
        
        # Refresh via Google OAuth
        client_id = os.environ.get('GOOGLE_DRIVE_CLIENT_ID')
        client_secret = os.environ.get('GOOGLE_DRIVE_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            print("❌ Missing GOOGLE_DRIVE_CLIENT_ID or GOOGLE_DRIVE_CLIENT_SECRET")
            await conn.close()
            return
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }
            )
            
            if resp.status_code != 200:
                print(f"❌ Refresh failed: {resp.text}")
                await conn.close()
                return
            
            data = resp.json()
            new_access_token = data['access_token']
            expires_in = data.get('expires_in', 3600)
            
            # Update database
            await conn.execute("""
                UPDATE google_drive_tokens 
                SET access_token = $1, 
                    expires_at = NOW() + INTERVAL '$2 seconds',
                    updated_at = NOW()
                WHERE user_id = 'SYSTEM'
            """, new_access_token, expires_in)
            
            print(f"✅ Token refreshed! Expires in {expires_in} seconds")
        
        await conn.close()
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(refresh())
