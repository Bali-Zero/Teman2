"""Tests for IntelEventSubscriber — event filtering + graceful errors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from backend.services.dossier_fanout.dispatcher import (
    DomainFanoutDispatcher,
    FanoutResult,
)
from backend.services.dossier_fanout.subscriber import (
    DOSSIER_EVENT_TYPES,
    IntelEventSubscriber,
)
from backend.services.intel.dossier_models import ResearchDossier, TopicCategory


def _dossier(did: UUID | None = None) -> ResearchDossier:
    now = datetime.now(timezone.utc)
    return ResearchDossier(
        id=did or uuid4(),
        slug="s",
        title="T",
        topic_category=TopicCategory.VISA,
        domains=["chatbot"],
        public_safe=True,
        facts=[],
        numbers=[],
        citations=[],
        entities_linked=[],
        precedents=[],
        confidence_0_1=0.7,
        freshness_expiry=now + timedelta(days=30),
        source_signals=None,
        language="it",
        summary_short="s",
        summary_medium="m",
        created_at=now,
        updated_at=now,
        archived_at=None,
    )


@pytest.fixture
def repo_dispatcher():
    repo = AsyncMock()
    dispatcher = AsyncMock(spec=DomainFanoutDispatcher)
    dispatcher.dispatch = AsyncMock(
        return_value=FanoutResult(dossier_id=uuid4(), ran_at=datetime.now(timezone.utc)),
    )
    return repo, dispatcher


def test_dossier_event_types_whitelist():
    assert DOSSIER_EVENT_TYPES == {"dossier_created", "dossier_updated"}


@pytest.mark.asyncio
async def test_handle_ignores_trend_signal_event(repo_dispatcher):
    repo, dispatcher = repo_dispatcher
    sub = IntelEventSubscriber(repo=repo, dispatcher=dispatcher)
    out = await sub.handle({
        "event_type": "trend_signal_detected",
        "signal_id": str(uuid4()),
    })
    assert out is None
    dispatcher.dispatch.assert_not_called()
    repo.get_dossier.assert_not_called()


@pytest.mark.asyncio
async def test_handle_requires_dossier_id(repo_dispatcher):
    repo, dispatcher = repo_dispatcher
    sub = IntelEventSubscriber(repo=repo, dispatcher=dispatcher)
    out = await sub.handle({"event_type": "dossier_created"})
    assert out is None
    dispatcher.dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_handle_rejects_bad_uuid(repo_dispatcher):
    repo, dispatcher = repo_dispatcher
    sub = IntelEventSubscriber(repo=repo, dispatcher=dispatcher)
    out = await sub.handle({
        "event_type": "dossier_created",
        "dossier_id": "not-a-uuid",
    })
    assert out is None
    dispatcher.dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_handle_dispatches_on_dossier_created(repo_dispatcher):
    repo, dispatcher = repo_dispatcher
    did = uuid4()
    repo.get_dossier = AsyncMock(return_value=_dossier(did))
    sub = IntelEventSubscriber(repo=repo, dispatcher=dispatcher)
    out = await sub.handle({
        "event_type": "dossier_created",
        "dossier_id": str(did),
    })
    assert out is not None
    dispatcher.dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_dispatches_on_dossier_updated(repo_dispatcher):
    repo, dispatcher = repo_dispatcher
    did = uuid4()
    repo.get_dossier = AsyncMock(return_value=_dossier(did))
    sub = IntelEventSubscriber(repo=repo, dispatcher=dispatcher)
    out = await sub.handle({
        "event_type": "dossier_updated",
        "dossier_id": str(did),
    })
    assert out is not None


@pytest.mark.asyncio
async def test_handle_dossier_not_found_silently(repo_dispatcher):
    repo, dispatcher = repo_dispatcher
    repo.get_dossier = AsyncMock(return_value=None)
    sub = IntelEventSubscriber(repo=repo, dispatcher=dispatcher)
    out = await sub.handle({
        "event_type": "dossier_created",
        "dossier_id": str(uuid4()),
    })
    assert out is None
    dispatcher.dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_handle_get_dossier_exception_caught(repo_dispatcher):
    repo, dispatcher = repo_dispatcher
    repo.get_dossier = AsyncMock(side_effect=RuntimeError("pg down"))
    sub = IntelEventSubscriber(repo=repo, dispatcher=dispatcher)
    out = await sub.handle({
        "event_type": "dossier_created",
        "dossier_id": str(uuid4()),
    })
    assert out is None
    dispatcher.dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_handle_dispatch_exception_caught(repo_dispatcher):
    repo, dispatcher = repo_dispatcher
    repo.get_dossier = AsyncMock(return_value=_dossier())
    dispatcher.dispatch = AsyncMock(side_effect=RuntimeError("boom"))
    sub = IntelEventSubscriber(repo=repo, dispatcher=dispatcher)
    out = await sub.handle({
        "event_type": "dossier_created",
        "dossier_id": str(uuid4()),
    })
    assert out is None
