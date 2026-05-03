"""Tests for AnomalyDetector — pairwise compare + severity + idempotency."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from backend.services.cognitive.anomaly_detector import (
    PAIR_IDEMPOTENCY_DAYS,
    AnomalyDetector,
    _extract_contradictions,
    _render_prompt,
)
from backend.services.cognitive.models import (
    AlertSeverity,
    ComplianceAlert,
)
from backend.services.council.cli_runners import CLIRunner, RunnerResult
from backend.services.intel.dossier_models import ResearchDossier, TopicCategory


@dataclass
class MockRunner(CLIRunner):
    name: str = "mock-claude"
    default_timeout: int = 60
    scripts: list[str] = field(default_factory=list)
    call_count: int = 0
    fail: bool = False

    async def run(self, prompt, timeout=None) -> RunnerResult:
        idx = self.call_count
        self.call_count += 1
        if self.fail:
            return RunnerResult(
                runner_name=self.name,
                prompt_chars=len(prompt),
                ok=False,
                error="runner down",
            )
        if idx >= len(self.scripts):
            return RunnerResult(
                runner_name=self.name,
                prompt_chars=len(prompt),
                ok=False,
                error="exhausted",
            )
        return RunnerResult(
            runner_name=self.name,
            prompt_chars=len(prompt),
            ok=True,
            output=self.scripts[idx],
        )


def _dossier(
    *,
    did: UUID | None = None,
    category: TopicCategory = TopicCategory.TAX,
    title: str = "Dossier",
) -> ResearchDossier:
    now = datetime.now(timezone.utc)
    return ResearchDossier(
        id=did or uuid4(),
        slug=f"s-{uuid4().hex[:6]}",
        title=title,
        topic_category=category,
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
        summary_short="short",
        summary_medium="medium",
        created_at=now,
        updated_at=now,
        archived_at=None,
    )


def _returned_alert(
    reference_id: UUID,
    other_id: UUID,
    severity: AlertSeverity = AlertSeverity.HIGH,
) -> ComplianceAlert:
    return ComplianceAlert(
        id=uuid4(),
        detected_at=datetime.now(timezone.utc),
        dossier_a_id=reference_id,
        dossier_b_id=other_id,
        contradiction_type="grace_vs_enforcement",
        severity=severity,
    )


def _contradictions(items: list[dict]) -> str:
    return json.dumps({"contradictions": items})


# ── helper unit tests ─────────────────────────────────────────


def test_extract_contradictions_none():
    assert _extract_contradictions({}) == []


def test_extract_contradictions_wrong_type():
    assert _extract_contradictions({"contradictions": "bad"}) == []


def test_extract_contradictions_filters_non_dicts():
    raw = {"contradictions": [{"a": 1}, "nope", 2]}
    assert len(_extract_contradictions(raw)) == 1


def test_render_prompt_mentions_both_dossiers():
    ref = _dossier(title="Reference")
    c1 = _dossier(title="Candidate 1")
    c2 = _dossier(title="Candidate 2")
    prompt = _render_prompt(ref, [c1, c2])
    assert str(ref.id) in prompt
    assert str(c1.id) in prompt
    assert str(c2.id) in prompt
    assert "Reference" in prompt
    assert "Candidate 1" in prompt


def test_idempotency_constant_14_days():
    assert PAIR_IDEMPOTENCY_DAYS == 14


# ── Orchestrator ──────────────────────────────────────────────


@pytest.fixture
def intel_repo():
    repo = AsyncMock()
    repo.related_fresh_dossiers = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def cognitive_repo():
    repo = AsyncMock()
    repo.alert_exists_for_pair = AsyncMock(return_value=False)
    repo.insert_alert = AsyncMock()
    return repo


def _make_detector(
    intel,
    cognitive,
    *,
    scripts: list[str] | None = None,
    fail: bool = False,
    min_severity: AlertSeverity = AlertSeverity.MEDIUM,
) -> AnomalyDetector:
    runner = MockRunner(scripts=scripts or [], fail=fail)
    return AnomalyDetector(
        intel_repo=intel,
        cognitive_repo=cognitive,
        runner=runner,
        min_severity=min_severity,
    )


@pytest.mark.asyncio
async def test_no_candidates_no_work(intel_repo, cognitive_repo):
    ref = _dossier()
    detector = _make_detector(intel_repo, cognitive_repo)
    result = await detector.analyze_dossier(ref)
    assert result.candidates_considered == 0
    assert result.alerts_inserted == 0


@pytest.mark.asyncio
async def test_cli_failure_captured(intel_repo, cognitive_repo):
    ref = _dossier()
    intel_repo.related_fresh_dossiers = AsyncMock(
        return_value=[_dossier()],
    )
    detector = _make_detector(intel_repo, cognitive_repo, fail=True)
    result = await detector.analyze_dossier(ref)
    assert any("runner" in e for e in result.errors)


@pytest.mark.asyncio
async def test_happy_path_inserts_alert(intel_repo, cognitive_repo):
    ref = _dossier()
    other = _dossier()
    intel_repo.related_fresh_dossiers = AsyncMock(return_value=[other])
    cognitive_repo.insert_alert = AsyncMock(
        return_value=_returned_alert(ref.id, other.id, AlertSeverity.HIGH),
    )
    payload = [
        {
            "other_dossier_id": str(other.id),
            "contradiction_type": "grace_period_vs_enforcement",
            "severity": "high",
            "suggested_action": "notify PT PMA clients",
        }
    ]
    detector = _make_detector(
        intel_repo, cognitive_repo, scripts=[_contradictions(payload)],
    )
    result = await detector.analyze_dossier(ref)

    assert result.contradictions_proposed == 1
    assert result.alerts_inserted == 1
    assert result.alerts_rejected == 0
    assert result.inserted_alerts[0].severity == AlertSeverity.HIGH


@pytest.mark.asyncio
async def test_rejects_other_id_not_in_batch(intel_repo, cognitive_repo):
    ref = _dossier()
    other = _dossier()
    intel_repo.related_fresh_dossiers = AsyncMock(return_value=[other])
    payload = [
        {
            "other_dossier_id": str(uuid4()),   # not in batch
            "contradiction_type": "scope_mismatch",
            "severity": "medium",
        }
    ]
    detector = _make_detector(
        intel_repo, cognitive_repo, scripts=[_contradictions(payload)],
    )
    result = await detector.analyze_dossier(ref)
    assert result.alerts_rejected == 1
    assert result.alerts_inserted == 0


@pytest.mark.asyncio
async def test_rejects_self_reference(intel_repo, cognitive_repo):
    ref = _dossier()
    intel_repo.related_fresh_dossiers = AsyncMock(
        return_value=[_dossier()],
    )
    payload = [
        {
            "other_dossier_id": str(ref.id),
            "contradiction_type": "scope_mismatch",
            "severity": "medium",
        }
    ]
    detector = _make_detector(
        intel_repo, cognitive_repo, scripts=[_contradictions(payload)],
    )
    result = await detector.analyze_dossier(ref)
    assert result.alerts_rejected == 1


@pytest.mark.asyncio
async def test_rejects_missing_contradiction_type(intel_repo, cognitive_repo):
    ref = _dossier()
    other = _dossier()
    intel_repo.related_fresh_dossiers = AsyncMock(return_value=[other])
    payload = [
        {
            "other_dossier_id": str(other.id),
            "contradiction_type": "",
            "severity": "high",
        }
    ]
    detector = _make_detector(
        intel_repo, cognitive_repo, scripts=[_contradictions(payload)],
    )
    result = await detector.analyze_dossier(ref)
    assert result.alerts_rejected == 1


@pytest.mark.asyncio
async def test_rejects_invalid_severity_value(intel_repo, cognitive_repo):
    ref = _dossier()
    other = _dossier()
    intel_repo.related_fresh_dossiers = AsyncMock(return_value=[other])
    payload = [
        {
            "other_dossier_id": str(other.id),
            "contradiction_type": "x",
            "severity": "maybe",
        }
    ]
    detector = _make_detector(
        intel_repo, cognitive_repo, scripts=[_contradictions(payload)],
    )
    result = await detector.analyze_dossier(ref)
    assert result.alerts_rejected == 1


@pytest.mark.asyncio
async def test_rejects_below_min_severity(intel_repo, cognitive_repo):
    ref = _dossier()
    other = _dossier()
    intel_repo.related_fresh_dossiers = AsyncMock(return_value=[other])
    payload = [
        {
            "other_dossier_id": str(other.id),
            "contradiction_type": "x",
            "severity": "low",     # below MEDIUM min
        }
    ]
    detector = _make_detector(
        intel_repo, cognitive_repo, scripts=[_contradictions(payload)],
    )
    result = await detector.analyze_dossier(ref)
    assert result.alerts_rejected == 1
    assert result.alerts_inserted == 0


@pytest.mark.asyncio
async def test_idempotent_skip_when_pair_exists(intel_repo, cognitive_repo):
    ref = _dossier()
    other = _dossier()
    intel_repo.related_fresh_dossiers = AsyncMock(return_value=[other])
    cognitive_repo.alert_exists_for_pair = AsyncMock(return_value=True)
    payload = [
        {
            "other_dossier_id": str(other.id),
            "contradiction_type": "x",
            "severity": "high",
        }
    ]
    detector = _make_detector(
        intel_repo, cognitive_repo, scripts=[_contradictions(payload)],
    )
    result = await detector.analyze_dossier(ref)
    assert result.idempotent_skipped == 1
    assert result.alerts_inserted == 0
    cognitive_repo.insert_alert.assert_not_called()


@pytest.mark.asyncio
async def test_insert_failure_counts_rejected(intel_repo, cognitive_repo):
    ref = _dossier()
    other = _dossier()
    intel_repo.related_fresh_dossiers = AsyncMock(return_value=[other])
    cognitive_repo.insert_alert = AsyncMock(side_effect=RuntimeError("pg"))
    payload = [
        {
            "other_dossier_id": str(other.id),
            "contradiction_type": "x",
            "severity": "medium",
        }
    ]
    detector = _make_detector(
        intel_repo, cognitive_repo, scripts=[_contradictions(payload)],
    )
    result = await detector.analyze_dossier(ref)
    assert result.alerts_rejected == 1
    assert result.alerts_inserted == 0
