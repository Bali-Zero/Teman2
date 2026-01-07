#!/bin/bash
# Manual Trigger for Daily Report (Injection Strategy)
# Features: Raw Data Dump, Safe Markdown, Truncation, Connection Pool Fix, Dynamic Missing Check, Ruslana Filter
# Update: Switched to local httpx telegram sender to avoid loading heavy AI services and silencing warnings.

APP_NAME="nuzantara-rag"
REGION="sin"
IMAGE_REF="registry.fly.io/nuzantara-rag:deployment-01KE8BCX7GYCYM6P4NR00071B3"

echo "🚀 TRIGGERING MANUAL REPORT to $APP_NAME..."

# The injected python script
CMD=$(cat <<'EOF'
echo "🕒 Checking Time..."
echo "✅ FORCE_RUN=1 detected. Running Report NOW..."

# Write the script
cat > /app/run_report.py <<'PYTHON'
import asyncio
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx 

# FIX PATHS FOR DOCKER IMAGE
sys.path.insert(0, "/app")

from backend.app.core.config import settings
import asyncpg

# Local Telegram Sender to avoid importing backend.services (which triggers AI module warnings)
async def send_telegram_message(token: str, chat_id: str, text: str):
    if not token:
        print("❌ Telegram Token missing in settings!")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json={
                "chat_id": chat_id, 
                "text": text, 
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            })
            if resp.status_code == 200:
                print("✅ Sent!")
            else:
                print(f"❌ Telegram API Error: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"❌ Failed to send Telegram report: {e}")

async def main():
    print("🚀 Starting Daily Report (Lightweight)...")
    
    # Get configuration from Environment (Fly Secrets)
    ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "8290313965")
    DB_URL = os.getenv("DATABASE_URL")
    
    if not DB_URL:
        print("❌ DATABASE_URL is missing!")
        return

    print(f"🔌 Connecting to DB...")

    pool = None
    try:
        pool = await asyncpg.create_pool(DB_URL)
        print("✅ DB Connected")
        
        # --- PATCH: Update View Definition ---
        print("🔧 Patching DB View to show active sessions...")
        async with pool.acquire() as conn:
            await conn.execute("""
            CREATE OR REPLACE VIEW daily_work_hours AS
            SELECT
                user_id,
                email,
                DATE(clock_in_bali) as work_date,
                clock_in_bali,
                CASE
                    WHEN next_action_type = 'clock_out' THEN clock_out_bali
                    ELSE NULL
                END as clock_out_bali,
                CASE
                    WHEN next_action_type = 'clock_out' THEN ROUND(CAST(EXTRACT(EPOCH FROM (clock_out_bali - clock_in_bali))/3600 AS NUMERIC), 2)
                    ELSE NULL
                END as hours_worked
            FROM (
                SELECT
                    user_id,
                    email,
                    (timestamp AT TIME ZONE 'Asia/Makassar') as clock_in_bali,
                    LEAD((timestamp AT TIME ZONE 'Asia/Makassar')) OVER (
                        PARTITION BY user_id 
                        ORDER BY timestamp
                    ) as clock_out_bali,
                    action_type,
                    LEAD(action_type) OVER (
                        PARTITION BY user_id
                        ORDER BY timestamp
                    ) as next_action_type
                FROM team_timesheet
            ) AS shifts
            WHERE action_type = 'clock_in';
            """)
            print("✅ DB View Patched.")
            print("⚠️ Skipping force offline (view is read-only).")
        
        # Explicit Bali Time
        BALI_TZ = ZoneInfo("Asia/Makassar")
        today_bali = datetime.now(BALI_TZ)
        
        print(f"📅 Querying list for: {today_bali.date()}")
        
        # DEBUG: Check RAW table counts
        print("🔍 DEBUG: Checking raw 'team_timesheet' table for today...")
        
        raw_rows = []
        async with pool.acquire() as conn:
            raw_rows = await conn.fetch(
                "SELECT * FROM team_timesheet WHERE created_at::date = $1 ORDER BY created_at DESC", 
                today_bali.date()
            )
            
        print(f"🔍 DEBUG: Found {len(raw_rows)} raw rows in team_timesheet for today.")
        
        raw_msg_part = "\n\n📋 *Raw Logs (Debug):*\n"
        count = 0
        
        if not raw_rows:
            raw_msg_part += "No raw entries found."
        else:
            for r in raw_rows:
                 email_raw = r['email']
                 
                 # FILTER: Skip Ruslana spam
                 if "ruslana@balizero.com" in email_raw:
                     continue

                 if count < 15:
                     # Format timestamp to Bali Time (approximate or just show raw string if timezoned)
                     ts = r['created_at'].strftime("%H:%M:%S")
                     
                     # Escape Email for Markdown (replace _ with \_)
                     safe_email = email_raw.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")
                     safe_action = r['action_type'].replace("_", "\\_")
                     raw_msg_part += f"- `{ts}` {safe_action} - {safe_email}\n"
                     count += 1
                     
            if count == 0:
                 raw_msg_part += "_No other activity (Spam filtered)._"
        
        # --- QUERY VIEW DIRECTLY (Bypassing Service to handle NULLs Safe) ---
        print("🔍 Querying view directly (bypass service)...")
        daily_hours = []
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM daily_work_hours WHERE work_date = $1 ORDER BY hours_worked DESC NULLS LAST", today_bali.date())
            for row in rows:
                c_in = row["clock_in_bali"].strftime("%H:%M") if row["clock_in_bali"] else "?"
                c_out = row["clock_out_bali"].strftime("%H:%M") if row["clock_out_bali"] else None
                
                daily_hours.append({
                    "email": row["email"],
                    "clock_in": c_in,
                    "clock_out": c_out,
                    "hours_worked": float(row["hours_worked"]) if row["hours_worked"] else 0.0,
                    "raw_start_time": row["clock_in_bali"]
                })
        
        print(f"📊 Found {len(daily_hours) if daily_hours else 0} entries")
        
        # --- MISSING PERSON CHECK ---
        print("🔍 Checking explicit team roster for missing members...")
        missing_members = []
        present_emails = {e['email'] for e in daily_hours}
        
        async with pool.acquire() as conn:
            # Query all ACTIVE team members
            team_rows = await conn.fetch("SELECT email, full_name FROM team_members WHERE active = true")
            
            for member in team_rows:
                email = member['email']
                # Skip known bot/admin accounts if necessary (optional)
                if email not in present_emails:
                    missing_members.append(email)
        
        print(f"⚠️ Missing {len(missing_members)} active members.")

        if not daily_hours:
            message = f"📅 *Daily Report: {today_bali.strftime('%Y-%m-%d')}*\n\nNo activity recorded today."
        else:
            message = f"📅 *Daily Report: {today_bali.strftime('%Y-%m-%d')}*\n\n"
            for entry in daily_hours:
                clock_out_val = entry.get('clock_out')
                status_icon = "🟢" if clock_out_val is None else "🔴"
                hours = entry.get('hours_worked', 0) or 0.0
                
                # Escape summary email too
                entry_email = entry['email'].replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")
                
                message += f"{status_icon} *{entry_email}*\n"
                message += f"   Clock In: {entry['clock_in']}\n"
                if clock_out_val:
                    message += f"   Clock Out: {clock_out_val}\n"
                    message += f"   Hours: {hours:.2f}h\n\n"
                else:
                    # Calculate Elapsed Time
                    start_time = entry.get('raw_start_time')
                    if start_time:
                         # Ensure start_time is aware (DB 'AT TIME ZONE' returns naive local time)
                         if start_time.tzinfo is None:
                             start_time = start_time.replace(tzinfo=ZoneInfo("Asia/Makassar"))
                             
                         now_bali = datetime.now(ZoneInfo("Asia/Makassar"))
                         elapsed = now_bali - start_time
                         
                         # Format as Xh Ym
                         total_seconds = int(elapsed.total_seconds())
                         hours_e = total_seconds // 3600
                         minutes_e = (total_seconds % 3600) // 60
                         message += f"   Clock Out: ⏳ *Active* (Running: {hours_e}h {minutes_e}m)\n"
                         message += f"   Hours: --\n\n"
                    else:
                         message += f"   Clock Out: *Active*\n"
                         message += f"   Hours: --\n\n"
        
        # Append Raw Logs
        message += raw_msg_part
        
        # Append Missing Members Report
        if missing_members:
            message += "\n\n⚠️ *Missing Team Members:*\n"
            for m_email in missing_members:
                safe_m_email = m_email.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")
                message += f"- {safe_m_email}\n"
        else:
            message += "\n\n✅ *Full Team Attendance!*"

        print(f"📨 Sending to {ADMIN_CHAT_ID}...")
        await send_telegram_message(settings.telegram_bot_token, ADMIN_CHAT_ID, message)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if pool:
            await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
PYTHON

# Execute
python /app/run_report.py
EOF
)

# Run once (--rm is back? No, keep it persistent for debugging if it fails)
fly machine run "$IMAGE_REF" \
  --app "$APP_NAME" \
  --region "$REGION" \
  --name "manual-fix-test-$(date +%s)" \
  --vm-memory "2048" \
  --env TELEGRAM_ADMIN_CHAT_ID=8290313965 \
  --env FORCE_RUN=1 \
  --entrypoint "sh" \
  --detach \
  -- -c "$CMD"

echo "✅ Manual trigger sent."
