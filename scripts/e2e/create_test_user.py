#!/usr/bin/env python3
"""
Create or verify test user for E2E tests
Usage: python scripts/create_test_user.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps/backend-rag"))

import asyncpg
import bcrypt
from backend.app.core.config import settings


async def create_test_user():
    """Create test user if not exists"""

    # Test user configuration
    TEST_EMAIL = "test@balizero.com"
    TEST_PIN = "123456"  # Simple PIN for testing
    TEST_NAME = "Test User"
    TEST_ROLE = "user"

    print(f"🔧 Creating/verifying test user...")
    print(f"   Email: {TEST_EMAIL}")
    print(f"   PIN: {TEST_PIN}")
    print(f"   Name: {TEST_NAME}")
    print(f"   Role: {TEST_ROLE}")
    print()

    try:
        # Connect to database
        conn = await asyncpg.connect(settings.database_url)
        print("✅ Connected to database")

        # Check if user exists
        existing_user = await conn.fetchrow(
            "SELECT id, email, full_name, active FROM team_members WHERE email = $1",
            TEST_EMAIL
        )

        if existing_user:
            print(f"✅ Test user already exists (ID: {existing_user['id']})")
            print(f"   Name: {existing_user['full_name']}")
            print(f"   Active: {existing_user['active']}")

            if not existing_user['active']:
                # Activate user
                await conn.execute(
                    "UPDATE team_members SET active = true WHERE email = $1",
                    TEST_EMAIL
                )
                print("✅ Activated test user")
        else:
            # Create new test user
            print("📝 Creating new test user...")

            # Hash PIN
            pin_hash = bcrypt.hashpw(TEST_PIN.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            # Insert user
            user_id = await conn.fetchval(
                """
                INSERT INTO team_members (
                    email, full_name, pin_hash, role, active, language,
                    created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
                RETURNING id
                """,
                TEST_EMAIL, TEST_NAME, pin_hash, TEST_ROLE, True, "en"
            )

            print(f"✅ Test user created (ID: {user_id})")

        # Update PIN to ensure it's correct
        print("🔑 Updating PIN hash...")
        pin_hash = bcrypt.hashpw(TEST_PIN.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        await conn.execute(
            "UPDATE team_members SET pin_hash = $1, active = true WHERE email = $2",
            pin_hash, TEST_EMAIL
        )
        print("✅ PIN hash updated")

        await conn.close()

        print()
        print("=" * 60)
        print("✅ TEST USER READY")
        print("=" * 60)
        print()
        print("Add these to apps/webapp-next/.env.test:")
        print()
        print(f"E2E_TEST_EMAIL={TEST_EMAIL}")
        print(f"E2E_TEST_PIN={TEST_PIN}")
        print()
        print("Then run:")
        print("  cd apps/webapp-next")
        print("  npm run test:e2e -- zantara-complete.spec.ts")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(create_test_user())
