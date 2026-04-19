"""Strategos — Layer 3 weekly strategic brief (design §17.3).

Aggregates 30-day context across:
    - recent dossiers (top by confidence)
    - active cross-dossier theses (Connector L1 output)
    - unresolved wr_anomaly_alerts (Anomaly L2 output)
    - war_room_posts + metrics (avg composite / reach / engagement per register)
    - recent rejections (top reasons)
    - genome skills/scars (Learner output, optional)

Produces a :class:`WeeklyStrategicBrief` via Claude CLI long-context.
Writes via UPSERT on ``week_of`` — same Monday twice = overwrite (intentional).

Run weekly on Sunday 22:00 WITA (design §2 cadence).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from backend.services.cognitive.models import (
    WeeklyStrategicBrief,
    WeeklyStrategicBriefCreate,
)
from backend.services.cognitive.repository import CognitiveRepository
from backend.services.council.cli_runners import CLIRunner
from backend.services.intel.dossier_repository import IntelRepository
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


DEFAULT_DOSSIER_LOOKBACK = 30
DEFAULT_THESES_LOOKBACK = 14
DEFAULT_METRICS_LOOKBACK = 30
DEFAULT_REJECTIONS_LOOKBACK = 30

DEFAULT_TOP_DOSSIERS = 25
DEFAULT_TOP_THESES = 8

CONTEXT_MAX_CHARS = 8000

# Optional hook for Learner integration (kept injectable to avoid import cycle).
SkillsSnapshotFn = Callable[[], Awaitable[str]]


# ── Data contracts ────────────────────────────────────────────


@dataclass
class StrategosContext:
    """Compact snapshot fed to the LLM prompt."""

    week_of: date
    dossiers_block: str = ""
    theses_block: str = ""
    alerts_block: str = ""
    metrics_block: str = ""
    rejections_block: str = ""
    skills_block: str = ""

    def as_prompt_context(self, max_chars: int = CONTEXT_MAX_CHARS) -> str:
        parts: list[str] = []
        if self.dossiers_block:
            parts.append("[DOSSIER (top 25 ultimi 30gg)]")
            parts.append(self.dossiers_block)
        if self.theses_block:
            parts.append("")
            parts.append("[TESI CROSS-DOSSIER (ultimi 14gg)]")
            parts.append(self.theses_block)
        if self.alerts_block:
            parts.append("")
            parts.append("[COMPLIANCE ALERTS APERTI]")
            parts.append(self.alerts_block)
        if self.metrics_block:
            parts.append("")
            parts.append("[WAR ROOM METRICHE per registro (30gg)]")
            parts.append(self.metrics_block)
        if self.rejections_block:
            parts.append("")
            parts.append("[REJECTIONS per motivo (30gg)]")
            parts.append(self.rejections_block)
        if self.skills_block:
            parts.append("")
            parts.append("[GENOME — skill/scar recenti]")
            parts.append(self.skills_block)
        joined = "\n".join(parts).rstrip()
        if len(joined) <= max_chars:
            return joined
        return joined[:max_chars].rstrip() + "\n…[truncated]"


@dataclass
class StrategosResult:
    ran_at: datetime
    week_of: date
    brief: WeeklyStrategicBrief | None = None
    prompt_chars: int = 0
    context_chars: int = 0
    inserted: bool = False
    errors: list[str] = field(default_factory=list)


# ── Context builder ───────────────────────────────────────────


class StrategosContextBuilder:
    """Read-side aggregator. Pure-ish: only queries repos, no writes."""

    def __init__(
        self,
        intel_repo: IntelRepository,
        cognitive_repo: CognitiveRepository,
        war_room_repo: WarRoomRepository,
        *,
        skills_snapshot_fn: SkillsSnapshotFn | None = None,
    ) -> None:
        self.intel_repo = intel_repo
        self.cognitive_repo = cognitive_repo
        self.war_room_repo = war_room_repo
        self.skills_snapshot_fn = skills_snapshot_fn

    async def build(self, *, week_of: date) -> StrategosContext:
        context = StrategosContext(week_of=week_of)

        # 1. dossiers
        try:
            rows = await self.intel_repo.fetch_safe(
                """
                SELECT id, title, topic_category, confidence_0_1, summary_short
                  FROM research_dossiers
                 WHERE archived_at IS NULL
                   AND created_at > NOW() - make_interval(days => $1)
                 ORDER BY confidence_0_1 DESC, created_at DESC
                 LIMIT $2;
                """,
                DEFAULT_DOSSIER_LOOKBACK,
                DEFAULT_TOP_DOSSIERS,
            )
            context.dossiers_block = "\n".join(
                _format_dossier_row(r) for r in rows
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("dossiers context failed: %s", exc)

        # 2. theses
        try:
            theses = await self.cognitive_repo.recent_theses(
                days=DEFAULT_THESES_LOOKBACK,
            )
            context.theses_block = "\n".join(
                f"- conf={t.confidence:.2f} | {t.title[:120]} "
                f"→ {(t.implication or '')[:120]}"
                for t in theses[:DEFAULT_TOP_THESES]
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("theses context failed: %s", exc)

        # 3. unresolved alerts
        try:
            alerts = await self.cognitive_repo.unresolved_alerts()
            context.alerts_block = "\n".join(
                f"- {a.severity.value} | {a.contradiction_type[:80]} "
                f"(A={a.dossier_a_id} B={a.dossier_b_id})"
                for a in alerts[:10]
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("alerts context failed: %s", exc)

        # 4. metrics per register
        try:
            metric_rows = await self.war_room_repo.fetch_safe(
                """
                SELECT COALESCE(p.register, 'unknown') AS register,
                       m.metric_name,
                       AVG(m.value)::float            AS avg_value,
                       COUNT(*)                       AS n
                  FROM war_room_metrics m
                  JOIN war_room_posts p ON p.id = m.post_id
                 WHERE m.collected_at > NOW() - make_interval(days => $1)
                 GROUP BY 1, 2
                 ORDER BY 1 ASC, 2 ASC;
                """,
                DEFAULT_METRICS_LOOKBACK,
            )
            context.metrics_block = "\n".join(
                f"- {r['register']} · {r['metric_name']} "
                f"avg={float(r['avg_value']):.2f} n={r['n']}"
                for r in metric_rows
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("metrics context failed: %s", exc)

        # 5. rejections
        try:
            rej_rows = await self.war_room_repo.fetch_safe(
                """
                SELECT reason, COUNT(*) AS n
                  FROM war_room_rejections
                 WHERE rejected_at > NOW() - make_interval(days => $1)
                 GROUP BY reason
                 ORDER BY n DESC;
                """,
                DEFAULT_REJECTIONS_LOOKBACK,
            )
            context.rejections_block = "\n".join(
                f"- {r['reason']}: {r['n']}" for r in rej_rows
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("rejections context failed: %s", exc)

        # 6. genome snapshot (optional)
        if self.skills_snapshot_fn is not None:
            try:
                snapshot = await self.skills_snapshot_fn()
                context.skills_block = (snapshot or "")[:1500]
            except Exception as exc:  # noqa: BLE001
                logger.debug("skills snapshot failed: %s", exc)

        return context


# ── Orchestrator ──────────────────────────────────────────────


_STRATEGOS_PROMPT_TEMPLATE = """Sei Strategos L3 del Consiglio Nuzantara.
Leggi il contesto e produci il brief strategico settimanale per Zero.

SETTIMANA: {week_of}

CONTESTO:
{context}

COMPITO: produci un brief strategico concreto. NON copiare il contesto —
sintetizza in tesi, azioni concrete, KPI misurabili.

Rispondi SOLO JSON strict:

{{
  "top_themes": [
    {{"name": "tema breve", "weight": 0.0-1.0, "why": "1 riga motivazione"}}
  ],
  "proposed_actions": [
    {{
      "action": "descrizione azione concreta (es. 'commissiona 3 articoli pedagogici su B211A')",
      "owner": "war_room|crm|intel|zero|team",
      "deadline_days": 1-14,
      "rationale": "1-2 righe"
    }}
  ],
  "kpi_targets": {{
    "reach_uplift_pct": 0-100,
    "escalation_reduction_pct": 0-100,
    "additional_kpis": {{"metric_name": "target"}}
  }},
  "team_assignments": {{
    "role": "persona/team responsabile per ogni action"
  }},
  "narrative": "3-5 righe — la tesi strategica unitaria della settimana"
}}

Regole:
- Azioni concrete, non generiche.
- Se il contesto mostra una deriva tonale (registro > 40%), includi un'azione di ribilanciamento.
- Se ci sono anomaly_alerts aperti severi, prioritizza azioni CRM.
- Max 5 top_themes, max 6 proposed_actions."""


class StrategosOrchestrator:
    """Weekly brief builder. Upserts on ``week_of``."""

    def __init__(
        self,
        intel_repo: IntelRepository,
        cognitive_repo: CognitiveRepository,
        war_room_repo: WarRoomRepository,
        runner: CLIRunner,
        *,
        context_builder: StrategosContextBuilder | None = None,
        timeout_seconds: int = 180,
    ) -> None:
        self.intel_repo = intel_repo
        self.cognitive_repo = cognitive_repo
        self.war_room_repo = war_room_repo
        self.runner = runner
        self.context_builder = context_builder or StrategosContextBuilder(
            intel_repo=intel_repo,
            cognitive_repo=cognitive_repo,
            war_room_repo=war_room_repo,
        )
        self.timeout = timeout_seconds
        self.logger = logger

    async def run_once(
        self,
        *,
        week_of: date | None = None,
    ) -> StrategosResult:
        week_of = week_of or _iso_week_monday(datetime.now(timezone.utc))
        result = StrategosResult(
            ran_at=datetime.now(timezone.utc),
            week_of=week_of,
        )

        try:
            context = await self.context_builder.build(week_of=week_of)
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"context: {type(exc).__name__}: {exc}")
            return result

        context_text = context.as_prompt_context()
        result.context_chars = len(context_text)
        prompt = _STRATEGOS_PROMPT_TEMPLATE.format(
            week_of=week_of.isoformat(),
            context=context_text,
        )
        result.prompt_chars = len(prompt)

        parsed, runner_result = await self.runner.run_json(
            prompt, timeout=self.timeout,
        )
        if not runner_result.ok or parsed is None:
            result.errors.append(
                f"runner: {runner_result.error or 'no JSON'}",
            )
            return result

        try:
            payload = _build_brief_payload(parsed, week_of)
        except ValueError as exc:
            result.errors.append(f"parse: {exc}")
            return result

        try:
            brief = await self.cognitive_repo.insert_brief(payload)
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"insert: {type(exc).__name__}: {exc}")
            return result

        result.brief = brief
        result.inserted = True
        return result


# ── Helpers ────────────────────────────────────────────────────


def _format_dossier_row(r: Any) -> str:
    dossier_id = r["id"]
    category = r["topic_category"]
    confidence = float(r["confidence_0_1"])
    title = (r["title"] or "")[:120]
    summary = r["summary_short"] or ""
    line = (
        f"- id={dossier_id} cat={category} conf={confidence:.2f} | {title}"
    )
    if summary:
        line += f" — {summary[:140]}"
    return line


def _iso_week_monday(now: datetime) -> date:
    """Monday of the current ISO week (in UTC)."""
    d = now.astimezone(timezone.utc).date()
    return d - timedelta(days=d.weekday())


def _build_brief_payload(
    parsed: dict[str, Any],
    week_of: date,
) -> WeeklyStrategicBriefCreate:
    themes = _coerce_list_of_dicts(parsed.get("top_themes"))[:5]
    actions = _coerce_list_of_dicts(parsed.get("proposed_actions"))[:6]
    kpi = parsed.get("kpi_targets")
    if not isinstance(kpi, dict):
        kpi = None
    assignments = parsed.get("team_assignments")
    if not isinstance(assignments, dict):
        assignments = None
    narrative = parsed.get("narrative")
    if narrative is not None:
        narrative = str(narrative).strip() or None

    if not themes and not actions and not narrative:
        raise ValueError("empty_brief")

    return WeeklyStrategicBriefCreate(
        week_of=week_of,
        top_themes=themes,
        proposed_actions=actions,
        kpi_targets=kpi,
        team_assignments=assignments,
        narrative=narrative,
    )


def _coerce_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, dict)]
