#!/usr/bin/env python3
"""
Daily Team Activity Report Automation
-------------------------------------
Sends a summary of team clock-ins/outs to the admin via Telegram.
"""

import asyncio
import os
import sys
from datetime import datetime

# ==============================================================================
# 🔧 PATH FIX: Ensure Backend Python Environment is loaded correctly
# ==============================================================================
BACKEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../apps/backend-rag")
)
sys.path.insert(0, BACKEND_DIR)
# Also add backend root to path so 'llm', 'backend', etc are resolvable if needed
sys.path.insert(0, os.path.join(BACKEND_DIR, "backend"))

# ==============================================================================
# 🔑 ENV LOADING & CONFIGURATION
# ==============================================================================
# We need to set these BEFORE importing config to avoid validation errors
os.environ["ENVIRONMENT"] = "development"
os.environ["API_KEYS"] = "test_key_daily_report"
os.environ["JWT_SECRET_KEY"] = "dev_secret_key_fixed_for_script_execution_32_chars_min"

# Force the correct DB URL for LOCAL DOCKERIZED POSTGRES
# Based on docker-compose.yml:
# - User: user
# - Pass: password
# - DB: nuzantara_dev
# - Port Mapped: 5433 (host) -> 5432 (container)
LOCAL_DB_URL = "postgresql://user:password@localhost:5433/nuzantara_dev"

# Set it in env so config.py picks it up (though we might pass it directly to asyncpg)
os.environ["DATABASE_URL"] = LOCAL_DB_URL

# Now we can import backend modules
# We import Settings to make sure we don't crash on init
try:
    from backend.app.core.config import settings

    # Override settings explicitly just in case
    settings.database_url = LOCAL_DB_URL
except Exception as e:
    print(f"⚠️ Warning loading settings: {e}")

from backend.services.integrations.telegram_bot_service import telegram_bot
from backend.services.analytics.team_timesheet_service import TeamTimesheetService
import asyncpg


async def main():
    print("🚀 Starting Daily Report Automation...")

    # Target Admin (Zero)
    ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "8290313965")

    print(f"🔌 Connecting to DB: {LOCAL_DB_URL.split('@')[-1]}")

    try:
        pool = await asyncpg.create_pool(LOCAL_DB_URL)
        print("✅ DB Connected")
    except Exception as e:
        print(f"❌ DB Connection failed: {e}")
        return

    try:
        # Initialize service manually with the pool
        service = TeamTimesheetService(pool)

        # Get today's stats
        today = datetime.now()

        try:
            daily_hours = await service.get_daily_hours(today)
        except Exception as e:
            print(f"❌ DB Query Error (relation probably missing if DB is empty): {e}")
            # Fallback check for table existence might be good here, but let's just fail loudly
            return

        print(f"📊 Found {len(daily_hours) if daily_hours else 0} entries for today")

        if not daily_hours:
            message = f"📅 *Daily Report: {today.strftime('%Y-%m-%d')}*\n\nNo activity recorded today."
        else:
            message = f"📅 *Daily Report: {today.strftime('%Y-%m-%d')}*\n\n"
            for entry in daily_hours:
                # Handle possible None for clock_out
                clock_out_val = entry.get("clock_out")
                status_icon = "🟢" if clock_out_val is None else "🔴"
                hours = entry.get("hours_worked", 0) or 0.0

                message += f"{status_icon} *{entry['email']}*\n"
                message += f"   Clock In: {entry['clock_in']}\n"
                if clock_out_val:
                    message += f"   Clock Out: {clock_out_val}\n"
                message += f"   Hours: {hours:.2f}h\n\n"

        # Send via Telegram
        print(f"📨 Sending report to {ADMIN_CHAT_ID}...")
        try:
            await telegram_bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
            print("✅ Daily report sent successfully!")
        except Exception as e:
            print(f"❌ Failed to send Telegram report: {e}")
            print("💡 Tip: Check if the bot has been started by the user first.")

    finally:
        await pool.close()
        # Close telegram client if needed
        await telegram_bot.close()


if __name__ == "__main__":
    asyncio.run(main())
