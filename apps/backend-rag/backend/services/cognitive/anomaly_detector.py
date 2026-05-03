"""Anomaly Detector — Layer 2 (design §17.2).

Event-driven: for each freshly-inserted dossier, pick up to N related
dossiers (same topic_category, fresh, last 30 days) and ask Claude whether
any pair contradicts the new one. Insert a :class:`ComplianceAlert` per
real contradiction.

Validation is strict:
    - contradiction_type + severity required
    - severity ∈ {low, medium, high, critical}
    - pair-level idempotency via ``alert_exists_for_pair`` (14d window)

Designed to run on-demand from :class:`AnomalyEventSubscriber` (Sprint 16.3)
but also invokable directly for backfills.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from backend.services.cognitive.models import (
    AlertSeverity,
    ComplianceAlert,
    ComplianceAlertCreate,
)
from backend.services.cognitive.repository import CognitiveRepository
from backend.services.council.cli_runners import CLIRunner
from backend.services.intel.dossier_models import ResearchDossier
from backend.services.intel.dossier_repository import IntelRepository

logger = logging.getLogger(__name__)


DEFAULT_MAX_CANDIDATES = 8
DEFAULT_LOOKBACK_DAYS = 30
PAIR_IDEMPOTENCY_DAYS = 14
MIN_SEVERITY_TO_EMIT = AlertSeverity.MEDIUM


_SEVERITY_ORDER: dict[AlertSeverity, int] = {
    AlertSeverity.LOW: 0,
    AlertSeverity.MEDIUM: 1,
    AlertSeverity.HIGH: 2,
    AlertSeverity.CRITICAL: 3,
}


@dataclass
class AnomalyResult:
    ran_at: datetime
    reference_dossier_id: UUID | None = None
    candidates_considered: int = 0
    contradictions_proposed: int = 0
    alerts_inserted: int = 0
    alerts_rejected: int = 0
    idempotent_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    inserted_alerts: list[ComplianceAlert] = field(default_factory=list)


_ANOMALY_PROMPT_TEMPLATE = """Sei il rilevatore L2 di anomalie compliance Nuzantara.

DOSSIER DI RIFERIMENTO (appena entrato):
    id: {ref_id}
    titolo: {ref_title}
    summary: {ref_summary}

DOSSIER CORRELATI (stessa categoria, ultimi 30gg):
{candidates_block}

COMPITO: identifica ogni CONTRADDIZIONE REALE fra il dossier di riferimento
e uno dei dossier correlati. Non chiedere altri dati. Non inventare.

Se non trovi contraddizioni, restituisci "contradictions": [].

Rispondi SOLO JSON strict:

{{
  "contradictions": [
    {{
      "other_dossier_id": "uuid del dossier correlato",
      "contradiction_type": "grace_period_vs_enforcement|new_rule_vs_existing_skill|date_mismatch|amount_mismatch|scope_mismatch|jurisdiction_clash|other",
      "severity": "low|medium|high|critical",
      "suggested_action": "come risolverla o cosa comunicare (2-3 righe)",
      "affected_client_query": "descrizione testuale del segmento cliente impattato (facoltativo)"
    }}
  ]
}}"""


class AnomalyDetector:
    """Pairwise contradiction detector between a reference dossier and its
    recent peers.

    Parameters
    ----------
    intel_repo : IntelRepository
        Fetch related dossier candidates.
    cognitive_repo : CognitiveRepository
        Insert alerts + idempotency probe.
    runner : CLIRunner
        Claude CLI. Single call per reference dossier (scales with candidate count).
    """

    def __init__(
        self,
        intel_repo: IntelRepository,
        cognitive_repo: CognitiveRepository,
        runner: CLIRunner,
        *,
        max_candidates: int = DEFAULT_MAX_CANDIDATES,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        min_severity: AlertSeverity = MIN_SEVERITY_TO_EMIT,
        timeout_seconds: int = 90,
    ) -> None:
        self.intel_repo = intel_repo
        self.cognitive_repo = cognitive_repo
        self.runner = runner
        self.max_candidates = max_candidates
        self.lookback_days = lookback_days
        self.min_severity = min_severity
        self.timeout = timeout_seconds
        self.logger = logger

    # ── Main ────────────────────────────────────────────────────

    async def analyze_dossier(
        self,
        reference: ResearchDossier,
    ) -> AnomalyResult:
        result = AnomalyResult(
            ran_at=datetime.now(timezone.utc),
            reference_dossier_id=reference.id,
        )

        try:
            candidates = await self.intel_repo.related_fresh_dossiers(
                reference,
                days=self.lookback_days,
                limit=self.max_candidates,
            )
        except Exception as exc:  # noqa: BLE001
            result.errors.append(
                f"related_fresh_dossiers: {type(exc).__name__}: {exc}",
            )
            return result

        result.candidates_considered = len(candidates)
        if not candidates:
            return result

        candidate_by_id = {c.id: c for c in candidates}
        prompt = _render_prompt(reference, candidates)

        parsed, runner_result = await self.runner.run_json(
            prompt, timeout=self.timeout,
        )
        if not runner_result.ok or parsed is None:
            result.errors.append(
                f"runner: {runner_result.error or 'no JSON'}",
            )
            return result

        contradictions = _extract_contradictions(parsed)
        result.contradictions_proposed = len(contradictions)

        for raw in contradictions:
            outcome = await self._process_contradiction(
                raw=raw,
                reference=reference,
                candidate_by_id=candidate_by_id,
                result=result,
            )
            if outcome == "inserted":
                result.alerts_inserted += 1
            elif outcome == "idempotent":
                result.idempotent_skipped += 1
            else:
                result.alerts_rejected += 1

        return result

    # ── Per-contradiction pipeline ──────────────────────────────

    async def _process_contradiction(
        self,
        *,
        raw: dict[str, Any],
        reference: ResearchDossier,
        candidate_by_id: dict[UUID, ResearchDossier],
        result: AnomalyResult,
    ) -> str:
        try:
            other_id = UUID(str(raw.get("other_dossier_id") or ""))
        except (TypeError, ValueError):
            return "rejected"
        if other_id not in candidate_by_id:
            return "rejected"
        if other_id == reference.id:
            return "rejected"

        contradiction_type = str(raw.get("contradiction_type") or "").strip()
        if not contradiction_type:
            return "rejected"

        try:
            severity = AlertSeverity(str(raw.get("severity") or "").lower())
        except ValueError:
            return "rejected"
        if _SEVERITY_ORDER[severity] < _SEVERITY_ORDER[self.min_severity]:
            return "rejected"

        try:
            exists = await self.cognitive_repo.alert_exists_for_pair(
                reference.id, other_id, days=PAIR_IDEMPOTENCY_DAYS,
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("alert_exists_for_pair failed: %s", exc)
            exists = False
        if exists:
            return "idempotent"

        payload = ComplianceAlertCreate(
            dossier_a_id=reference.id,
            dossier_b_id=other_id,
            contradiction_type=contradiction_type[:200],
            severity=severity,
            suggested_action=_trim(raw.get("suggested_action"), 1500),
            affected_client_query=_trim(raw.get("affected_client_query"), 500),
        )
        try:
            alert = await self.cognitive_repo.insert_alert(payload)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("insert_alert failed: %s", exc)
            return "rejected"
        result.inserted_alerts.append(alert)
        return "inserted"


# ── helpers ────────────────────────────────────────────────────


def _trim(value: Any, max_chars: int) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:max_chars]


def _render_prompt(
    reference: ResearchDossier,
    candidates: list[ResearchDossier],
) -> str:
    cand_lines: list[str] = []
    for c in candidates:
        summary = c.summary_short or c.summary_medium or c.title
        cand_lines.append(
            f"- id={c.id} conf={c.confidence_0_1:.2f}\n"
            f"  title: {c.title}\n"
            f"  summary: {(summary or '')[:220]}"
        )
    return _ANOMALY_PROMPT_TEMPLATE.format(
        ref_id=reference.id,
        ref_title=reference.title,
        ref_summary=(
            reference.summary_medium
            or reference.summary_short
            or reference.title
        )[:600],
        candidates_block="\n".join(cand_lines),
    )


def _extract_contradictions(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    value = parsed.get("contradictions")
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, dict)]
