"""Trend-Hunter orchestrator.

Cycle:
    gather_sources(adapters) -> SourceAdapterResult[]
    flatten -> NormalizedSignal[]
    dedup -> NormalizedSignal[] (by source+topic hash, 24h window)
    score_bali_zero_relevance (Gemini CLI, optional) -> float per signal
    link_entities (KG entity_linker) -> entities_linked JSON
    persist via IntelRepository.append_trend -> trend_signals row + pg_notify
    return SprintRunSummary

The orchestrator is host-aware: on Air it runs the degraded subset
(RSS only, no xAI OSINT) per Law 2 Sovranità locale.
"""

from __future__ import annotations

import hashlib
import logging
import os
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.services.intel.dossier_models import TrendSignalCreate
from backend.services.intel.dossier_repository import IntelRepository
from backend.services.intel.trend_hunter.adapters import (
    GoogleTrendsAdapter,
    RedditAdapter,
    RSSAdapter,
    SourceAdapter,
    XAIAdapter,
    gather_sources,
)
from backend.services.intel.trend_hunter.types import (
    NormalizedSignal,
    SourceAdapterResult,
)

logger = logging.getLogger(__name__)


@dataclass
class RunSummary:
    started_at: datetime
    finished_at: datetime | None = None
    adapters_run: list[SourceAdapterResult] = field(default_factory=list)
    raw_signals: int = 0
    after_dedup: int = 0
    persisted: int = 0
    host: str = ""
    degraded: bool = False


def _signal_dedup_key(sig: NormalizedSignal) -> str:
    key = f"{sig.source.value}|{sig.topic.strip().lower()}|{sig.source_url or ''}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def _dedup(signals: list[NormalizedSignal]) -> list[NormalizedSignal]:
    seen: set[str] = set()
    unique: list[NormalizedSignal] = []
    for sig in signals:
        fp = _signal_dedup_key(sig)
        if fp in seen:
            continue
        seen.add(fp)
        unique.append(sig)
    return unique


def _is_pro_host() -> bool:
    """Pro = nuzantara@Nuzantara; Air = antonellosiano@Nuzantara-9.

    We detect via hostname (stable) rather than USER (drifts in cron).
    """
    host = socket.gethostname()
    return host.startswith("Nuzantara") and "Nuzantara-9" not in host


class TrendHunterOrchestrator:
    """Coordinates adapters, dedup, scoring, and persistence.

    Primary entry: :meth:`run_cycle`.
    """

    def __init__(
        self,
        repo: IntelRepository,
        adapters: list[SourceAdapter] | None = None,
        *,
        force_degraded: bool | None = None,
        default_half_life_hours: int = 48,
    ) -> None:
        self.repo = repo
        self.degraded = (
            force_degraded
            if force_degraded is not None
            else not _is_pro_host()
        )
        if adapters is None:
            adapters = self._default_adapters(degraded=self.degraded)
        self.adapters = adapters
        self.default_half_life_hours = default_half_life_hours
        self.logger = logger

    # ── Default adapter wiring ──────────────────────────────────────────

    @staticmethod
    def _default_adapters(*, degraded: bool) -> list[SourceAdapter]:
        """RSS always; xAI only on Pro (Law 2 OSINT blindato).

        Reddit + GoogleTrends placeholders included so orchestrator logs
        the coverage gap — they return [] until implemented.
        """
        adapters: list[SourceAdapter] = [RSSAdapter()]
        if not degraded:
            grok_key = os.environ.get("GROK_API_KEY")
            if grok_key:
                adapters.append(XAIAdapter(api_key=grok_key))
            adapters.append(RedditAdapter())
            adapters.append(GoogleTrendsAdapter())
        return adapters

    # ── Main cycle ──────────────────────────────────────────────────────

    async def run_cycle(self) -> RunSummary:
        started = datetime.now(timezone.utc)
        summary = RunSummary(
            started_at=started,
            host=socket.gethostname(),
            degraded=self.degraded,
        )
        self.logger.info(
            "trend-hunter cycle start | host=%s degraded=%s adapters=%s",
            summary.host,
            summary.degraded,
            [a.name for a in self.adapters],
        )

        summary.adapters_run = await gather_sources(self.adapters)
        all_signals = [s for r in summary.adapters_run if r.ok for s in r.signals]
        summary.raw_signals = len(all_signals)

        unique = _dedup(all_signals)
        summary.after_dedup = len(unique)

        for sig in unique:
            try:
                await self._persist(sig)
                summary.persisted += 1
            except Exception as exc:  # noqa: BLE001 — never abort the cycle
                self.logger.warning(
                    "persist failed for %s: %s",
                    sig.topic[:80],
                    exc,
                    exc_info=True,
                )

        summary.finished_at = datetime.now(timezone.utc)
        self.logger.info(
            "trend-hunter cycle done | raw=%d dedup=%d persisted=%d duration=%sms",
            summary.raw_signals,
            summary.after_dedup,
            summary.persisted,
            int((summary.finished_at - summary.started_at).total_seconds() * 1000),
        )
        return summary

    # ── Persistence ─────────────────────────────────────────────────────

    async def _persist(self, sig: NormalizedSignal) -> None:
        relevance = await self._score_relevance(sig)
        entities = await self._link_entities(sig)

        await self.repo.append_trend(
            TrendSignalCreate(
                source=sig.source,
                topic=sig.topic,
                urgency_score=sig.urgency_hint,
                source_url=sig.source_url,
                raw_title=sig.raw_title,
                raw_snippet=sig.raw_snippet,
                language=sig.language,
                bali_zero_relevance=relevance,
                decay_half_life_hours=self.default_half_life_hours,
                entities_linked=entities,
            )
        )

    # ── Enrichment hooks (deferred wiring, kept safe) ───────────────────

    async def _score_relevance(self, sig: NormalizedSignal) -> float | None:
        """Gemini CLI scoring — deferred.

        Law 1 compliance: when wired, calls `gemini -p` subprocess with
        a short prompt, never HTTP SDK. Returns None for now so the trend
        is still persisted with only the heuristic urgency_score.
        """
        return None

    async def _link_entities(
        self, sig: NormalizedSignal,
    ) -> list[dict[str, str]] | None:
        """KG entity linking — deferred.

        When wired, calls the existing EntityLinker in
        backend/services/knowledge_graph/entity_linker.py. Returns None
        until the integration is stable.
        """
        return None
