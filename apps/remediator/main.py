import asyncio
import json
import logging
import os
import signal
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import httpx
import redis.asyncio as aioredis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [REMEDIATOR] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("remediator")

_shutdown = asyncio.Event()

DB_PATH = os.environ.get("REMEDIATOR_DB_PATH", "remediator.sqlite")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS remediation_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_id TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.commit()

def get_last_redis_id() -> str:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT value FROM state WHERE key = 'last_redis_id'")
        row = cursor.fetchone()
        return row[0] if row else "$"

def set_last_redis_id(redis_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO state (key, value) VALUES ('last_redis_id', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (redis_id, redis_id)
        )
        conn.commit()

def record_attempt(event_id: str, action: str, status: str):
    ts = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO remediation_attempts (timestamp, event_id, action, status) VALUES (?, ?, ?, ?)",
            (ts, event_id, action, status)
        )
        conn.commit()

def count_attempts_in_last_hour() -> int:
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM remediation_attempts WHERE timestamp >= ?",
            (one_hour_ago,)
        )
        row = cursor.fetchone()
        return row[0] if row else 0

def get_last_attempt_time() -> datetime | None:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT timestamp FROM remediation_attempts ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            return datetime.fromisoformat(row[0])
        return None

async def send_telegram_alert(message: str):
    bot_token = os.environ.get("CELL_TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("CELL_TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        logger.warning("Telegram token/chat not configured. Skipping alert.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": f"🚨 [REMEDIATOR] {message}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=10.0)
            resp.raise_for_status()
            logger.info("Telegram alert sent.")
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

async def execute_remediation(event_id: str) -> bool:
    action = "fly apps restart nuzantara-rag"
    logger.info(f"Executing L2 Remediation: {action}")
    try:
        # Fly restart action
        proc = await asyncio.create_subprocess_exec(
            "fly", "apps", "restart", "nuzantara-rag",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            logger.info("Remediation successful.")
            record_attempt(event_id, action, "success")
            return True
        else:
            logger.error(f"Remediation failed. stderr: {stderr.decode()}")
            record_attempt(event_id, action, "failure")
            return False
    except Exception as e:
        logger.error(f"Remediation error: {e}")
        record_attempt(event_id, action, f"error: {str(e)}")
        return False

def _handle_signal(sig: int, frame: object) -> None:
    logger.info(f"Received signal {sig}, shutting down...")
    _shutdown.set()

async def process_event(event_id: str, data: dict):
    # Parse event
    if data.get("kind") != "cell_pulse":
        return
    
    payload = data.get("payload", {})
    health = payload.get("health")
    if health != "red":
        return

    logger.warning(f"Detected red cell_pulse event: {event_id}")

    # Check cooldowns
    last_attempt = get_last_attempt_time()
    now = datetime.now(timezone.utc)
    if last_attempt and (now - last_attempt) < timedelta(minutes=5):
        logger.info("Cooldown active (5m). Skipping remediation.")
        return

    attempts_last_hour = count_attempts_in_last_hour()
    if attempts_last_hour >= 3:
        logger.critical("Max attempts (3/hr) reached. Escalating to L3 Telegram.")
        await send_telegram_alert(
            "System is critically degraded (health=red). "
            f"L2 Autoremediation failed after {attempts_last_hour} attempts in the last hour. "
            "Operator intervention required."
        )
        # Add a dummy record so we don't spam telegram every pulse (will wait 5m)
        record_attempt(event_id, "telegram_escalation", "success")
        return

    # Execute
    await execute_remediation(event_id)

async def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    init_db()

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    logger.info(f"Connected to Redis at {redis_url.split('@')[-1]}")

    last_id = get_last_redis_id()
    logger.info(f"Starting read from Redis stream organism:events at ID {last_id}")

    while not _shutdown.is_set():
        try:
            # Block for 5 seconds
            streams = await redis_client.xread(
                {"organism:events": last_id}, 
                count=10, 
                block=5000
            )
            
            if not streams:
                continue

            for stream_name, messages in streams:
                for message_id, message_data in messages:
                    # message_data format: {"data": "json string"}
                    raw_data = message_data.get("data")
                    if raw_data:
                        try:
                            event_data = json.parse(raw_data) if hasattr(json, 'parse') else json.loads(raw_data)
                            await process_event(message_id, event_data)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse event data: {raw_data}")
                    last_id = message_id
            
            set_last_redis_id(last_id)

        except aioredis.exceptions.ConnectionError:
            logger.error("Redis connection error. Retrying in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Event loop error: {e}")
            await asyncio.sleep(1)

    await redis_client.aclose()
    logger.info("Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
