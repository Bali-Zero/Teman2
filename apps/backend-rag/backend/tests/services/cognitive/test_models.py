"""Unit tests for cognitive Pydantic models (migration 114)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.services.cognitive.models import (
    AlertSeverity,
    CognitiveEventPayload,
    ComplianceAlertCreate,
    CrossDossierThesis,
    CrossDossierThesisCreate,
    ThesisStatus,
    UltraMoveCreate,
    UltraMoveDecision,
    WeeklyStrategicBriefCreate,
)

# ── Enum completeness matches migration 114 CHECK constraints ──


def test_thesis_status_values():
    assert {s.value for s in ThesisStatus} == {"active", "superseded", "archived"}


def test_alert_severity_values():
    assert {s.value for s in AlertSeverity} == {"low", "medium", "high", "critical"}


def test_ultra_move_decision_values():
    assert {d.value for d in UltraMoveDecision} == {
        "pending", "approved", "rejected", "deferred",
    }


# ── CrossDossierThesisCreate ───────────────────────────────────


def test_thesis_create_requires_min_2_sources():
    with pytest.raises(ValidationError):
        CrossDossierThesisCreate(
            title="x",
            narrative="y",
            source_dossier_ids=[uuid4()],
            confidence=0.8,
        )


def test_thesis_create_max_15_sources():
    with pytest.raises(ValidationError):
        CrossDossierThesisCreate(
            title="x",
            narrative="y",
            source_dossier_ids=[uuid4() for _ in range(20)],
            confidence=0.8,
        )


def test_thesis_create_confidence_range():
    with pytest.raises(ValidationError):
        CrossDossierThesisCreate(
            title="x",
            narrative="y",
            source_dossier_ids=[uuid4(), uuid4()],
            confidence=1.5,
        )
    with pytest.raises(ValidationError):
        CrossDossierThesisCreate(
            title="x",
            narrative="y",
            source_dossier_ids=[uuid4(), uuid4()],
            confidence=-0.1,
        )


def test_thesis_create_happy_path():
    payload = CrossDossierThesisCreate(
        title="Indonesia digital-compliance convergence",
        narrative="BI + DJP + OJK allineano KYC + DPP entro Q3 2026",
        source_dossier_ids=[uuid4(), uuid4(), uuid4()],
        confidence=0.78,
        implication="PT PMA fintech a 90gg dalla scadenza",
    )
    assert payload.confidence == 0.78
    assert len(payload.source_dossier_ids) == 3


def test_thesis_full_model_status_default():
    now = datetime.now(timezone.utc)
    t = CrossDossierThesis(
        id=uuid4(),
        title="t",
        narrative="n",
        source_dossier_ids=[uuid4(), uuid4()],
        confidence=0.7,
        generated_at=now,
    )
    assert t.status == ThesisStatus.ACTIVE


# ── ComplianceAlertCreate ──────────────────────────────────────


def test_alert_create_default_medium():
    a = ComplianceAlertCreate(
        dossier_a_id=uuid4(),
        dossier_b_id=uuid4(),
        contradiction_type="grace_period_vs_enforcement",
    )
    assert a.severity == AlertSeverity.MEDIUM


# ── WeeklyStrategicBriefCreate ─────────────────────────────────


def test_brief_create_minimal():
    b = WeeklyStrategicBriefCreate(week_of=date(2026, 4, 20))
    assert b.top_themes == []
    assert b.proposed_actions == []


def test_brief_create_with_lists():
    b = WeeklyStrategicBriefCreate(
        week_of=date(2026, 4, 20),
        top_themes=[{"name": "B211A reform", "weight": 0.7}],
        proposed_actions=[
            {"action": "commissioning 3 analitico pedagogical posts"},
        ],
        kpi_targets={"reach_uplift_pct": 20},
    )
    assert len(b.top_themes) == 1
    assert b.kpi_targets["reach_uplift_pct"] == 20


# ── UltraMoveCreate ────────────────────────────────────────────


def test_ultra_move_create_title_cap():
    with pytest.raises(ValidationError):
        UltraMoveCreate(
            thesis="x" * 600,   # > 500
            narrative="y",
        )


def test_ultra_move_create_happy_path():
    u = UltraMoveCreate(
        thesis="Pre-flight audit 458 PT PMA before Sep DJP cross-check",
        narrative="Connector+Strategos suggest a proactive audit",
        estimated_cost="2gg lavoro",
        estimated_value="evitare flag automatico",
        recommended_tone_register="analitico",
        source_inputs={"theses": [], "briefs": []},
    )
    assert u.recommended_tone_register == "analitico"


# ── Event payload ──────────────────────────────────────────────


def test_cognitive_event_payload_small():
    p = CognitiveEventPayload(
        event_type="thesis_INSERT",
        occurred_at=datetime.now(timezone.utc),
        table="cross_dossier_theses",
        thesis_id=uuid4(),
    )
    serialized = p.model_dump_json()
    assert len(serialized.encode()) < 512
