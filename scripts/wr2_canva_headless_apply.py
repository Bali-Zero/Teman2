"""WR2 headless Canva actuator — launches `claude -p` to apply canva_pending.json
via the /canva-apply skill (duplica-poi-edita). Lease functions here serialize
edits on the master template_design_id across Pro/Mini (shared Fly Postgres)."""
from __future__ import annotations

import hashlib
import subprocess

import asyncpg


def _lock_key(template_design_id: str) -> int:
    return int(hashlib.sha256(template_design_id.encode()).hexdigest()[:15], 16)


async def acquire_master_lock(conn: asyncpg.Connection, template_design_id: str) -> bool:
    """pg_try_advisory_lock keyed on template_design_id. False if held by Pro OR Mini
    (session-level advisory locks are cluster-global on the shared Fly Postgres)."""
    return await conn.fetchval("SELECT pg_try_advisory_lock($1)", _lock_key(template_design_id))


async def release_master_lock(conn: asyncpg.Connection, template_design_id: str) -> None:
    await conn.execute("SELECT pg_advisory_unlock($1)", _lock_key(template_design_id))


_QUOTA_BLOCK_PATTERNS = ("usage limit", "out of extra usage", "quota exceeded",
                         "rate limit", "429", "exhausted", "resets in")


def quota_ok_to_run() -> bool:
    """BEST-EFFORT quota signal (A5): `claude auth status` is NOT a reliable MAX
    rolling-window oracle — it reports login state, not remaining quota. This scan
    only catches the case where the CLI surfaces an explicit limit string. Treat a
    True result as "no obvious block", NOT "quota confirmed available". Fail-open on
    probe error. The real protection against a 3am quota outage is the LaunchAgent
    cadence + Telegram alert on repeated headless failures, not this check."""
    try:
        r = subprocess.run(["claude", "auth", "status"], capture_output=True,
                           text=True, timeout=15)
    except Exception:
        return True  # fail-open on probe error: don't block pipeline on a flaky probe
    text = (r.stdout + r.stderr).lower()
    return not any(p in text for p in _QUOTA_BLOCK_PATTERNS)
