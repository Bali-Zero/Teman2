"""T4 Social Media Monitor for NLM NB-2.

Fetches immigration-relevant content from:
  - RSS feeds (ngurahrai, ditjenimigrasi)
  - Government websites (/berita/ pages)
  - X/Twitter v2 API (time-boxed 30 days)

Applies a 3-layer relevance filter, computes SVS, and ingests
ADMIT articles into NLM NB-2 via the nlm CLI.
"""

from __future__ import annotations

import hashlib
import httpx
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    from apps.evaluator.nlm_deep_research.t4_state import T4State


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NB2_ID = "cff93ab0-813a-42f2-a8de-36987e724271"
MAX_T4_SLOTS = 11
CB_T4_FAILURE_THRESHOLD = 3
CB_T4_RECOVERY_MINUTES = 30

CRITICAL_KEYWORDS = [
    "timpora",
    "deportasi",
    "deportation",
    "overstay",
    "blacklist",
    "daftar cekal",
    "visa dicabut",
    "wna ditangkap",
    "razia",
    "pendeportasian",
    "izin tinggal dibatalkan",
    "cegah tangkal",
]

HIGH_KEYWORDS = [
    "kitas",
    "kitap",
    "visa",
    "izin tinggal",
    "paspor",
    "imigrasi",
    "wna",
    "warga negara asing",
    "tenaga kerja asing",
    "tka",
    "peraturan imigrasi",
    "kebijakan visa",
    "perpanjangan visa",
]

REFERENCE_QUERY = (
    "Indonesian immigration enforcement TIMPORA deportation overstay "
    "WNA foreign nationals visa regulation Bali"
)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_SIMILARITY_THRESHOLD = 0.35
EMBEDDING_BORDERLINE_LOW = 0.30
EMBEDDING_BORDERLINE_HIGH = 0.40


# ---------------------------------------------------------------------------
# Enums / dataclasses
# ---------------------------------------------------------------------------


class FilterResult(str, Enum):
    ADMIT = "ADMIT"
    REJECT = "REJECT"


@dataclass
class Article:
    """Normalized article from any T4 source."""

    source_handle: str
    article_id: str               # URL hash — PRIMARY dedup key
    url: str
    title: str
    content: str
    scraped_at: datetime
    platform: Literal["rss", "website", "twitter", "instagram"]
    published_at: Optional[datetime] = None  # UNRELIABLE — prefer scraped_at
    svs_score: float = 0.0
    filter_result: str = "PENDING"


@dataclass
class Post:
    """Normalized social media post (Twitter / Instagram)."""

    handle: str
    post_id: str                  # tweet_id or shortcode — PRIMARY dedup key
    url: str
    content: str
    scraped_at: datetime
    platform: Literal["twitter", "instagram"]
    timestamp: Optional[datetime] = None


# Authority scores per source handle
SOURCE_AUTHORITY: dict[str, float] = {
    "ngurahrai.imigrasi.go.id": 1.0,
    "ditjenimigrasi.go.id": 1.0,
    "imigrasi.go.id": 0.95,
    "kanwilbali.kemenkumham.go.id": 0.90,
    "kemenkumham.go.id": 0.85,
    "ditjen_imigrasi": 0.90,
    "imngurahrai": 0.95,
    "kemenkumbali": 0.85,
}

PLATFORM_BOOST: dict[str, float] = {
    "rss": 0.10,
    "website": 0.05,
    "twitter": 0.08,
    "instagram": 0.03,
}


class T4SVSScorer:
    """Compute SVS for T4 articles.

    Weights:
        authority  0.30
        freshness  0.25
        uniqueness 0.20   (keyword density proxy)
        density    0.15   (CRITICAL keyword count)
        platform   0.10   (platform boost)
    """

    W_AUTHORITY = 0.30
    W_FRESHNESS = 0.25
    W_UNIQUENESS = 0.20
    W_DENSITY = 0.15
    W_PLATFORM = 0.10

    def score(self, article: Article) -> float:
        authority = self._authority(article)
        freshness = self._freshness(article)
        uniqueness = self._uniqueness(article)
        density = self._density(article)
        platform = PLATFORM_BOOST.get(article.platform, 0.0)

        # Keyword relevance gate: attenuate authority and freshness when there
        # is no meaningful enforcement signal.  Mirrors the Layer-1 rule:
        # CRITICAL ≥ 1  OR  HIGH ≥ 2.  Without that signal, high-authority
        # sources must not inflate scores for irrelevant content.
        text = (article.title + " " + article.content).lower()
        critical_hits = sum(1 for kw in CRITICAL_KEYWORDS if kw in text)
        high_hits = sum(1 for kw in HIGH_KEYWORDS if kw in text)
        has_signal = critical_hits >= 1 or high_hits >= 2
        if not has_signal:
            authority *= 0.20
            freshness *= 0.20

        raw = (
            self.W_AUTHORITY * authority
            + self.W_FRESHNESS * freshness
            + self.W_UNIQUENESS * uniqueness
            + self.W_DENSITY * density
            + self.W_PLATFORM * platform
        )
        return max(0.0, min(1.0, raw))

    def _authority(self, article: Article) -> float:
        from urllib.parse import urlparse  # noqa: PLC0415

        try:
            host = urlparse(article.url).hostname or ""
        except Exception:
            host = ""
        return SOURCE_AUTHORITY.get(host, SOURCE_AUTHORITY.get(article.source_handle, 0.60))

    def _freshness(self, article: Article) -> float:
        """Exponential decay: half-life = NEWS_HALF_LIFE_DAYS (15 days)."""
        from apps.evaluator.nlm_deep_research.t4_state import NEWS_HALF_LIFE_DAYS  # noqa: PLC0415

        delta_days = (
            datetime.now(timezone.utc) - article.scraped_at
        ).total_seconds() / 86400
        return math.exp(-math.log(2) * delta_days / NEWS_HALF_LIFE_DAYS)

    def _uniqueness(self, article: Article) -> float:
        """Keyword density as uniqueness proxy (normalized)."""
        text = (article.title + " " + article.content).lower()
        all_keywords = CRITICAL_KEYWORDS + HIGH_KEYWORDS
        hits = sum(1 for kw in all_keywords if kw in text)
        return min(1.0, hits / 5.0)

    def _density(self, article: Article) -> float:
        """CRITICAL keyword density."""
        text = (article.title + " " + article.content).lower()
        hits = sum(1 for kw in CRITICAL_KEYWORDS if kw in text)
        return min(1.0, hits / 3.0)


# ---------------------------------------------------------------------------
# T4RelevanceFilter
# ---------------------------------------------------------------------------


class T4RelevanceFilter:
    """3-layer relevance filter for T4 immigration content.

    Layer 1 — keyword recall (~0ms, fast gate)
    Layer 2 — embedding cosine similarity (~50ms, precision gate)
    Layer 3 — Haiku LLM classifier (~500ms, borderline only)
    """

    def __init__(self) -> None:
        self._openai_client: Optional[object] = None
        self._anthropic_client: Optional[object] = None

    def _get_openai_client(self) -> object:
        if self._openai_client is None:
            import openai  # noqa: PLC0415

            self._openai_client = openai.AsyncOpenAI()
        return self._openai_client

    def _get_anthropic_client(self) -> object:
        if self._anthropic_client is None:
            import anthropic  # noqa: PLC0415

            self._anthropic_client = anthropic.AsyncAnthropic()
        return self._anthropic_client

    def layer1_keywords(self, text: str) -> bool:
        """Return True if text passes keyword recall gate."""
        lower = text.lower()
        critical_hits = sum(1 for kw in CRITICAL_KEYWORDS if kw in lower)
        if critical_hits >= 1:
            return True
        high_hits = sum(1 for kw in HIGH_KEYWORDS if kw in lower)
        return high_hits >= 2

    async def _embed(self, text: str) -> list[float]:
        """Embed text using OpenAI text-embedding-3-small."""
        client = self._get_openai_client()
        resp = await client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        return resp.data[0].embedding

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def layer2_embedding(
        self, text: str, *, cached_ref: Optional[list[float]] = None
    ) -> float:
        """Return cosine similarity between text and reference query."""
        ref = cached_ref or await self._embed(REFERENCE_QUERY)
        text_vec = await self._embed(text)
        return self._cosine(text_vec, ref)

    async def _haiku_classify(self, text: str) -> float:
        """Call Haiku to score immigration relevance (0.0–1.0)."""
        client = self._get_anthropic_client()
        prompt = (
            "You are an immigration advisor for Bali, Indonesia. "
            "Score the following article's relevance to immigration enforcement "
            "(deportation, overstay, visa cancellation, arrests of foreign nationals). "
            "Respond with ONLY a decimal between 0.0 and 1.0. "
            "1.0 = highly relevant enforcement news. 0.0 = irrelevant.\n\n"
            f"Article: {text[:1500]}"
        )
        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        try:
            return float(raw)
        except ValueError:
            logger.warning("Haiku returned non-float: %r — defaulting to 0.0", raw)
            return 0.0

    async def layer3_haiku(self, text: str) -> float:
        """Return Haiku relevance score for text."""
        return await self._haiku_classify(text)

    async def classify(
        self,
        text: str,
        *,
        ref_embedding: Optional[list[float]] = None,
    ) -> FilterResult:
        """Run full 3-layer pipeline. Returns ADMIT or REJECT."""
        if not self.layer1_keywords(text):
            return FilterResult.REJECT

        similarity = await self.layer2_embedding(text, cached_ref=ref_embedding)

        if similarity >= EMBEDDING_SIMILARITY_THRESHOLD:
            return FilterResult.ADMIT

        if EMBEDDING_BORDERLINE_LOW <= similarity < EMBEDDING_BORDERLINE_HIGH:
            score = await self.layer3_haiku(text)
            return FilterResult.ADMIT if score >= 0.5 else FilterResult.REJECT

        return FilterResult.REJECT


# ---------------------------------------------------------------------------
# Circuit Breaker CB_T4 (standalone — does NOT cascade to CB_NLM)
# ---------------------------------------------------------------------------


class T4CircuitBreaker:
    """Standalone circuit breaker for T4 monitor.

    Thresholds:
        failure_threshold = 3 consecutive failures → OPEN
        recovery_timeout  = 30 minutes → HALF_OPEN probe
        DOMChangedError   → immediate OPEN

    Does NOT cascade to CB_NLM or CB_SOURCE (independent failure domain).
    """

    def is_open(self, state: "T4State") -> bool:
        """Return True if CB is currently OPEN (blocking requests)."""
        if state.cb_status == "OPEN":
            self.maybe_transition(state)
            return state.cb_status == "OPEN"
        return False

    def maybe_transition(self, state: "T4State") -> None:
        """Transition OPEN → HALF_OPEN if recovery timeout has elapsed."""
        if state.cb_status != "OPEN":
            return
        if state.cb_last_failure is None:
            state.cb_status = "HALF_OPEN"
            return
        elapsed = (
            datetime.now(timezone.utc) - state.cb_last_failure
        ).total_seconds() / 60
        if elapsed >= CB_T4_RECOVERY_MINUTES:
            state.cb_status = "HALF_OPEN"
            logger.info("CB_T4 → HALF_OPEN after %.0f min", elapsed)

    def record_failure(self, state: "T4State") -> None:
        """Increment failure counter; open CB after threshold."""
        state.cb_failure_count += 1
        state.cb_last_failure = datetime.now(timezone.utc)
        if state.cb_status == "HALF_OPEN":
            state.cb_status = "OPEN"
            logger.warning("CB_T4 HALF_OPEN probe failed → back to OPEN")
        elif state.cb_failure_count >= CB_T4_FAILURE_THRESHOLD:
            state.cb_status = "OPEN"
            logger.warning(
                "CB_T4 OPEN after %d failures", state.cb_failure_count
            )

    def record_success(self, state: "T4State") -> None:
        """Reset failure counter and close CB."""
        state.cb_failure_count = 0
        state.cb_status = "CLOSED"

    def open_immediately(self, state: "T4State", reason: str = "") -> None:
        """Force CB OPEN (e.g., DOMChangedError)."""
        state.cb_status = "OPEN"
        state.cb_failure_count = CB_T4_FAILURE_THRESHOLD
        state.cb_last_failure = datetime.now(timezone.utc)
        logger.error("CB_T4 forced OPEN: %s", reason)


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------


class T4Fetcher:
    """Fetch articles from RSS feeds, government websites, and X/Twitter."""

    async def fetch_rss(
        self, url: str, *, source_handle: str
    ) -> list[Article]:
        """Fetch and parse an RSS feed. Returns [] on any error."""
        import feedparser  # noqa: PLC0415

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)
        except Exception:
            logger.exception("RSS fetch failed for %s", url)
            return []

        articles: list[Article] = []
        for entry in feed.entries:
            link = getattr(entry, "link", "") or ""
            if not link:
                continue
            article_id = hashlib.sha1(link.encode()).hexdigest()[:16]
            title = getattr(entry, "title", link)
            summary = getattr(entry, "summary", "")
            content_detail = getattr(entry, "content", [])
            body = content_detail[0].value if content_detail else summary

            published_at: Optional[datetime] = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                from time import mktime  # noqa: PLC0415

                try:
                    published_at = datetime.fromtimestamp(
                        mktime(entry.published_parsed), tz=timezone.utc
                    )
                except Exception:
                    pass

            articles.append(
                Article(
                    source_handle=source_handle,
                    article_id=article_id,
                    url=link,
                    title=title,
                    content=f"{title}. {body}",
                    scraped_at=datetime.now(timezone.utc),
                    platform="rss",
                    published_at=published_at,
                )
            )
        return articles

    async def fetch_website(
        self,
        url: str,
        *,
        source_handle: str,
        article_selector: str = "article",
        title_selector: str = "h2",
        link_selector: str = "a",
    ) -> list[Article]:
        """Scrape a /berita/ listing page. Returns [] on any error."""
        from bs4 import BeautifulSoup  # noqa: PLC0415

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
        except Exception:
            logger.exception("Website fetch failed for %s", url)
            return []

        articles: list[Article] = []
        for block in soup.select(article_selector)[:20]:
            title_el = block.select_one(title_selector)
            link_el = block.select_one(link_selector)
            if not title_el or not link_el:
                continue
            title = title_el.get_text(strip=True)
            link = link_el.get("href", "")
            if not link:
                continue
            if not link.startswith("http"):
                from urllib.parse import urljoin  # noqa: PLC0415

                link = urljoin(url, link)
            article_id = hashlib.sha1(link.encode()).hexdigest()[:16]
            text = block.get_text(separator=" ", strip=True)

            articles.append(
                Article(
                    source_handle=source_handle,
                    article_id=article_id,
                    url=link,
                    title=title,
                    content=text[:2000],
                    scraped_at=datetime.now(timezone.utc),
                    platform="website",
                )
            )
        return articles

    async def fetch_twitter(
        self,
        handle: str,
        *,
        bearer_token: str,
        max_results: int = 20,
    ) -> list[Post]:
        """Fetch recent tweets via Twitter API v2. Returns [] on any error."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                user_resp = await client.get(
                    f"https://api.twitter.com/2/users/by/username/{handle.lstrip('@')}",
                    headers={"Authorization": f"Bearer {bearer_token}"},
                )
                user_resp.raise_for_status()
                user_id = user_resp.json()["data"]["id"]

                tweet_resp = await client.get(
                    f"https://api.twitter.com/2/users/{user_id}/tweets",
                    headers={"Authorization": f"Bearer {bearer_token}"},
                    params={
                        "max_results": max_results,
                        "tweet.fields": "created_at,text",
                    },
                )
                tweet_resp.raise_for_status()
                tweets = tweet_resp.json().get("data", [])
        except Exception:
            logger.exception("Twitter fetch failed for @%s", handle)
            return []

        posts: list[Post] = []
        for tweet in tweets:
            tweet_id = tweet["id"]
            url = f"https://twitter.com/{handle.lstrip('@')}/status/{tweet_id}"
            created = None
            if tweet.get("created_at"):
                try:
                    created = datetime.fromisoformat(
                        tweet["created_at"].replace("Z", "+00:00")
                    )
                except ValueError:
                    pass
            posts.append(
                Post(
                    handle=handle,
                    post_id=tweet_id,
                    url=url,
                    content=tweet.get("text", ""),
                    scraped_at=datetime.now(timezone.utc),
                    platform="twitter",
                    timestamp=created,
                )
            )
        return posts
