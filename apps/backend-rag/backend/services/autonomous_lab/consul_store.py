"""PostgreSQL fencing for the synthetic Dual Consul lifecycle slice.

Only the trusted broker calls ``bind``, after validating authority and the frozen
review; hashes supplied by a model are not admission. ``guard`` encloses ONLY a
same-connection synthetic receipt write. Its locks give no remote-effect atomicity
and this module does not establish a separate operating-system service identity.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

import asyncpg


@dataclass(frozen=True)
class Lease:
    run_id: str
    owner_id: str
    generation: int


async def _lock_parent(conn: asyncpg.Connection, run_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "SELECT worker_id, status FROM autonomous_lab_runs WHERE run_id = $1 FOR UPDATE",
        run_id,
    )


async def bind(
    conn: asyncpg.Connection,
    *,
    run_id: str,
    owner_id: str,
    resource: str,
    intent_hash: str,
    approval_hash: str,
    review_hash: str,
    packet_hash: str,
    grant_expires_at: datetime,
    lease_seconds: int = 60,
) -> Lease:
    """Bind a freshly authorized grant; rebind fences every earlier generation."""
    if not 1 <= lease_seconds <= 3600:
        raise ValueError("lease_seconds must be between 1 and 3600")
    if grant_expires_at.utcoffset() is None:
        raise ValueError("grant expiry must be timezone-aware")
    async with conn.transaction():
        parent = await _lock_parent(conn, run_id)
        if not parent or parent["status"] != "running" or parent["worker_id"] != owner_id:
            raise PermissionError("run is not owned by this running worker")
        previous = await conn.fetchrow(
            "SELECT revoked_approval_hashes FROM autonomous_lab_consul_leases "
            "WHERE run_id = $1 FOR UPDATE",
            run_id,
        )
        if previous and approval_hash in previous["revoked_approval_hashes"]:
            raise PermissionError("approval was revoked")
        now = await conn.fetchval("SELECT clock_timestamp()")
        if grant_expires_at <= now:
            raise PermissionError("grant has expired")
        generation = await conn.fetchval(
            """
            INSERT INTO autonomous_lab_consul_leases
                (run_id, owner_id, generation, resource, intent_hash, approval_hash,
                 review_hash, packet_hash, lease_expires_at, grant_expires_at)
            VALUES ($1, $2, 1, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (run_id) DO UPDATE SET
                owner_id = EXCLUDED.owner_id,
                generation = autonomous_lab_consul_leases.generation + 1,
                resource = EXCLUDED.resource, intent_hash = EXCLUDED.intent_hash,
                approval_hash = EXCLUDED.approval_hash, review_hash = EXCLUDED.review_hash,
                packet_hash = EXCLUDED.packet_hash,
                lease_expires_at = EXCLUDED.lease_expires_at,
                grant_expires_at = EXCLUDED.grant_expires_at, revoked_at = NULL
            RETURNING generation
            """,
            run_id,
            owner_id,
            resource,
            intent_hash,
            approval_hash,
            review_hash,
            packet_hash,
            min(now + timedelta(seconds=lease_seconds), grant_expires_at),
            grant_expires_at,
        )
        return Lease(run_id, owner_id, generation)


async def revoke(conn: asyncpg.Connection, lease: Lease) -> bool:
    """Revoke this generation and remember its approval across future rebinds."""
    async with conn.transaction():
        await _lock_parent(conn, lease.run_id)
        row = await conn.fetchrow(
            """
            UPDATE autonomous_lab_consul_leases
            SET revoked_at = clock_timestamp(),
                revoked_approval_hashes = array_append(revoked_approval_hashes, approval_hash)
            WHERE run_id = $1 AND owner_id = $2 AND generation = $3 AND revoked_at IS NULL
            RETURNING run_id
            """,
            lease.run_id,
            lease.owner_id,
            lease.generation,
        )
        return row is not None


async def revoke_approval(conn: asyncpg.Connection, *, run_id: str, approval_hash: str) -> bool:
    """Trusted broker revocation, including superseded grants; False if unchanged."""
    if not re.fullmatch(r"[a-f0-9]{64}", approval_hash):
        raise ValueError("approval_hash must be lowercase SHA-256 hex")
    async with conn.transaction():
        if await _lock_parent(conn, run_id) is None:
            return False
        row = await conn.fetchrow(
            """
            UPDATE autonomous_lab_consul_leases
            SET revoked_approval_hashes = array_append(revoked_approval_hashes, $2),
                revoked_at = CASE WHEN approval_hash = $2
                    THEN COALESCE(revoked_at, clock_timestamp()) ELSE revoked_at END
            WHERE run_id = $1 AND NOT ($2 = ANY (revoked_approval_hashes))
            RETURNING run_id
            """,
            run_id,
            approval_hash,
        )
        return row is not None


@asynccontextmanager
async def guard(
    conn: asyncpg.Connection,
    *,
    lease: Lease,
    resource: str,
    intent_hash: str,
    approval_hash: str,
    review_hash: str,
    packet_hash: str,
) -> AsyncIterator[datetime]:
    """Hold parent/lease locks and recheck all authority pins before a DB effect."""
    async with conn.transaction():
        parent = await _lock_parent(conn, lease.run_id)
        row = await conn.fetchrow(
            "SELECT * FROM autonomous_lab_consul_leases WHERE run_id = $1 FOR UPDATE",
            lease.run_id,
        )
        now = await conn.fetchval("SELECT clock_timestamp()")
        expected = {
            "owner_id": lease.owner_id,
            "generation": lease.generation,
            "resource": resource,
            "intent_hash": intent_hash,
            "approval_hash": approval_hash,
            "review_hash": review_hash,
            "packet_hash": packet_hash,
        }
        if (
            not parent
            or parent["status"] != "running"
            or parent["worker_id"] != lease.owner_id
            or not row
            or any(row[key] != value for key, value in expected.items())
            or row["revoked_at"] is not None
            or approval_hash in row["revoked_approval_hashes"]
            or row["lease_expires_at"] <= now
            or row["grant_expires_at"] <= now
        ):
            raise PermissionError("lease, authorization or frozen review is no longer current")
        yield now
