"""SqlitePendingActionStore — F6's CAS machinery, sqlite-backed (B3's lane
description names sqlite as the team-bot's storage: "webhook, identity,
typed loop, confirmations, registry, audit, sqlite state + Mini->Pro
replication"). Replication itself is a separate unit, out of scope here.

Steals its shape from two things already in the repo, per F6's explicit
instruction ("Steal the shape from review_handler.py and the wa_broker CAS
— both already in the repo"):

- ``wa_broker.py``'s CAS idiom: a single ``UPDATE ... WHERE state = X``,
  then check whether the write actually happened (sqlite: ``rowcount``;
  Postgres: the same shape via ``FOR UPDATE SKIP LOCKED`` + rowcount) rather
  than a read-then-write race. Every transition below is exactly that.
- ``review_handler.py``'s idempotent-branch idiom: re-read the CURRENT row
  first, classify what it actually says (not-found / already-terminal /
  wrong actor / valid-for-transition), and respond accordingly — "approving
  the same draft twice is a no-op" becomes "confirming the same code twice
  is a no-op" here.

leader_epoch is CARRIED and CHECKED on every CAS (F6's frozen field list),
never GENERATED here — F9's team-bot-failoverd (a separate, not-yet-built
unit) owns incrementing the fleet epoch on an actual failover; this store
only refuses a transition whose row's epoch does not match the epoch it was
constructed with, so a stale node cannot mutate after a handoff. In v1
there is exactly one epoch (0) and this check is inert — consistent with
"AUTO-failover stays DARK until a staging-WABA drill" (F9).

Author: Claude Sonnet 5 (lane B3 — team-bot confirmation state machine)
"""

from __future__ import annotations

import random
import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from team_bot.loop.execution_record import ExecutionRecord, ExecutionSource
from team_bot.registry import TOOL_NAMES

from .crypto import ArgsCipher, ArgsIntegrityError
from .idempotency import compute_idempotency_key
from .models import PendingAction, PendingActionStatus

__all__ = [
    "ConfirmOutcome",
    "ConfirmResult",
    "DEFAULT_TTL_SECONDS",
    "ExecuteOutcome",
    "ExecuteResult",
    "ProposeOutcome",
    "ProposeResult",
    "SqlitePendingActionStore",
]

DEFAULT_TTL_SECONDS = 300  # F6: "5-min expiry"

_NON_TERMINAL = (PendingActionStatus.PROPOSED.value, PendingActionStatus.CONFIRMED.value)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    short_code TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    encrypted_args BLOB NOT NULL,
    args_sha256 TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL,
    leader_epoch INTEGER NOT NULL,
    proposed_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    confirmed_at TEXT,
    executed_at TEXT,
    execution_result_ref TEXT,
    cancelled_reason TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_pending_actions_idempotency
    ON pending_actions(idempotency_key);
CREATE UNIQUE INDEX IF NOT EXISTS ux_pending_actions_short_code_active
    ON pending_actions(short_code) WHERE status IN ('proposed', 'confirmed');
CREATE UNIQUE INDEX IF NOT EXISTS ux_pending_actions_one_per_actor
    ON pending_actions(principal_id) WHERE status IN ('proposed', 'confirmed');
"""

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I — WhatsApp-legible


def _generate_short_code(length: int = 4) -> str:
    """Retries until the result contains at least one letter — the same
    invariant ``SHORT_CODE_PATTERN`` (models.py) requires, so a generated
    code can never collide with a pure-digit ID fragment in free text (see
    confirmation_input.py's module docstring for the collision this
    closes)."""
    while True:
        code = "".join(random.choices(_CODE_ALPHABET, k=length))
        if any(c.isalpha() for c in code):
            return code


class ProposeOutcome(StrEnum):
    CREATED = "created"
    REPLAYED_SAME_REQUEST = "replayed_same_request"
    ACTOR_HAS_PENDING = "actor_has_pending"


class ProposeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    outcome: ProposeOutcome
    action: PendingAction


class ConfirmOutcome(StrEnum):
    CONFIRMED = "confirmed"
    NOT_FOUND = "not_found"
    WRONG_PRINCIPAL = "wrong_principal"
    ALREADY_CONFIRMED = "already_confirmed"
    ALREADY_EXECUTED = "already_executed"
    EXPIRED = "expired"
    WRONG_EPOCH = "wrong_epoch"


class ConfirmResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    outcome: ConfirmOutcome
    action: PendingAction | None = None


class ExecuteOutcome(StrEnum):
    EXECUTED = "executed"
    ALREADY_EXECUTED = "already_executed"
    NOT_CONFIRMED = "not_confirmed"
    EXECUTION_FAILED = "execution_failed"
    NOT_FOUND = "not_found"
    INTEGRITY_FAILURE = "integrity_failure"


class ExecuteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    outcome: ExecuteOutcome
    action: PendingAction | None = None
    execution_record: ExecutionRecord | None = None


class CancelOutcome(StrEnum):
    CANCELLED = "cancelled"
    NOT_FOUND = "not_found"
    ALREADY_TERMINAL = "already_terminal"


class CancelResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    outcome: CancelOutcome
    action: PendingAction | None = None


def _row_to_action(row: sqlite3.Row) -> PendingAction:
    return PendingAction(
        short_code=row["short_code"],
        principal_id=row["principal_id"],
        tool_name=row["tool_name"],
        encrypted_args=row["encrypted_args"],
        args_sha256=row["args_sha256"],
        idempotency_key=row["idempotency_key"],
        status=PendingActionStatus(row["status"]),
        leader_epoch=row["leader_epoch"],
        proposed_at=datetime.fromisoformat(row["proposed_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]),
        confirmed_at=datetime.fromisoformat(row["confirmed_at"]) if row["confirmed_at"] else None,
        executed_at=datetime.fromisoformat(row["executed_at"]) if row["executed_at"] else None,
        execution_result_ref=row["execution_result_ref"],
        cancelled_reason=row["cancelled_reason"],
    )


class SqlitePendingActionStore:
    """Single-connection, synchronous. Team-bot v1 is one process on the
    Mini (F4) — concurrent multi-process writers are out of scope for this
    unit (that is what F9's leader-epoch handoff governs at the fleet
    level, not what this store's own locking needs to solve)."""

    def __init__(self, conn: sqlite3.Connection, cipher: ArgsCipher, *, current_epoch: int = 0) -> None:
        conn.row_factory = sqlite3.Row
        self._conn = conn
        self._cipher = cipher
        self._epoch = current_epoch
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ── propose ──────────────────────────────────────────────────────

    def propose(
        self,
        *,
        principal_id: str,
        tool_name: str,
        args: dict[str, object],
        now: datetime,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> ProposeResult:
        if tool_name not in TOOL_NAMES:
            raise ValueError(f"tool_name {tool_name!r} is not in the F5 registry")

        ciphertext, args_sha256 = self._cipher.encrypt_canonical_args(args)
        idempotency_key = compute_idempotency_key(
            principal_id=principal_id, tool_name=tool_name, args_sha256=args_sha256, now=now
        )

        existing_by_key = self._conn.execute(
            "SELECT * FROM pending_actions WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        if existing_by_key is not None:
            return ProposeResult(
                outcome=ProposeOutcome.REPLAYED_SAME_REQUEST, action=_row_to_action(existing_by_key)
            )

        existing_for_actor = self._conn.execute(
            "SELECT * FROM pending_actions WHERE principal_id = ? AND status IN (?, ?)",
            (principal_id, *_NON_TERMINAL),
        ).fetchone()
        if existing_for_actor is not None:
            return ProposeResult(
                outcome=ProposeOutcome.ACTOR_HAS_PENDING, action=_row_to_action(existing_for_actor)
            )

        expires_at = now + timedelta(seconds=ttl_seconds)
        for _attempt in range(8):
            short_code = _generate_short_code()
            try:
                self._conn.execute(
                    """
                    INSERT INTO pending_actions
                        (short_code, principal_id, tool_name, encrypted_args, args_sha256,
                         idempotency_key, status, leader_epoch, proposed_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        short_code,
                        principal_id,
                        tool_name,
                        ciphertext,
                        args_sha256,
                        idempotency_key,
                        PendingActionStatus.PROPOSED.value,
                        self._epoch,
                        now.isoformat(),
                        expires_at.isoformat(),
                    ),
                )
                self._conn.commit()
                break
            except sqlite3.IntegrityError:
                self._conn.rollback()
                continue
        else:
            raise RuntimeError("could not allocate a unique short_code after 8 attempts")

        row = self._conn.execute(
            "SELECT * FROM pending_actions WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        return ProposeResult(outcome=ProposeOutcome.CREATED, action=_row_to_action(row))

    # ── confirm ──────────────────────────────────────────────────────

    def confirm(
        self, *, short_code: str, confirming_principal_id: str, now: datetime
    ) -> ConfirmResult:
        row = self._conn.execute(
            "SELECT * FROM pending_actions WHERE short_code = ? AND status IN (?, ?, 'executed') "
            "ORDER BY id DESC LIMIT 1",
            (short_code, *_NON_TERMINAL),
        ).fetchone()
        if row is None:
            return ConfirmResult(outcome=ConfirmOutcome.NOT_FOUND)

        action = _row_to_action(row)

        if action.principal_id != confirming_principal_id:
            return ConfirmResult(outcome=ConfirmOutcome.WRONG_PRINCIPAL, action=action)
        if action.status == PendingActionStatus.EXECUTED:
            return ConfirmResult(outcome=ConfirmOutcome.ALREADY_EXECUTED, action=action)
        if action.status == PendingActionStatus.CONFIRMED:
            return ConfirmResult(outcome=ConfirmOutcome.ALREADY_CONFIRMED, action=action)
        if action.expires_at <= now:
            self._expire_row(row["id"])
            return ConfirmResult(outcome=ConfirmOutcome.EXPIRED, action=action)
        if action.leader_epoch != self._epoch:
            return ConfirmResult(outcome=ConfirmOutcome.WRONG_EPOCH, action=action)

        cur = self._conn.execute(
            """
            UPDATE pending_actions
            SET status = ?, confirmed_at = ?
            WHERE id = ? AND status = ? AND leader_epoch = ?
            """,
            (PendingActionStatus.CONFIRMED.value, now.isoformat(), row["id"], PendingActionStatus.PROPOSED.value, self._epoch),
        )
        self._conn.commit()
        if cur.rowcount == 0:
            # Lost a race between the read above and this CAS — re-read and
            # classify fresh rather than assume (review_handler.py's idiom).
            return self.confirm(
                short_code=short_code, confirming_principal_id=confirming_principal_id, now=now
            )

        confirmed_row = self._conn.execute(
            "SELECT * FROM pending_actions WHERE id = ?", (row["id"],)
        ).fetchone()
        return ConfirmResult(outcome=ConfirmOutcome.CONFIRMED, action=_row_to_action(confirmed_row))

    # ── execute ──────────────────────────────────────────────────────

    def execute(
        self,
        *,
        short_code: str,
        now: datetime,
        execute_fn: Callable[[str, dict[str, object], str], tuple[bool, str | None]],
    ) -> ExecuteResult:
        """``execute_fn(tool_name, args, idempotency_key) -> (ok,
        result_ref)`` is injected — this store never calls a CRM directly
        (no CRM client exists in this unit). The ``idempotency_key`` is
        passed through so a real CRM client CAN honor Kimi's note (LENS 6
        §2): "Executor is idempotent on idempotency_key too: crash between
        CRM call and status flip -> retry sees key already applied -> flip
        only" — this store does not own that contract, only carries the key
        to whoever does. Idempotent at THIS layer too: an ALREADY-EXECUTED
        row returns the stored receipt WITHOUT calling ``execute_fn`` again
        (F6: "Replay returns the existing receipt")."""
        row = self._conn.execute(
            "SELECT * FROM pending_actions WHERE short_code = ? ORDER BY id DESC LIMIT 1",
            (short_code,),
        ).fetchone()
        if row is None:
            return ExecuteResult(outcome=ExecuteOutcome.NOT_FOUND)

        action = _row_to_action(row)

        if action.status == PendingActionStatus.EXECUTED:
            record = ExecutionRecord(
                tool_name=action.tool_name,
                ok=True,
                source=ExecutionSource.PENDING_ACTION,
                executed_at=action.executed_at or now,
                result_ref=action.execution_result_ref,
            )
            return ExecuteResult(
                outcome=ExecuteOutcome.ALREADY_EXECUTED, action=action, execution_record=record
            )
        if action.status != PendingActionStatus.CONFIRMED:
            return ExecuteResult(outcome=ExecuteOutcome.NOT_CONFIRMED, action=action)

        try:
            plaintext_args = self._cipher.decrypt_args(
                action.encrypted_args, expected_sha256=action.args_sha256
            )
        except ArgsIntegrityError:
            return ExecuteResult(outcome=ExecuteOutcome.INTEGRITY_FAILURE, action=action)

        # The executor calls the CRM with the STORED payload (F6) — the
        # decrypted args, not anything derived from post-confirmation text.
        ok, result_ref = execute_fn(action.tool_name, plaintext_args, action.idempotency_key)
        if not ok:
            # Row stays CONFIRMED (not a new terminal state F6 never named)
            # — a retry can call execute() again. Whether execute_fn itself
            # is safe to retry is the CRM endpoint's own idempotency
            # contract (Kimi LENS 6 §2), which this store does not own.
            return ExecuteResult(outcome=ExecuteOutcome.EXECUTION_FAILED, action=action)

        executed_at = now
        cur = self._conn.execute(
            """
            UPDATE pending_actions
            SET status = ?, executed_at = ?, execution_result_ref = ?
            WHERE id = ? AND status = ?
            """,
            (
                PendingActionStatus.EXECUTED.value,
                executed_at.isoformat(),
                result_ref,
                row["id"],
                PendingActionStatus.CONFIRMED.value,
            ),
        )
        self._conn.commit()
        if cur.rowcount == 0:
            # A concurrent execute() already claimed it — replay the result.
            return self.execute(short_code=short_code, now=now, execute_fn=execute_fn)

        executed_row = self._conn.execute("SELECT * FROM pending_actions WHERE id = ?", (row["id"],)).fetchone()
        executed_action = _row_to_action(executed_row)
        record = ExecutionRecord(
            tool_name=executed_action.tool_name,
            ok=True,
            source=ExecutionSource.PENDING_ACTION,
            executed_at=executed_at,
            result_ref=result_ref,
        )
        return ExecuteResult(outcome=ExecuteOutcome.EXECUTED, action=executed_action, execution_record=record)

    # ── cancel ───────────────────────────────────────────────────────

    def cancel(self, *, short_code: str, reason: str, now: datetime) -> CancelResult:
        """Kimi LENS 6 §2: "Anything else while a proposal is open ->
        cancel proposal + route message to the LLM normally." Only a
        PROPOSED row can be cancelled — a CONFIRMED one is already past the
        point Kimi's rule targets."""
        row = self._conn.execute(
            "SELECT * FROM pending_actions WHERE short_code = ? ORDER BY id DESC LIMIT 1",
            (short_code,),
        ).fetchone()
        if row is None:
            return CancelResult(outcome=CancelOutcome.NOT_FOUND)
        action = _row_to_action(row)
        if action.status != PendingActionStatus.PROPOSED:
            return CancelResult(outcome=CancelOutcome.ALREADY_TERMINAL, action=action)

        cur = self._conn.execute(
            "UPDATE pending_actions SET status = ?, cancelled_reason = ? WHERE id = ? AND status = ?",
            (PendingActionStatus.CANCELLED.value, reason, row["id"], PendingActionStatus.PROPOSED.value),
        )
        self._conn.commit()
        if cur.rowcount == 0:
            return self.cancel(short_code=short_code, reason=reason, now=now)

        cancelled_row = self._conn.execute("SELECT * FROM pending_actions WHERE id = ?", (row["id"],)).fetchone()
        return CancelResult(outcome=CancelOutcome.CANCELLED, action=_row_to_action(cancelled_row))

    # ── expiry sweep ─────────────────────────────────────────────────

    def expire_stale(self, *, now: datetime) -> int:
        """Sweeps PROPOSED rows past ``expires_at``. Does NOT touch
        CONFIRMED rows — a confirmed action is expected to execute
        immediately after confirm(), and F6 names expiry only for the
        PROPOSED "awaiting confirmation" window."""
        cur = self._conn.execute(
            "UPDATE pending_actions SET status = ? WHERE status = ? AND expires_at <= ?",
            (PendingActionStatus.EXPIRED.value, PendingActionStatus.PROPOSED.value, now.isoformat()),
        )
        self._conn.commit()
        return cur.rowcount

    def _expire_row(self, row_id: int) -> None:
        self._conn.execute(
            "UPDATE pending_actions SET status = ? WHERE id = ? AND status = ?",
            (PendingActionStatus.EXPIRED.value, row_id, PendingActionStatus.PROPOSED.value),
        )
        self._conn.commit()

    def get(self, short_code: str) -> PendingAction | None:
        row = self._conn.execute(
            "SELECT * FROM pending_actions WHERE short_code = ? ORDER BY id DESC LIMIT 1", (short_code,)
        ).fetchone()
        return _row_to_action(row) if row is not None else None
