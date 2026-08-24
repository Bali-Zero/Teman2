"""SqlitePendingActionStore — the F6 CAS state machine end-to-end.

Every test uses a fresh in-memory sqlite DB and an ephemeral Fernet key —
no shared state between tests, no real CRM (execute_fn is a fake).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from team_bot.confirmation.crypto import ArgsCipher
from team_bot.confirmation.models import PendingActionStatus
from team_bot.confirmation.store import (
    CancelOutcome,
    ConfirmOutcome,
    ExecuteOutcome,
    ProposeOutcome,
    SqlitePendingActionStore,
)

_NOW = datetime(2026, 8, 25, 10, 0, 0, tzinfo=UTC)


def _store(*, epoch: int = 0) -> SqlitePendingActionStore:
    conn = sqlite3.connect(":memory:")
    cipher = ArgsCipher(Fernet.generate_key())
    return SqlitePendingActionStore(conn, cipher, current_epoch=epoch)


def _ok_execute_fn(tool_name: str, args: dict, idempotency_key: str) -> tuple[bool, str | None]:
    return True, f"AUD-{idempotency_key[:8]}"


# ---------------------------------------------------------------------------
# propose()
# ---------------------------------------------------------------------------


def test_propose_creates_a_proposed_row() -> None:
    store = _store()
    result = store.propose(
        principal_id="USR-102",
        tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"},
        now=_NOW,
    )
    assert result.outcome == ProposeOutcome.CREATED
    assert result.action.status == PendingActionStatus.PROPOSED
    assert result.action.principal_id == "USR-102"
    assert result.action.leader_epoch == 0
    assert result.action.expires_at == _NOW + timedelta(seconds=300)


def test_propose_rejects_a_tool_not_in_the_registry() -> None:
    store = _store()
    with pytest.raises(ValueError):
        store.propose(principal_id="USR-102", tool_name="delete_everything", args={}, now=_NOW)


def test_propose_same_request_within_the_hour_replays() -> None:
    store = _store()
    args = {"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}
    first = store.propose(principal_id="USR-102", tool_name="update_practice_status", args=args, now=_NOW)
    second = store.propose(
        principal_id="USR-102", tool_name="update_practice_status", args=args, now=_NOW + timedelta(minutes=5)
    )
    assert second.outcome == ProposeOutcome.REPLAYED_SAME_REQUEST
    assert second.action.short_code == first.action.short_code


def test_propose_while_actor_has_a_pending_action_is_rejected() -> None:
    store = _store()
    first = store.propose(
        principal_id="USR-102",
        tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"},
        now=_NOW,
    )
    second = store.propose(
        principal_id="USR-102",
        tool_name="open_practice",
        args={
            "client_id": "CL-1042",
            "practice_type": "limited_stay_kitas",
            "assigned_to": "USR-102",
            "priority": "normal",
            "source_channel": "whatsapp",
        },
        now=_NOW,
    )
    assert second.outcome == ProposeOutcome.ACTOR_HAS_PENDING
    assert second.action.short_code == first.action.short_code


def test_two_different_actors_can_each_have_their_own_pending_action() -> None:
    store = _store()
    a = store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}, now=_NOW,
    )
    b = store.propose(
        principal_id="USR-103", tool_name="update_practice_status",
        args={"practice_id": "PR-1043", "new_status": "approved", "reason_code": "completed"}, now=_NOW,
    )
    assert a.outcome == ProposeOutcome.CREATED
    assert b.outcome == ProposeOutcome.CREATED
    assert a.action.short_code != b.action.short_code


# ---------------------------------------------------------------------------
# confirm()
# ---------------------------------------------------------------------------


def test_confirm_happy_path() -> None:
    store = _store()
    proposed = store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}, now=_NOW,
    )
    result = store.confirm(
        short_code=proposed.action.short_code, confirming_principal_id="USR-102", now=_NOW
    )
    assert result.outcome == ConfirmOutcome.CONFIRMED
    assert result.action.status == PendingActionStatus.CONFIRMED
    assert result.action.confirmed_at == _NOW


def test_confirm_unknown_code_is_not_found() -> None:
    store = _store()
    result = store.confirm(short_code="ZZZZ", confirming_principal_id="USR-102", now=_NOW)
    assert result.outcome == ConfirmOutcome.NOT_FOUND
    assert result.action is None


def test_confirm_by_a_different_principal_is_rejected() -> None:
    store = _store()
    proposed = store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}, now=_NOW,
    )
    result = store.confirm(
        short_code=proposed.action.short_code, confirming_principal_id="USR-999", now=_NOW
    )
    assert result.outcome == ConfirmOutcome.WRONG_PRINCIPAL


def test_double_confirm_is_idempotent() -> None:
    store = _store()
    proposed = store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}, now=_NOW,
    )
    code = proposed.action.short_code
    first = store.confirm(short_code=code, confirming_principal_id="USR-102", now=_NOW)
    second = store.confirm(short_code=code, confirming_principal_id="USR-102", now=_NOW + timedelta(seconds=1))
    assert first.outcome == ConfirmOutcome.CONFIRMED
    assert second.outcome == ConfirmOutcome.ALREADY_CONFIRMED
    # A double-tap "sì sì" confirms once — the timestamp does not move.
    assert second.action.confirmed_at == first.action.confirmed_at


def test_confirm_after_expiry_is_rejected() -> None:
    store = _store()
    proposed = store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"},
        now=_NOW, ttl_seconds=300,
    )
    late = _NOW + timedelta(seconds=301)
    result = store.confirm(short_code=proposed.action.short_code, confirming_principal_id="USR-102", now=late)
    assert result.outcome == ConfirmOutcome.EXPIRED


def test_confirm_from_a_stale_leader_epoch_is_rejected() -> None:
    # Two "nodes" sharing one underlying DB (in reality Mini/Pro would each
    # have their own connection to the replicated sqlite file — out of
    # scope here) at different epochs, simulating a stale node still
    # running the OLD epoch after an F9 failover bumped the fleet epoch to
    # 1. This store never GENERATES the epoch itself, only refuses a
    # mismatch (see store.py module docstring).
    conn = sqlite3.connect(":memory:")
    cipher = ArgsCipher(Fernet.generate_key())
    epoch_0_store = SqlitePendingActionStore(conn, cipher, current_epoch=0)
    epoch_1_store = SqlitePendingActionStore(conn, cipher, current_epoch=1)

    proposed = epoch_0_store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}, now=_NOW,
    )
    result = epoch_1_store.confirm(
        short_code=proposed.action.short_code, confirming_principal_id="USR-102", now=_NOW
    )
    assert result.outcome == ConfirmOutcome.WRONG_EPOCH


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def test_execute_happy_path_calls_execute_fn_with_decrypted_args() -> None:
    store = _store()
    args = {"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}
    proposed = store.propose(principal_id="USR-102", tool_name="update_practice_status", args=args, now=_NOW)
    code = proposed.action.short_code
    store.confirm(short_code=code, confirming_principal_id="USR-102", now=_NOW)

    seen: list[tuple[str, dict, str]] = []

    def capturing_execute_fn(tool_name: str, decrypted_args: dict, idem_key: str) -> tuple[bool, str | None]:
        seen.append((tool_name, decrypted_args, idem_key))
        return True, "AUD-12345"

    result = store.execute(short_code=code, now=_NOW, execute_fn=capturing_execute_fn)

    assert result.outcome == ExecuteOutcome.EXECUTED
    assert result.execution_record is not None
    assert result.execution_record.ok is True
    assert result.execution_record.tool_name == "update_practice_status"
    assert seen == [("update_practice_status", args, proposed.action.idempotency_key)]


def test_execute_before_confirm_is_rejected_and_execute_fn_never_called() -> None:
    store = _store()
    proposed = store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}, now=_NOW,
    )
    calls: list[object] = []

    def spy(tool_name: str, args: dict, idem_key: str) -> tuple[bool, str | None]:
        calls.append((tool_name, args, idem_key))
        return True, "AUD"

    result = store.execute(short_code=proposed.action.short_code, now=_NOW, execute_fn=spy)
    assert result.outcome == ExecuteOutcome.NOT_CONFIRMED
    assert calls == []


def test_execute_unknown_code_is_not_found() -> None:
    store = _store()
    result = store.execute(short_code="ZZZZ", now=_NOW, execute_fn=_ok_execute_fn)
    assert result.outcome == ExecuteOutcome.NOT_FOUND


def test_execute_replay_does_not_call_execute_fn_again() -> None:
    """F6: 'Replay returns the existing receipt.'"""
    store = _store()
    proposed = store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}, now=_NOW,
    )
    code = proposed.action.short_code
    store.confirm(short_code=code, confirming_principal_id="USR-102", now=_NOW)

    call_count = 0

    def counting_execute_fn(tool_name: str, args: dict, idem_key: str) -> tuple[bool, str | None]:
        nonlocal call_count
        call_count += 1
        return True, "AUD-12345"

    first = store.execute(short_code=code, now=_NOW, execute_fn=counting_execute_fn)
    second = store.execute(short_code=code, now=_NOW + timedelta(seconds=5), execute_fn=counting_execute_fn)

    assert call_count == 1
    assert first.outcome == ExecuteOutcome.EXECUTED
    assert second.outcome == ExecuteOutcome.ALREADY_EXECUTED
    assert second.execution_record.result_ref == first.execution_record.result_ref


def test_execute_failure_leaves_row_confirmed_and_a_retry_can_succeed() -> None:
    store = _store()
    proposed = store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}, now=_NOW,
    )
    code = proposed.action.short_code
    store.confirm(short_code=code, confirming_principal_id="USR-102", now=_NOW)

    attempts = {"n": 0}

    def flaky_execute_fn(tool_name: str, args: dict, idem_key: str) -> tuple[bool, str | None]:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return False, None
        return True, "AUD-retry"

    first = store.execute(short_code=code, now=_NOW, execute_fn=flaky_execute_fn)
    assert first.outcome == ExecuteOutcome.EXECUTION_FAILED
    assert store.get(code).status == PendingActionStatus.CONFIRMED

    second = store.execute(short_code=code, now=_NOW, execute_fn=flaky_execute_fn)
    assert second.outcome == ExecuteOutcome.EXECUTED
    assert attempts["n"] == 2


# ---------------------------------------------------------------------------
# cancel()
# ---------------------------------------------------------------------------


def test_cancel_a_proposed_row() -> None:
    store = _store()
    proposed = store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}, now=_NOW,
    )
    result = store.cancel(short_code=proposed.action.short_code, reason="user sent something else", now=_NOW)
    assert result.outcome == CancelOutcome.CANCELLED
    assert result.action.status == PendingActionStatus.CANCELLED
    assert result.action.cancelled_reason == "user sent something else"


def test_cancel_an_already_confirmed_row_is_a_no_op_report() -> None:
    store = _store()
    proposed = store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}, now=_NOW,
    )
    store.confirm(short_code=proposed.action.short_code, confirming_principal_id="USR-102", now=_NOW)
    result = store.cancel(short_code=proposed.action.short_code, reason="too late", now=_NOW)
    assert result.outcome == CancelOutcome.ALREADY_TERMINAL


def test_cancel_frees_the_actor_slot_for_a_new_proposal() -> None:
    store = _store()
    proposed = store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}, now=_NOW,
    )
    store.cancel(short_code=proposed.action.short_code, reason="changed their mind", now=_NOW)

    second = store.propose(
        principal_id="USR-102", tool_name="open_practice",
        args={
            "client_id": "CL-1042", "practice_type": "limited_stay_kitas",
            "assigned_to": "USR-102", "priority": "normal", "source_channel": "whatsapp",
        },
        now=_NOW,
    )
    assert second.outcome == ProposeOutcome.CREATED


# ---------------------------------------------------------------------------
# expire_stale()
# ---------------------------------------------------------------------------


def test_expire_stale_sweeps_only_expired_proposed_rows() -> None:
    store = _store()
    stale = store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"},
        now=_NOW, ttl_seconds=60,
    )
    fresh = store.propose(
        principal_id="USR-103", tool_name="update_practice_status",
        args={"practice_id": "PR-1043", "new_status": "approved", "reason_code": "completed"},
        now=_NOW, ttl_seconds=600,
    )
    later = _NOW + timedelta(seconds=120)
    swept = store.expire_stale(now=later)

    assert swept == 1
    assert store.get(stale.action.short_code).status == PendingActionStatus.EXPIRED
    assert store.get(fresh.action.short_code).status == PendingActionStatus.PROPOSED


def test_expire_stale_frees_the_actor_slot() -> None:
    store = _store()
    proposed = store.propose(
        principal_id="USR-102", tool_name="update_practice_status",
        args={"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"},
        now=_NOW, ttl_seconds=60,
    )
    store.expire_stale(now=_NOW + timedelta(seconds=120))

    second = store.propose(
        principal_id="USR-102", tool_name="open_practice",
        args={
            "client_id": "CL-1042", "practice_type": "limited_stay_kitas",
            "assigned_to": "USR-102", "priority": "normal", "source_channel": "whatsapp",
        },
        now=_NOW + timedelta(seconds=121),
    )
    assert second.outcome == ProposeOutcome.CREATED
    _ = proposed
