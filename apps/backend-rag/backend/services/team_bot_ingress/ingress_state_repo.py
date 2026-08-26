"""Postgres-backed ``IngressLeaderStore`` (migration 291,
``team_bot_ingress_leader``).

Thin adapter, Golden Rule #7: every business rule lives in
``ingress_leader.py`` (the CAS shape via ``UPDATE ... WHERE leader_epoch =
$expected`` mirrors ``ingress_leader.InMemoryIngressLeaderStore``'s
lock-guarded compare-and-swap exactly; ``authorize()`` delegates to the
SAME ``evaluate_authorize`` pure function the in-memory store uses, so the
two implementations cannot silently diverge on what counts as authorized).

Follows the pool-based async repo convention already established by
``services/channels/inbound_webhook_repo.py`` and
``services/integrations/wa_outbox_worker.py`` — an ``asyncpg.Pool`` passed
in per call, never held as module state (Golden Rule #10: persistent
clients live in the app lifespan, not constructed here).

NOT exercised against a real Postgres instance by this lane's own test
suite — ``backend/tests/duebot/`` is a no-real-sockets harness by design
(``network_guard.py``) and this worktree has no live dev database with
this schema attached (Mini deliberately does not mirror the Pro's
``nuzantara_dev`` — see CLAUDE.md's Mini host doc). The state machine
this module delegates to IS exercised, exhaustively, in
``test_ingress_leader.py``; this file's own correctness claim is narrower
and honest about it: the SQL is reviewed, syntactically valid, and
follows an established convention in this exact codebase — not
empirically proven here. Say so in review rather than assume otherwise.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import asyncpg

from backend.services.team_bot_ingress.ingress_leader import (
    DEFAULT_RECORD_ID,
    AuthorizeResult,
    IngressLeaderState,
    PromoteOutcome,
    PromoteResult,
    RenewOutcome,
    RenewResult,
    evaluate_authorize,
)

logger = logging.getLogger(__name__)

_SELECT_COLUMNS = (
    "record_id, active_node_id, leader_epoch, lease_expires_at, "
    "callback_uri_sha256, changed_at"
)


class IngressLeaderRecordMissingError(RuntimeError):
    """The control row does not exist. Migration 291 bootstraps it — this
    means the migration has not run, or ``record_id`` is wrong. Never
    auto-create it here: a control record that can spontaneously appear
    mid-request is exactly the kind of implicit state this table exists
    to rule out.
    """


def _row_to_state(row: asyncpg.Record) -> IngressLeaderState:
    return IngressLeaderState(
        record_id=row["record_id"],
        active_node_id=row["active_node_id"],
        leader_epoch=row["leader_epoch"],
        lease_expires_at=row["lease_expires_at"],
        callback_uri_sha256=row["callback_uri_sha256"],
        changed_at=row["changed_at"],
    )


class PostgresIngressLeaderStore:
    """Implements ``ingress_leader.IngressLeaderStore`` against
    ``team_bot_ingress_leader`` (migration 291).
    """

    def __init__(self, pool: asyncpg.Pool, *, record_id: str = DEFAULT_RECORD_ID) -> None:
        self._pool = pool
        self._record_id = record_id

    async def read(self) -> IngressLeaderState:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_SELECT_COLUMNS} FROM team_bot_ingress_leader WHERE record_id = $1",
                self._record_id,
            )
        if row is None:
            raise IngressLeaderRecordMissingError(self._record_id)
        return _row_to_state(row)

    async def try_promote(
        self,
        *,
        expected_epoch: int,
        new_node_id: str,
        lease_seconds: float,
        new_callback_sha256: str,
        now: datetime,
    ) -> PromoteResult:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE team_bot_ingress_leader
                SET active_node_id = $2,
                    leader_epoch = leader_epoch + 1,
                    lease_expires_at = $3,
                    callback_uri_sha256 = $4,
                    changed_at = $5
                WHERE record_id = $1 AND leader_epoch = $6
                RETURNING {_SELECT_COLUMNS}
                """,
                self._record_id,
                new_node_id,
                now + timedelta(seconds=lease_seconds),
                new_callback_sha256,
                now,
                expected_epoch,
            )
        if row is not None:
            state = _row_to_state(row)
            logger.info(
                "team_bot_ingress_leader: PROMOTED record_id=%s node=%s epoch=%d",
                self._record_id,
                new_node_id,
                state.leader_epoch,
            )
            return PromoteResult(outcome=PromoteOutcome.PROMOTED, state=state)
        # Zero rows matched — the CAS missed. Re-read to report what the
        # caller's expected_epoch actually lost to, in ONE extra read
        # rather than folding a second UPDATE-less SELECT into the same
        # statement (keeps the write path a single, easily-audited
        # UPDATE ... WHERE ... RETURNING).
        current = await self.read()
        logger.warning(
            "team_bot_ingress_leader: CAS conflict record_id=%s expected_epoch=%d actual_epoch=%d",
            self._record_id,
            expected_epoch,
            current.leader_epoch,
        )
        return PromoteResult(outcome=PromoteOutcome.CONFLICT_STALE_EPOCH, state=current)

    async def renew(
        self,
        *,
        node_id: str,
        epoch: int,
        lease_seconds: float,
        now: datetime,
    ) -> RenewResult:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE team_bot_ingress_leader
                SET lease_expires_at = $4,
                    changed_at = $4
                WHERE record_id = $1 AND active_node_id = $2 AND leader_epoch = $3
                RETURNING {_SELECT_COLUMNS}
                """,
                self._record_id,
                node_id,
                epoch,
                now + timedelta(seconds=lease_seconds),
            )
        if row is not None:
            return RenewResult(outcome=RenewOutcome.RENEWED, state=_row_to_state(row))
        # Zero rows matched — distinguish stale-epoch from wrong-node by
        # reading current state, same as InMemoryIngressLeaderStore does
        # inside its lock (checked in that order there too).
        current = await self.read()
        if current.leader_epoch != epoch:
            return RenewResult(outcome=RenewOutcome.REJECTED_STALE_EPOCH, state=current)
        return RenewResult(outcome=RenewOutcome.REJECTED_WRONG_NODE, state=current)

    async def authorize(
        self,
        *,
        node_id: str,
        epoch: int,
        now: datetime,
    ) -> AuthorizeResult:
        current = await self.read()
        return evaluate_authorize(current, node_id=node_id, epoch=epoch, now=now)


__all__ = ["IngressLeaderRecordMissingError", "PostgresIngressLeaderStore"]
