"""Tests for CognitiveRepository (mocked asyncpg)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.cognitive.models import (
    AlertSeverity,
    ComplianceAlertCreate,
    CrossDossierThesisCreate,
    ThesisStatus,
    UltraMoveCreate,
    UltraMoveDecision,
    WeeklyStrategicBriefCreate,
)
from backend.services.cognitive.repository import CognitiveRepository, _parse_json


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _thesis_row(**overrides) -> dict:
    base = {
        "id": uuid4(),
        "title": "t",
        "narrative": "n",
        "source_dossier_ids": json.dumps([str(uuid4()), str(uuid4())]),
        "confidence": Decimal("0.7"),
        "implication": "imp",
        "target_clients_query": None,
        "generated_at": _now(),
        "valid_until": _now() + timedelta(days=14),
        "status": "active",
    }
    base.update(overrides)
    return base


def _alert_row(**overrides) -> dict:
    base = {
        "id": uuid4(),
        "detected_at": _now(),
        "dossier_a_id": uuid4(),
        "dossier_b_id": uuid4(),
        "contradiction_type": "grace_vs_enforcement",
        "severity": "medium",
        "suggested_action": None,
        "affected_client_query": None,
        "notified_zero": False,
        "resolved": False,
        "resolved_at": None,
    }
    base.update(overrides)
    return base


def _brief_row(**overrides) -> dict:
    base = {
        "id": uuid4(),
        "week_of": date(2026, 4, 20),
        "top_themes": json.dumps([]),
        "proposed_actions": json.dumps([]),
        "kpi_targets": None,
        "team_assignments": None,
        "narrative": None,
        "generated_at": _now(),
        "zero_approval": None,
        "approved_at": None,
    }
    base.update(overrides)
    return base


def _move_row(**overrides) -> dict:
    base = {
        "id": uuid4(),
        "proposed_at": _now(),
        "thesis": "t",
        "narrative": "n",
        "target_query": None,
        "estimated_cost": None,
        "estimated_value": None,
        "recommended_tone_register": None,
        "source_inputs": json.dumps({}),
        "zero_decision": "pending",
        "decided_at": None,
        "notes": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def repo_conn(mock_db_pool):
    pool, conn = mock_db_pool
    return CognitiveRepository(db_pool=pool), conn


# ── _parse_json ────────────────────────────────────────────


def test_parse_json_none():
    assert _parse_json(None) is None


def test_parse_json_string():
    assert _parse_json('[1,2,3]') == [1, 2, 3]


def test_parse_json_passthrough_dict():
    assert _parse_json({"a": 1}) == {"a": 1}


def test_parse_json_invalid_returns_none():
    assert _parse_json("not json") is None


# ── CrossDossierThesis ─────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_thesis(repo_conn):
    repo, conn = repo_conn
    conn.fetchrow = AsyncMock(return_value=_thesis_row())
    t = await repo.insert_thesis(CrossDossierThesisCreate(
        title="Digital convergence",
        narrative="BI + DJP + OJK align",
        source_dossier_ids=[uuid4(), uuid4()],
        confidence=0.78,
    ))
    assert t.status == ThesisStatus.ACTIVE
    assert len(t.source_dossier_ids) == 2


@pytest.mark.asyncio
async def test_recent_theses_active_filter(repo_conn):
    repo, conn = repo_conn
    conn.fetch = AsyncMock(return_value=[_thesis_row()])
    out = await repo.recent_theses(days=7, active_only=True)
    assert len(out) == 1
    query = conn.fetch.call_args.args[0]
    assert "status = 'active'" in query


@pytest.mark.asyncio
async def test_thesis_exists_for_sources_true(repo_conn):
    repo, conn = repo_conn
    conn.fetchrow = AsyncMock(return_value={"exists": 1})
    exists = await repo.thesis_exists_for_sources(
        [uuid4(), uuid4()], days=7,
    )
    assert exists is True


@pytest.mark.asyncio
async def test_thesis_exists_for_sources_empty_short_circuits(repo_conn):
    repo, conn = repo_conn
    conn.fetchrow = AsyncMock()
    exists = await repo.thesis_exists_for_sources([], days=7)
    assert exists is False
    conn.fetchrow.assert_not_called()


@pytest.mark.asyncio
async def test_archive_thesis(repo_conn):
    repo, conn = repo_conn
    conn.execute = AsyncMock(return_value="UPDATE 1")
    await repo.archive_thesis(uuid4())
    conn.execute.assert_called_once()


# ── ComplianceAlert ────────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_alert(repo_conn):
    repo, conn = repo_conn
    conn.fetchrow = AsyncMock(return_value=_alert_row(severity="high"))
    alert = await repo.insert_alert(ComplianceAlertCreate(
        dossier_a_id=uuid4(),
        dossier_b_id=uuid4(),
        contradiction_type="grace_vs_enforcement",
        severity=AlertSeverity.HIGH,
    ))
    assert alert.severity == AlertSeverity.HIGH


@pytest.mark.asyncio
async def test_unresolved_alerts_with_severity_filter(repo_conn):
    repo, conn = repo_conn
    conn.fetch = AsyncMock(return_value=[_alert_row(severity="critical")])
    alerts = await repo.unresolved_alerts(severity=AlertSeverity.CRITICAL)
    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.CRITICAL


# ── WeeklyStrategicBrief ───────────────────────────────────


@pytest.mark.asyncio
async def test_insert_brief_with_jsonb(repo_conn):
    repo, conn = repo_conn
    conn.fetchrow = AsyncMock(return_value=_brief_row(
        top_themes=json.dumps([{"x": 1}]),
    ))
    brief = await repo.insert_brief(WeeklyStrategicBriefCreate(
        week_of=date(2026, 4, 20),
        top_themes=[{"x": 1}],
    ))
    assert brief.week_of == date(2026, 4, 20)
    assert brief.top_themes == [{"x": 1}]


@pytest.mark.asyncio
async def test_latest_brief(repo_conn):
    repo, conn = repo_conn
    conn.fetchrow = AsyncMock(return_value=_brief_row())
    brief = await repo.latest_brief()
    assert brief is not None


@pytest.mark.asyncio
async def test_latest_weekly_brief_narrative_returns_text(repo_conn):
    repo, conn = repo_conn
    conn.fetchrow = AsyncMock(
        return_value={"narrative": "Bali Zero weekly thesis X"},
    )
    narrative = await repo.latest_weekly_brief_narrative()
    assert narrative == "Bali Zero weekly thesis X"


@pytest.mark.asyncio
async def test_latest_weekly_brief_narrative_none_when_empty(repo_conn):
    repo, conn = repo_conn
    conn.fetchrow = AsyncMock(return_value=None)
    narrative = await repo.latest_weekly_brief_narrative()
    assert narrative is None


# ── UltraMove ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_ultra_move_pending_default(repo_conn):
    repo, conn = repo_conn
    conn.fetchrow = AsyncMock(return_value=_move_row())
    move = await repo.insert_ultra_move(UltraMoveCreate(
        thesis="t", narrative="n", recommended_tone_register="analitico",
    ))
    assert move.zero_decision == UltraMoveDecision.PENDING


@pytest.mark.asyncio
async def test_update_ultra_move_decision(repo_conn):
    repo, conn = repo_conn
    conn.fetchrow = AsyncMock(return_value=_move_row(
        zero_decision="approved",
        decided_at=_now(),
        notes="good call",
    ))
    move = await repo.update_ultra_move_decision(
        uuid4(), UltraMoveDecision.APPROVED, notes="good call",
    )
    assert move is not None
    assert move.zero_decision == UltraMoveDecision.APPROVED


@pytest.mark.asyncio
async def test_pending_ultra_moves(repo_conn):
    repo, conn = repo_conn
    conn.fetch = AsyncMock(return_value=[_move_row()])
    moves = await repo.pending_ultra_moves()
    assert len(moves) == 1
    assert moves[0].zero_decision == UltraMoveDecision.PENDING
