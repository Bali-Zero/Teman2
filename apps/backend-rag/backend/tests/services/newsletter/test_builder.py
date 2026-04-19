"""Tests for WeeklyRoundupBuilder — public_safe filter + graceful per-section."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.cognitive.models import (
    CrossDossierThesis,
    WeeklyStrategicBrief,
)
from backend.services.newsletter.builder import (
    DEFAULT_DOSSIERS_MAX,
    DEFAULT_THESES_MAX,
    WeeklyRoundupBuilder,
    _iso_monday,
)


def _now() -> datetime:
    return datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)  # Wednesday


def _dossier_row(
    *,
    title: str = "Test dossier",
    confidence: float = 0.8,
    public_safe: bool = True,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": uuid4(),
        "slug": "s",
        "title": title,
        "topic_category": "visa",
        "domains": json.dumps(["newsletter"]),
        "public_safe": public_safe,
        "facts": json.dumps([]),
        "numbers": json.dumps([]),
        "citations": json.dumps([]),
        "entities_linked": json.dumps([]),
        "precedents": json.dumps([]),
        "confidence_0_1": confidence,
        "freshness_expiry": now + timedelta(days=30),
        "source_signals": None,
        "language": "it",
        "summary_short": "summary here",
        "summary_medium": "medium summary",
        "created_at": now,
        "updated_at": now,
        "archived_at": None,
    }


def _thesis(title: str = "thesis") -> CrossDossierThesis:
    return CrossDossierThesis(
        id=uuid4(),
        title=title,
        narrative="narrative",
        source_dossier_ids=[uuid4(), uuid4()],
        confidence=0.75,
        generated_at=datetime.now(timezone.utc),
    )


def _brief() -> WeeklyStrategicBrief:
    return WeeklyStrategicBrief(
        id=uuid4(),
        week_of=date(2026, 4, 20),
        top_themes=[{"name": "Focus pedagogico"}],
        proposed_actions=[{"action": "3 articoli analitici"}],
        narrative="Settimana di ribilanciamento",
        generated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def repos():
    intel = AsyncMock()
    intel.fetch_safe = AsyncMock(return_value=[])
    cognitive = AsyncMock()
    cognitive.recent_theses = AsyncMock(return_value=[])
    cognitive.latest_brief = AsyncMock(return_value=None)
    return intel, cognitive


# ── _iso_monday ────────────────────────────────────────


def test_iso_monday_from_wednesday():
    assert _iso_monday(_now()) == date(2026, 4, 20)


def test_iso_monday_from_monday():
    mon = datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc)
    assert _iso_monday(mon) == date(2026, 4, 20)


def test_iso_monday_from_sunday():
    sun = datetime(2026, 4, 26, 23, 0, tzinfo=timezone.utc)
    assert _iso_monday(sun) == date(2026, 4, 20)


# ── Empty state ────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_empty_all_sources(repos):
    intel, cognitive = repos
    builder = WeeklyRoundupBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build(now=_now())
    assert content.is_empty
    assert content.week_of == date(2026, 4, 20)


# ── Public-safe filter (Legge 2) ───────────────────────


@pytest.mark.asyncio
async def test_build_only_public_safe_dossiers(repos):
    intel, cognitive = repos
    # Return two rows — but the SQL already filters public_safe=TRUE so we
    # feed only public rows to confirm they pass through.
    intel.fetch_safe = AsyncMock(return_value=[
        _dossier_row(title="public A", public_safe=True),
        _dossier_row(title="public B", public_safe=True),
    ])
    builder = WeeklyRoundupBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build(now=_now())
    assert len(content.dossiers) == 2
    assert all(d.public_safe for d in content.dossiers)
    # the query must include public_safe filter
    sql = intel.fetch_safe.call_args.args[0]
    assert "public_safe = TRUE" in sql


# ── Dossier cap ────────────────────────────────────────


@pytest.mark.asyncio
async def test_dossiers_respect_default_cap(repos):
    intel, cognitive = repos
    intel.fetch_safe = AsyncMock(return_value=[])
    builder = WeeklyRoundupBuilder(intel_repo=intel, cognitive_repo=cognitive)
    await builder.build(now=_now())
    # SQL receives LIMIT $2 with DEFAULT_DOSSIERS_MAX = 5
    args = intel.fetch_safe.call_args.args
    assert args[2] == DEFAULT_DOSSIERS_MAX


# ── Theses cap ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_theses_capped_to_three(repos):
    intel, cognitive = repos
    cognitive.recent_theses = AsyncMock(return_value=[
        _thesis(f"t{i}") for i in range(10)
    ])
    builder = WeeklyRoundupBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build(now=_now())
    assert len(content.theses) == DEFAULT_THESES_MAX


# ── Brief included ─────────────────────────────────────


@pytest.mark.asyncio
async def test_brief_included(repos):
    intel, cognitive = repos
    cognitive.latest_brief = AsyncMock(return_value=_brief())
    builder = WeeklyRoundupBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build(now=_now())
    assert content.brief is not None
    assert content.brief.narrative


# ── Graceful per-section failure ───────────────────────


@pytest.mark.asyncio
async def test_intel_fetch_failure_returns_no_dossiers(repos):
    intel, cognitive = repos
    intel.fetch_safe = AsyncMock(side_effect=RuntimeError("pg"))
    cognitive.recent_theses = AsyncMock(return_value=[_thesis("ok")])
    builder = WeeklyRoundupBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build(now=_now())
    # dossiers empty; theses still populated — partial rollup
    assert content.dossiers == []
    assert len(content.theses) == 1


@pytest.mark.asyncio
async def test_theses_failure_does_not_abort(repos):
    intel, cognitive = repos
    intel.fetch_safe = AsyncMock(return_value=[_dossier_row()])
    cognitive.recent_theses = AsyncMock(side_effect=RuntimeError("pg"))
    builder = WeeklyRoundupBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build(now=_now())
    assert len(content.dossiers) == 1
    assert content.theses == []


@pytest.mark.asyncio
async def test_brief_failure_does_not_abort(repos):
    intel, cognitive = repos
    cognitive.latest_brief = AsyncMock(side_effect=RuntimeError("pg"))
    builder = WeeklyRoundupBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build(now=_now())
    assert content.brief is None


# ── RoundupContent.is_empty ────────────────────────────


@pytest.mark.asyncio
async def test_is_empty_when_all_sections_empty(repos):
    intel, cognitive = repos
    builder = WeeklyRoundupBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build(now=_now())
    assert content.is_empty is True


@pytest.mark.asyncio
async def test_is_empty_false_when_any_section_present(repos):
    intel, cognitive = repos
    cognitive.recent_theses = AsyncMock(return_value=[_thesis()])
    builder = WeeklyRoundupBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build(now=_now())
    assert content.is_empty is False
