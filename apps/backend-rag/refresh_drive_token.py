#!/usr/bin/env python3
"""
🔄 Google Drive Token Refresh Tool
Force refresh del token OAuth SYSTEM
"""

import asyncio
import os
import sys

import asyncpg

sys.path.insert(0, ".")


async def refresh_drive_token():
    """Force refresh Google Drive SYSTEM token."""

    print("=" * 60)
    print("🔄 Google Drive Token Refresh")
    print("=" * 60)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not set")
        return False

    try:
        pool = await asyncpg.create_pool(database_url)

        from backend.services.integrations.google_drive_service import GoogleDriveService

        drive_service = GoogleDriveService(pool)

        if not drive_service.is_configured():
            print("❌ Google Drive not configured")
            print("   Check env vars:")
            print("   - GOOGLE_DRIVE_CLIENT_ID")
            print("   - GOOGLE_DRIVE_CLIENT_SECRET")
            print("   - GOOGLE_DRIVE_REDIRECT_URI")
            await pool.close()
            return False

        print("✅ Drive service configured\n")

        # Get current token info
        async with pool.acquire() as conn:
            current = await conn.fetchrow(
                "SELECT expires_at, refresh_token FROM google_drive_tokens WHERE user_id = 'SYSTEM'"
            )

            if current:
                print(f"Current token expires: {current['expires_at']}")
                print(
                    f"Refresh token present: {'✅ Yes' if current['refresh_token'] else '❌ No'}\n"
                )
            else:
                print("❌ No SYSTEM token found in database")
                print("   You need to authorize first:")
                print("   https://zantara-crm.vercel.app/admin/google-drive/auth\n")
                await pool.close()
                return False

        # Force token refresh
        print("🔄 Attempting token refresh...\n")

        try:
            # This will trigger refresh if token is expired or close to expiry
            new_token = await drive_service._refresh_token_if_needed("SYSTEM")

            if new_token:
                print("✅ Token refresh successful!")
                print(f"   New token: {new_token[:30]}...")

                # Verify with API call
                files = await drive_service.list_files("SYSTEM", page_size=1)
                print("\n✅ Drive API working!")
                print(f"   Listed {len(files.get('files', []))} files")

                await pool.close()
                return True
            else:
                print("❌ Token refresh returned None")
                print("   The refresh token may be invalid or revoked")
                print("\n📝 Manual re-authorization required:")
                print("   1. Go to: https://zantara-crm.vercel.app/admin/google-drive/auth")
                print("   2. Login with: antonellosiano@gmail.com")
                print("   3. Grant permissions")

                await pool.close()
                return False

        except Exception as e:
            print(f"❌ Token refresh failed: {e}")
            print("\n📝 Manual re-authorization required")
            await pool.close()
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(refresh_drive_token())
    sys.exit(0 if success else 1)
