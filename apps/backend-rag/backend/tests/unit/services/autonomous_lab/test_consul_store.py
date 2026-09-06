"""Control-flow tests; PostgreSQL locking is proved by the synthetic DB smoke."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from backend.services.autonomous_lab.consul_store import Lease, bind, guard, revoke, revoke_approval

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)
LEASE = Lease("synthetic-run", "consul-astra", 2)
PINS = {
    "resource": "synthetic:receipt",
    "intent_hash": "a" * 64,
    "approval_hash": "b" * 64,
    "review_hash": "c" * 64,
    "packet_hash": "d" * 64,
}


class Connection:
    def __init__(self, rows: list[Any], values: list[Any] | None = None) -> None:
        self.rows = rows
        self.values = list(values if values is not None else [NOW])
        self.active = False
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    @asynccontextmanager
    async def transaction(self) -> Any:
        self.active = True
        try:
            yield
        finally:
            self.active = False

    async def fetchrow(self, query: str, *args: Any) -> Any:
        assert self.active
        self.calls.append((query, args))
        return self.rows.pop(0)

    async def fetchval(self, query: str, *args: Any) -> Any:
        assert self.active
        self.calls.append((query, args))
        return self.values.pop(0)


def parent(**changes: Any) -> dict[str, Any]:
    return {"worker_id": LEASE.owner_id, "status": "running", **changes}


def row(**changes: Any) -> dict[str, Any]:
    return {
        **PINS,
        "owner_id": LEASE.owner_id,
        "generation": LEASE.generation,
        "lease_expires_at": NOW + timedelta(seconds=60),
        "grant_expires_at": NOW + timedelta(minutes=5),
        "revoked_at": None,
        "revoked_approval_hashes": [],
        **changes,
    }


@pytest.mark.asyncio
async def test_guard_holds_locks_through_effect_and_reads_clock_after_locks() -> None:
    conn = Connection([parent(), row()])
    async with guard(conn, lease=LEASE, **PINS) as timestamp:
        assert conn.active
        assert timestamp == NOW
        assert all("FOR UPDATE" in query for query, _ in conn.calls[:2])
        assert conn.calls[2][0] == "SELECT clock_timestamp()"
    assert not conn.active


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"owner_id": "consul-fable"},
        {"generation": 3},
        {"resource": "synthetic:other"},
        *[{name: "e" * 64} for name in PINS if name.endswith("_hash")],
        {"lease_expires_at": NOW},
        {"grant_expires_at": NOW},
        {"revoked_at": NOW},
        {"revoked_approval_hashes": [PINS["approval_hash"]]},
    ],
)
async def test_guard_refuses_before_effect_for_every_stale_pin(changes: dict[str, Any]) -> None:
    conn = Connection([parent(), row(**changes)])
    with pytest.raises(PermissionError):
        async with guard(conn, lease=LEASE, **PINS):
            pytest.fail("unauthorized effect entered")
    assert not conn.active


@pytest.mark.asyncio
@pytest.mark.parametrize("run", [None, parent(status="cancelled"), parent(worker_id="other")])
async def test_guard_refuses_missing_or_no_longer_owned_run(run: Any) -> None:
    with pytest.raises(PermissionError):
        async with guard(Connection([run, row()]), lease=LEASE, **PINS):
            pytest.fail("unauthorized effect entered")


@pytest.mark.asyncio
async def test_bind_uses_new_db_generation_and_clamps_lease_to_grant() -> None:
    expiry = NOW + timedelta(seconds=20)
    conn = Connection([parent(), {"revoked_approval_hashes": []}], [NOW, 3])
    lease = await bind(
        conn, run_id=LEASE.run_id, owner_id=LEASE.owner_id, **PINS, grant_expires_at=expiry
    )
    assert lease == Lease(LEASE.run_id, LEASE.owner_id, 3)
    assert conn.calls[-1][1][-2:] == (expiry, expiry)
    assert not conn.active


@pytest.mark.asyncio
async def test_bind_never_resurrects_an_older_revoked_approval() -> None:
    conn = Connection([parent(), {"revoked_approval_hashes": [PINS["approval_hash"]]}])
    with pytest.raises(PermissionError, match="revoked"):
        await bind(
            conn,
            run_id=LEASE.run_id,
            owner_id=LEASE.owner_id,
            **PINS,
            grant_expires_at=NOW + timedelta(minutes=5),
        )
    assert len(conn.calls) == 2


@pytest.mark.asyncio
async def test_bind_refuses_expired_grant_before_write() -> None:
    conn = Connection([parent(), None])
    with pytest.raises(PermissionError, match="expired"):
        await bind(conn, run_id=LEASE.run_id, owner_id=LEASE.owner_id, **PINS, grant_expires_at=NOW)
    assert len(conn.calls) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("updated, expected", [(None, False), ({"run_id": LEASE.run_id}, True)])
async def test_revoke_returns_actual_owner_scoped_update(updated: Any, expected: bool) -> None:
    conn = Connection([parent(), updated])
    assert await revoke(conn, LEASE) is expected
    assert conn.calls[1][1] == (LEASE.run_id, LEASE.owner_id, LEASE.generation)
    assert not conn.active


@pytest.mark.asyncio
@pytest.mark.parametrize("digest", ["", "a" * 63, "a" * 65, "A" * 64, "g" * 64])
async def test_revoke_approval_rejects_invalid_hash_before_database(digest: str) -> None:
    conn = Connection([])
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        await revoke_approval(conn, run_id=LEASE.run_id, approval_hash=digest)
    assert conn.calls == []


@pytest.mark.asyncio
async def test_revoke_approval_does_not_invent_a_missing_mission() -> None:
    conn = Connection([None])
    assert not await revoke_approval(conn, run_id=LEASE.run_id, approval_hash=PINS["approval_hash"])
    assert len(conn.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("updated, expected", [(None, False), ({"run_id": LEASE.run_id}, True)])
async def test_revoke_approval_reports_whether_a_new_tombstone_was_added(
    updated: Any, expected: bool
) -> None:
    conn = Connection([parent(), updated])
    assert (
        await revoke_approval(conn, run_id=LEASE.run_id, approval_hash=PINS["approval_hash"])
        is expected
    )
    assert not conn.active
