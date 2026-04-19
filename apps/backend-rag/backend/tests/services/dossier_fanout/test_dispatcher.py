"""Tests for DomainFanoutDispatcher — routing, public_safe gating, record_reuse."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.dossier_fanout.base import (
    ConsumeResult,
    DossierConsumer,
    FanoutSkipReason,
)
from backend.services.dossier_fanout.dispatcher import DomainFanoutDispatcher
from backend.services.intel.dossier_models import (
    ConsumerType,
    ResearchDossier,
    TopicCategory,
)

# ── Test doubles ────────────────────────────────────────────


class _Recording(DossierConsumer):
    """Consumer that records how it was called; configurable behaviour."""

    def __init__(
        self,
        consumer_type: ConsumerType,
        *,
        require_public_safe: bool = False,
        result: ConsumeResult | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self.consumer_type = consumer_type
        self.require_public_safe = require_public_safe
        self._result = result
        self._raise = raise_exc
        self.calls = 0

    async def consume(self, dossier: ResearchDossier) -> ConsumeResult:
        self.calls += 1
        if self._raise is not None:
            raise self._raise
        return self._result or ConsumeResult(
            consumer_type=self.consumer_type,
            ok=True,
            entity_id="id",
        )


def _dossier(
    *,
    domains: list[str] | None = None,
    public_safe: bool = True,
) -> ResearchDossier:
    now = datetime.now(timezone.utc)
    return ResearchDossier(
        id=uuid4(),
        slug="test-slug-abc",
        title="Test dossier",
        topic_category=TopicCategory.VISA,
        domains=domains or ["chatbot", "warroom"],
        public_safe=public_safe,
        facts=[],
        numbers=[],
        citations=[],
        entities_linked=[],
        precedents=[],
        confidence_0_1=0.7,
        freshness_expiry=now + timedelta(days=30),
        source_signals=None,
        language="it",
        summary_short="short",
        summary_medium="medium",
        created_at=now,
        updated_at=now,
        archived_at=None,
    )


# ── Dispatch basics ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_routes_only_matching_domains():
    chatbot = _Recording(ConsumerType.CHATBOT)
    crm = _Recording(ConsumerType.CRM)
    nlm = _Recording(ConsumerType.NLM)
    disp = DomainFanoutDispatcher(
        consumers=[chatbot, crm, nlm],
        repo=None,
    )
    result = await disp.dispatch(_dossier(domains=["chatbot", "warroom"]))

    assert chatbot.calls == 1
    assert crm.calls == 0
    assert nlm.calls == 0

    # crm+nlm present in per_consumer as skipped
    types_skipped = {
        r.consumer_type for r in result.per_consumer if r.skipped
    }
    assert types_skipped == {ConsumerType.CRM, ConsumerType.NLM}


@pytest.mark.asyncio
async def test_skip_reason_domain_not_matched():
    crm = _Recording(ConsumerType.CRM)
    disp = DomainFanoutDispatcher(consumers=[crm], repo=None)
    result = await disp.dispatch(_dossier(domains=["chatbot"]))
    r = result.per_consumer[0]
    assert r.skipped is True
    assert r.skip_reason == FanoutSkipReason.DOMAIN_NOT_MATCHED


@pytest.mark.asyncio
async def test_public_safe_gating_skips_private_dossier():
    nlm = _Recording(ConsumerType.NLM, require_public_safe=True)
    disp = DomainFanoutDispatcher(consumers=[nlm], repo=None)
    result = await disp.dispatch(
        _dossier(domains=["nlm"], public_safe=False),
    )
    r = result.per_consumer[0]
    assert r.skipped is True
    assert r.skip_reason == FanoutSkipReason.NOT_PUBLIC_SAFE
    assert nlm.calls == 0


@pytest.mark.asyncio
async def test_public_safe_consumer_runs_on_public_dossier():
    nlm = _Recording(ConsumerType.NLM, require_public_safe=True)
    disp = DomainFanoutDispatcher(consumers=[nlm], repo=None)
    result = await disp.dispatch(
        _dossier(domains=["nlm"], public_safe=True),
    )
    assert nlm.calls == 1
    assert result.ok_count == 1


# ── Error isolation ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_consumer_exception_caught_as_failure():
    good = _Recording(ConsumerType.CHATBOT)
    bad = _Recording(
        ConsumerType.WARROOM,
        raise_exc=RuntimeError("boom"),
    )
    disp = DomainFanoutDispatcher(consumers=[good, bad], repo=None)
    result = await disp.dispatch(
        _dossier(domains=["chatbot", "warroom"]),
    )
    assert result.ok_count == 1
    assert result.failure_count == 1

    bad_result = next(
        r for r in result.per_consumer if r.consumer_type == ConsumerType.WARROOM
    )
    assert bad_result.ok is False
    assert "RuntimeError" in (bad_result.error or "")


@pytest.mark.asyncio
async def test_parallelism_preserves_per_consumer_order_logically():
    """per_consumer preserves the order of consumers in the list."""
    consumers = [
        _Recording(ConsumerType.CHATBOT),
        _Recording(ConsumerType.CRM),
        _Recording(ConsumerType.WARROOM),
    ]
    disp = DomainFanoutDispatcher(consumers=consumers, repo=None)
    result = await disp.dispatch(
        _dossier(domains=["chatbot", "crm", "warroom"]),
    )
    assert [r.consumer_type for r in result.per_consumer] == [
        ConsumerType.CHATBOT, ConsumerType.CRM, ConsumerType.WARROOM,
    ]


# ── Record reuse ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_reuse_only_for_ok_non_skipped():
    ok_consumer = _Recording(
        ConsumerType.CHATBOT,
        result=ConsumeResult(
            consumer_type=ConsumerType.CHATBOT,
            ok=True,
            entity_id="qdrant:42",
        ),
    )
    fail_consumer = _Recording(
        ConsumerType.CRM,
        result=ConsumeResult(
            consumer_type=ConsumerType.CRM,
            ok=False,
            error="crm pool down",
        ),
    )
    repo = AsyncMock()
    repo.record_reuse = AsyncMock()

    disp = DomainFanoutDispatcher(
        consumers=[ok_consumer, fail_consumer],
        repo=repo,
    )
    result = await disp.dispatch(_dossier(domains=["chatbot", "crm"]))
    assert result.recorded_reuses == 1
    assert repo.record_reuse.await_count == 1
    called_args = repo.record_reuse.await_args.args
    assert called_args[1] == ConsumerType.CHATBOT
    assert repo.record_reuse.await_args.kwargs["consumer_entity_id"] == "qdrant:42"


@pytest.mark.asyncio
async def test_record_reuse_skipped_when_consumer_skipped():
    nlm = _Recording(ConsumerType.NLM, require_public_safe=True)
    repo = AsyncMock()
    repo.record_reuse = AsyncMock()

    disp = DomainFanoutDispatcher(consumers=[nlm], repo=repo)
    await disp.dispatch(
        _dossier(domains=["nlm"], public_safe=False),
    )
    repo.record_reuse.assert_not_called()


@pytest.mark.asyncio
async def test_record_reuse_disabled_by_flag():
    c = _Recording(ConsumerType.CHATBOT)
    repo = AsyncMock()
    repo.record_reuse = AsyncMock()

    disp = DomainFanoutDispatcher(
        consumers=[c], repo=repo, record_reuse=False,
    )
    await disp.dispatch(_dossier(domains=["chatbot"]))
    repo.record_reuse.assert_not_called()


@pytest.mark.asyncio
async def test_record_reuse_failure_isolated():
    c = _Recording(ConsumerType.CHATBOT)
    repo = AsyncMock()
    repo.record_reuse = AsyncMock(side_effect=RuntimeError("pg"))

    disp = DomainFanoutDispatcher(consumers=[c], repo=repo)
    result = await disp.dispatch(_dossier(domains=["chatbot"]))
    # dispatch completes; ok_count reflects successful consumption
    assert result.ok_count == 1
    assert result.recorded_reuses == 0
