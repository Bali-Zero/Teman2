"""Source adapters for Trend-Hunter.

Each adapter:
- has a single responsibility (one source)
- is async
- returns SourceAdapterResult (never raises to orchestrator)
- respects Law 1 (CLI-only LLM) — adapters only do retrieval/normalization,
  not reasoning. Scoring happens in the orchestrator via Gemini CLI.
- respects Law 2 (OSINT blindato) — adapters producing OSINT data must
  run on Pro only; orchestrator checks host at startup.

Currently implemented:
- RSSAdapter — feedparser on curated Indonesian compliance/visa/KBLI feeds

Placeholders (Sprint 2+):
- XAIAdapter — Grok search via HTTP (GROK_API_KEY, Law 2 exception)
- RedditAdapter — PRAW r/bali, r/indonesia
- GoogleTrendsAdapter — pytrends
- PlaywrightScraper — Bali Post, Antara
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.services.intel.dossier_models import TrendSource
from backend.services.intel.trend_hunter.types import (
    NormalizedSignal,
    SourceAdapterResult,
)

logger = logging.getLogger(__name__)


DEFAULT_RSS_FEEDS: list[str] = [
    # Legal / compliance / visa aggregators covering Indonesia regulatory moves.
    # Curated list — extend via config if needed. DA VERIFICARE accessibility each.
    "https://www.hukumonline.com/berita/rss",
    "https://www.thejakartapost.com/rss",
    "https://www.bisnis.com/rss",
    "https://www.antaranews.com/rss/terkini.xml",
]

# Keywords used to triage RSS items before spending Gemini CLI tokens on scoring.
_BALI_ZERO_TRIAGE_KEYWORDS = {
    "kbli",
    "kitas",
    "b211a",
    "b211",
    "visa",
    "imigrasi",
    "pph",
    "ppn",
    "djp",
    "coretax",
    "oss",
    "nib",
    "lkpm",
    "pma",
    "permenkumham",
    "bank indonesia",
    "ojk",
    "hak pakai",
    "bpjs",
    "npwp",
}


class SourceAdapter(ABC):
    name: str

    @abstractmethod
    async def fetch(self) -> list[NormalizedSignal]:
        """Return normalized signals (may be empty). Must not raise."""
        ...

    async def run(self) -> SourceAdapterResult:
        start = time.perf_counter()
        try:
            signals = await self.fetch()
            return SourceAdapterResult(
                adapter_name=self.name,
                signals=signals,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as exc:  # noqa: BLE001 — adapters must be safe
            logger.warning("adapter %s failed: %s", self.name, exc, exc_info=True)
            return SourceAdapterResult(
                adapter_name=self.name,
                duration_ms=(time.perf_counter() - start) * 1000,
                error=str(exc),
            )


class RSSAdapter(SourceAdapter):
    """Parse curated RSS feeds; triage by Bali Zero keyword list.

    Uses feedparser if available; falls back to httpx + minimal XML parse.
    """

    name = "rss"

    def __init__(
        self,
        feeds: list[str] | None = None,
        http_timeout: float = 8.0,
        triage_keywords: set[str] | None = None,
    ) -> None:
        self.feeds = feeds or DEFAULT_RSS_FEEDS
        self.http_timeout = http_timeout
        self.triage_keywords = triage_keywords or _BALI_ZERO_TRIAGE_KEYWORDS

    async def fetch(self) -> list[NormalizedSignal]:
        results: list[NormalizedSignal] = []
        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            for feed_url in self.feeds:
                try:
                    resp = await client.get(feed_url)
                    if resp.status_code != 200:
                        logger.debug(
                            "rss %s returned %s", feed_url, resp.status_code,
                        )
                        continue
                    items = _parse_rss(resp.text)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "rss fetch failed for %s: %s", feed_url, exc,
                    )
                    continue

                for item in items:
                    title = item.get("title", "")
                    snippet = item.get("description", "")[:500]
                    haystack = f"{title} {snippet}".lower()
                    if not any(kw in haystack for kw in self.triage_keywords):
                        continue
                    results.append(
                        NormalizedSignal(
                            source=TrendSource.RSS,
                            topic=title[:200],
                            source_url=item.get("link"),
                            raw_title=title,
                            raw_snippet=snippet,
                            language=item.get("language") or "id",
                            urgency_hint=_heuristic_urgency(haystack),
                            detected_at=datetime.now(timezone.utc),
                        )
                    )
        return results


class XAIAdapter(SourceAdapter):
    """Grok search (HTTP, Law 2 OSINT exception).

    Uses xAI's /v1/live-search endpoint to query Indonesia visa/KBLI/tax
    signals in last 24h. Requires GROK_API_KEY env var.
    """

    name = "xai"

    def __init__(
        self,
        api_key: str,
        queries: list[str] | None = None,
        http_timeout: float = 15.0,
    ) -> None:
        self.api_key = api_key
        self.queries = queries or [
            "Indonesia KBLI 2025 compliance latest",
            "Bali visa enforcement news this week",
            "PT PMA Indonesia regulatory update",
            "Coretax DJP notification Indonesia",
        ]
        self.http_timeout = http_timeout

    async def fetch(self) -> list[NormalizedSignal]:
        # Skeleton — actual xAI endpoint integration deferred until we verify
        # the current /v1/live-search or /v1/messages contract with Grok-4.
        # Returns empty gracefully so the orchestrator keeps running.
        logger.info(
            "xai adapter skeleton — not yet wired; skipping %d queries",
            len(self.queries),
        )
        return []


class RedditAdapter(SourceAdapter):
    """Placeholder — Sprint 2 follow-up (needs PRAW credentials)."""

    name = "reddit"

    async def fetch(self) -> list[NormalizedSignal]:
        logger.debug("reddit adapter placeholder")
        return []


class GoogleTrendsAdapter(SourceAdapter):
    """Placeholder — Sprint 2 follow-up (needs pytrends install)."""

    name = "gtrends"

    async def fetch(self) -> list[NormalizedSignal]:
        logger.debug("gtrends adapter placeholder")
        return []


# ── Helpers ─────────────────────────────────────────────────────────────


def _parse_rss(xml_text: str) -> list[dict[str, Any]]:
    """Minimal RSS/Atom parser. Prefers feedparser if installed."""
    try:
        import feedparser  # type: ignore[import-untyped]

        parsed = feedparser.parse(xml_text)
        return [
            {
                "title": entry.get("title", ""),
                "description": entry.get("summary", entry.get("description", "")),
                "link": entry.get("link", ""),
                "language": parsed.feed.get("language") if hasattr(parsed, "feed") else None,
            }
            for entry in parsed.entries
        ]
    except ImportError:
        return _parse_rss_fallback(xml_text)


def _parse_rss_fallback(xml_text: str) -> list[dict[str, Any]]:
    """Fallback parser using defusedxml — extracts <item> title/description/link."""
    try:
        from defusedxml import ElementTree as ET  # type: ignore[import-untyped]
    except ImportError:
        import xml.etree.ElementTree as ET  # type: ignore[import-not-found]  # nosec B405

    try:
        root = ET.fromstring(xml_text)
    except Exception:  # noqa: BLE001
        return []

    items: list[dict[str, Any]] = []
    # RSS 2.0
    for item in root.iter("item"):
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "description": (item.findtext("description") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "language": None,
            }
        )
    if items:
        return items

    # Atom fallback
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry in root.findall("a:entry", ns):
        items.append(
            {
                "title": (entry.findtext("a:title", namespaces=ns) or "").strip(),
                "description": (
                    entry.findtext("a:summary", namespaces=ns)
                    or entry.findtext("a:content", namespaces=ns)
                    or ""
                ).strip(),
                "link": (entry.find("a:link", ns) or {}).get("href", ""),  # type: ignore[union-attr]
                "language": None,
            }
        )
    return items


def _heuristic_urgency(haystack: str) -> float:
    """Cheap pre-scoring based on urgency markers — refined later by Gemini CLI."""
    score = 40.0
    urgent_markers = (
        "breaking", "urgent", "deadline", "effective",
        "enforcement", "sanction", "deportation", "audit",
        "segera", "batas waktu", "sanksi", "mendesak",
    )
    for marker in urgent_markers:
        if marker in haystack:
            score += 10.0
    return min(score, 100.0)


async def gather_sources(
    adapters: list[SourceAdapter],
) -> list[SourceAdapterResult]:
    """Run all adapters concurrently; return per-adapter results.

    Adapter failures isolated (Law 4 Graceful degradation).
    """
    return await asyncio.gather(*[a.run() for a in adapters])
