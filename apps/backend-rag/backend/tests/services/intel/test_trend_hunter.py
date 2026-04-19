"""Unit tests for Trend-Hunter adapters + orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from backend.services.intel.dossier_models import TrendSource
from backend.services.intel.trend_hunter.adapters import (
    RSSAdapter,
    _heuristic_urgency,
    _parse_rss,
)
from backend.services.intel.trend_hunter.orchestrator import (
    TrendHunterOrchestrator,
    _dedup,
    _signal_dedup_key,
)
from backend.services.intel.trend_hunter.types import NormalizedSignal

# ── Adapter helpers ────────────────────────────────────────────────────

def test_heuristic_urgency_default_baseline():
    assert _heuristic_urgency("something neutral") == 40.0


def test_heuristic_urgency_boosts_on_markers():
    score = _heuristic_urgency("urgent enforcement deadline in 30 days")
    assert score > 40.0
    assert score <= 100.0


def test_heuristic_urgency_caps_at_100():
    many = " ".join([
        "breaking", "urgent", "deadline", "effective",
        "enforcement", "sanction", "deportation", "audit",
    ])
    assert _heuristic_urgency(many) == 100.0


def test_parse_rss_returns_empty_on_invalid_xml():
    assert _parse_rss("not xml at all") == []


def test_parse_rss_handles_simple_feed():
    xml = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <title>t</title>
      <item>
        <title>KBLI 2025 enforcement wave</title>
        <description>Desc on KBLI compliance</description>
        <link>https://example.com/a</link>
      </item>
      <item>
        <title>Unrelated weather update</title>
        <description>Rain today</description>
        <link>https://example.com/b</link>
      </item>
    </channel></rss>
    """
    items = _parse_rss(xml)
    assert len(items) == 2
    titles = {i["title"] for i in items}
    assert "KBLI 2025 enforcement wave" in titles


def test_rss_adapter_triages_by_keywords():
    """Only items mentioning triage keywords should survive."""
    xml = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>Rain today in Kuta</title><description>weather</description><link>u1</link></item>
      <item><title>KBLI 2025 enforcement</title><description>compliance</description><link>u2</link></item>
    </channel></rss>
    """
    items = _parse_rss(xml)
    adapter = RSSAdapter(feeds=[])  # no fetch; we triage manually via attrs
    # Apply same triage logic as adapter.fetch()
    surviving = [
        i for i in items
        if any(kw in (i["title"] + i["description"]).lower()
               for kw in adapter.triage_keywords)
    ]
    assert len(surviving) == 1
    assert "KBLI" in surviving[0]["title"]


# ── Dedup + fingerprint ───────────────────────────────────────────────

def _mk_signal(topic: str, source: TrendSource = TrendSource.RSS,
               url: str | None = None) -> NormalizedSignal:
    return NormalizedSignal(
        source=source,
        topic=topic,
        source_url=url,
        urgency_hint=50.0,
        detected_at=datetime.now(timezone.utc),
    )


def test_fingerprint_is_stable():
    a = _mk_signal("KBLI 2025 wave", url="https://x")
    b = _mk_signal("KBLI 2025 wave", url="https://x")
    assert _signal_dedup_key(a) == _signal_dedup_key(b)


def test_fingerprint_different_for_different_topic():
    a = _mk_signal("KBLI 2025 wave")
    b = _mk_signal("B211A extension")
    assert _signal_dedup_key(a) != _signal_dedup_key(b)


def test_dedup_removes_duplicates():
    sigs = [
        _mk_signal("A"),
        _mk_signal("A"),
        _mk_signal("B"),
        _mk_signal("B", url="https://diff"),
    ]
    unique = _dedup(sigs)
    assert len(unique) == 3  # A once, B twice (different URLs)


def test_dedup_preserves_order():
    sigs = [_mk_signal("first"), _mk_signal("second"), _mk_signal("first")]
    unique = _dedup(sigs)
    assert [s.topic for s in unique] == ["first", "second"]


# ── Orchestrator cycle ─────────────────────────────────────────────────


class _StaticAdapter:
    """Minimal adapter that yields pre-set signals."""

    def __init__(self, name: str, signals: list[NormalizedSignal]) -> None:
        self.name = name
        self._signals = signals

    async def run(self):
        from backend.services.intel.trend_hunter.types import SourceAdapterResult
        return SourceAdapterResult(
            adapter_name=self.name,
            signals=self._signals,
            duration_ms=1.0,
        )


@pytest.mark.asyncio
async def test_orchestrator_persists_each_unique_signal():
    mock_repo = AsyncMock()
    mock_repo.append_trend = AsyncMock()

    adapter = _StaticAdapter(
        "static",
        [_mk_signal("topic A"), _mk_signal("topic B"), _mk_signal("topic A")],
    )
    orch = TrendHunterOrchestrator(
        repo=mock_repo,
        adapters=[adapter],
        force_degraded=False,
    )
    summary = await orch.run_cycle()

    assert summary.raw_signals == 3
    assert summary.after_dedup == 2
    assert summary.persisted == 2
    assert mock_repo.append_trend.call_count == 2


@pytest.mark.asyncio
async def test_orchestrator_continues_when_persist_fails():
    mock_repo = AsyncMock()
    mock_repo.append_trend = AsyncMock(
        side_effect=[None, RuntimeError("simulated"), None],
    )
    adapter = _StaticAdapter(
        "static",
        [_mk_signal("a"), _mk_signal("b"), _mk_signal("c")],
    )
    orch = TrendHunterOrchestrator(
        repo=mock_repo,
        adapters=[adapter],
        force_degraded=False,
    )
    summary = await orch.run_cycle()

    assert summary.after_dedup == 3
    assert summary.persisted == 2  # one failure absorbed


@pytest.mark.asyncio
async def test_orchestrator_degraded_mode_forced():
    mock_repo = AsyncMock()
    orch = TrendHunterOrchestrator(
        repo=mock_repo,
        adapters=[_StaticAdapter("static", [])],
        force_degraded=True,
    )
    summary = await orch.run_cycle()
    assert summary.degraded is True


@pytest.mark.asyncio
async def test_orchestrator_default_adapters_degraded_excludes_xai(monkeypatch):
    """On Air (degraded), xAI adapter must NOT be present (Law 2 OSINT)."""
    monkeypatch.setenv("GROK_API_KEY", "fake-key")
    adapters = TrendHunterOrchestrator._default_adapters(degraded=True)
    names = {a.name for a in adapters}
    assert "rss" in names
    assert "xai" not in names


@pytest.mark.asyncio
async def test_orchestrator_default_adapters_pro_includes_xai(monkeypatch):
    monkeypatch.setenv("GROK_API_KEY", "fake-key")
    adapters = TrendHunterOrchestrator._default_adapters(degraded=False)
    names = {a.name for a in adapters}
    assert "rss" in names
    assert "xai" in names
