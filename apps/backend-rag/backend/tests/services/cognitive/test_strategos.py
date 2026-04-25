"""Tests for Strategos context builder + orchestrator."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.cognitive.models import (
    AlertSeverity,
    ComplianceAlert,
    CrossDossierThesis,
    WeeklyStrategicBrief,
)
from backend.services.cognitive.strategos import (
    CONTEXT_MAX_CHARS,
    StrategosContext,
    StrategosContextBuilder,
    StrategosOrchestrator,
    _build_brief_payload,
    _iso_week_monday,
)
from backend.services.council.cli_runners import CLIRunner, RunnerResult

# ── Helpers ───────────────────────────────────────────────────


@dataclass
class MockRunner(CLIRunner):
    name: str = "mock"
    default_timeout: int = 60
    scripts: list[str] = field(default_factory=list)
    call_count: int = 0
    fail: bool = False

    async def run(self, prompt, timeout=None) -> RunnerResult:
        idx = self.call_count
        self.call_count += 1
        if self.fail:
            return RunnerResult(
                runner_name=self.name, prompt_chars=len(prompt),
                ok=False, error="runner down",
            )
        if idx >= len(self.scripts):
            return RunnerResult(
                runner_name=self.name, prompt_chars=len(prompt),
                ok=False, error="exhausted",
            )
        return RunnerResult(
            runner_name=self.name, prompt_chars=len(prompt),
            ok=True, output=self.scripts[idx],
        )


def _brief_json(**kwargs) -> str:
    base = {
        "top_themes": [
            {"name": "Tonal rebalance", "weight": 0.5, "why": "too cinico"}
        ],
        "proposed_actions": [
            {
                "action": "commissiona 3 articoli pedagogici",
                "owner": "war_room",
                "deadline_days": 5,
                "rationale": "alzare engagement",
            }
        ],
        "kpi_targets": {"reach_uplift_pct": 20},
        "team_assignments": {"war_room": "Damar"},
        "narrative": "Settimana di ribilanciamento tonale",
    }
    base.update(kwargs)
    return json.dumps(base)


def _returned_brief() -> WeeklyStrategicBrief:
    now = datetime.now(timezone.utc)
    return WeeklyStrategicBrief(
        id=uuid4(),
        week_of=_iso_week_monday(now),
        top_themes=[],
        proposed_actions=[],
        generated_at=now,
    )


# ── _iso_week_monday ──────────────────────────────────────────


def test_iso_week_monday_wednesday():
    d = datetime(2026, 4, 22, 18, 0, tzinfo=timezone.utc)  # Wednesday
    assert _iso_week_monday(d) == date(2026, 4, 20)  # Monday of same week


def test_iso_week_monday_is_monday():
    d = datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc)
    assert _iso_week_monday(d) == date(2026, 4, 20)


def test_iso_week_monday_sunday_wraps_back():
    d = datetime(2026, 4, 26, 23, 0, tzinfo=timezone.utc)  # Sunday
    assert _iso_week_monday(d) == date(2026, 4, 20)


# ── _build_brief_payload ─────────────────────────────────────


def test_build_brief_payload_caps_lists():
    parsed = {
        "top_themes": [{"name": f"t{i}"} for i in range(10)],
        "proposed_actions": [{"action": f"a{i}"} for i in range(10)],
        "narrative": "ok",
    }
    payload = _build_brief_payload(parsed, week_of=date(2026, 4, 20))
    assert len(payload.top_themes) == 5
    assert len(payload.proposed_actions) == 6


def test_build_brief_payload_rejects_empty():
    with pytest.raises(ValueError):
        _build_brief_payload({}, week_of=date(2026, 4, 20))


def test_build_brief_payload_ignores_non_dict_entries():
    parsed = {
        "top_themes": [{"name": "ok"}, "bogus", 42],
        "proposed_actions": [],
        "narrative": "x",
    }
    payload = _build_brief_payload(parsed, week_of=date(2026, 4, 20))
    assert len(payload.top_themes) == 1


def test_build_brief_payload_ignores_non_dict_kpi():
    parsed = {
        "top_themes": [{"name": "x"}],
        "proposed_actions": [],
        "kpi_targets": "not a dict",
        "narrative": None,
    }
    payload = _build_brief_payload(parsed, week_of=date(2026, 4, 20))
    assert payload.kpi_targets is None


# ── StrategosContext rendering ──────────────────────────────


def test_context_as_prompt_truncates_over_budget():
    ctx = StrategosContext(
        week_of=date(2026, 4, 20),
        dossiers_block="x" * (CONTEXT_MAX_CHARS * 2),
    )
    out = ctx.as_prompt_context(max_chars=500)
    assert len(out) <= 600  # truncation + ellipsis
    assert "[truncated]" in out


def test_context_as_prompt_includes_only_present_sections():
    ctx = StrategosContext(
        week_of=date(2026, 4, 20),
        theses_block="thesis 1",
    )
    out = ctx.as_prompt_context()
    assert "TESI CROSS-DOSSIER" in out
    assert "[DOSSIER" not in out
    assert "[COMPLIANCE" not in out


# ── Context builder ─────────────────────────────────────────


@pytest.fixture
def repos():
    intel = AsyncMock()
    cognitive = AsyncMock()
    cognitive.recent_theses = AsyncMock(return_value=[])
    cognitive.unresolved_alerts = AsyncMock(return_value=[])
    war_room = AsyncMock()
    intel.fetch_safe = AsyncMock(return_value=[])
    war_room.fetch_safe = AsyncMock(return_value=[])
    return intel, cognitive, war_room


@pytest.mark.asyncio
async def test_context_builder_empty_sources(repos):
    intel, cognitive, war_room = repos
    builder = StrategosContextBuilder(
        intel_repo=intel, cognitive_repo=cognitive, war_room_repo=war_room,
    )
    ctx = await builder.build(week_of=date(2026, 4, 20))
    assert ctx.dossiers_block == ""
    assert ctx.theses_block == ""


@pytest.mark.asyncio
async def test_context_builder_populates_all_sections(repos):
    intel, cognitive, war_room = repos
    now = datetime.now(timezone.utc)

    # Dossier rows
    intel.fetch_safe = AsyncMock(return_value=[
        {
            "id": uuid4(),
            "title": "Permenkumham 22/2023",
            "topic_category": "visa",
            "confidence_0_1": 0.85,
            "summary_short": "art.51 limite estensioni",
        }
    ])

    # Theses
    cognitive.recent_theses = AsyncMock(return_value=[
        CrossDossierThesis(
            id=uuid4(),
            title="Convergence fintech",
            narrative="long",
            source_dossier_ids=[uuid4(), uuid4()],
            confidence=0.8,
            implication="90d audit",
            generated_at=now,
        )
    ])

    # Alerts
    cognitive.unresolved_alerts = AsyncMock(return_value=[
        ComplianceAlert(
            id=uuid4(),
            detected_at=now,
            dossier_a_id=uuid4(),
            dossier_b_id=uuid4(),
            contradiction_type="grace_vs_enforcement",
            severity=AlertSeverity.HIGH,
        )
    ])

    # War room side: multiple fetch_safe calls → use side_effect based on query
    call_count = {"n": 0}

    async def war_room_fetch(query, *args):
        call_count["n"] += 1
        q = query.strip()
        if "war_room_metrics" in q:
            return [
                {
                    "register": "analitico",
                    "metric_name": "reach",
                    "avg_value": 1234.5,
                    "n": 8,
                }
            ]
        if "war_room_rejections" in q:
            return [{"reason": "clickbait", "n": 3}]
        return []

    war_room.fetch_safe = AsyncMock(side_effect=war_room_fetch)

    builder = StrategosContextBuilder(
        intel_repo=intel, cognitive_repo=cognitive, war_room_repo=war_room,
    )
    ctx = await builder.build(week_of=date(2026, 4, 20))

    assert "Permenkumham 22/2023" in ctx.dossiers_block
    assert "Convergence fintech" in ctx.theses_block
    assert "grace_vs_enforcement" in ctx.alerts_block
    assert "analitico" in ctx.metrics_block
    assert "clickbait" in ctx.rejections_block


@pytest.mark.asyncio
async def test_context_builder_section_failure_is_isolated(repos):
    intel, cognitive, war_room = repos
    intel.fetch_safe = AsyncMock(side_effect=RuntimeError("pg down"))
    cognitive.recent_theses = AsyncMock(return_value=[])
    cognitive.unresolved_alerts = AsyncMock(return_value=[])
    war_room.fetch_safe = AsyncMock(return_value=[])

    builder = StrategosContextBuilder(
        intel_repo=intel, cognitive_repo=cognitive, war_room_repo=war_room,
    )
    ctx = await builder.build(week_of=date(2026, 4, 20))
    # dossiers section failed but others worked
    assert ctx.dossiers_block == ""


@pytest.mark.asyncio
async def test_context_builder_calls_skills_snapshot_when_provided(repos):
    intel, cognitive, war_room = repos
    called = {"n": 0}

    async def snapshot():
        called["n"] += 1
        return "top skills here"

    builder = StrategosContextBuilder(
        intel_repo=intel,
        cognitive_repo=cognitive,
        war_room_repo=war_room,
        skills_snapshot_fn=snapshot,
    )
    ctx = await builder.build(week_of=date(2026, 4, 20))
    assert called["n"] == 1
    assert "top skills here" in ctx.skills_block


# ── Orchestrator ────────────────────────────────────────────


@pytest.fixture
def orchestrator_deps(repos):
    intel, cognitive, war_room = repos
    cognitive.insert_brief = AsyncMock(return_value=_returned_brief())
    return intel, cognitive, war_room


def _make_orch(
    intel,
    cognitive,
    war_room,
    *,
    scripts=None,
    fail=False,
) -> StrategosOrchestrator:
    runner = MockRunner(scripts=scripts or [], fail=fail)
    return StrategosOrchestrator(
        intel_repo=intel,
        cognitive_repo=cognitive,
        war_room_repo=war_room,
        runner=runner,
    )


@pytest.mark.asyncio
async def test_orchestrator_happy_path(orchestrator_deps):
    intel, cognitive, war_room = orchestrator_deps
    orch = _make_orch(intel, cognitive, war_room, scripts=[_brief_json()])
    result = await orch.run_once(week_of=date(2026, 4, 20))
    assert result.inserted is True
    assert result.brief is not None
    cognitive.insert_brief.assert_awaited_once()


@pytest.mark.asyncio
async def test_orchestrator_cli_failure(orchestrator_deps):
    intel, cognitive, war_room = orchestrator_deps
    orch = _make_orch(intel, cognitive, war_room, fail=True)
    result = await orch.run_once(week_of=date(2026, 4, 20))
    assert result.inserted is False
    assert any("runner" in e for e in result.errors)


@pytest.mark.asyncio
async def test_orchestrator_empty_parsed_brief_rejected(orchestrator_deps):
    intel, cognitive, war_room = orchestrator_deps
    orch = _make_orch(
        intel, cognitive, war_room,
        scripts=[json.dumps({"top_themes": [], "proposed_actions": []})],
    )
    result = await orch.run_once(week_of=date(2026, 4, 20))
    assert result.inserted is False
    assert any("parse" in e for e in result.errors)


@pytest.mark.asyncio
async def test_orchestrator_insert_failure_captured(orchestrator_deps):
    intel, cognitive, war_room = orchestrator_deps
    cognitive.insert_brief = AsyncMock(side_effect=RuntimeError("pg down"))
    orch = _make_orch(intel, cognitive, war_room, scripts=[_brief_json()])
    result = await orch.run_once(week_of=date(2026, 4, 20))
    assert result.inserted is False
    assert any("insert" in e for e in result.errors)


@pytest.mark.asyncio
async def test_orchestrator_tracks_prompt_size(orchestrator_deps):
    intel, cognitive, war_room = orchestrator_deps
    orch = _make_orch(intel, cognitive, war_room, scripts=[_brief_json()])
    result = await orch.run_once(week_of=date(2026, 4, 20))
    assert result.prompt_chars > 0
    assert result.context_chars >= 0


# ── Orchestrator rerank wire-up (dormant) ────────────────────


@pytest.mark.asyncio
async def test_orchestrator_rerank_disabled_by_default(
    orchestrator_deps, monkeypatch,
):
    """No env flag = no filter constructed = legacy behavior preserved."""
    monkeypatch.delenv("STRATEGOS_RERANK_ENABLED", raising=False)
    intel, cognitive, war_room = orchestrator_deps
    orch = _make_orch(intel, cognitive, war_room, scripts=[_brief_json()])
    assert orch.context_builder.dossier_filter is None


@pytest.mark.asyncio
async def test_orchestrator_rerank_flag_off_ignores_qdrant(
    orchestrator_deps, monkeypatch,
):
    """STRATEGOS_RERANK_ENABLED=false: filter not built even if deps provided."""
    monkeypatch.setenv("STRATEGOS_RERANK_ENABLED", "false")
    intel, cognitive, war_room = orchestrator_deps
    runner = MockRunner(scripts=[_brief_json()])
    orch = StrategosOrchestrator(
        intel_repo=intel,
        cognitive_repo=cognitive,
        war_room_repo=war_room,
        runner=runner,
        qdrant_client=object(),
        embedder=object(),
        rerank_collection="research_dossiers_v1",
    )
    assert orch.context_builder.dossier_filter is None


@pytest.mark.asyncio
async def test_orchestrator_rerank_flag_on_builds_filter(
    orchestrator_deps, monkeypatch,
):
    """STRATEGOS_RERANK_ENABLED=true + all deps → filter attached to builder."""
    monkeypatch.setenv("STRATEGOS_RERANK_ENABLED", "true")
    intel, cognitive, war_room = orchestrator_deps
    runner = MockRunner(scripts=[_brief_json()])

    class _StubEmbedder:
        async def embed(self, text):
            return [0.1] * 1536

    orch = StrategosOrchestrator(
        intel_repo=intel,
        cognitive_repo=cognitive,
        war_room_repo=war_room,
        runner=runner,
        qdrant_client=object(),
        embedder=_StubEmbedder(),
        rerank_collection="research_dossiers_v1",
    )
    assert orch.context_builder.dossier_filter is not None
    assert (
        orch.context_builder.dossier_filter.collection == "research_dossiers_v1"
    )


@pytest.mark.asyncio
async def test_orchestrator_rerank_flag_on_but_missing_deps_skips_filter(
    orchestrator_deps, monkeypatch,
):
    """Flag ON but qdrant/embedder not provided → no filter (safe degradation)."""
    monkeypatch.setenv("STRATEGOS_RERANK_ENABLED", "true")
    intel, cognitive, war_room = orchestrator_deps
    orch = _make_orch(intel, cognitive, war_room, scripts=[_brief_json()])
    assert orch.context_builder.dossier_filter is None
