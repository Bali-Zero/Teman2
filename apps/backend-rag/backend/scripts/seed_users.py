import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BACKEND_DIR))
sys.path.append(str(BACKEND_DIR / "backend"))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Override DB URL for local dev if needed BEFORE imports
if not os.getenv("DATABASE_URL"):
    # Default to local system DB
    os.environ["DATABASE_URL"] = "postgresql://antonellosiano@localhost:5432/nuzantara_dev"
    logger.info(f"Set DATABASE_URL to default: {os.environ['DATABASE_URL']}")

from backend.app.modules.identity.service import IdentityService
from backend.app.core.config import settings


DATA_FILE = BACKEND_DIR / "backend/data/team_members.json"

async def seed_users():
    logger.info(f"Seeding users from {DATA_FILE}")
    
    if not DATA_FILE.exists():
        logger.error(f"Data file not found: {DATA_FILE}")
        return

    with open(DATA_FILE, 'r') as f:
        users = json.load(f)

    service = IdentityService()
    conn = await service.get_db_connection()
    
    try:
        # Check if table exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'team_members'
            );
        """)
        
        if not exists:
            logger.error("Table 'team_members' does not exist. Please run migrations first.")
            return

        for user in users:
            email = user['email']
            pin = user['pin']
            name = user['name']
            role = user['role']
            department = user['department']
            
            notes = user.get('notes', '')
            
            # Hash PIN
            pin_hash = service.get_password_hash(pin)
            
            # Check if user exists
            existing = await conn.fetchrow("SELECT id FROM team_members WHERE email = $1", email)
            
            if existing:
                logger.info(f"Updating user {name} ({email})")
                await conn.execute("""
                    UPDATE team_members 
                    SET full_name = $1, pin_hash = $2, role = $3, department = $4, notes = $5, active = true, updated_at = NOW()
                    WHERE email = $6
                """, name, pin_hash, role, department, notes, email)
            else:
                logger.info(f"Creating user {name} ({email})")
                await conn.execute("""
                    INSERT INTO team_members (full_name, email, pin_hash, role, department, notes, active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, true, NOW(), NOW())
                """, name, email, pin_hash, role, department, notes)
                
        logger.info("Seeding complete!")
        
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(seed_users())
