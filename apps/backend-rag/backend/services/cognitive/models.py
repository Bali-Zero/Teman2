"""Pydantic models for the 4 cognitive-layer tables (migration 114)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ── Enums matching migration 114 CHECK constraints ───────────────


class ThesisStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class UltraMoveDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


# ── CrossDossierThesis (L1 Connector, Sprint 15) ─────────────────


class CrossDossierThesis(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    narrative: str
    source_dossier_ids: list[UUID] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    implication: str | None = None
    target_clients_query: str | None = None
    generated_at: datetime
    valid_until: datetime | None = None
    status: ThesisStatus = ThesisStatus.ACTIVE


class CrossDossierThesisCreate(BaseModel):
    title: str = Field(max_length=300)
    narrative: str
    source_dossier_ids: list[UUID] = Field(min_length=2, max_length=15)
    confidence: float = Field(ge=0, le=1, default=0.6)
    implication: str | None = None
    target_clients_query: str | None = None
    valid_until: datetime | None = None


# ── ComplianceAlert (L2 Anomaly, Sprint 16) ──────────────────────


class ComplianceAlert(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    detected_at: datetime
    dossier_a_id: UUID
    dossier_b_id: UUID
    contradiction_type: str
    severity: AlertSeverity
    suggested_action: str | None = None
    affected_client_query: str | None = None
    notified_zero: bool = False
    resolved: bool = False
    resolved_at: datetime | None = None


class ComplianceAlertCreate(BaseModel):
    dossier_a_id: UUID
    dossier_b_id: UUID
    contradiction_type: str = Field(max_length=200)
    severity: AlertSeverity = AlertSeverity.MEDIUM
    suggested_action: str | None = None
    affected_client_query: str | None = None


# ── WeeklyStrategicBrief (L3 Strategos, Sprint 17) ───────────────


class WeeklyStrategicBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    week_of: date
    top_themes: list[dict[str, Any]] = Field(default_factory=list)
    proposed_actions: list[dict[str, Any]] = Field(default_factory=list)
    kpi_targets: dict[str, Any] | None = None
    team_assignments: dict[str, Any] | None = None
    narrative: str | None = None
    generated_at: datetime
    zero_approval: bool | None = None
    approved_at: datetime | None = None


class WeeklyStrategicBriefCreate(BaseModel):
    week_of: date
    top_themes: list[dict[str, Any]] = Field(default_factory=list)
    proposed_actions: list[dict[str, Any]] = Field(default_factory=list)
    kpi_targets: dict[str, Any] | None = None
    team_assignments: dict[str, Any] | None = None
    narrative: str | None = None


# ── UltraMove (L4 Oracle, Sprint 18) ─────────────────────────────


class UltraMove(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    proposed_at: datetime
    thesis: str
    narrative: str
    target_query: str | None = None
    estimated_cost: str | None = None
    estimated_value: str | None = None
    recommended_tone_register: str | None = None
    source_inputs: dict[str, Any] = Field(default_factory=dict)
    zero_decision: UltraMoveDecision = UltraMoveDecision.PENDING
    decided_at: datetime | None = None
    notes: str | None = None


class UltraMoveCreate(BaseModel):
    thesis: str = Field(max_length=500)
    narrative: str
    target_query: str | None = None
    estimated_cost: str | None = None
    estimated_value: str | None = None
    recommended_tone_register: str | None = None
    source_inputs: dict[str, Any] = Field(default_factory=dict)


# ── Event payload ───────────────────────────────────────────────


class CognitiveEventPayload(BaseModel):
    event_type: str
    occurred_at: datetime
    table: str
    thesis_id: UUID | None = None
    alert_id: UUID | None = None
    brief_id: UUID | None = None
    move_id: UUID | None = None
    severity: str | None = None
    week_of: date | None = None
    zero_decision: str | None = None
