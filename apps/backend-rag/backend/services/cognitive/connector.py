"""Connector — Layer 1 cognitive synthesis (design §17.1).

Nightly sweep: pick the ≤30 most recent confident dossiers → ask Claude
to find ≤3 theses that **no single dossier expresses** → validate →
insert into cross_dossier_theses.

Validation is strict:
    - each thesis references ≥2 source dossier ids that exist in the input batch
    - confidence ≥ MIN_CONFIDENCE (default 0.6)
    - title + narrative non-empty
    - sources-set idempotency: skip if same sorted source-set already present
      in the last N days

The Connector NEVER acts on its own: it only deposits theses. Downstream
consumers (Strategos brief builder, Telegram alerter for critical implications)
are separate modules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from backend.services.cognitive.models import (
    CrossDossierThesisCreate,
)
from backend.services.cognitive.repository import CognitiveRepository
from backend.services.council.cli_runners import CLIRunner
from backend.services.intel.dossier_models import ResearchDossier
from backend.services.intel.dossier_repository import IntelRepository

logger = logging.getLogger(__name__)


DEFAULT_BATCH_SIZE = 30
MIN_CONFIDENCE = 0.6
MAX_THESES_PER_RUN = 3
DEFAULT_VALID_DAYS = 14
IDEMPOTENCY_LOOKBACK_DAYS = 7


@dataclass
class ConnectorResult:
    ran_at: datetime
    dossiers_considered: int = 0
    theses_proposed: int = 0
    theses_inserted: int = 0
    theses_rejected: int = 0
    idempotent_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    inserted_ids: list[UUID] = field(default_factory=list)


_CONNECTOR_PROMPT_TEMPLATE = """Sei l'analista L1 del Consiglio Nuzantara.

DOSSIER IN ESAME (titolo + dossier_id + summary_short):

{dossiers_block}

COMPITO: trova fino a {max_theses} TESI CROSS-DOSSIER che nessun singolo
dossier esprime da solo. Deve essere un legame fra minimo DUE dossier.

Ogni tesi deve citare gli `dossier_id` sorgenti (almeno 2, max 5).

Rispondi SOLO JSON strict:

{{
  "theses": [
    {{
      "title": "titolo max 150 char",
      "narrative": "2-4 righe — il legame non ovvio fra i dossier",
      "source_dossier_ids": ["uuid-1", "uuid-2", ...],
      "confidence": 0.0-1.0,
      "implication": "azione o conseguenza suggerita (facoltativo)",
      "target_clients_query": "descrizione testuale del segmento cliente impattato (facoltativo)"
    }}
  ]
}}

Regole:
- Confidence < 0.6 = non produrre la tesi.
- Se non trovi legami reali, restituisci "theses": [].
- NON ripetere il contenuto di un singolo dossier — il valore è nel LEGAME.
- Fai riferimento a dossier_id reali presenti nella lista."""


class ConnectorOrchestrator:
    """Builds cross-dossier theses from a batch of recent dossiers.

    Parameters
    ----------
    intel_repo : IntelRepository
        Read dossier batch.
    cognitive_repo : CognitiveRepository
        Write theses, check idempotency.
    runner : CLIRunner
        Claude CLI (Opus preferred for 500K context; Sonnet OK).
    """

    def __init__(
        self,
        intel_repo: IntelRepository,
        cognitive_repo: CognitiveRepository,
        runner: CLIRunner,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        min_confidence: float = MIN_CONFIDENCE,
        max_theses: int = MAX_THESES_PER_RUN,
        valid_days: int = DEFAULT_VALID_DAYS,
        timeout_seconds: int = 120,
    ) -> None:
        self.intel_repo = intel_repo
        self.cognitive_repo = cognitive_repo
        self.runner = runner
        self.batch_size = batch_size
        self.min_confidence = min_confidence
        self.max_theses = max_theses
        self.valid_days = valid_days
        self.timeout = timeout_seconds
        self.logger = logger

    # ── Main ────────────────────────────────────────────────────

    async def run_once(self) -> ConnectorResult:
        started = datetime.now(timezone.utc)
        result = ConnectorResult(ran_at=started)

        try:
            dossiers = await self._load_recent_dossiers()
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"load_dossiers: {type(exc).__name__}: {exc}")
            return result

        result.dossiers_considered = len(dossiers)
        if len(dossiers) < 2:
            # can't link fewer than 2 dossiers
            return result

        valid_ids = {d.id for d in dossiers}

        prompt = _render_prompt(dossiers, self.max_theses)
        parsed, runner_result = await self.runner.run_json(
            prompt, timeout=self.timeout,
        )
        if not runner_result.ok or parsed is None:
            result.errors.append(
                f"runner: {runner_result.error or 'no JSON'}",
            )
            return result

        theses = _extract_theses(parsed)
        result.theses_proposed = len(theses)

        for raw in theses[: self.max_theses]:
            processed = await self._process_thesis(raw, valid_ids=valid_ids)
            if processed == "inserted":
                result.theses_inserted += 1
            elif processed == "idempotent":
                result.idempotent_skipped += 1
            else:
                result.theses_rejected += 1

        # capture inserted ids for subsequent consumers
        if result.theses_inserted > 0:
            try:
                recent = await self.cognitive_repo.recent_theses(days=1)
                result.inserted_ids = [t.id for t in recent[: result.theses_inserted]]
            except Exception:  # noqa: BLE001
                pass

        return result

    # ── Internals ───────────────────────────────────────────────

    async def _load_recent_dossiers(self) -> list[ResearchDossier]:
        """Top-N by created_at within validity, favouring higher confidence."""
        rows = await self.intel_repo.fetch_safe(
            """
            SELECT * FROM research_dossiers
             WHERE archived_at IS NULL
               AND freshness_expiry > NOW()
             ORDER BY confidence_0_1 DESC, created_at DESC
             LIMIT $1;
            """,
            self.batch_size,
        )
        # reuse _row_to_dossier from repository to keep parsing consistent
        from backend.services.intel.dossier_repository import _row_to_dossier

        return [_row_to_dossier(row) for row in rows]

    async def _process_thesis(
        self,
        raw: dict[str, Any],
        *,
        valid_ids: set[UUID],
    ) -> str:
        """Returns ``inserted``, ``idempotent``, or ``rejected``."""
        try:
            source_ids = [
                UUID(str(x)) for x in (raw.get("source_dossier_ids") or [])
            ]
        except (TypeError, ValueError):
            return "rejected"

        # filter to sources that actually exist in the batch
        valid_sources = [sid for sid in source_ids if sid in valid_ids]
        if len(valid_sources) < 2:
            return "rejected"

        try:
            confidence = float(raw.get("confidence") or 0.0)
        except (TypeError, ValueError):
            return "rejected"
        if confidence < self.min_confidence:
            return "rejected"

        title = str(raw.get("title") or "").strip()
        narrative = str(raw.get("narrative") or "").strip()
        if not title or not narrative:
            return "rejected"

        # idempotency — same source-set recently? skip.
        try:
            already = await self.cognitive_repo.thesis_exists_for_sources(
                valid_sources, days=IDEMPOTENCY_LOOKBACK_DAYS,
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("idempotency check failed: %s", exc)
            already = False
        if already:
            return "idempotent"

        payload = CrossDossierThesisCreate(
            title=title[:300],
            narrative=narrative,
            source_dossier_ids=valid_sources[:15],
            confidence=max(0.0, min(1.0, confidence)),
            implication=_trim(raw.get("implication"), 1000),
            target_clients_query=_trim(raw.get("target_clients_query"), 500),
            valid_until=datetime.now(timezone.utc) + timedelta(days=self.valid_days),
        )
        try:
            await self.cognitive_repo.insert_thesis(payload)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("insert_thesis failed: %s", exc)
            return "rejected"
        return "inserted"


# ── helpers ────────────────────────────────────────────────────


def _trim(value: Any, max_chars: int) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:max_chars]


def _render_prompt(dossiers: list[ResearchDossier], max_theses: int) -> str:
    lines: list[str] = []
    for d in dossiers:
        summary = d.summary_short or d.summary_medium or d.title
        lines.append(
            f"- id={d.id} cat={d.topic_category.value} conf={d.confidence_0_1:.2f}\n"
            f"  title: {d.title}\n"
            f"  summary: {(summary or '')[:220]}"
        )
    dossiers_block = "\n".join(lines)
    return _CONNECTOR_PROMPT_TEMPLATE.format(
        dossiers_block=dossiers_block,
        max_theses=max_theses,
    )


def _extract_theses(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    theses = parsed.get("theses")
    if not isinstance(theses, list):
        return []
    return [t for t in theses if isinstance(t, dict)]
