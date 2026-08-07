"""Guilt/innocence corpus for the conversation retention floor (Zero, 2026-08-08).

The policy is two answers — "5 anni" and "non cancellare" — and it has two
clock-driven enforcement points (the admin router and the repository) plus one
deliberate carve-out (per-subject erasure). This file asserts all three, because
the previous arrangement was a comment and the comment lost.

Three properties are load-bearing and each is asserted rather than assumed:

  * the refusal happens BEFORE the database is touched (an exploding pool),
  * the refusal ESCAPES the repository's `except Exception: return 0`, which
    would otherwise report a policy violation as a successful "0 rows",
  * the delete opt-in does NOT lift the floor — they are independent guards, and
    the composition is where a two-guard design usually leaks.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.app.routers.admin_conversation_cleanup import (
    DEFAULT_ANONYMIZE_AFTER_DAYS,
    DEFAULT_DELETE_AFTER_DAYS,
    run_conversation_cleanup,
)
from backend.core.retention_policy import (
    ALLOW_CLOCK_DELETE_ENV,
    RETENTION_MIN_DAYS,
    RetentionPolicyViolation,
    clock_delete_allowed,
    enforce_retention_floor,
)
from backend.db.repositories.conversation_repository import ConversationRepository
from backend.jobs.conversation_cleanup import cleanup_conversations

# The windows that were live until 2026-08-08 and are now refused. Named so a
# failure reads as "the old cron's request was accepted", not "30 != 1826".
CRON_DELETE_WINDOW = 30
CRON_ANONYMIZE_WINDOW = 7


def _working_pool(execute_result: str = "DELETE 3", count: int = 3) -> tuple[Any, Any]:
    """A pool that answers normally."""
    pool = MagicMock()
    conn = AsyncMock()
    conn.execute.return_value = execute_result
    conn.fetchval.return_value = count
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm
    return pool, conn


def _exploding_pool() -> Any:
    """A pool that fails the test if anything tries to use the database.

    This is what turns "it returned 400" into "it returned 400 without asking
    the database anything" — the property that makes a dry run of a forbidden
    window impossible, not merely unreported.
    """
    pool = MagicMock()
    pool.acquire.side_effect = AssertionError("the database was acquired despite a policy refusal")
    return pool


# ─────────────────────────── policy module ────────────────────────────────


def test_floor_rejects_below_and_admits_at_the_boundary() -> None:
    with pytest.raises(RetentionPolicyViolation) as exc:
        enforce_retention_floor("days", RETENTION_MIN_DAYS - 1)
    assert str(RETENTION_MIN_DAYS) in str(exc.value)
    # Innocence: exactly at the floor is legal, and so is anything longer.
    enforce_retention_floor("days", RETENTION_MIN_DAYS)
    enforce_retention_floor("days", RETENTION_MIN_DAYS * 2)


def test_five_years_is_1826_days_not_1825() -> None:
    """Leap-inclusive. A 1825-day floor is five *common* years and silently
    short-changes the requirement in four cases out of five."""
    assert RETENTION_MIN_DAYS == 1826


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        (" 1 ", True),
        ("0", False),
        ("yes", False),
        ("", False),
        ("false", False),
    ],
)
def test_delete_switch_vocabulary_is_fail_safe(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    """`yes` is a plausible thing to write and must NOT enable deletion."""
    monkeypatch.setenv(ALLOW_CLOCK_DELETE_ENV, value)
    assert clock_delete_allowed() is expected


def test_delete_switch_is_read_at_call_time_not_import_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The module was imported long before this line ran; flipping the variable
    now must take effect, or the docstring's "never cached" is a lie."""
    monkeypatch.delenv(ALLOW_CLOCK_DELETE_ENV, raising=False)
    assert clock_delete_allowed() is False
    monkeypatch.setenv(ALLOW_CLOCK_DELETE_ENV, "1")
    assert clock_delete_allowed() is True


# ─────────────────────────── router: guilt ────────────────────────────────


@pytest.mark.asyncio
async def test_router_refuses_the_old_crons_delete_window_without_touching_db() -> None:
    with pytest.raises(HTTPException) as exc:
        await run_conversation_cleanup(
            delete_after_days=CRON_DELETE_WINDOW,
            anonymize_after_days=DEFAULT_ANONYMIZE_AFTER_DAYS,
            dry_run=True,
            _access=True,
            pool=_exploding_pool(),
        )
    assert exc.value.status_code == 400
    assert "delete_after_days" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_router_refuses_the_old_crons_anonymize_window() -> None:
    """7 days destroys the five-year record within a week — the window that made
    this floor necessary, and the one an "it's only anonymisation" reading
    waves through."""
    with pytest.raises(HTTPException) as exc:
        await run_conversation_cleanup(
            delete_after_days=DEFAULT_DELETE_AFTER_DAYS,
            anonymize_after_days=CRON_ANONYMIZE_WINDOW,
            dry_run=True,
            _access=True,
            pool=_exploding_pool(),
        )
    assert exc.value.status_code == 400
    assert "anonymize_after_days" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_router_refuses_the_write_path_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ALLOW_CLOCK_DELETE_ENV, raising=False)
    with pytest.raises(HTTPException) as exc:
        await run_conversation_cleanup(
            delete_after_days=DEFAULT_DELETE_AFTER_DAYS,
            anonymize_after_days=DEFAULT_ANONYMIZE_AFTER_DAYS,
            dry_run=False,
            _access=True,
            pool=_exploding_pool(),
        )
    assert exc.value.status_code == 409
    assert ALLOW_CLOCK_DELETE_ENV in str(exc.value.detail)


@pytest.mark.asyncio
async def test_the_delete_optin_does_not_lift_the_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two independent guards. Opting into timed deletion must not also buy a
    30-day window — the composition is where two-guard designs leak."""
    monkeypatch.setenv(ALLOW_CLOCK_DELETE_ENV, "1")
    with pytest.raises(HTTPException) as exc:
        await run_conversation_cleanup(
            delete_after_days=CRON_DELETE_WINDOW,
            anonymize_after_days=CRON_ANONYMIZE_WINDOW,
            dry_run=False,
            _access=True,
            pool=_exploding_pool(),
        )
    assert exc.value.status_code == 400


# ────────────────────────── router: innocence ─────────────────────────────


@pytest.mark.asyncio
async def test_router_default_call_is_a_dry_run_that_works() -> None:
    """The endpoint is not bricked: at its own defaults it counts and reports."""
    pool, _conn = _working_pool(count=3)
    result = await run_conversation_cleanup(
        delete_after_days=DEFAULT_DELETE_AFTER_DAYS,
        anonymize_after_days=DEFAULT_ANONYMIZE_AFTER_DAYS,
        dry_run=True,
        _access=True,
        pool=pool,
    )
    assert result.status == "dry_run"
    assert result.deleted_count == 3
    assert pool.acquire.called


@pytest.mark.asyncio
async def test_router_write_path_runs_once_the_operator_opts_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The capability is recoverable without a code change — that is the whole
    point of the switch, so it is asserted, not assumed."""
    monkeypatch.setenv(ALLOW_CLOCK_DELETE_ENV, "1")
    pool, conn = _working_pool(execute_result="DELETE 2")
    result = await run_conversation_cleanup(
        delete_after_days=DEFAULT_DELETE_AFTER_DAYS,
        anonymize_after_days=DEFAULT_ANONYMIZE_AFTER_DAYS,
        dry_run=False,
        _access=True,
        pool=pool,
    )
    assert result.status == "ok"
    assert conn.execute.called


@pytest.mark.asyncio
async def test_router_defaults_sit_at_the_floor_not_below_it() -> None:
    """Regression pin: they were 90/30 while the cron asked for 30/7."""
    assert DEFAULT_DELETE_AFTER_DAYS == RETENTION_MIN_DAYS
    assert DEFAULT_ANONYMIZE_AFTER_DAYS == RETENTION_MIN_DAYS


# ──────────────────────── repository: guilt ───────────────────────────────


@pytest.mark.asyncio
async def test_repo_delete_refuses_sub_floor_window_and_does_not_return_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The method body is wrapped in `except Exception: return 0`. If the guard
    sat inside it, this refusal would surface as a successful no-op."""
    monkeypatch.setenv(ALLOW_CLOCK_DELETE_ENV, "1")
    repo = ConversationRepository(_exploding_pool())
    with pytest.raises(RetentionPolicyViolation):
        await repo.cleanup_old_conversations(days=CRON_DELETE_WINDOW)


@pytest.mark.asyncio
async def test_repo_delete_refuses_when_the_switch_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ALLOW_CLOCK_DELETE_ENV, raising=False)
    repo = ConversationRepository(_exploding_pool())
    with pytest.raises(RetentionPolicyViolation) as exc:
        await repo.cleanup_old_conversations(days=RETENTION_MIN_DAYS)
    assert ALLOW_CLOCK_DELETE_ENV in str(exc.value)


@pytest.mark.asyncio
async def test_repo_anonymize_refuses_sub_floor_window() -> None:
    repo = ConversationRepository(_exploding_pool())
    with pytest.raises(RetentionPolicyViolation):
        await repo.anonymize_user_data(days=CRON_ANONYMIZE_WINDOW)


@pytest.mark.asyncio
async def test_repo_still_swallows_genuine_database_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Innocence for the swallow itself: a real DB failure keeps returning 0.

    Without this, moving the guards above the try could be "proven" by a change
    that simply stopped swallowing anything — a different behaviour change,
    smuggled in under the same green.
    """
    monkeypatch.setenv(ALLOW_CLOCK_DELETE_ENV, "1")
    pool, conn = _working_pool()
    conn.execute.side_effect = RuntimeError("connection reset")
    repo = ConversationRepository(pool)
    assert await repo.cleanup_old_conversations(days=RETENTION_MIN_DAYS) == 0


# ────────────────────── repository: innocence ─────────────────────────────


@pytest.mark.asyncio
async def test_repo_anonymize_at_the_floor_runs_without_the_delete_switch() -> None:
    """Anonymisation is not a deletion and is not gated by the delete opt-in —
    the two guards are distinct, and conflating them would quietly disable a
    legal operation."""
    pool, conn = _working_pool(execute_result="UPDATE 5")
    repo = ConversationRepository(pool)
    assert await repo.anonymize_user_data(days=RETENTION_MIN_DAYS) == 5
    assert conn.execute.called


@pytest.mark.asyncio
async def test_repo_defaults_are_the_floor() -> None:
    """They were 30 and 7. A default below the floor is a signature advertising
    an argument that always raises."""
    import inspect

    sig = inspect.signature(ConversationRepository.cleanup_old_conversations)
    assert sig.parameters["days"].default == RETENTION_MIN_DAYS
    sig = inspect.signature(ConversationRepository.anonymize_user_data)
    assert sig.parameters["days"].default == RETENTION_MIN_DAYS
    sig = inspect.signature(cleanup_conversations)
    assert sig.parameters["retention_days"].default == RETENTION_MIN_DAYS
    assert sig.parameters["anonymize_days"].default == RETENTION_MIN_DAYS


# ──────────── the carve-out: per-subject erasure stays possible ────────────


@pytest.mark.asyncio
async def test_per_subject_erasure_is_not_floored() -> None:
    """UU PDP Art. 43. A data subject asking us to delete their own history is
    not a clock, and the retention floor must never stand in front of it.

    Asserted by executing the endpoint, not by grepping for the absence of an
    import: "the floor is not applied here" is a behaviour, and behaviour is the
    only thing a form check cannot confirm.
    """
    from backend.app.routers.conversations import clear_conversation_history

    pool, conn = _working_pool(execute_result="DELETE 4")
    result = await clear_conversation_history(
        session_id=None,
        current_user={"email": "subject@example.com"},
        db_pool=pool,
    )
    assert result["success"] is True
    assert result["deleted_count"] == 4
