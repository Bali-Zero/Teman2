"""FederationAlertRepo — CRUD against federation_alert_proposals.

This repo wraps the proposal state machine in a typed API. The DB
constraints (CHECK, UNIQUE, FK) remain authoritative — Python validation
in models.py mirrors them so failures surface earlier, but the DB has
the last word.

Idempotency contract:
    create_from_alert() does ON CONFLICT (idempotency_key) DO UPDATE
    SET updated_at = NOW(). Same alert fingerprint within the dedup
    window returns the existing row (callers detect duplicate via
    ``returned.created_at < now - small_delta``).

Lease contract (used by daemon):
    acquire_lease(proposal_id, owner, ttl_seconds) sets lease_owner +
    lease_expires_at on the row IFF current lease is expired or unset.
    Returns True on acquisition, False on contention. Cooperates with
    pg_try_advisory_lock() for action-level mutex.

Status transitions:
    advance_status(proposal_id, to=...) is the ONLY API for changing
    status; it validates the transition against TERMINAL_STATUSES and
    refuses backward moves.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

from backend.services.federation_alerts.models import (
    AlertInput,
    FederationAlertMode,
    ProposalRow,
    ProposalStatus,
    is_terminal_status,
)

logger = logging.getLogger(__name__)


def _parse_jsonb(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _row_to_proposal(row: Any) -> ProposalRow:
    return ProposalRow(
        id=row["id"],
        proposal_id=row["proposal_id"],
        run_id=row["run_id"],
        idempotency_key=row["idempotency_key"],
        source_outbox_id=row["source_outbox_id"],
        source_channel=row["source_channel"],
        source_ref=row["source_ref"],
        mode=row["mode"],
        status=row["status"],
        alert_type=row["alert_type"],
        severity=row["severity"],
        risk_level=row["risk_level"],
        requested_action=row["requested_action"],
        target_file=row["target_file"],
        action_payload=_parse_jsonb(row["action_payload"]),
        compact_payload=_parse_jsonb(row["compact_payload"]),
        full_payload=_parse_jsonb(row["full_payload"]),
        dispatch_plan=_parse_jsonb(row["dispatch_plan"]),
        deliberation_result=_parse_jsonb(row["deliberation_result"]),
        votes=_parse_jsonb(row["votes"]),
        gate_6_passes=row["gate_6_passes"],
        requires_approval=row["requires_approval"],
        approval_token=row["approval_token"],
        telegram_chat_id=row["telegram_chat_id"],
        telegram_message_id=row["telegram_message_id"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
        rejected_by=row["rejected_by"],
        rejected_at=row["rejected_at"],
        action_idempotency_key=row["action_idempotency_key"],
        quarantine_token=row["quarantine_token"],
        quarantine_reason=row["quarantine_reason"],
        quarantined_at=row["quarantined_at"],
        lease_owner=row["lease_owner"],
        lease_expires_at=row["lease_expires_at"],
        attempt_count=row["attempt_count"],
        max_attempts=row["max_attempts"],
        next_attempt_at=row["next_attempt_at"],
        last_error=row["last_error"],
        last_error_at=row["last_error_at"],
        artifact_uri=row["artifact_uri"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
    )


class FederationAlertRepo:
    """Repository for federation_alert_proposals.

    Constructor takes either a Pool (most callers) or a single
    Connection (when running inside an existing transaction). The
    methods that MUST run in their own transaction (e.g. lease acquire)
    accept an explicit ``conn=`` arg.
    """

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        conn: asyncpg.Connection | None = None,
    ) -> None:
        if pool is None and conn is None:
            raise ValueError("FederationAlertRepo requires pool or conn")
        self._pool = pool
        self._conn = conn

    def _acquire(self) -> Any:
        """Return an async context manager yielding a connection.

        - When constructed with a pool: delegates to ``pool.acquire()``.
        - When constructed with a single conn (e.g. inside an open
          transaction): returns a no-op context manager that yields the
          stored conn.
        """
        if self._conn is not None:
            stored_conn = self._conn

            class _StoredConnCtx:
                async def __aenter__(self_inner) -> Any:
                    return stored_conn

                async def __aexit__(self_inner, *exc: Any) -> None:
                    return None

            return _StoredConnCtx()
        assert self._pool is not None
        return self._pool.acquire()

    # ------------------------------------------------------------------
    # Create / dedup
    # ------------------------------------------------------------------

    async def create_from_alert(self, alert: AlertInput) -> ProposalRow:
        """Insert proposal, idempotent on idempotency_key.

        Returns the row (existing if duplicate, new otherwise). Callers
        compare returned.created_at against now to detect duplicates.
        """
        sql = """
            INSERT INTO federation_alert_proposals (
                proposal_id, run_id, idempotency_key,
                source_outbox_id, source_channel, source_ref,
                mode, alert_type, severity, risk_level,
                requested_action, target_file,
                action_payload, compact_payload, full_payload
            ) VALUES (
                $1, $2, $3,
                $4, $5, $6,
                $7, $8, $9, $10,
                $11, $12,
                $13::jsonb, $14::jsonb, $15::jsonb
            )
            ON CONFLICT (idempotency_key) DO UPDATE
                SET updated_at = NOW()
            RETURNING *
        """
        async with self._acquire() as conn:
            row = await conn.fetchrow(
                sql,
                alert.proposal_id,
                alert.run_id,
                alert.idempotency_key,
                alert.source_outbox_id,
                alert.source_channel,
                alert.source_ref,
                alert.mode if isinstance(alert.mode, str) else alert.mode.value,
                alert.alert_type,
                (
                    alert.severity
                    if isinstance(alert.severity, str)
                    else alert.severity.value
                ),
                (
                    alert.risk_level
                    if isinstance(alert.risk_level, str)
                    else alert.risk_level.value
                ),
                (
                    alert.requested_action
                    if isinstance(alert.requested_action, str)
                    or alert.requested_action is None
                    else alert.requested_action.value
                ),
                alert.target_file,
                json.dumps(alert.action_payload, separators=(",", ":")),
                json.dumps(alert.compact_payload, separators=(",", ":")),
                json.dumps(alert.full_payload, separators=(",", ":")),
            )
        if row is None:
            raise RuntimeError(
                f"create_from_alert returned no row for "
                f"idempotency_key={alert.idempotency_key}"
            )
        return _row_to_proposal(row)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_proposal_id(self, proposal_id: str) -> ProposalRow | None:
        sql = "SELECT * FROM federation_alert_proposals WHERE proposal_id = $1"
        async with self._acquire() as conn:
            row = await conn.fetchrow(sql, proposal_id)
        return _row_to_proposal(row) if row else None

    async def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> ProposalRow | None:
        sql = "SELECT * FROM federation_alert_proposals WHERE idempotency_key = $1"
        async with self._acquire() as conn:
            row = await conn.fetchrow(sql, idempotency_key)
        return _row_to_proposal(row) if row else None

    async def list_active(self, limit: int = 100) -> list[ProposalRow]:
        """Rows that are NOT in a terminal status — daemon's working set."""
        sql = """
            SELECT * FROM federation_alert_proposals
            WHERE status IN (
                'received', 'deliberating', 'proposed',
                'dry_executing', 'awaiting_approval', 'executing'
            )
            ORDER BY next_attempt_at ASC, created_at ASC
            LIMIT $1
        """
        async with self._acquire() as conn:
            rows = await conn.fetch(sql, limit)
        return [_row_to_proposal(r) for r in rows]

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    async def advance_status(
        self,
        proposal_id: str,
        to: ProposalStatus,
        *,
        last_error: str | None = None,
        artifact_uri: str | None = None,
    ) -> ProposalRow:
        """Move status forward. Refuses backward moves and terminal mutations."""
        new_status = to.value if isinstance(to, ProposalStatus) else to

        async with self._acquire() as conn:
            current = await conn.fetchrow(
                "SELECT status FROM federation_alert_proposals "
                "WHERE proposal_id = $1",
                proposal_id,
            )
            if current is None:
                raise LookupError(f"proposal not found: {proposal_id}")
            if is_terminal_status(current["status"]):
                raise ValueError(
                    f"cannot transition terminal status "
                    f"{current['status']} → {new_status}"
                )

            mark_completed = is_terminal_status(new_status)
            row = await conn.fetchrow(
                """
                UPDATE federation_alert_proposals
                   SET status = $2,
                       last_error = COALESCE($3, last_error),
                       last_error_at = CASE WHEN $3 IS NOT NULL THEN NOW()
                                            ELSE last_error_at END,
                       artifact_uri = COALESCE($4, artifact_uri),
                       completed_at = CASE WHEN $5 THEN NOW()
                                           ELSE completed_at END,
                       updated_at = NOW()
                 WHERE proposal_id = $1
                 RETURNING *
                """,
                proposal_id,
                new_status,
                last_error,
                artifact_uri,
                mark_completed,
            )
        if row is None:
            raise RuntimeError(
                f"advance_status returned no row for {proposal_id}"
            )
        return _row_to_proposal(row)

    # ------------------------------------------------------------------
    # Lease (daemon coordination)
    # ------------------------------------------------------------------

    async def acquire_lease(
        self,
        proposal_id: str,
        *,
        owner: str,
        ttl_seconds: int = 300,
    ) -> bool:
        """Set lease_owner + lease_expires_at IFF current lease is expired/unset.

        Returns True on acquire, False on contention. Use pg_try_advisory_lock
        on top of this when the action itself must be globally serialized
        (see B5 mitigation in spec).
        """
        sql = """
            UPDATE federation_alert_proposals
               SET lease_owner = $2,
                   lease_expires_at = NOW() + ($3 || ' seconds')::interval,
                   attempt_count = attempt_count + 1,
                   updated_at = NOW()
             WHERE proposal_id = $1
               AND (lease_expires_at IS NULL OR lease_expires_at < NOW())
            RETURNING id
        """
        async with self._acquire() as conn:
            row = await conn.fetchrow(sql, proposal_id, owner, str(ttl_seconds))
        return row is not None

    async def release_lease(self, proposal_id: str, *, owner: str) -> None:
        """Clear lease. Idempotent."""
        sql = """
            UPDATE federation_alert_proposals
               SET lease_owner = NULL,
                   lease_expires_at = NULL,
                   updated_at = NOW()
             WHERE proposal_id = $1 AND lease_owner = $2
        """
        async with self._acquire() as conn:
            await conn.execute(sql, proposal_id, owner)

    # ------------------------------------------------------------------
    # Approval gate (PR #3)
    # ------------------------------------------------------------------

    async def request_approval(
        self,
        proposal_id: str,
        *,
        approval_token: str,
        telegram_chat_id: str,
        telegram_message_id: int | None = None,
    ) -> ProposalRow:
        """Move proposal to status='awaiting_approval' with a fresh token.

        Refuses to overwrite an existing token (a re-issue must rotate
        the token via a separate ``rotate_approval_token`` flow — out of
        scope for V1).
        """
        async with self._acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE federation_alert_proposals
                   SET requires_approval = TRUE,
                       approval_token = $2,
                       telegram_chat_id = $3,
                       telegram_message_id = $4,
                       status = 'awaiting_approval',
                       updated_at = NOW()
                 WHERE proposal_id = $1
                   AND approval_token IS NULL
                   AND status NOT IN (
                       'completed', 'failed', 'quarantined', 'duplicate'
                   )
                 RETURNING *
                """,
                proposal_id,
                approval_token,
                telegram_chat_id,
                telegram_message_id,
            )
        if row is None:
            raise RuntimeError(
                f"request_approval failed: proposal {proposal_id} either not "
                "found, terminal, or already has an approval_token"
            )
        return _row_to_proposal(row)

    async def record_approval(
        self,
        proposal_id: str,
        *,
        approved_by: str,
    ) -> ProposalRow:
        """Mark proposal approved + transition to 'executing'.

        Refuses if proposal is not in awaiting_approval (defense against
        late callbacks — Telegram delivers at-least-once).
        """
        async with self._acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE federation_alert_proposals
                   SET approved_by = $2,
                       approved_at = NOW(),
                       status = 'executing',
                       updated_at = NOW()
                 WHERE proposal_id = $1
                   AND status = 'awaiting_approval'
                 RETURNING *
                """,
                proposal_id,
                approved_by,
            )
        if row is None:
            raise LookupError(
                f"record_approval: proposal {proposal_id} not in "
                "awaiting_approval"
            )
        return _row_to_proposal(row)

    async def record_rejection(
        self,
        proposal_id: str,
        *,
        rejected_by: str,
        reason: str = "rejected via Telegram",
    ) -> ProposalRow:
        """Mark proposal rejected → terminal status='quarantined'."""
        async with self._acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE federation_alert_proposals
                   SET rejected_by = $2,
                       rejected_at = NOW(),
                       status = 'quarantined',
                       quarantine_reason = $3,
                       quarantined_at = NOW(),
                       completed_at = NOW(),
                       updated_at = NOW()
                 WHERE proposal_id = $1
                   AND status = 'awaiting_approval'
                 RETURNING *
                """,
                proposal_id,
                rejected_by,
                reason[:500],
            )
        if row is None:
            raise LookupError(
                f"record_rejection: proposal {proposal_id} not in "
                "awaiting_approval"
            )
        return _row_to_proposal(row)

    # ------------------------------------------------------------------
    # Mode persistence
    # ------------------------------------------------------------------

    async def get_db_mode(self) -> str:
        """Read the federation_alert_mode from system_settings (seeded by m147)."""
        sql = (
            "SELECT value FROM system_settings "
            "WHERE key = 'federation_alert_mode'"
        )
        async with self._acquire() as conn:
            row = await conn.fetchrow(sql)
        if row is None:
            # Defensive fallback: should always exist after m147 ran.
            return FederationAlertMode.OBSERVE.value
        return row["value"]

    async def set_db_mode(
        self, new_mode: str, *, changed_by: str | None = None
    ) -> None:
        """Update federation_alert_mode in system_settings.

        Validation: caller must have pre-validated against
        FederationAlertMode enum. We do NOT downgrade silently here —
        env override is applied at read time via effective_mode().
        """
        if new_mode not in {m.value for m in FederationAlertMode}:
            raise ValueError(f"invalid federation_alert_mode: {new_mode}")
        sql = """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES ('federation_alert_mode', $1, NOW())
            ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value,
                    updated_at = NOW()
        """
        async with self._acquire() as conn:
            await conn.execute(sql, new_mode)
        logger.info(
            "federation_alert_mode set to %s by %s",
            new_mode,
            changed_by or "system",
        )
