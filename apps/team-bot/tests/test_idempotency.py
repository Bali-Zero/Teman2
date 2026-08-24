"""compute_idempotency_key — composite, hour-bucketed (resolves the
underspecification in F6's frozen field list — see idempotency.py)."""

from __future__ import annotations

from datetime import UTC, datetime

from team_bot.confirmation.idempotency import compute_idempotency_key


def test_same_inputs_same_hour_same_key() -> None:
    a = compute_idempotency_key(
        principal_id="USR-102", tool_name="create_reminder", args_sha256="a" * 64,
        now=datetime(2026, 8, 25, 10, 15, tzinfo=UTC),
    )
    b = compute_idempotency_key(
        principal_id="USR-102", tool_name="create_reminder", args_sha256="a" * 64,
        now=datetime(2026, 8, 25, 10, 45, tzinfo=UTC),  # same hour, different minute
    )
    assert a == b


def test_different_hour_different_key() -> None:
    a = compute_idempotency_key(
        principal_id="USR-102", tool_name="create_reminder", args_sha256="a" * 64,
        now=datetime(2026, 8, 25, 10, 59, tzinfo=UTC),
    )
    b = compute_idempotency_key(
        principal_id="USR-102", tool_name="create_reminder", args_sha256="a" * 64,
        now=datetime(2026, 8, 25, 11, 1, tzinfo=UTC),
    )
    assert a != b


def test_different_actor_different_key_even_with_identical_args() -> None:
    """The exact case args_sha256 ALONE would get wrong (see idempotency.py
    module docstring): two different actors proposing the identical
    mutation must not collide into one row."""
    now = datetime(2026, 8, 25, 10, 15, tzinfo=UTC)
    a = compute_idempotency_key(principal_id="USR-102", tool_name="create_reminder", args_sha256="a" * 64, now=now)
    b = compute_idempotency_key(principal_id="USR-999", tool_name="create_reminder", args_sha256="a" * 64, now=now)
    assert a != b


def test_different_tool_different_key_even_with_identical_args() -> None:
    now = datetime(2026, 8, 25, 10, 15, tzinfo=UTC)
    a = compute_idempotency_key(principal_id="USR-102", tool_name="create_reminder", args_sha256="a" * 64, now=now)
    b = compute_idempotency_key(principal_id="USR-102", tool_name="update_practice_status", args_sha256="a" * 64, now=now)
    assert a != b
