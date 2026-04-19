"""Tests for AnomalyEventSubscriber — event filtering + graceful errors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from backend.services.cognitive.anomaly_detector import (
    AnomalyDetector,
    AnomalyResult,
)
from backend.services.cognitive.anomaly_subscriber import (
    TRIGGER_EVENT_TYPES,
    AnomalyEventSubscriber,
)
from backend.services.intel.dossier_models import ResearchDossier, TopicCategory


def _dossier(did: UUID | None = None) -> ResearchDossier:
    now = datetime.now(timezone.utc)
    return ResearchDossier(
        id=did or uuid4(),
        slug="s",
        title="t",
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
def intel_and_detector():
    intel = AsyncMock()
    detector = AsyncMock(spec=AnomalyDetector)
    detector.analyze_dossier = AsyncMock(
        return_value=AnomalyResult(
            ran_at=datetime.now(timezone.utc),
        ),
    )
    return intel, detector


def test_trigger_whitelist_only_created():
    """Updates are refreshes — don't re-run anomaly detection."""
    assert TRIGGER_EVENT_TYPES == {"dossier_created"}


@pytest.mark.asyncio
async def test_subscriber_ignores_updated(intel_and_detector):
    intel, detector = intel_and_detector
    sub = AnomalyEventSubscriber(intel_repo=intel, detector=detector)
    out = await sub.handle({
        "event_type": "dossier_updated",
        "dossier_id": str(uuid4()),
    })
    assert out is None
    detector.analyze_dossier.assert_not_called()
    intel.get_dossier.assert_not_called()


@pytest.mark.asyncio
async def test_subscriber_ignores_trend_signal(intel_and_detector):
    intel, detector = intel_and_detector
    sub = AnomalyEventSubscriber(intel_repo=intel, detector=detector)
    out = await sub.handle({"event_type": "trend_signal_detected"})
    assert out is None


@pytest.mark.asyncio
async def test_subscriber_missing_dossier_id(intel_and_detector):
    intel, detector = intel_and_detector
    sub = AnomalyEventSubscriber(intel_repo=intel, detector=detector)
    out = await sub.handle({"event_type": "dossier_created"})
    assert out is None


@pytest.mark.asyncio
async def test_subscriber_bad_uuid(intel_and_detector):
    intel, detector = intel_and_detector
    sub = AnomalyEventSubscriber(intel_repo=intel, detector=detector)
    out = await sub.handle({
        "event_type": "dossier_created",
        "dossier_id": "not-a-uuid",
    })
    assert out is None


@pytest.mark.asyncio
async def test_subscriber_dossier_not_found(intel_and_detector):
    intel, detector = intel_and_detector
    intel.get_dossier = AsyncMock(return_value=None)
    sub = AnomalyEventSubscriber(intel_repo=intel, detector=detector)
    out = await sub.handle({
        "event_type": "dossier_created",
        "dossier_id": str(uuid4()),
    })
    assert out is None
    detector.analyze_dossier.assert_not_called()


@pytest.mark.asyncio
async def test_subscriber_dispatches_on_created(intel_and_detector):
    intel, detector = intel_and_detector
    did = uuid4()
    intel.get_dossier = AsyncMock(return_value=_dossier(did))
    sub = AnomalyEventSubscriber(intel_repo=intel, detector=detector)
    out = await sub.handle({
        "event_type": "dossier_created",
        "dossier_id": str(did),
    })
    assert out is not None
    detector.analyze_dossier.assert_awaited_once()


@pytest.mark.asyncio
async def test_subscriber_get_dossier_exception_caught(intel_and_detector):
    intel, detector = intel_and_detector
    intel.get_dossier = AsyncMock(side_effect=RuntimeError("pg down"))
    sub = AnomalyEventSubscriber(intel_repo=intel, detector=detector)
    out = await sub.handle({
        "event_type": "dossier_created",
        "dossier_id": str(uuid4()),
    })
    assert out is None


@pytest.mark.asyncio
async def test_subscriber_analyze_exception_caught(intel_and_detector):
    intel, detector = intel_and_detector
    intel.get_dossier = AsyncMock(return_value=_dossier())
    detector.analyze_dossier = AsyncMock(side_effect=RuntimeError("boom"))
    sub = AnomalyEventSubscriber(intel_repo=intel, detector=detector)
    out = await sub.handle({
        "event_type": "dossier_created",
        "dossier_id": str(uuid4()),
    })
    assert out is None
