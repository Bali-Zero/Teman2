"""Tests for DossierCompiler — clustering, coercion, CLI integration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.council.cli_runners import CLIRunner, RunnerResult
from backend.services.intel.dossier_compiler import (
    DEFAULT_FRESHNESS_DAYS,
    DossierCompiler,
    _cluster_trends,
    _coerce_confidence,
    _coerce_fact,
    _coerce_topic_category,
    _render_signals,
)
from backend.services.intel.dossier_models import (
    ResearchDossier,
    TopicCategory,
    TrendSignal,
    TrendSource,
)


@dataclass
class MockRunner(CLIRunner):
    name: str = "mock"
    default_timeout: int = 30
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


def _trend(
    topic: str,
    urgency: float = 70.0,
    *,
    source: TrendSource = TrendSource.RSS,
    source_url: str | None = None,
) -> TrendSignal:
    return TrendSignal(
        id=uuid4(),
        source=source,
        source_url=source_url,
        topic=topic,
        raw_title=topic,
        raw_snippet="snippet",
        language="id",
        urgency_score=urgency,
        bali_zero_relevance=80.0,
        decay_half_life_hours=48,
        entities_linked=None,
        detected_at=datetime.now(timezone.utc),
        expires_at=None,
        consumed_by_dossier=None,
    )


def _compile_json(**overrides: Any) -> str:
    base = {
        "title": "Permenkumham 22/2023: estensione B211A",
        "topic_category": "visa",
        "confidence_0_1": 0.7,
        "domains": ["chatbot", "warroom"],
        "public_safe": True,
        "facts": [
            {"claim": "art.51 comma 3 limita 4 estensioni", "confidence": 0.9}
        ],
        "numbers": [
            {"metric": "max_days", "value": 180, "unit": "days"}
        ],
        "citations": [
            {"norma": "Permenkumham 22/2023", "articolo": "51", "comma": "3", "year": 2023}
        ],
        "entities_linked": [
            {"kg_entity_id": "visa:B211A", "type": "Visa", "role": "subject"}
        ],
        "summary_short": "B211A ora ha limite di 4 estensioni.",
        "summary_medium": "Permenkumham 22/2023 all'articolo 51 introduce un tetto operativo.",
    }
    base.update(overrides)
    return json.dumps(base)


def _dossier_returned() -> ResearchDossier:
    now = datetime.now(timezone.utc)
    return ResearchDossier(
        id=uuid4(),
        slug="permenkumham-22-2023-b211a-aabbccdd",
        title="Permenkumham 22/2023",
        topic_category=TopicCategory.VISA,
        domains=["chatbot", "warroom"],
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


# ── Clustering ───────────────────────────────────────────────


def test_cluster_empty_list():
    assert _cluster_trends([]) == []


def test_cluster_single_trend():
    trends = [_trend("Permenkumham 22 2023 art 51")]
    clusters = _cluster_trends(trends)
    assert len(clusters) == 1
    assert len(clusters[0]) == 1


def test_cluster_groups_similar_topics():
    trends = [
        _trend("Permenkumham 22 2023 art 51 comma 3", urgency=90),
        _trend("Permenkumham 22 2023 art 51 B211A", urgency=80),
        _trend("Permenkumham 22 2023 estensione B211A", urgency=70),
        _trend("Coretax DPP 2026 update"),  # separate
    ]
    clusters = _cluster_trends(trends)
    assert len(clusters) == 2
    big = max(clusters, key=len)
    assert len(big) == 3
    # anchor = most urgent
    assert big[0].urgency_score == 90


def test_cluster_separate_when_no_overlap():
    trends = [
        _trend("KBLI 47711 migration"),
        _trend("Crypto bappebti rule"),
        _trend("Hak Pakai villa Bali"),
    ]
    clusters = _cluster_trends(trends)
    assert len(clusters) == 3


# ── Coercion helpers ─────────────────────────────────────────


def test_coerce_confidence_clamped():
    assert _coerce_confidence(0.5) == 0.5
    assert _coerce_confidence(-1) == 0.3   # MIN
    assert _coerce_confidence(2) == 0.95  # MAX
    assert _coerce_confidence("bad") == 0.5


def test_coerce_fact_handles_non_dict():
    got = _coerce_fact("just a string")
    assert got["claim"] == "just a string"
    assert got["confidence"] == 0.5


def test_coerce_fact_clamps_confidence():
    got = _coerce_fact({"claim": "x", "confidence": 5.0})
    assert got["confidence"] == 1.0


def test_coerce_topic_category_prefers_explicit():
    assert _coerce_topic_category("tax", "B211A visa") == TopicCategory.TAX


def test_coerce_topic_category_falls_back_to_hint():
    assert _coerce_topic_category("bogus", "B211A extension") == TopicCategory.VISA


def test_coerce_topic_category_from_hint_default_other():
    assert _coerce_topic_category(None, "random unknown text") == TopicCategory.OTHER


# ── _render_signals ──────────────────────────────────────────


def test_render_signals_trims_snippet():
    t = _trend("x")
    t.raw_snippet = "y" * 500
    out = _render_signals([t])
    # snippet line is capped at 240
    assert "y" * 241 not in out


def test_render_signals_caps_at_eight():
    trends = [_trend(f"t{i}") for i in range(10)]
    out = _render_signals(trends)
    assert out.count("urgency=") == 8


# ── Full compiler cycle ──────────────────────────────────────


@pytest.fixture
def repo_runner():
    repo = AsyncMock()
    repo.top_unconsumed_trends = AsyncMock(return_value=[])
    repo.upsert_dossier = AsyncMock(return_value=_dossier_returned())
    repo.mark_trend_consumed = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_run_once_empty_batch(repo_runner):
    runner = MockRunner(scripts=[])
    compiler = DossierCompiler(repo=repo_runner, runner=runner)
    summary = await compiler.run_once()
    assert summary.batch_size == 0
    assert summary.dossiers_compiled == 0
    assert runner.call_count == 0


@pytest.mark.asyncio
async def test_run_once_happy_path(repo_runner):
    # both trends share >= 3 tokens (permenkumham 2023 art b211a) → same cluster
    trends = [
        _trend("Permenkumham 2023 art 51 B211A estensione"),
        _trend("Permenkumham 2023 B211A estensione quarta"),
    ]
    repo_runner.top_unconsumed_trends = AsyncMock(return_value=trends)
    runner = MockRunner(scripts=[_compile_json()])
    compiler = DossierCompiler(repo=repo_runner, runner=runner)

    summary = await compiler.run_once()
    assert summary.batch_size == 2
    assert summary.clusters_built == 1
    assert summary.dossiers_compiled == 1
    assert summary.signals_consumed == 2
    assert repo_runner.upsert_dossier.await_count == 1
    assert repo_runner.mark_trend_consumed.await_count == 2
    # per_dossier summary populated
    assert summary.per_dossier[0]["slug"].startswith("permenkumham")


@pytest.mark.asyncio
async def test_run_once_cli_failure_counts_as_dossier_failed(repo_runner):
    repo_runner.top_unconsumed_trends = AsyncMock(return_value=[_trend("x")])
    runner = MockRunner(fail=True)
    compiler = DossierCompiler(repo=repo_runner, runner=runner)
    summary = await compiler.run_once()
    assert summary.dossiers_compiled == 0
    assert summary.dossiers_failed == 1
    repo_runner.upsert_dossier.assert_not_called()
    repo_runner.mark_trend_consumed.assert_not_called()


@pytest.mark.asyncio
async def test_run_once_invalid_json_counts_failure(repo_runner):
    repo_runner.top_unconsumed_trends = AsyncMock(return_value=[_trend("x")])
    runner = MockRunner(scripts=["not json at all"])
    compiler = DossierCompiler(repo=repo_runner, runner=runner)
    summary = await compiler.run_once()
    assert summary.dossiers_failed == 1
    assert summary.dossiers_compiled == 0


@pytest.mark.asyncio
async def test_run_once_fetch_failure_surfaces(repo_runner):
    repo_runner.top_unconsumed_trends = AsyncMock(
        side_effect=RuntimeError("pg down"),
    )
    runner = MockRunner(scripts=[])
    compiler = DossierCompiler(repo=repo_runner, runner=runner)
    summary = await compiler.run_once()
    assert summary.batch_size == 0
    assert any("fetch_trends" in e for e in summary.errors)


@pytest.mark.asyncio
async def test_run_once_mark_consumed_failure_does_not_abort(repo_runner):
    repo_runner.top_unconsumed_trends = AsyncMock(return_value=[_trend("x")])
    repo_runner.mark_trend_consumed = AsyncMock(
        side_effect=RuntimeError("bad update"),
    )
    runner = MockRunner(scripts=[_compile_json()])
    compiler = DossierCompiler(repo=repo_runner, runner=runner)
    summary = await compiler.run_once()
    # dossier still counted as compiled even though mark failed
    assert summary.dossiers_compiled == 1
    assert summary.signals_consumed == 0


@pytest.mark.asyncio
async def test_run_once_coerces_bad_topic_category(repo_runner):
    repo_runner.top_unconsumed_trends = AsyncMock(return_value=[
        _trend("B211A extension rules"),
    ])
    runner = MockRunner(scripts=[_compile_json(topic_category="BOGUS")])
    compiler = DossierCompiler(repo=repo_runner, runner=runner)
    summary = await compiler.run_once()
    assert summary.dossiers_compiled == 1
    # Inspect what we'd pass to upsert
    dossier_create = repo_runner.upsert_dossier.await_args.args[0]
    # Should fall back to categorize_topic("B211A extension rules") → VISA
    assert dossier_create.topic_category == TopicCategory.VISA


@pytest.mark.asyncio
async def test_freshness_default_30_days(repo_runner):
    repo_runner.top_unconsumed_trends = AsyncMock(return_value=[_trend("x kbli")])
    runner = MockRunner(scripts=[_compile_json()])
    compiler = DossierCompiler(repo=repo_runner, runner=runner)
    await compiler.run_once()
    dc = repo_runner.upsert_dossier.await_args.args[0]
    delta = dc.freshness_expiry - datetime.now(timezone.utc)
    # ~30 days ±1
    assert timedelta(days=DEFAULT_FRESHNESS_DAYS - 1) < delta < timedelta(days=DEFAULT_FRESHNESS_DAYS + 1)
