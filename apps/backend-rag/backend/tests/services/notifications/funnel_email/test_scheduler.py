from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.services.notifications.funnel_email import scheduler
from backend.services.notifications.funnel_email.repository import EmailSubscription


def _subscription(
    *,
    sub_id: int = 1,
    trigger_type: str = "visa_clock_d30",
    payload: dict[str, Any] | None = None,
    unsubscribe_token: str = "tok_123",
) -> EmailSubscription:
    now = datetime(2026, 5, 9, 1, 0, tzinfo=timezone.utc)
    return EmailSubscription(
        id=sub_id,
        email="client@example.com",
        app="visa_clock",
        context_hash="hash",
        trigger_type=trigger_type,
        next_fire_at=now,
        fired_count=0,
        unsubscribed=False,
        unsubscribe_token=unsubscribe_token,
        payload=payload,
        created_at=now,
        updated_at=now,
    )


class _RecordingRepository:
    def __init__(self, due: list[EmailSubscription] | None = None) -> None:
        self.upserts: list[dict[str, Any]] = []
        self.due = due or []
        self.fetch_due_limits: list[int] = []
        self.marked_fired: list[tuple[int, datetime | None]] = []

    async def upsert(self, **kwargs: Any) -> EmailSubscription:
        self.upserts.append(kwargs)
        return _subscription(
            sub_id=len(self.upserts),
            trigger_type=kwargs["trigger_type"],
            payload=kwargs["payload"],
        )

    async def fetch_due(self, limit: int = 100) -> list[EmailSubscription]:
        self.fetch_due_limits.append(limit)
        return self.due

    async def mark_fired(
        self,
        subscription_id: int,
        *,
        next_fire_at: datetime | None,
    ) -> None:
        self.marked_fired.append((subscription_id, next_fire_at))


@pytest.mark.asyncio
async def test_subscribe_visa_clock_schedules_all_future_checkpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RecordingRepository()
    monkeypatch.setattr(scheduler, "EmailSubscriptionRepository", lambda pool: repo)

    subscriptions = await scheduler.subscribe_visa_clock(
        email="client@example.com",
        visa_type="E33G",
        entry_date=date(2098, 1, 1),
        expiry_date=date(2099, 1, 1),
        result_hash="result_hash",
        whatsapp_url="https://wa.me/628213107363",
        pool=object(),
    )

    assert [sub.trigger_type for sub in subscriptions] == [
        "visa_clock_d60",
        "visa_clock_d30",
        "visa_clock_d14",
        "visa_clock_d7",
        "visa_clock_d1",
    ]
    assert [call["next_fire_at"] for call in repo.upserts] == [
        datetime(2098, 11, 2, 1, 0, tzinfo=timezone.utc),
        datetime(2098, 12, 2, 1, 0, tzinfo=timezone.utc),
        datetime(2098, 12, 18, 1, 0, tzinfo=timezone.utc),
        datetime(2098, 12, 25, 1, 0, tzinfo=timezone.utc),
        datetime(2098, 12, 31, 1, 0, tzinfo=timezone.utc),
    ]
    assert repo.upserts[0]["payload"] == {
        "visa_type": "E33G",
        "entry_date": "2098-01-01",
        "expiry_date": "2099-01-01",
        "result_hash": "result_hash",
        "whatsapp_url": "https://wa.me/628213107363",
    }


@pytest.mark.asyncio
async def test_subscribe_visa_clock_skips_past_checkpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RecordingRepository()
    monkeypatch.setattr(scheduler, "EmailSubscriptionRepository", lambda pool: repo)

    subscriptions = await scheduler.subscribe_visa_clock(
        email="client@example.com",
        visa_type="E33G",
        entry_date=date(2000, 1, 1),
        expiry_date=date(2000, 2, 1),
        result_hash="result_hash",
        whatsapp_url="https://wa.me/628213107363",
        pool=object(),
    )

    assert subscriptions == []
    assert repo.upserts == []


@pytest.mark.asyncio
async def test_subscribe_visa_match_prearrival_schedules_future_nudge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RecordingRepository()
    monkeypatch.setattr(scheduler, "EmailSubscriptionRepository", lambda pool: repo)

    subscription = await scheduler.subscribe_visa_match_prearrival(
        email="client@example.com",
        recommended_visa="D12",
        arrival_date=date(2099, 1, 10),
        pre_arrival_steps=["Passport valid", "Return ticket"],
        result_hash="hash",
        whatsapp_url="https://wa.me/628213107363",
        pool=object(),
    )

    assert subscription is not None
    assert subscription.trigger_type == "visa_match_prearrival_d7"
    assert repo.upserts == [
        {
            "email": "client@example.com",
            "app": "visa_match",
            "trigger_type": "visa_match_prearrival_d7",
            "payload": {
                "recommended_visa": "D12",
                "arrival_date": "2099-01-10",
                "pre_arrival_steps": ["Passport valid", "Return ticket"],
                "result_hash": "hash",
                "whatsapp_url": "https://wa.me/628213107363",
            },
            "next_fire_at": datetime(2099, 1, 3, 1, 0, tzinfo=timezone.utc),
        }
    ]


@pytest.mark.asyncio
async def test_subscribe_visa_match_prearrival_returns_none_for_past_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RecordingRepository()
    monkeypatch.setattr(scheduler, "EmailSubscriptionRepository", lambda pool: repo)

    subscription = await scheduler.subscribe_visa_match_prearrival(
        email="client@example.com",
        recommended_visa="D12",
        arrival_date=date(2000, 1, 10),
        pre_arrival_steps=["Passport valid"],
        result_hash="hash",
        whatsapp_url="https://wa.me/628213107363",
        pool=object(),
    )

    assert subscription is None
    assert repo.upserts == []


def test_render_dispatches_clock_with_formatted_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler, "_PUBLIC_HOST", "https://example.test")
    rendered = scheduler._render(
        _subscription(
            trigger_type="visa_clock_d7",
            payload={
                "visa_type": "E33G",
                "expiry_date": "2099-01-01",
                "whatsapp_url": "https://wa.me/628213107363",
            },
            unsubscribe_token="tok_clock",
        )
    )

    assert "E33G" in rendered.subject
    assert "1 Jan 2099" in rendered.preheader
    assert "https://example.test/api/funnel_email/unsubscribe/tok_clock" in rendered.html


def test_render_dispatches_match_prearrival(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler, "_PUBLIC_HOST", "https://example.test")
    rendered = scheduler._render(
        _subscription(
            trigger_type="visa_match_prearrival_d7",
            payload={
                "recommended_visa": "D12",
                "arrival_date": "2099-01-10",
                "whatsapp_url": "https://wa.me/628213107363",
                "pre_arrival_steps": ["Passport valid", "Return ticket"],
            },
            unsubscribe_token="tok_match",
        )
    )

    assert rendered.subject == "Arriving in Bali next week? D12 checklist inside"
    assert "Passport valid" in rendered.html
    assert "10 Jan 2099" in rendered.html
    assert "https://example.test/api/funnel_email/unsubscribe/tok_match" in rendered.html


def test_render_rejects_unknown_trigger_type() -> None:
    with pytest.raises(ValueError, match="no renderer"):
        scheduler._render(_subscription(trigger_type="unknown_trigger"))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2099-01-10", "10 Jan 2099"),
        ("not-a-date", "not-a-date"),
        (None, ""),
    ],
)
def test_fmt_date_handles_valid_invalid_and_missing_inputs(
    raw: str | None,
    expected: str,
) -> None:
    assert scheduler._fmt_date(raw) == expected


@pytest.mark.asyncio
async def test_fire_due_sends_rendered_rows_and_skips_render_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RecordingRepository(
        due=[
            _subscription(
                sub_id=1,
                trigger_type="visa_clock_d30",
                payload={
                    "visa_type": "E33G",
                    "expiry_date": "2099-01-01",
                    "whatsapp_url": "https://wa.me/628213107363",
                },
            ),
            _subscription(sub_id=2, trigger_type="unknown_trigger", payload={}),
        ]
    )
    send_internal_email = AsyncMock()
    monkeypatch.setattr(scheduler, "EmailSubscriptionRepository", lambda pool: repo)
    monkeypatch.setattr(scheduler, "send_internal_email", send_internal_email)

    result = await scheduler.fire_due(pool=object(), limit=2)

    assert result == {"due": 2, "sent": 1, "skipped_render": 1}
    assert repo.fetch_due_limits == [2]
    assert repo.marked_fired == [(1, None)]
    send_internal_email.assert_awaited_once()
    call_kwargs = send_internal_email.await_args.kwargs
    assert call_kwargs["to"] == "client@example.com"
    assert "E33G" in call_kwargs["subject"]
    assert call_kwargs["log_context"] == "funnel=visa_clock trigger=visa_clock_d30 sub_id=1"
