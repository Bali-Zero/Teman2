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
- RSSAdapter — curated Indonesian compliance/visa/KBLI feeds (httpx + XML parse)
- RedditAdapter — public no-auth .rss endpoints for r/bali + r/indonesia
- GoogleTrendsAdapter — public no-auth Google Trends daily RSS (geo=ID)

Placeholders (Sprint 2+):
- XAIAdapter — Grok search via HTTP (GROK_API_KEY, Law 2 exception)
- PlaywrightScraper — Bali Post, Antara
"""

from __future__ import annotations

import asyncio
import logging
import os
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
    # B9 resurrection 2026-07-14: 3 of the 4 original feeds were dead for weeks
    # (hukumonline.com/berita/rss -> 403 Cloudflare wall; thejakartapost.com/rss
    # and bisnis.com/rss -> 404, both sites dropped RSS entirely — autodiscovery
    # on their homepages finds no feed). Every URL below returned HTTP 200 with
    # real XML on 2026-07-14 and parses through _parse_rss.
    # Override without a deploy via TREND_HUNTER_RSS_FEEDS (comma-separated).
    "https://www.antaranews.com/rss/terkini.xml",  # kept — national wire, ID
    "https://www.antaranews.com/rss/hukum.xml",  # legal desk — replaces hukumonline
    "https://en.antaranews.com/rss/news.xml",  # EN national — replaces thejakartapost
    "https://nasional.kontan.co.id/rss",  # business/policy — replaces bisnis.com
    "https://keuangan.kontan.co.id/rss",  # finance/tax desk (DJP, pajak coverage)
]

_RSS_FEEDS_ENV_VAR = "TREND_HUNTER_RSS_FEEDS"

# Public no-auth Reddit RSS endpoints. Reddit serves Atom XML on any listing
# URL suffixed with `.rss`; a descriptive User-Agent is REQUIRED (the default
# python-httpx UA is rate-limited to 429 almost immediately — verified live
# 2026-07-14: same URL, 200 with UA vs 429 without).
DEFAULT_REDDIT_SUBREDDITS: list[str] = ["bali", "indonesia"]
_REDDIT_USER_AGENT = "bali-zero-trend-hunter/1.0 (contact: zero@balizero.com)"

# Public no-auth Google Trends daily trending-searches RSS for Indonesia.
# Verified live 2026-07-14 (HTTP 200, RSS 2.0). The legacy
# /trends/trendingsearches/daily/rss path is 404 — do not revert to it.
GTRENDS_RSS_URL = "https://trends.google.com/trending/rss?geo=ID"


def _feeds_from_env(env_var: str = _RSS_FEEDS_ENV_VAR) -> list[str] | None:
    """Parse a comma-separated feed-URL override from the environment.

    Returns None when unset/blank so callers fall back to DEFAULT_RSS_FEEDS.
    Entries are stripped; empty entries dropped (trailing commas tolerated).
    """
    raw = os.environ.get(env_var, "")
    feeds = [u.strip() for u in raw.split(",") if u.strip()]
    return feeds or None

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
        except Exception as exc:
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
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        # Precedence: explicit arg > TREND_HUNTER_RSS_FEEDS env > defaults.
        self.feeds = feeds if feeds is not None else (_feeds_from_env() or DEFAULT_RSS_FEEDS)
        self.http_timeout = http_timeout
        self.triage_keywords = triage_keywords or _BALI_ZERO_TRIAGE_KEYWORDS
        self._transport = transport

    async def fetch(self) -> list[NormalizedSignal]:
        results: list[NormalizedSignal] = []
        dead_feeds = 0
        async with httpx.AsyncClient(
            timeout=self.http_timeout, transport=self._transport
        ) as client:
            for feed_url in self.feeds:
                try:
                    resp = await client.get(feed_url)
                    if resp.status_code != 200:
                        # WAS logger.debug — invisible at the INFO cron level,
                        # so 4/4 dead feeds ran silent for weeks (scar #2).
                        logger.warning(
                            "rss feed DEAD: %s returned HTTP %s — replace the URL "
                            "or override via %s",
                            feed_url,
                            resp.status_code,
                            _RSS_FEEDS_ENV_VAR,
                        )
                        dead_feeds += 1
                        continue
                    items = _parse_rss(resp.text)
                except Exception as exc:
                    logger.warning(
                        "rss fetch failed for %s: %s",
                        feed_url,
                        exc,
                    )
                    dead_feeds += 1
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
        if self.feeds and dead_feeds == len(self.feeds):
            # Every configured feed is unreachable — surface as an adapter
            # ERROR (SourceAdapterResult.error via run()) instead of a quiet
            # empty list, so the cron JSON line shows red, not "signals: 0".
            raise RuntimeError(
                f"all {len(self.feeds)} RSS feeds dead/unreachable — "
                "feed list needs replacement"
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
    """r/bali + r/indonesia via Reddit's public no-auth ``.rss`` endpoints.

    B9 resurrection 2026-07-14: this was an inert placeholder returning []
    in 0.0ms every cycle ("signals: 0, duration_ms: 0.0" in the cron JSON —
    it never attempted a request). PRAW/OAuth is NOT needed for read-only
    listing access: ``https://www.reddit.com/r/<sub>/new/.rss`` serves Atom
    XML unauthenticated. A descriptive User-Agent is mandatory (default UA
    gets 429 within a couple of requests — verified live). Failures now
    surface loudly instead of silently contributing zero.
    """

    name = "reddit"

    def __init__(
        self,
        subreddits: list[str] | None = None,
        http_timeout: float = 10.0,
        triage_keywords: set[str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.subreddits = subreddits or DEFAULT_REDDIT_SUBREDDITS
        self.http_timeout = http_timeout
        self.triage_keywords = triage_keywords or _BALI_ZERO_TRIAGE_KEYWORDS
        self._transport = transport

    async def fetch(self) -> list[NormalizedSignal]:
        results: list[NormalizedSignal] = []
        failed = 0
        async with httpx.AsyncClient(
            timeout=self.http_timeout,
            transport=self._transport,
            headers={"User-Agent": _REDDIT_USER_AGENT},
            follow_redirects=True,
        ) as client:
            for sub in self.subreddits:
                url = f"https://www.reddit.com/r/{sub}/new/.rss"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.warning(
                            "reddit r/%s returned HTTP %s%s",
                            sub,
                            resp.status_code,
                            " (rate-limited — check User-Agent)"
                            if resp.status_code == 429
                            else "",
                        )
                        failed += 1
                        continue
                    items = _parse_rss(resp.text)
                except Exception as exc:
                    logger.warning("reddit fetch failed for r/%s: %s", sub, exc)
                    failed += 1
                    continue

                for item in items:
                    title = item.get("title", "")
                    snippet = item.get("description", "")[:500]
                    haystack = f"{title} {snippet}".lower()
                    if not any(kw in haystack for kw in self.triage_keywords):
                        continue
                    results.append(
                        NormalizedSignal(
                            source=TrendSource.REDDIT,
                            topic=title[:200],
                            source_url=item.get("link"),
                            raw_title=title,
                            raw_snippet=snippet,
                            language="en",
                            urgency_hint=_heuristic_urgency(haystack),
                            detected_at=datetime.now(timezone.utc),
                        )
                    )
        if self.subreddits and failed == len(self.subreddits):
            raise RuntimeError(
                f"all {len(self.subreddits)} subreddit feeds failed — "
                "reddit adapter contributing zero"
            )
        return results


class GoogleTrendsAdapter(SourceAdapter):
    """Indonesia daily trending searches via Google Trends public RSS.

    B9 resurrection 2026-07-14: this was an inert placeholder returning []
    in 0.0ms every cycle. pytrends is NOT needed:
    ``https://trends.google.com/trending/rss?geo=ID`` serves RSS 2.0
    unauthenticated (verified live; the legacy
    /trends/trendingsearches/daily/rss path is 404). Trending search terms
    are triaged with the same Bali Zero keyword list; failures surface
    loudly instead of silently contributing zero.
    """

    name = "gtrends"

    def __init__(
        self,
        rss_url: str = GTRENDS_RSS_URL,
        http_timeout: float = 10.0,
        triage_keywords: set[str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.rss_url = rss_url
        self.http_timeout = http_timeout
        self.triage_keywords = triage_keywords or _BALI_ZERO_TRIAGE_KEYWORDS
        self._transport = transport

    async def fetch(self) -> list[NormalizedSignal]:
        async with httpx.AsyncClient(
            timeout=self.http_timeout,
            transport=self._transport,
            follow_redirects=True,
        ) as client:
            resp = await client.get(self.rss_url)
            if resp.status_code != 200:
                # Raise -> SourceAdapterResult.error via run(): loud, not a
                # quiet "signals: 0".
                raise RuntimeError(
                    f"gtrends RSS returned HTTP {resp.status_code} ({self.rss_url})"
                )
            items = _parse_rss(resp.text)

        results: list[NormalizedSignal] = []
        for item in items:
            title = item.get("title", "")
            snippet = item.get("description", "")[:500]
            haystack = f"{title} {snippet}".lower()
            if not any(kw in haystack for kw in self.triage_keywords):
                continue
            results.append(
                NormalizedSignal(
                    source=TrendSource.GTRENDS,
                    topic=title[:200],
                    source_url=item.get("link") or self.rss_url,
                    raw_title=title,
                    raw_snippet=snippet,
                    language="id",
                    urgency_hint=_heuristic_urgency(haystack),
                    detected_at=datetime.now(timezone.utc),
                )
            )
        return results


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
    except Exception:
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
        # NOTE: `entry.find(...) or {}` is a trap — a childless Element
        # (e.g. <link href="..."/>) is FALSY in ElementTree, so the href was
        # silently dropped for every Atom entry. Explicit None check required.
        link_el = entry.find("a:link", ns)
        items.append(
            {
                "title": (entry.findtext("a:title", namespaces=ns) or "").strip(),
                "description": (
                    entry.findtext("a:summary", namespaces=ns)
                    or entry.findtext("a:content", namespaces=ns)
                    or ""
                ).strip(),
                "link": link_el.get("href", "") if link_el is not None else "",
                "language": None,
            }
        )
    return items


def _heuristic_urgency(haystack: str) -> float:
    """Cheap pre-scoring based on urgency markers — refined later by Gemini CLI."""
    score = 40.0
    urgent_markers = (
        "breaking",
        "urgent",
        "deadline",
        "effective",
        "enforcement",
        "sanction",
        "deportation",
        "audit",
        "segera",
        "batas waktu",
        "sanksi",
        "mendesak",
    )
    for marker in urgent_markers:
        if marker in haystack:
            score += 10.0
    return min(score, 100.0)


async def gather_sources(
    adapters: list[SourceAdapter],
) -> list[SourceAdapterResult]:
    """Run all adapters concurrently; return per-adapter results.

    Adapter failures isolated (Law 4 Graceful degradation): each ``adapter.run()``
    catches its own exceptions and returns a ``SourceAdapterResult`` with ``error``,
    so TaskGroup never sees a raised exception here.
    """
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(a.run()) for a in adapters]
    return [t.result() for t in tasks]
