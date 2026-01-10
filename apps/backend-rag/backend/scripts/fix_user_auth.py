#!/usr/bin/env python3
"""
Fix user authentication - Update PIN hashes for users in database
Can be run on Fly.io to fix authentication issues
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BACKEND_DIR))
sys.path.append(str(BACKEND_DIR / "backend"))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from backend.app.modules.identity.service import IdentityService

DATA_FILE = BACKEND_DIR / "backend/data/team_members.json"


async def fix_user_auth():
    """Fix user authentication by updating PIN hashes"""
    logger.info("🔧 Starting user authentication fix...")

    if not DATA_FILE.exists():
        logger.error(f"❌ Data file not found: {DATA_FILE}")
        return False

    with open(DATA_FILE) as f:
        users = json.load(f)

    logger.info(f"📋 Found {len(users)} users in data file")

    service = IdentityService()
    conn = await service.get_db_connection()

    try:
        fixed_count = 0
        created_count = 0
        error_count = 0

        for user in users:
            email = user["email"]
            pin = user["pin"]
            name = user["name"]
            role = user.get("role", "member")
            department = user.get("department", "")
            notes = user.get("notes", "")

            try:
                # Hash PIN
                pin_hash = service.get_password_hash(pin)

                # Check if user exists
                existing = await conn.fetchrow(
                    "SELECT id, email, active FROM team_members WHERE LOWER(email) = LOWER($1)",
                    email,
                )

                if existing:
                    # Update existing user
                    await conn.execute(
                        """
                        UPDATE team_members
                        SET full_name = $1, 
                            pin_hash = $2, 
                            role = $3, 
                            department = $4, 
                            notes = $5, 
                            active = true, 
                            updated_at = NOW()
                        WHERE LOWER(email) = LOWER($6)
                        """,
                        name,
                        pin_hash,
                        role,
                        department,
                        notes,
                        email,
                    )
                    logger.info(f"✅ Updated: {name} ({email}) - PIN: {pin}")
                    fixed_count += 1
                else:
                    # Create new user
                    await conn.execute(
                        """
                        INSERT INTO team_members (full_name, email, pin_hash, role, department, notes, active, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, true, NOW(), NOW())
                        """,
                        name,
                        email,
                        pin_hash,
                        role,
                        department,
                        notes,
                    )
                    logger.info(f"🆕 Created: {name} ({email}) - PIN: {pin}")
                    created_count += 1

            except Exception as e:
                logger.error(f"❌ Error processing {email}: {e}")
                error_count += 1

        logger.info("\n📊 Summary:")
        logger.info(f"   ✅ Updated: {fixed_count}")
        logger.info(f"   🆕 Created: {created_count}")
        logger.info(f"   ❌ Errors: {error_count}")
        logger.info(f"   📝 Total processed: {len(users)}")

        return error_count == 0

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        return False
    finally:
        await conn.close()


if __name__ == "__main__":
    success = asyncio.run(fix_user_auth())
    sys.exit(0 if success else 1)
