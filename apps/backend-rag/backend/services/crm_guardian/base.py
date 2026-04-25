"""CRM Guardian base primitives — shared by all invariants.

Design principles:
 - No delete, only trash (reversible 30 days on Google Drive).
 - Every action recorded in crm_guardian_events (append-only, blocked UPDATE/DELETE).
 - Each invariant respects global kill switch + per-invariant enabled/dry_run flags.
 - Hard rate limits: max operations per run, max errors before circuit-breaker trip.
 - Idempotent: reprocessing the same target must not create duplicate side-effects.
"""
from __future__ import annotations

import glob
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)


# ============================================================
# Classification of each client vs CRM state (R1..R5)
# ============================================================
class Rule(str, Enum):
    """Five mutually-exclusive outcomes for each client scanned by the deep audit."""

    R1_TEST_DATA = "R1_test_data"           # name contains test/demo/autocheck → archive
    R2_CLEAN = "R2_clean"                   # has canonical, zero satellites → no-op
    R3_MERGE = "R3_merge"                   # has canonical, satellites → consolidate
    R4_PROVISION_CONSOLIDATE = "R4_provision_consolidate"  # no canonical, satellites → create + move
    R5_PROVISION_ONLY = "R5_provision_only"  # no canonical, no satellites → just create

    SKIP_TEAM_INTERNAL = "SKIP_team_internal"  # status == team_internal
    SKIP_ARCHIVED = "SKIP_archived"             # status == archived
    SKIP_EXCEPTION = "SKIP_exception"           # listed in crm_guardian_exceptions
    SKIP_ANTONELLO = "SKIP_antonello"           # client_id == 68 (owner himself)


TEST_NAME_MARKERS: tuple[str, ...] = ("test", "demo", "autocheck")
OWNER_CLIENT_ID = 68  # Antonello Siano — always excluded


def compute_rule(plan_row: dict, *, exceptions: set[tuple[str, str]] | None = None) -> Rule:
    """Classify one client from the deep_audit plan.jsonl row into an action rule.

    Args:
        plan_row: dict matching the shape produced by scripts/crm_guardian_deep_audit.py
        exceptions: set of (target_type, target_id) tuples currently valid in
                    crm_guardian_exceptions for this invariant.

    Returns:
        Rule value — consumers dispatch to the matching handler.
    """
    cid = plan_row["client_id"]

    if exceptions and ("client", str(cid)) in exceptions:
        return Rule.SKIP_EXCEPTION

    if cid == OWNER_CLIENT_ID:
        return Rule.SKIP_ANTONELLO

    status = (plan_row.get("status") or "").lower()
    if status == "team_internal":
        return Rule.SKIP_TEAM_INTERNAL
    if status == "archived":
        return Rule.SKIP_ARCHIVED

    name = plan_row.get("full_name", "").lower()
    if any(m in name for m in TEST_NAME_MARKERS):
        return Rule.R1_TEST_DATA

    has_canonical = bool(plan_row.get("has_canonical"))
    n_satellites = int(plan_row.get("n_satellites") or 0)

    if has_canonical and n_satellites == 0:
        return Rule.R2_CLEAN
    if has_canonical and n_satellites >= 1:
        return Rule.R3_MERGE
    if not has_canonical and n_satellites >= 1:
        return Rule.R4_PROVISION_CONSOLIDATE
    return Rule.R5_PROVISION_ONLY


# ============================================================
# Config + run context
# ============================================================
@dataclass
class GuardianConfig:
    """Runtime config resolved from crm_guardian_state.config + env + defaults."""

    dry_run: bool = True
    batch_size: int = 10
    max_ops_per_client: int = 500
    max_total_errors: int = 50   # trip circuit breaker (raised from 10 for batch runs)
    min_confidence: float = 0.6
    individual_crm_id: str = "1mNi2FkhZqP9inJH2Y1taXLCgS95UkYk4"
    companies_id: str = "1PGRBCSzXc8T3LYqEB1-hucBaH2YW77Av"


@dataclass
class GuardianRunContext:
    """Per-run context: one run_id ties all events from a single invocation."""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    invariant_id: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    config: GuardianConfig = field(default_factory=GuardianConfig)
    error_count: int = 0
    op_count: int = 0

    def bump_errors(self) -> None:
        self.error_count += 1

    def bump_ops(self) -> None:
        self.op_count += 1


# ============================================================
# Action + event dataclasses
# ============================================================
class GuardianAction(str, Enum):
    CREATE_FOLDER = "create_folder"
    CREATE_SUBFOLDER = "create_subfolder"
    MOVE_FILE = "move_file"
    MOVE_FOLDER = "move_folder"
    TRASH_FOLDER = "trash_folder"
    UPDATE_DB_FOLDER_ID = "update_db_folder_id"
    GENERATE_SUMMARY = "generate_summary"
    WRITE_BRIEF = "write_brief"
    SYNC_NOTEBOOK = "sync_notebook"
    SKIP = "skip"
    ERROR = "error"
    DRY_RUN = "dry_run"


@dataclass
class GuardianEvent:
    """One row to insert into crm_guardian_events."""

    invariant_id: str
    action: GuardianAction
    target_type: str
    target_id: str
    status: str              # 'success' | 'partial' | 'error' | 'dry_run' | 'skipped'
    client_id: Optional[int] = None
    before_state: Optional[dict[str, Any]] = None
    after_state: Optional[dict[str, Any]] = None
    dry_run: bool = False
    run_id: Optional[str] = None
    notes: Optional[str] = None
    error_message: Optional[str] = None


async def record_event(conn: asyncpg.Connection, event: GuardianEvent) -> None:
    """Append one row to crm_guardian_events. Never fails the caller's flow."""
    try:
        await conn.execute(
            """
            INSERT INTO crm_guardian_events
                (invariant_id, action, target_type, target_id, client_id,
                 before_state, after_state, status, dry_run, run_id, notes, error_message)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::uuid, $11, $12)
            """,
            event.invariant_id,
            event.action.value,
            event.target_type,
            event.target_id,
            event.client_id,
            json.dumps(event.before_state) if event.before_state is not None else None,
            json.dumps(event.after_state) if event.after_state is not None else None,
            event.status,
            event.dry_run,
            event.run_id,
            event.notes,
            event.error_message,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("failed to record guardian event: %s", exc)


# ============================================================
# Drive service resolution
# ============================================================
def build_drive_service(prefer_user_oauth: bool = True):
    """Return a Drive v3 service client.

    With prefer_user_oauth=True (default): use the SYSTEM-user OAuth refresh
    token stored in google_drive_tokens — this identity is `antonellosiano@gmail.com`
    (30TB storage, the canonical Bali Zero owner). Every folder created under
    this identity is owned by antonellosiano, so we consolidate ownership and
    avoid the "folder owned by a random team member" fragmentation.

    With prefer_user_oauth=False: fall back to the service account JSON (used
    for read-only enumeration of folders the user token can't see, or when
    called outside the backend app context).
    """
    from googleapiclient.discovery import build

    if prefer_user_oauth:
        try:
            return _build_oauth_user_drive()
        except Exception as exc:  # noqa: BLE001
            # Log and fall through to SA fallback.
            import logging
            logging.getLogger(__name__).warning(
                "OAuth user drive unavailable, falling back to service account: %s", exc
            )

    return _build_service_account_drive()


def _build_oauth_user_drive():
    """Load SYSTEM user OAuth token, refresh if expired, return Drive v3 service.

    This function runs synchronously from whatever thread calls it. When called
    from inside an asyncio loop (e.g. guardian apply path), using asyncpg would
    trigger `asyncio.run() cannot be called from a running event loop` — so we
    talk to Postgres via psycopg2 (sync) instead.
    """
    import os
    import psycopg2
    from datetime import datetime, timezone, timedelta
    import httpx
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    # Load env for OAuth client id/secret and DB URL
    env_file = Path(__file__).resolve().parents[4] / "apps" / "backend-rag" / ".env"
    if not env_file.exists():
        env_file = Path.home() / "Desktop/nuzantara/apps/backend-rag/.env"
    env: dict[str, str] = {}
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()

    # When running inside Fly, DATABASE_URL points to flycast; for local Pro
    # batches we use the flyctl-proxy rewrite (localhost:15432) already applied
    # to .nuzantara-secrets.env, so prefer that if present.
    db_url = env.get("DATABASE_URL", "")
    secrets_file = Path.home() / ".nuzantara-secrets.env"
    if secrets_file.exists():
        for line in secrets_file.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                raw = line.split("=", 1)[1].strip().strip('"')
                import re as _re
                db_url = _re.sub(r"@[^:/]+(\.internal)?:\d+", "@localhost:15432", raw)
                break

    client_id = env.get("GOOGLE_CLIENT_ID") or env.get("GOOGLE_DRIVE_CLIENT_ID")
    client_secret = env.get("GOOGLE_CLIENT_SECRET") or env.get("GOOGLE_DRIVE_CLIENT_SECRET")
    if not (db_url and client_id and client_secret):
        raise RuntimeError("Missing DATABASE_URL / GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET in .env")

    # psycopg2 expects postgresql:// (not postgres://)
    psy_url = db_url.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(psy_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT access_token, refresh_token, expires_at FROM google_drive_tokens WHERE user_id = 'SYSTEM'"
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("No SYSTEM OAuth token in google_drive_tokens")
            access_token, refresh_token, expires_at = row
    finally:
        conn.close()

    # Refresh if expired or within 2 min of expiry
    if expires_at < datetime.now(timezone.utc) + timedelta(minutes=2):
        r = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        if r.status_code != 200:
            raise RuntimeError(f"OAuth refresh failed ({r.status_code}): {r.text[:200]}")
        data = r.json()
        access_token = data["access_token"]
        new_exp = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(
            seconds=data.get("expires_in", 3600) - 60
        )
        conn = psycopg2.connect(psy_url)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE google_drive_tokens SET access_token = %s, expires_at = %s, updated_at = NOW() WHERE user_id = 'SYSTEM'",
                    (access_token, new_exp),
                )
            conn.commit()
        finally:
            conn.close()

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _build_service_account_drive():
    """Fallback: use the service account JSON (lower-privilege, different quota)."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    candidates: list[str] = []
    env_path = os.environ.get("NUZANTARA_DRIVE_SA_PATH")
    if env_path:
        candidates.append(env_path)
    candidates.append(str(Path.home() / ".nuzantara-drive-sa.json"))
    candidates.extend(
        glob.glob(
            str(Path.home() / ".config/gcloud/legacy_credentials/nuzantara-google-drive-sa*/adc.json")
        )
    )
    for path in candidates:
        if path and Path(path).exists():
            with open(path) as f:
                sa_info = json.load(f)
            creds = service_account.Credentials.from_service_account_info(
                sa_info, scopes=["https://www.googleapis.com/auth/drive"]
            )
            return build("drive", "v3", credentials=creds, cache_discovery=False)

    raise RuntimeError(
        "Neither OAuth user token nor SA credentials available. "
        "Check google_drive_tokens.SYSTEM row, or place SA JSON at ~/.nuzantara-drive-sa.json."
    )


# ============================================================
# Kill switch + invariant state helpers
# ============================================================
async def is_globally_enabled(conn: asyncpg.Connection) -> bool:
    val = await conn.fetchval("SELECT value FROM system_settings WHERE key = 'crm_guardian_enabled'")
    return (val or "false").lower() == "true"


async def get_invariant_state(conn: asyncpg.Connection, invariant_id: str) -> dict[str, Any]:
    row = await conn.fetchrow(
        "SELECT * FROM crm_guardian_state WHERE invariant_id = $1",
        invariant_id,
    )
    if not row:
        raise RuntimeError(f"Invariant {invariant_id!r} not seeded in crm_guardian_state")
    return dict(row)


async def load_exceptions(conn: asyncpg.Connection, invariant_id: str) -> set[tuple[str, str]]:
    rows = await conn.fetch(
        """
        SELECT target_type, target_id
        FROM crm_guardian_exceptions
        WHERE (invariant_id = $1 OR invariant_id = '*')
          AND (expires_at IS NULL OR expires_at > NOW())
        """,
        invariant_id,
    )
    return {(r["target_type"], r["target_id"]) for r in rows}


async def bump_circuit_breaker(conn: asyncpg.Connection, invariant_id: str, succeeded: bool, error_message: str | None = None) -> None:
    if succeeded:
        await conn.execute(
            """
            UPDATE crm_guardian_state
            SET last_run_at = NOW(),
                last_success_at = NOW(),
                consecutive_errors = 0,
                updated_at = NOW()
            WHERE invariant_id = $1
            """,
            invariant_id,
        )
    else:
        await conn.execute(
            """
            UPDATE crm_guardian_state
            SET last_run_at = NOW(),
                last_error_at = NOW(),
                last_error_message = $2,
                consecutive_errors = consecutive_errors + 1,
                circuit_breaker_tripped = (consecutive_errors + 1 >= 3),
                updated_at = NOW()
            WHERE invariant_id = $1
            """,
            invariant_id,
            (error_message or "")[:2000],
        )
