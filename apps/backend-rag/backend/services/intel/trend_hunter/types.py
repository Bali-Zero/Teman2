"""Internal types shared across Trend-Hunter adapters and orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from backend.services.intel.dossier_models import TrendSource


@dataclass
class NormalizedSignal:
    """Adapter-normalized signal — not yet persisted. Pre-scoring stage.

    Each source adapter returns a list of these; orchestrator then runs
    dedup, scoring (via Gemini CLI or heuristics), entity linking, and
    finally persistence via IntelRepository.append_trend().
    """

    source: TrendSource
    topic: str
    source_url: str | None = None
    raw_title: str | None = None
    raw_snippet: str | None = None
    language: str | None = None
    urgency_hint: float = 50.0  # adapter's guess before unified scoring
    detected_at: datetime | None = None


@dataclass
class SourceAdapterResult:
    """Per-adapter run outcome."""

    adapter_name: str
    signals: list[NormalizedSignal] = field(default_factory=list)
    duration_ms: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None
