"""WR2 headless Canva actuator — launches `claude -p` to apply canva_pending.json
via the /canva-apply skill (duplica-poi-edita). Lease functions here serialize
edits on the master template_design_id across Pro/Mini (shared Fly Postgres)."""
from __future__ import annotations

import hashlib

import asyncpg


def _lock_key(template_design_id: str) -> int:
    return int(hashlib.sha256(template_design_id.encode()).hexdigest()[:15], 16)


async def acquire_master_lock(conn: asyncpg.Connection, template_design_id: str) -> bool:
    """pg_try_advisory_lock keyed on template_design_id. False if held by Pro OR Mini
    (session-level advisory locks are cluster-global on the shared Fly Postgres)."""
    return await conn.fetchval("SELECT pg_try_advisory_lock($1)", _lock_key(template_design_id))


async def release_master_lock(conn: asyncpg.Connection, template_design_id: str) -> None:
    await conn.execute("SELECT pg_advisory_unlock($1)", _lock_key(template_design_id))
