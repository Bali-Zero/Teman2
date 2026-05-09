"""Tests for ConnectorOrchestrator — prompt assembly, validation, idempotency."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from backend.services.cognitive.connector import (
    MIN_CONFIDENCE,
    ConnectorOrchestrator,
    _extract_theses,
    _render_prompt,
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


def _dossier(did: UUID | None = None) -> ResearchDossier:
    now = datetime.now(timezone.utc)
    return ResearchDossier(
        id=did or uuid4(),
        slug="t",
        title="Title",
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
        summary_short="short summary",
        summary_medium="medium summary",
        created_at=now,
        updated_at=now,
        archived_at=None,
    )


def _theses_json(theses: list[dict]) -> str:
    return json.dumps({"theses": theses})


# ── helpers ─────────────────────────────────────────────────


def test_extract_theses_missing_key():
    assert _extract_theses({}) == []


def test_extract_theses_wrong_shape():
    assert _extract_theses({"theses": "not a list"}) == []


def test_extract_theses_filters_non_dict_entries():
    raw = {"theses": [{"title": "ok"}, "ignore me", 42]}
    assert len(_extract_theses(raw)) == 1


def test_render_prompt_includes_every_dossier_id():
    d1, d2 = _dossier(), _dossier()
    prompt = _render_prompt([d1, d2], max_theses=3)
    assert str(d1.id) in prompt
    assert str(d2.id) in prompt
    assert "VISA" not in prompt  # cat lowercased
    assert "id=" in prompt


# ── Validation / orchestration ──────────────────────────────


@pytest.fixture
def intel_repo():
    repo = AsyncMock()
    repo.fetch_safe = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def cognitive_repo():
    repo = AsyncMock()
    repo.insert_thesis = AsyncMock()
    repo.thesis_exists_for_sources = AsyncMock(return_value=False)
    repo.recent_theses = AsyncMock(return_value=[])
    return repo


def _make_orch(intel, cognitive, scripts=None, fail=False) -> ConnectorOrchestrator:
    runner = MockRunner(scripts=scripts or [], fail=fail)
    return ConnectorOrchestrator(
        intel_repo=intel, cognitive_repo=cognitive, runner=runner,
    )


async def _stub_dossiers(intel, dossiers):
    """fetch_safe returns asyncpg.Record-like rows when queried for dossiers."""
    async def side_effect(query, *args):
        # The connector uses _row_to_dossier which expects certain columns.
        rows = []
        for d in dossiers:
            rows.append({
                "id": d.id,
                "slug": d.slug,
                "title": d.title,
                "topic_category": d.topic_category.value,
                "domains": json.dumps(d.domains),
                "public_safe": d.public_safe,
                "facts": json.dumps([]),
                "numbers": json.dumps([]),
                "citations": json.dumps([]),
                "entities_linked": json.dumps([]),
                "precedents": json.dumps([]),
                "confidence_0_1": d.confidence_0_1,
                "freshness_expiry": d.freshness_expiry,
                "source_signals": None,
                "language": d.language,
                "summary_short": d.summary_short,
                "summary_medium": d.summary_medium,
                "created_at": d.created_at,
                "updated_at": d.updated_at,
                "archived_at": d.archived_at,
            })
        return rows

    intel.fetch_safe = AsyncMock(side_effect=side_effect)


# ── Sweep outcomes ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_dossiers_no_work(intel_repo, cognitive_repo):
    await _stub_dossiers(intel_repo, [])
    orch = _make_orch(intel_repo, cognitive_repo)
    result = await orch.run_once()
    assert result.dossiers_considered == 0
    assert result.theses_inserted == 0


@pytest.mark.asyncio
async def test_one_dossier_cannot_link(intel_repo, cognitive_repo):
    await _stub_dossiers(intel_repo, [_dossier()])
    orch = _make_orch(intel_repo, cognitive_repo)
    result = await orch.run_once()
    assert result.dossiers_considered == 1
    # connector short-circuits when <2 dossiers
    assert result.theses_inserted == 0


@pytest.mark.asyncio
async def test_happy_path_insert_valid_thesis(intel_repo, cognitive_repo):
    d1, d2, d3 = _dossier(), _dossier(), _dossier()
    await _stub_dossiers(intel_repo, [d1, d2, d3])

    theses_payload = [
        {
            "title": "Regulatory convergence Q3 2026",
            "narrative": "BI, DJP and OJK are aligning on fintech KYC",
            "source_dossier_ids": [str(d1.id), str(d2.id)],
            "confidence": 0.8,
            "implication": "PT PMA fintech clients need 90d audit",
        }
    ]
    orch = _make_orch(intel_repo, cognitive_repo, scripts=[_theses_json(theses_payload)])
    result = await orch.run_once()

    assert result.dossiers_considered == 3
    assert result.theses_proposed == 1
    assert result.theses_inserted == 1
    cognitive_repo.insert_thesis.assert_awaited_once()


@pytest.mark.asyncio
async def test_rejects_thesis_below_min_confidence(intel_repo, cognitive_repo):
    d1, d2 = _dossier(), _dossier()
    await _stub_dossiers(intel_repo, [d1, d2])
    theses_payload = [
        {
            "title": "weak",
            "narrative": "shaky link",
            "source_dossier_ids": [str(d1.id), str(d2.id)],
            "confidence": 0.4,   # below MIN_CONFIDENCE
        }
    ]
    orch = _make_orch(intel_repo, cognitive_repo, scripts=[_theses_json(theses_payload)])
    result = await orch.run_once()
    assert result.theses_rejected == 1
    assert result.theses_inserted == 0
    cognitive_repo.insert_thesis.assert_not_called()


@pytest.mark.asyncio
async def test_rejects_thesis_with_only_one_valid_source(intel_repo, cognitive_repo):
    d1, d2 = _dossier(), _dossier()
    await _stub_dossiers(intel_repo, [d1, d2])
    theses_payload = [
        {
            "title": "x",
            "narrative": "y",
            "source_dossier_ids": [str(d1.id), str(uuid4())],  # second not in batch
            "confidence": 0.9,
        }
    ]
    orch = _make_orch(intel_repo, cognitive_repo, scripts=[_theses_json(theses_payload)])
    result = await orch.run_once()
    assert result.theses_rejected == 1


@pytest.mark.asyncio
async def test_rejects_thesis_with_empty_title(intel_repo, cognitive_repo):
    d1, d2 = _dossier(), _dossier()
    await _stub_dossiers(intel_repo, [d1, d2])
    theses_payload = [
        {
            "title": "",
            "narrative": "n",
            "source_dossier_ids": [str(d1.id), str(d2.id)],
            "confidence": 0.8,
        }
    ]
    orch = _make_orch(intel_repo, cognitive_repo, scripts=[_theses_json(theses_payload)])
    result = await orch.run_once()
    assert result.theses_rejected == 1


@pytest.mark.asyncio
async def test_idempotent_when_source_set_already_exists(intel_repo, cognitive_repo):
    d1, d2 = _dossier(), _dossier()
    await _stub_dossiers(intel_repo, [d1, d2])
    cognitive_repo.thesis_exists_for_sources = AsyncMock(return_value=True)

    theses_payload = [
        {
            "title": "duplicate",
            "narrative": "already exists",
            "source_dossier_ids": [str(d1.id), str(d2.id)],
            "confidence": 0.9,
        }
    ]
    orch = _make_orch(intel_repo, cognitive_repo, scripts=[_theses_json(theses_payload)])
    result = await orch.run_once()
    assert result.idempotent_skipped == 1
    assert result.theses_inserted == 0
    cognitive_repo.insert_thesis.assert_not_called()


@pytest.mark.asyncio
async def test_respects_max_theses_cap(intel_repo, cognitive_repo):
    d1, d2 = _dossier(), _dossier()
    await _stub_dossiers(intel_repo, [d1, d2])
    # Build 5 valid theses — connector should cap at 3.
    theses_payload = [
        {
            "title": f"t{i}",
            "narrative": "n",
            "source_dossier_ids": [str(d1.id), str(d2.id)],
            "confidence": 0.9,
        }
        for i in range(5)
    ]
    orch = _make_orch(intel_repo, cognitive_repo, scripts=[_theses_json(theses_payload)])
    # note: idempotency would filter the 2nd+ — we disable it
    cognitive_repo.thesis_exists_for_sources = AsyncMock(return_value=False)
    result = await orch.run_once()
    # proposed = 5 (what Claude said); processed up to max_theses (3)
    assert result.theses_proposed == 5
    assert result.theses_inserted + result.theses_rejected + result.idempotent_skipped == 3


@pytest.mark.asyncio
async def test_cli_failure_surfaces_as_error(intel_repo, cognitive_repo):
    d1, d2 = _dossier(), _dossier()
    await _stub_dossiers(intel_repo, [d1, d2])
    orch = _make_orch(intel_repo, cognitive_repo, fail=True)
    result = await orch.run_once()
    assert result.theses_inserted == 0
    assert any("runner" in e for e in result.errors)


@pytest.mark.asyncio
async def test_non_json_runner_output_retries_once(intel_repo, cognitive_repo):
    d1, d2 = _dossier(), _dossier()
    await _stub_dossiers(intel_repo, [d1, d2])
    theses_payload = [
        {
            "title": "Recovered JSON",
            "narrative": "The retry returned parseable output",
            "source_dossier_ids": [str(d1.id), str(d2.id)],
            "confidence": 0.8,
        }
    ]
    orch = _make_orch(
        intel_repo,
        cognitive_repo,
        scripts=["I found no useful links today.", _theses_json(theses_payload)],
    )

    result = await orch.run_once()

    assert orch.runner.call_count == 2
    assert result.theses_inserted == 1
    assert result.errors == []


@pytest.mark.asyncio
async def test_fetch_dossiers_failure_captured(intel_repo, cognitive_repo):
    intel_repo.fetch_safe = AsyncMock(side_effect=RuntimeError("pg down"))
    orch = _make_orch(intel_repo, cognitive_repo)
    result = await orch.run_once()
    assert any("load_dossiers" in e for e in result.errors)


@pytest.mark.asyncio
async def test_insert_failure_counts_as_rejected(intel_repo, cognitive_repo):
    d1, d2 = _dossier(), _dossier()
    await _stub_dossiers(intel_repo, [d1, d2])
    cognitive_repo.insert_thesis = AsyncMock(side_effect=RuntimeError("pg"))
    theses_payload = [
        {
            "title": "valid",
            "narrative": "n",
            "source_dossier_ids": [str(d1.id), str(d2.id)],
            "confidence": 0.85,
        }
    ]
    orch = _make_orch(intel_repo, cognitive_repo, scripts=[_theses_json(theses_payload)])
    result = await orch.run_once()
    assert result.theses_rejected == 1
    assert result.theses_inserted == 0


def test_min_confidence_matches_design():
    assert MIN_CONFIDENCE == 0.6
