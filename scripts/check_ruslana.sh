#!/bin/bash
# Check and Fix access for Ruslana
# Usage: ./scripts/check_ruslana.sh

APP_NAME="nuzantara-rag"
REGION="sin"
# Using the specific image reference from previous successful runs
IMAGE_REF="registry.fly.io/nuzantara-rag:deployment-01KEB43G790V4CXRXF4GH1JFGF"

echo "🚀 CHECKING ACCESS for Ruslana..."

CMD=$(cat <<'EOF'
cat > /app/run_check_ruslana.py <<'PYTHON'
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

    try:
        pool = await asyncpg.create_pool(DB_URL)
        print("✅ Connected")
        
        # Search for Ruslana
        search_term = 'Ruslana'
        target_email = 'ruslana@balizero.com' # Best guess standard email
        
        async with pool.acquire() as conn:
            # 1. Search by name or email
            print(f"🔍 Searching for '{search_term}' or '{target_email}'...")
            rows = await conn.fetch("""
                SELECT id, full_name, email, active, role, pin_hash, failed_attempts, locked_until 
                FROM team_members 
                WHERE full_name ILIKE $1 OR email ILIKE $2
            """, f'%{search_term}%', f'%{target_email}%')
            
            if rows:
                for row in rows:
                    print(f"\n👤 Found User: {row['full_name']}")
                    print(f"   - ID: {row['id']}")
                    print(f"   - Email: {row['email']}")
                    print(f"   - Active: {row['active']}")
                    print(f"   - Role: {row['role']}")
                    print(f"   - Failed Attempts: {row['failed_attempts']}")
                    print(f"   - Locked Until: {row['locked_until']}")
                    
                    # Logic to FIX if inactive or locked
                    needs_update = False
                    if not row['active']:
                        print("   ⚠️  User is INACTIVE")
                        needs_update = True
                    if row['failed_attempts'] > 0:
                        print(f"   ⚠️  Has {row['failed_attempts']} failed attempts")
                        needs_update = True
                        
                    if needs_update:
                        print("   🔄 Reactivating and unlocking user...")
                        await conn.execute("""
                            UPDATE team_members 
                            SET active = true, failed_attempts = 0, locked_until = NULL 
                            WHERE id = $1
                        """, row['id'])
                        print("   ✅ User Reactivated & Unlocked!")
                        
                    # RESET PIN OPTION (Always checking pin validity is hard without known pin)
                    # We will simply report status. To reset, we would need a pin.
                    # Let's forcefully set a known PIN for recovery if requested
                    # Uncomment below to force reset
                    # new_pin = "123456"
                    # new_hash = get_password_hash(new_pin)
                    # await conn.execute("UPDATE team_members SET pin_hash = $1 WHERE id = $2", new_hash, row['id'])
                    # print(f"   🔑 PIN Reset to default: {new_pin}")
                    
            else:
                print("❌ User NOT found.")
                print("   Creating new user for Ruslana...")
                new_pin = "889900" # Default pin for new user
                pin_hash = get_password_hash(new_pin)
                try:
                    await conn.execute("""
                        INSERT INTO team_members (full_name, email, active, pin_hash, department, role)
                        VALUES ($1, $2, true, $3, 'Operations', 'staff')
                    """, "Ruslana", target_email, pin_hash)
                    print(f"   ✅ Created user 'Ruslana' ({target_email}) with PIN {new_pin}")
                except Exception as e:
                    print(f"   ❌ Failed to create user: {e}")

        await pool.close()
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("🎉 Done.")

if __name__ == "__main__":
    asyncio.run(main())
PYTHON

python /app/run_check_ruslana.py
EOF
)

fly machine run "$IMAGE_REF" \
  --app "$APP_NAME" \
  --region "$REGION" \
  --name "admin-check-ruslana-$(date +%s)" \
  --vm-memory "512" \
  --env FORCE_RUN=1 \
  --entrypoint "sh" \
  -- -c "$CMD"
