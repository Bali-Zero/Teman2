#!/bin/bash
# Fix access for kadek@balizero.com
# Usage: ./scripts/fix_kadek.sh

APP_NAME="nuzantara-rag"
REGION="sin"
IMAGE_REF="registry.fly.io/nuzantara-rag:deployment-01KE8BCX7GYCYM6P4NR00071B3"

echo "🚀 FIXING ACCESS for kadek@balizero.com..."

CMD=$(cat <<'EOF'
cat > /app/run_fix_kadek.py <<'PYTHON'
import asyncio
import os
import asyncpg
from passlib.context import CryptContext

# Setup password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

async def main():
    print("🔌 Connecting to DB...")
    DB_URL = os.getenv("DATABASE_URL")
    if not DB_URL:
        print("❌ DATABASE_URL missing")
        return

    pool = await asyncpg.create_pool(DB_URL)
    print("✅ Connected")
    
    target_email = 'kadek@balizero.com'
    target_pin = '786294'
    target_name = 'Kadek'
    
    # Generate Hash
    pin_hash = get_password_hash(target_pin)
    print(f"🔑 Generated hash for PIN ending in ...{target_pin[-2:]}")
    
    async with pool.acquire() as conn:
        # Check if exists
        row = await conn.fetchrow("SELECT id, full_name FROM team_members WHERE email = $1", target_email)
        
        if row:
            print(f"👤 User found: {row['full_name']} (ID: {row['id']})")
            print("🔄 Updating PIN and Active status...")
            await conn.execute("""
                UPDATE team_members 
                SET pin_hash = $1, active = true, failed_attempts = 0, locked_until = NULL 
                WHERE email = $2
            """, pin_hash, target_email)
            print("✅ User Updated!")
        else:
            print("👤 User NOT found. Creating new user...")
            await conn.execute("""
                INSERT INTO team_members (full_name, email, active, pin_hash, department, role)
                VALUES ($1, $2, true, $3, 'Operations', 'staff')
            """, target_name, target_email, pin_hash)
            print("✅ User Created!")
            
    await pool.close()
    print("🎉 Done.")

if __name__ == "__main__":
    asyncio.run(main())
PYTHON

python /app/run_fix_kadek.py
EOF
)

fly machine run "$IMAGE_REF" \
  --app "$APP_NAME" \
  --region "$REGION" \
  --name "admin-fix-kadek-$(date +%s)" \
  --vm-memory "512" \
  --env FORCE_RUN=1 \
  --entrypoint "sh" \
  --rm \
  -- -c "$CMD"
