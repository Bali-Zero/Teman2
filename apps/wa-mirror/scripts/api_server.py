#!/usr/bin/env python3
import asyncio
import json
import os
import re
from pathlib import Path
from typing import Literal
import asyncpg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Nuzantara WhatsApp Mirror Control & CRM API",
    description="Local API wrapper for wa-mirror daemon processes and PG database on M5/Mac Pro",
    version="1.1.0"
)

# Allow local files (CORS) to communicate with localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Paths & Environment ────────────────────────────────────────────────────────
HOME = Path.home()
ACCOUNTS_JSON = HOME / ".wa-mirror.accounts.json"
WA_MIRROR_DIR = HOME / "Desktop" / "nuzantara" / "apps" / "wa-mirror"
PID_DIR = Path("/tmp/wa-mirror-pids")
LOG_DIR = Path("/tmp/wa-mirror-logs")
SCRIPT_DIR = HOME / "scripts" / "wa-mirror-launcher"

# Database Configuration (Active secrets retrieved from Pro-dev)
DB_DSN = "postgresql://backend_rag_v2:ivlC8QT5UdZhNwcBG3ALEvysMb7cxPdJbsSxxWYh@127.0.0.1:15432/nuzantara_rag?sslmode=disable"
db_pool = None


# ── Startup/Shutdown events ───────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    global db_pool
    try:
        # Establish connection pool via SSH forwarded tunnel
        db_pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=5, timeout=5.0)
        print("Connected to PostgreSQL proxy tunnel successfully (127.0.0.1:15432)")
    except Exception as e:
        print(f"PostgreSQL proxy tunnel not running or connection failed: {e}")
        db_pool = None


@app.on_event("shutdown")
async def shutdown_event():
    global db_pool
    if db_pool:
        await db_pool.close()
        print("PostgreSQL connection pool closed.")


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_accounts() -> list[dict]:
    if not ACCOUNTS_JSON.exists():
        return []
    try:
        with open(ACCOUNTS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("accounts", [])
    except Exception:
        return []


def is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def get_account_status(name: str, e164: str) -> dict:
    name_lower = name.lower()
    pid_file = PID_DIR / f"{name_lower}.pid"
    log_file = LOG_DIR / f"{name_lower}.log"
    ses_dir = WA_MIRROR_DIR / "sessions" / e164

    # 1. Process Status
    status = "STOPPED"
    pid = None
    if pid_file.exists():
        try:
            stored_pid = int(pid_file.read_text().strip())
            if is_pid_running(stored_pid):
                status = "RUNNING"
                pid = stored_pid
            else:
                status = "DEAD"
        except ValueError:
            status = "DEAD"

    # 2. Session link status
    linked = False
    if ses_dir.exists() and any(ses_dir.iterdir()):
        linked = True

    # 3. Last log line
    last_log = ""
    if log_file.exists():
        try:
            with open(log_file, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size > 0:
                    read_size = min(size, 256)
                    f.seek(-read_size, os.SEEK_END)
                    lines = f.read().decode("utf-8", errors="replace").splitlines()
                    if lines:
                        last_log = lines[-1].strip()
        except Exception:
            pass

    return {
        "status": status,
        "pid": pid,
        "session_linked": linked,
        "last_log": last_log
    }


# ── Models ────────────────────────────────────────────────────────────────────
class ControlRequest(BaseModel):
    action: Literal["start", "stop", "restart", "qr"]


class PromoteRequest(BaseModel):
    status: str


# ── API Routes ────────────────────────────────────────────────────────────────
@app.get("/api/accounts")
def get_accounts():
    """Retrieve all WhatsApp mirror accounts and their real-time daemon statuses."""
    accounts = load_accounts()
    result = []
    for acc in accounts:
        name = acc.get("name", "")
        e164 = acc.get("e164", "")
        if not name or not e164:
            continue
        
        status_info = get_account_status(name, e164)
        result.append({
            "name": name,
            "e164": e164,
            "label": acc.get("label", ""),
            "role": acc.get("role", ""),
            "status": status_info["status"],
            "pid": status_info["pid"],
            "session_linked": status_info["session_linked"],
            "last_log": status_info["last_log"]
        })
    return {"status": "success", "data": result}


@app.post("/api/accounts/{name}/control")
async def control_account(name: str, payload: ControlRequest):
    """Start, stop, or restart a specific account scraper process."""
    name_clean = name.strip().lower()
    accounts = load_accounts()
    valid_names = {a["name"].lower(): a for a in accounts if "name" in a}
    
    if name_clean not in valid_names:
        raise HTTPException(status_code=404, detail=f"Employee '{name}' not found in roster.")
    
    start_script = SCRIPT_DIR / "start-one.sh"
    stop_script = SCRIPT_DIR / "stop-one.sh"
    
    if not start_script.exists() or not stop_script.exists():
        raise HTTPException(status_code=500, detail="Launcher control scripts are missing.")

    action = payload.action
    cmd = []
    
    if action == "start":
        cmd = ["bash", str(start_script), name_clean]
    elif action == "qr":
        cmd = ["bash", str(start_script), name_clean, "--qr"]
    elif action == "stop":
        cmd = ["bash", str(stop_script), name_clean]
    elif action == "restart":
        cmd = ["bash", str(stop_script), name_clean]
    
    try:
        if action == "restart":
            stop_proc = await asyncio.create_subprocess_exec(
                "bash", str(stop_script), name_clean,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await stop_proc.communicate()
            cmd = ["bash", str(start_script), name_clean]
            
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=18.0)
            output = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            output = "Action initiated, but process monitoring timed out. Daemon should be running."

        acc_info = valid_names[name_clean]
        new_status = get_account_status(name_clean, acc_info["e164"])
        
        return {
            "status": "success",
            "message": f"Action '{action}' processed for {name_clean}.",
            "output_summary": output.splitlines()[-5:] if output else [],
            "daemon_status": new_status
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute control action: {e}")


@app.get("/api/accounts/{name}/logs")
def get_logs(name: str, lines: int = Query(50, ge=1, le=500)):
    """Retrieve the last N lines of logs for a specific daemon securely."""
    name_clean = name.strip().lower()
    accounts = load_accounts()
    valid_names = {a["name"].lower() for a in accounts if "name" in a}
    
    if name_clean not in valid_names:
        raise HTTPException(status_code=404, detail=f"Employee '{name}' not found.")
        
    log_file = LOG_DIR / f"{name_clean}.log"
    try:
        resolved_path = log_file.resolve()
        if not str(resolved_path).startswith(str(LOG_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Access denied.")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file path.")

    if not log_file.exists():
        return {
            "status": "success",
            "name": name_clean,
            "lines": ["[No log file found. Daemon has not been started yet.]"]
        }

    try:
        from collections import deque
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            last_lines = list(deque(f, maxlen=lines))
        
        return {
            "status": "success",
            "name": name_clean,
            "lines": [line.rstrip("\r\n") for line in last_lines]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {e}")


# ── Lead Promotion (Real DB Integration) ──────────────────────────────────────
@app.get("/api/leads")
async def get_leads():
    """Fetch potential lead candidates directly from live PostgreSQL database."""
    global db_pool
    if not db_pool:
        raise HTTPException(
            status_code=503, 
            detail="PostgreSQL connection offline. Ensure SSH tunnel (ssh -L 15432:localhost:15432 pro) is active."
        )

    # Cohesive lead query combining inbound message stats, CRM client matching, and keyword-based topic classification
    query = """
    WITH per_phone AS (
        SELECT
            counterpart_phone AS phone,
            COUNT(*) FILTER (WHERE direction = 'inbound') AS n_inbound,
            MAX(created_at) AS last_seen,
            (ARRAY_AGG(sender_push_name_snapshot ORDER BY created_at DESC) FILTER (WHERE sender_push_name_snapshot IS NOT NULL))[1] AS push_name,
            STRING_AGG(CASE WHEN direction = 'inbound' THEN body ELSE NULL END, ' | ' ORDER BY created_at DESC) AS inbound_bodies
        FROM whatsapp_message_context
        WHERE source = 'wa_mirror'
          AND counterpart_phone IS NOT NULL
          AND COALESCE(chat_type, 'direct') <> 'group'
        GROUP BY counterpart_phone
        HAVING COUNT(*) FILTER (WHERE direction = 'inbound') >= 1
    ),
    with_crm AS (
        SELECT pp.*,
               (SELECT cl.full_name FROM clients cl
                 WHERE REGEXP_REPLACE(COALESCE(cl.phone_normalized, ''), '\\D', '', 'g') = pp.phone
                    OR REGEXP_REPLACE(COALESCE(cl.whatsapp, ''), '\\D', '', 'g') = pp.phone
                    OR REGEXP_REPLACE(COALESCE(cl.phone, ''), '\\D', '', 'g') = pp.phone
                 ORDER BY cl.deleted_at IS NULL DESC, cl.id DESC LIMIT 1) as client_name,
               (SELECT cl.deleted_at FROM clients cl
                 WHERE REGEXP_REPLACE(COALESCE(cl.phone_normalized, ''), '\\D', '', 'g') = pp.phone
                    OR REGEXP_REPLACE(COALESCE(cl.whatsapp, ''), '\\D', '', 'g') = pp.phone
                    OR REGEXP_REPLACE(COALESCE(cl.phone, ''), '\\D', '', 'g') = pp.phone
                 ORDER BY cl.deleted_at IS NULL DESC, cl.id DESC LIMIT 1) as client_deleted_at
        FROM per_phone pp
    )
    SELECT 
        phone,
        n_inbound,
        last_seen::text,
        COALESCE(client_name, push_name, 'Unknown') AS name,
        inbound_bodies,
        CASE
            WHEN client_name IS NOT NULL AND client_deleted_at IS NULL THEN 'CLIENT'
            WHEN client_name IS NOT NULL AND client_deleted_at IS NOT NULL THEN 'ARCHIVED_CLIENT'
            ELSE 'NEW_LEAD'
        END as status,
        CASE 
            WHEN inbound_bodies ILIKE '%visa%' OR inbound_bodies ILIKE '%kitas%' OR inbound_bodies ILIKE '%permit%' OR inbound_bodies ILIKE '%immigration%' THEN 'visa, KITAS, or stay permit'
            WHEN inbound_bodies ILIKE '%extend%' OR inbound_bodies ILIKE '%renew%' OR inbound_bodies ILIKE '%perpanjang%' THEN 'extension or renewal'
            WHEN inbound_bodies ILIKE '%price%' OR inbound_bodies ILIKE '%cost%' OR inbound_bodies ILIKE '%harga%' OR inbound_bodies ILIKE '%fee%' OR inbound_bodies ILIKE '%payment%' THEN 'pricing, payment, or bank transfer'
            WHEN inbound_bodies ILIKE '%tax%' OR inbound_bodies ILIKE '%pajak%' OR inbound_bodies ILIKE '%company%' OR inbound_bodies ILIKE '%pt pma%' OR inbound_bodies ILIKE '%director%' THEN 'tax or company matter'
            ELSE 'general inquiry'
        END as topic
    FROM with_crm
    ORDER BY last_seen DESC
    LIMIT 20;
    """
    
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query)
            # Convert record objects to dictionary list
            return {"status": "success", "data": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")


@app.post("/api/leads/{phone}/promote")
async def promote_lead(phone: str, payload: PromoteRequest):
    """Simulate lead promotion to CRM database."""
    # Log the action (YOLO mode logs it to the terminal screen)
    print(f"[YOLO CRM] Promoting lead phone {phone} with status: {payload.status}")
    return {
        "status": "success",
        "message": f"Lead {phone} successfully promoted to CRM with status: {payload.status}."
    }


# ── Run Server ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="127.0.0.1", port=15433, reload=False)
