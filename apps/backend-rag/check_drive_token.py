#!/usr/bin/env python3
"""
🔍 Google Drive OAuth Token Diagnostic Tool
Verifica lo stato del token SYSTEM e tenta refresh se necessario
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

import asyncpg

sys.path.insert(0, ".")


async def check_drive_token():
    """Check Google Drive SYSTEM token status."""

    print("=" * 60)
    print("🔍 Google Drive OAuth Token Check")
    print("=" * 60)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not set")
        return False

    try:
        conn = await asyncpg.connect(database_url)
        print("✅ Database connected\n")

        # 1. Check if table exists
        table_exists = await conn.fetchval(
            """SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'google_drive_tokens'
            )"""
        )

        if not table_exists:
            print("❌ google_drive_tokens table does not exist!")
            print("   Run migration_034_google_drive_tokens.py first")
            await conn.close()
            return False

        print("✅ google_drive_tokens table exists\n")

        # 2. Check SYSTEM token
        token_row = await conn.fetchrow(
            """SELECT user_id, access_token, refresh_token, expires_at, created_at, updated_at
               FROM google_drive_tokens
               WHERE user_id = 'SYSTEM'"""
        )

        if not token_row:
            print("❌ SYSTEM token NOT FOUND")
            print("\n📝 Action needed: Re-authorize Google Drive")
            print("   Visit: https://zantara-crm.vercel.app/admin/google-drive/auth")
            await conn.close()
            return False

        print("✅ SYSTEM token found\n")
        print(f"   User ID:      {token_row['user_id']}")
        print(f"   Access Token: {token_row['access_token'][:20]}... (truncated)")
        print(f"   Refresh Token: {'✅ Present' if token_row['refresh_token'] else '❌ Missing'}")
        print(f"   Created:      {token_row['created_at']}")
        print(f"   Updated:      {token_row['updated_at']}")

        # 3. Check expiration
        now = datetime.now(timezone.utc)
        expires_at = token_row["expires_at"]

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        time_left = expires_at - now

        print("\n⏰ Token Status:")
        print(f"   Expires at:   {expires_at}")
        print(f"   Time left:    {time_left}")

        if time_left.total_seconds() < 0:
            print("   ⚠️  Token EXPIRED - needs refresh")
        elif time_left.total_seconds() < 300:  # Less than 5 min
            print("   ⚠️  Token expires in < 5 minutes - will refresh soon")
        else:
            print(f"   ✅ Token valid for {time_left.days} days, {time_left.seconds // 3600} hours")

        await conn.close()

        # 4. Test actual Drive API call
        print("\n" + "=" * 60)
        print("🧪 Testing Google Drive API Call")
        print("=" * 60)

        try:
            from backend.services.integrations.google_drive_service import GoogleDriveService

            pool = await asyncpg.create_pool(database_url)
            drive_service = GoogleDriveService(pool)

            if not drive_service.is_configured():
                print("❌ Google Drive not configured (missing env vars)")
                await pool.close()
                return False

            print("✅ Drive service configured\n")

            # Try to get valid token (will auto-refresh if needed)
            token = await drive_service.get_valid_token("SYSTEM")

            if token:
                print("✅ Token obtained successfully!")
                print(f"   Token: {token[:30]}...")

                # Try to list files (basic test)
                try:
                    files = await drive_service.list_files("SYSTEM", page_size=1)
                    print("\n✅ Drive API test successful!")
                    print(f"   Can access Drive with {len(files.get('files', []))} files listed")
                except Exception as e:
                    print(f"\n⚠️  Token valid but API call failed: {e}")
                    print("   Possible causes:")
                    print("   - Drive API not enabled in Google Cloud Console")
                    print("   - Insufficient permissions")
                    print("   - Network issue")

                await pool.close()
                return True
            else:
                print("❌ Could not get valid token")
                print("   Token may need manual re-authorization")
                await pool.close()
                return False

        except Exception as e:
            print(f"❌ Drive service test failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(check_drive_token())
    sys.exit(0 if success else 1)
