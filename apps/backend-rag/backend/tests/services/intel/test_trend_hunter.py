"""Unit tests for Trend-Hunter adapters + orchestrator."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest

from backend.services.intel.dossier_models import TrendSource
from backend.services.intel.trend_hunter.adapters import (
    GoogleTrendsAdapter,
    RedditAdapter,
    RSSAdapter,
    _feeds_from_env,
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
    many = " ".join(
        [
            "breaking",
            "urgent",
            "deadline",
            "effective",
            "enforcement",
            "sanction",
            "deportation",
            "audit",
        ]
    )
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
        i
        for i in items
        if any(kw in (i["title"] + i["description"]).lower() for kw in adapter.triage_keywords)
    ]
    assert len(surviving) == 1
    assert "KBLI" in surviving[0]["title"]


# ── Dedup + fingerprint ───────────────────────────────────────────────


def _mk_signal(
    topic: str, source: TrendSource = TrendSource.RSS, url: str | None = None
) -> NormalizedSignal:
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


# ── Starvation receptor (scar #2: green cron, empty output) ─────────────


@pytest.mark.asyncio
async def test_starvation_receptor_fires_on_zero_signals(caplog):
    """A cycle where ALL adapters yield 0 signals must log a loud STARVATION line."""
    mock_repo = AsyncMock()
    orch = TrendHunterOrchestrator(
        repo=mock_repo,
        adapters=[_StaticAdapter("empty-a", []), _StaticAdapter("empty-b", [])],
        force_degraded=False,
    )
    with caplog.at_level(logging.WARNING):
        summary = await orch.run_cycle()

    assert summary.raw_signals == 0
    starvation = [r for r in caplog.records if "STARVATION" in r.getMessage()]
    assert len(starvation) == 1
    msg = starvation[0].getMessage()
    assert "[trend-hunter] STARVATION: 0 signals from 2 adapters" in msg
    assert "empty-a" in msg
    assert "empty-b" in msg


@pytest.mark.asyncio
async def test_starvation_receptor_reports_adapter_errors(caplog):
    """Adapters that errored are named with their error in the starvation line."""

    class _ErrorAdapter:
        name = "broken"

        async def run(self):
            from backend.services.intel.trend_hunter.types import SourceAdapterResult

            return SourceAdapterResult(
                adapter_name=self.name, duration_ms=1.0, error="boom"
            )

    mock_repo = AsyncMock()
    orch = TrendHunterOrchestrator(
        repo=mock_repo,
        adapters=[_ErrorAdapter()],
        force_degraded=False,
    )
    with caplog.at_level(logging.WARNING):
        await orch.run_cycle()

    starvation = [r for r in caplog.records if "STARVATION" in r.getMessage()]
    assert len(starvation) == 1
    assert "broken: error=boom" in starvation[0].getMessage()


@pytest.mark.asyncio
async def test_starvation_receptor_silent_when_signals_present(caplog):
    """Innocence: a cycle with signals must NOT emit the starvation line."""
    mock_repo = AsyncMock()
    orch = TrendHunterOrchestrator(
        repo=mock_repo,
        adapters=[_StaticAdapter("static", [_mk_signal("topic A")])],
        force_degraded=False,
    )
    with caplog.at_level(logging.WARNING):
        summary = await orch.run_cycle()

    assert summary.raw_signals == 1
    assert not [r for r in caplog.records if "STARVATION" in r.getMessage()]


# ── Feed env override parsing ───────────────────────────────────────────


def test_feeds_from_env_unset_returns_none(monkeypatch):
    monkeypatch.delenv("TREND_HUNTER_RSS_FEEDS", raising=False)
    assert _feeds_from_env() is None


def test_feeds_from_env_blank_returns_none(monkeypatch):
    monkeypatch.setenv("TREND_HUNTER_RSS_FEEDS", "  ,  ")
    assert _feeds_from_env() is None


def test_feeds_from_env_parses_and_strips(monkeypatch):
    monkeypatch.setenv(
        "TREND_HUNTER_RSS_FEEDS",
        " https://a.example/rss , https://b.example/feed.xml,",
    )
    assert _feeds_from_env() == [
        "https://a.example/rss",
        "https://b.example/feed.xml",
    ]


def test_rss_adapter_uses_env_override(monkeypatch):
    monkeypatch.setenv("TREND_HUNTER_RSS_FEEDS", "https://only.example/rss")
    adapter = RSSAdapter()
    assert adapter.feeds == ["https://only.example/rss"]


def test_rss_adapter_explicit_feeds_beat_env(monkeypatch):
    monkeypatch.setenv("TREND_HUNTER_RSS_FEEDS", "https://env.example/rss")
    adapter = RSSAdapter(feeds=["https://arg.example/rss"])
    assert adapter.feeds == ["https://arg.example/rss"]


# ── RSS adapter loudness ────────────────────────────────────────────────

_RSS_XML_KBLI = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>KBLI 2025 enforcement wave</title>
    <description>Compliance update</description>
    <link>https://example.com/a</link>
  </item>
</channel></rss>
"""


@pytest.mark.asyncio
async def test_rss_adapter_all_feeds_dead_raises_loud_error(caplog):
    """4/4 dead feeds must be an adapter ERROR, not a silent empty list."""
    transport = httpx.MockTransport(lambda request: httpx.Response(404))
    adapter = RSSAdapter(
        feeds=["https://dead-1.example/rss", "https://dead-2.example/rss"],
        transport=transport,
    )
    with caplog.at_level(logging.WARNING):
        result = await adapter.run()

    assert result.error is not None
    assert "dead" in result.error
    dead_warnings = [r for r in caplog.records if "rss feed DEAD" in r.getMessage()]
    assert len(dead_warnings) == 2
    assert any("HTTP 404" in r.getMessage() for r in dead_warnings)


@pytest.mark.asyncio
async def test_rss_adapter_partial_death_still_returns_signals(caplog):
    """Innocence: one live feed among dead ones still yields signals, no raise."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "live" in str(request.url):
            return httpx.Response(200, text=_RSS_XML_KBLI)
        return httpx.Response(404)

    adapter = RSSAdapter(
        feeds=["https://dead.example/rss", "https://live.example/rss"],
        transport=httpx.MockTransport(handler),
    )
    with caplog.at_level(logging.WARNING):
        result = await adapter.run()

    assert result.error is None
    assert len(result.signals) == 1
    assert result.signals[0].source == TrendSource.RSS


# ── Reddit adapter (public .rss, no auth) ───────────────────────────────

_REDDIT_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>KITAS renewal question for Bali</title>
    <summary>Anyone renewed their kitas recently at imigrasi?</summary>
    <link href="https://www.reddit.com/r/bali/comments/xyz/"/>
  </entry>
  <entry>
    <title>Best beach clubs?</title>
    <summary>Looking for recommendations</summary>
    <link href="https://www.reddit.com/r/bali/comments/abc/"/>
  </entry>
</feed>
"""


@pytest.mark.asyncio
async def test_reddit_adapter_fetches_and_triages():
    captured_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.append(request.headers)
        return httpx.Response(200, text=_REDDIT_ATOM)

    adapter = RedditAdapter(
        subreddits=["bali"], transport=httpx.MockTransport(handler)
    )
    result = await adapter.run()

    assert result.error is None
    # Only the KITAS entry survives triage; beach clubs does not.
    assert len(result.signals) == 1
    sig = result.signals[0]
    assert sig.source == TrendSource.REDDIT
    assert "KITAS" in sig.topic
    assert sig.source_url == "https://www.reddit.com/r/bali/comments/xyz/"
    # The descriptive User-Agent is load-bearing (default UA -> 429).
    assert "bali-zero-trend-hunter" in captured_headers[0]["user-agent"]


@pytest.mark.asyncio
async def test_reddit_adapter_all_subs_failed_raises_loud_error(caplog):
    transport = httpx.MockTransport(lambda request: httpx.Response(429))
    adapter = RedditAdapter(subreddits=["bali", "indonesia"], transport=transport)
    with caplog.at_level(logging.WARNING):
        result = await adapter.run()

    assert result.error is not None
    assert "zero" in result.error
    rate_limited = [r for r in caplog.records if "429" in r.getMessage()]
    assert len(rate_limited) == 2


# ── Google Trends adapter (public RSS, no auth) ─────────────────────────

_GTRENDS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Daily Search Trends</title>
  <item>
    <title>coretax djp login</title>
    <description>20,000+ searches</description>
    <link>https://trends.google.com/trending?geo=ID</link>
  </item>
  <item>
    <title>hasil pertandingan bola</title>
    <description>50,000+ searches</description>
    <link>https://trends.google.com/trending?geo=ID</link>
  </item>
</channel></rss>
"""


@pytest.mark.asyncio
async def test_gtrends_adapter_fetches_and_triages():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text=_GTRENDS_RSS)
    )
    adapter = GoogleTrendsAdapter(transport=transport)
    result = await adapter.run()

    assert result.error is None
    # Only the coretax/djp trend survives triage; football does not.
    assert len(result.signals) == 1
    sig = result.signals[0]
    assert sig.source == TrendSource.GTRENDS
    assert "coretax" in sig.topic


@pytest.mark.asyncio
async def test_gtrends_adapter_http_error_is_loud():
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    adapter = GoogleTrendsAdapter(transport=transport)
    result = await adapter.run()

    assert result.error is not None
    assert "503" in result.error
