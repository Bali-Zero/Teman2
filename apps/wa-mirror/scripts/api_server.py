#!/usr/bin/env python3
import asyncio
import json
import os
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
# `~/Desktop/nuzantara` still resolves on the Pro, but only because a compat
# symlink survives the 2026-07-16 move out of Desktop (W84/TCC). `_lib.sh`, the
# launcher's own source of truth, says `$HOME/nuzantara/apps/wa-mirror` — two
# files disagreeing about where wa-mirror lives is how the session-linked column
# silently reads the wrong tree the day someone tidies the symlink away.
WA_MIRROR_DIR = Path(
    os.environ.get("WA_MIRROR_DIR") or (HOME / "nuzantara" / "apps" / "wa-mirror")
)
PID_DIR = Path("/tmp/wa-mirror-pids")
LOG_DIR = Path("/tmp/wa-mirror-logs")
SCRIPT_DIR = HOME / "scripts" / "wa-mirror-launcher"

# Database configuration. Golden Rule #6: never a literal here.
#
# This file carried a hardcoded production DSN — user, password and all — for as
# long as it lived HOME-only. Tracking it in a PUBLIC repo turns that literal into
# a publication, so the credential is read from the environment and the process
# refuses to start without it rather than falling back to anything.
#
# On the Pro the value is already in ~/.nuzantara-secrets.env (0600):
#   set -a; . ~/.nuzantara-secrets.env; set +a
# The port is the local proxy tunnel (`ssh -L 15432:localhost:15432 pro`), so this
# never dials production directly.
DB_DSN = os.environ.get("WA_LAUNCHER_DB_DSN") or os.environ.get("DATABASE_URL")
if not DB_DSN:
    raise SystemExit(
        "FATAL: no database DSN. Export WA_LAUNCHER_DB_DSN (or DATABASE_URL) — "
        "e.g. `set -a; . ~/.nuzantara-secrets.env; set +a` — and start again. "
        "This server deliberately has no built-in fallback: a default here is how "
        "a production credential ends up in a public repo."
    )
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


def roster_account(name: str) -> dict | None:
    """Map a caller-supplied employee name to its roster record, or None.

    Every filesystem path and subprocess argument downstream is built from the
    RETURNED record — never from the caller's string. That distinction is the
    whole fix: the endpoints already refused unknown names, but they then went
    on to use the *request* value to build the path, so the tainted value still
    reached the sink. A guard that only raises does not sanitise anything; one
    that returns the trusted value does. Concretely, `/api/accounts/{name}/logs`
    can now only ever open a log file named after a roster entry, even if this
    comparison were subtly wrong (case folding, unicode, stray whitespace).
    """
    wanted = name.strip().lower()
    if not wanted:
        return None
    for acc in load_accounts():
        roster_name = str(acc.get("name", "")).strip().lower()
        if roster_name and roster_name == wanted:
            return acc
    return None


def roster_stem(acc: dict) -> str:
    """The lowercase roster name, the only value allowed to name a file."""
    return str(acc.get("name", "")).strip().lower()


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
        except OSError as exc:
            # Say so in the field the dashboard renders. An empty string here is
            # indistinguishable from "the daemon has logged nothing", which is
            # the shape that lets a broken read read as a quiet account.
            last_log = f"[log unreadable: {type(exc).__name__}]"

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
    acc_info = roster_account(name)
    if acc_info is None:
        raise HTTPException(status_code=404, detail="Employee not found in roster.")

    # Roster-derived from here down: nothing the caller typed reaches argv.
    name_clean = roster_stem(acc_info)

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

        new_status = get_account_status(name_clean, str(acc_info.get("e164", "")))
        
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
    acc_info = roster_account(name)
    if acc_info is None:
        raise HTTPException(status_code=404, detail="Employee not found.")

    # Roster-derived: the filename can only ever be a name the roster carries.
    name_clean = roster_stem(acc_info)
    log_file = LOG_DIR / f"{name_clean}.log"

    # Belt and braces. The containment check is deliberately OUTSIDE the try:
    # in the previous version the `raise HTTPException(403)` sat inside a
    # `try: ... except Exception:` block, so the guard's own refusal was caught
    # by its own handler and re-raised as a 400 — it still refused, but a guard
    # whose raise is swallowed by its own except is one edit away from passing.
    try:
        resolved_path = log_file.resolve()
        log_root = LOG_DIR.resolve()
    except OSError:
        raise HTTPException(status_code=400, detail="Invalid file path.")
    if resolved_path.parent != log_root:
        raise HTTPException(status_code=403, detail="Access denied.")

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
