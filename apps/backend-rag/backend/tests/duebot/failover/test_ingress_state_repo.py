"""Proves ``PostgresIngressLeaderStore``'s CONTROL FLOW — how it maps a
present/absent ``RETURNING`` row to an outcome, and that ``authorize()``
delegates to the exact same ``evaluate_authorize`` the in-memory store
uses — without a real Postgres.

This does NOT prove the SQL text itself is correct against a live
server (honestly disclosed in the module's own docstring and in B5's
report). ``_FakeAsyncpgPool`` below implements just enough of asyncpg's
``Pool``/``Connection`` surface (``acquire()`` as an async context
manager, ``fetchrow()``) to simulate the SAME compare-and-swap semantics
a real ``UPDATE ... WHERE leader_epoch = $expected`` gives: it inspects
the query's leading verb and the bound epoch parameter and decides
match/no-match exactly as Postgres's row-level WHERE clause would,
rather than executing the SQL text.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.services.team_bot_ingress.ingress_leader import (
    DEFAULT_RECORD_ID,
    AuthorizeOutcome,
    PromoteOutcome,
    RenewOutcome,
)
from backend.services.team_bot_ingress.ingress_state_repo import (
    IngressLeaderRecordMissingError,
    PostgresIngressLeaderStore,
)

T0 = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)


class _FakeRecord(dict):
    """asyncpg.Record supports ``row["col"]`` — a dict already does."""


class _FakeConn:
    def __init__(self, store: _FakeAsyncpgPool) -> None:
        self._store = store

    async def fetchrow(self, query: str, *args: object):
        q = " ".join(query.split()).upper()
        row = self._store.row
        if q.startswith("SELECT"):
            (record_id,) = args
            if row is None or row["record_id"] != record_id:
                return None
            return _FakeRecord(row)
        if q.startswith("UPDATE") and "LEADER_EPOCH = LEADER_EPOCH + 1" in q:
            # try_promote signature: record_id, new_node_id, lease_expires_at,
            # new_callback_sha256, changed_at, expected_epoch
            record_id, new_node_id, lease_expires_at, new_callback_sha256, changed_at, expected_epoch = args
            if row is None or row["record_id"] != record_id or row["leader_epoch"] != expected_epoch:
                return None
            row = dict(row)
            row["active_node_id"] = new_node_id
            row["leader_epoch"] += 1
            row["lease_expires_at"] = lease_expires_at
            row["callback_uri_sha256"] = new_callback_sha256
            row["changed_at"] = changed_at
            self._store.row = row
            return _FakeRecord(row)
        if q.startswith("UPDATE"):
            # renew signature: record_id, node_id, epoch, lease_expires_at
            record_id, node_id, epoch, lease_expires_at = args
            if (
                row is None
                or row["record_id"] != record_id
                or row["active_node_id"] != node_id
                or row["leader_epoch"] != epoch
            ):
                return None
            row = dict(row)
            row["lease_expires_at"] = lease_expires_at
            row["changed_at"] = lease_expires_at
            self._store.row = row
            return _FakeRecord(row)
        raise AssertionError(f"unexpected query shape: {query!r}")

    async def __aenter__(self) -> _FakeConn:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class _FakeAsyncpgPool:
    def __init__(self, row: dict | None) -> None:
        self.row = row

    def acquire(self) -> _FakeConn:
        return _FakeConn(self)


def _seed_row(
    *, active_node_id: str = "mini-pro2", epoch: int = 1, lease_seconds: float = 30.0
) -> dict:
    return {
        "record_id": DEFAULT_RECORD_ID,
        "active_node_id": active_node_id,
        "leader_epoch": epoch,
        "lease_expires_at": T0 + timedelta(seconds=lease_seconds),
        "callback_uri_sha256": "a" * 64,
        "changed_at": T0,
    }


async def test_read_returns_seeded_state() -> None:
    pool = _FakeAsyncpgPool(_seed_row())
    store = PostgresIngressLeaderStore(pool)
    state = await store.read()
    assert state.active_node_id == "mini-pro2"
    assert state.leader_epoch == 1


async def test_read_raises_when_record_missing() -> None:
    pool = _FakeAsyncpgPool(None)
    store = PostgresIngressLeaderStore(pool)
    with pytest.raises(IngressLeaderRecordMissingError):
        await store.read()


async def test_try_promote_maps_returning_row_to_promoted() -> None:
    pool = _FakeAsyncpgPool(_seed_row(epoch=1))
    store = PostgresIngressLeaderStore(pool)
    result = await store.try_promote(
        expected_epoch=1,
        new_node_id="pro",
        lease_seconds=60.0,
        new_callback_sha256="b" * 64,
        now=T0 + timedelta(seconds=5),
    )
    assert result.outcome is PromoteOutcome.PROMOTED
    assert result.state.active_node_id == "pro"
    assert result.state.leader_epoch == 2


async def test_try_promote_maps_zero_rows_to_conflict_and_rereads_current() -> None:
    pool = _FakeAsyncpgPool(_seed_row(active_node_id="pro", epoch=2))
    store = PostgresIngressLeaderStore(pool)
    result = await store.try_promote(
        expected_epoch=1,  # stale — real row is at epoch 2
        new_node_id="mini-pro2",
        lease_seconds=60.0,
        new_callback_sha256="c" * 64,
        now=T0,
    )
    assert result.outcome is PromoteOutcome.CONFLICT_STALE_EPOCH
    # The re-read reports the REAL current owner, not the caller's guess.
    assert result.state.active_node_id == "pro"
    assert result.state.leader_epoch == 2


async def test_renew_maps_returning_row_to_renewed() -> None:
    pool = _FakeAsyncpgPool(_seed_row(active_node_id="mini-pro2", epoch=1, lease_seconds=10.0))
    store = PostgresIngressLeaderStore(pool)
    result = await store.renew(
        node_id="mini-pro2", epoch=1, lease_seconds=30.0, now=T0 + timedelta(seconds=5)
    )
    assert result.outcome is RenewOutcome.RENEWED
    assert result.state.lease_expires_at == T0 + timedelta(seconds=35)


async def test_renew_distinguishes_stale_epoch_from_wrong_node() -> None:
    pool = _FakeAsyncpgPool(_seed_row(active_node_id="pro", epoch=2))
    store = PostgresIngressLeaderStore(pool)
    stale = await store.renew(node_id="pro", epoch=1, lease_seconds=30.0, now=T0)
    assert stale.outcome is RenewOutcome.REJECTED_STALE_EPOCH
    wrong_node = await store.renew(node_id="mini-pro2", epoch=2, lease_seconds=30.0, now=T0)
    assert wrong_node.outcome is RenewOutcome.REJECTED_WRONG_NODE


async def test_authorize_delegates_to_shared_evaluate_authorize() -> None:
    """Not re-testing every branch (test_ingress_leader.py already does,
    exhaustively, against evaluate_authorize directly) — just proving
    THIS store actually calls it, via one representative case per
    outcome the real function can produce.
    """
    pool = _FakeAsyncpgPool(_seed_row(active_node_id="mini-pro2", epoch=1, lease_seconds=30.0))
    store = PostgresIngressLeaderStore(pool)
    ok = await store.authorize(node_id="mini-pro2", epoch=1, now=T0 + timedelta(seconds=5))
    assert ok.outcome is AuthorizeOutcome.AUTHORIZED
    stale = await store.authorize(node_id="mini-pro2", epoch=99, now=T0)
    assert stale.outcome is AuthorizeOutcome.REJECTED_STALE_EPOCH
