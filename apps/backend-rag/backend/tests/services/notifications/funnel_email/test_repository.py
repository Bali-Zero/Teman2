from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.notifications.funnel_email import repository as repo_module
from backend.services.notifications.funnel_email.repository import (
    EmailSubscription,
    EmailSubscriptionRepository,
    context_hash,
    new_unsubscribe_token,
)


def _row(**overrides: Any) -> dict[str, Any]:
    now = datetime(2026, 5, 9, 1, 0, tzinfo=timezone.utc)
    data: dict[str, Any] = {
        "id": 42,
        "email": "client@example.com",
        "app": "visa_clock",
        "context_hash": "abc123",
        "trigger_type": "visa_clock_d30",
        "next_fire_at": now,
        "fired_count": 0,
        "unsubscribed": False,
        "unsubscribe_token": "tok_123",
        "payload": {"visa_type": "E33G"},
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return data


def test_context_hash_is_stable_order_independent_and_short() -> None:
    left = {"email": "client@example.com", "payload": {"b": 2, "a": 1}}
    right = {"payload": {"a": 1, "b": 2}, "email": "client@example.com"}

    digest = context_hash(left)

    assert digest == context_hash(right)
    assert len(digest) == 20
    assert digest != context_hash({"email": "other@example.com"})


def test_new_unsubscribe_token_uses_requested_length_and_alphabet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(repo_module.secrets, "choice", lambda alphabet: alphabet[-1])

    token = new_unsubscribe_token(length=8)

    assert token == "9" * 8


@pytest.mark.asyncio
async def test_upsert_normalizes_email_and_serializes_payload(mock_db_pool: Any) -> None:
    pool, conn = mock_db_pool
    payload = {"visa_type": "E33G", "expiry_date": "2099-01-01"}
    next_fire_at = datetime(2098, 12, 2, 1, 0, tzinfo=timezone.utc)
    conn.fetchrow.return_value = _row(
        email="client@example.com",
        context_hash=context_hash(payload),
        payload=json.dumps(payload),
        next_fire_at=next_fire_at,
    )

    subscription = await EmailSubscriptionRepository(pool).upsert(
        email=" Client@Example.COM ",
        app="visa_clock",
        trigger_type="visa_clock_d30",
        payload=payload,
        next_fire_at=next_fire_at,
    )

    call_args = conn.fetchrow.await_args.args
    assert call_args[1] == "client@example.com"
    assert call_args[2] == "visa_clock"
    assert call_args[3] == context_hash(payload)
    assert call_args[4] == "visa_clock_d30"
    assert call_args[5] == next_fire_at
    assert json.loads(call_args[7]) == payload
    assert subscription.context_hash == context_hash(payload)
    assert subscription.next_fire_at == next_fire_at
    assert subscription.payload == payload


@pytest.mark.asyncio
async def test_upsert_returns_existing_subscription_on_insert_conflict(mock_db_pool: Any) -> None:
    pool, conn = mock_db_pool
    payload = {"recommended_visa": "D12"}
    conn.fetchrow.side_effect = [
        None,
        _row(
            app="visa_match",
            context_hash=context_hash(payload),
            trigger_type="visa_match_prearrival_d7",
            payload=payload,
        ),
    ]

    subscription = await EmailSubscriptionRepository(pool).upsert(
        email="client@example.com",
        app="visa_match",
        trigger_type="visa_match_prearrival_d7",
        payload=payload,
        next_fire_at=None,
    )

    assert conn.fetchrow.await_count == 2
    select_args = conn.fetchrow.await_args_list[1].args
    assert select_args[1:] == (
        "client@example.com",
        "visa_match",
        context_hash(payload),
        "visa_match_prearrival_d7",
    )
    assert subscription.app == "visa_match"
    assert subscription.trigger_type == "visa_match_prearrival_d7"


@pytest.mark.asyncio
async def test_fetch_due_maps_rows_and_passes_limit(mock_db_pool: Any) -> None:
    pool, conn = mock_db_pool
    conn.fetch.return_value = [
        _row(id=1, payload=json.dumps({"visa_type": "E33G"})),
        _row(id=2, payload={"visa_type": "D12"}, trigger_type="visa_clock_d60"),
    ]

    due = await EmailSubscriptionRepository(pool).fetch_due(limit=25)

    assert [sub.id for sub in due] == [1, 2]
    assert due[0].payload == {"visa_type": "E33G"}
    assert conn.fetch.await_args.args[1] == 25


@pytest.mark.asyncio
async def test_mark_fired_updates_counter_and_next_fire(mock_db_pool: Any) -> None:
    pool, conn = mock_db_pool
    next_fire_at = datetime(2099, 1, 1, 1, 0, tzinfo=timezone.utc)

    await EmailSubscriptionRepository(pool).mark_fired(42, next_fire_at=next_fire_at)

    call_args = conn.execute.await_args.args
    assert call_args[1:] == (next_fire_at, 42)


@pytest.mark.asyncio
async def test_unsubscribe_by_token_marks_all_rows_for_email_and_app(mock_db_pool: Any) -> None:
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {"email": "client@example.com", "app": "visa_clock"}
    conn.execute.return_value = "UPDATE 3"

    count = await EmailSubscriptionRepository(pool).unsubscribe_by_token("tok_123")

    assert count == 3
    assert conn.fetchrow.await_args.args[1] == "tok_123"
    assert conn.execute.await_args.args[1:] == ("client@example.com", "visa_clock")


@pytest.mark.asyncio
async def test_unsubscribe_by_token_returns_zero_when_token_missing(mock_db_pool: Any) -> None:
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = None

    count = await EmailSubscriptionRepository(pool).unsubscribe_by_token("missing")

    assert count == 0
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("execute_result", ["UPDATE", "not-a-count"])
async def test_unsubscribe_by_token_returns_zero_for_unparseable_update_count(
    execute_result: str,
) -> None:
    pool = MagicMock()
    conn = AsyncMock()

    class _Ctx:
        async def __aenter__(self) -> AsyncMock:
            return conn

        async def __aexit__(self, *args: Any) -> None:
            return None

    pool.acquire = MagicMock(return_value=_Ctx())
    conn.fetchrow.return_value = {"email": "client@example.com", "app": "visa_clock"}
    conn.execute.return_value = execute_result

    count = await EmailSubscriptionRepository(pool).unsubscribe_by_token("tok_123")

    assert count == 0


def test_row_to_sub_decodes_json_payload() -> None:
    subscription = EmailSubscriptionRepository._row_to_sub(
        _row(payload='{"visa_type": "E33G", "expiry_date": "2099-01-01"}')
    )

    assert isinstance(subscription, EmailSubscription)
    assert subscription.payload == {"visa_type": "E33G", "expiry_date": "2099-01-01"}
