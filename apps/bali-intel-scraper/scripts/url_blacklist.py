"""URL blacklist for static/guide-style pages that pollute the intel feed.

Added 2026-04-09 after RCA of "same 4 articles every night" bug.
Root cause: static guide pages like expat.com/en/guide/* get rescraped every
night, always score high, and dominate the enriched top-N. They are not news.

This module is imported by unified_scraper and exa_scraper. Keep patterns
conservative — only block pages that are demonstrably non-news indexes/guides.
"""
from __future__ import annotations

import re
from typing import Iterable

# Exact regex patterns matched against the full URL (case-insensitive).
# Keep this list small and well-justified. Every entry should have a comment
# explaining WHY it's blocked.
_BLACKLIST_PATTERNS = [
    # expat.com static country guides (e.g. expat.com/en/guide/asia/indonesia/...)
    # These are evergreen handbooks, not news. Seen repeating every run.
    re.compile(r"^https?://(?:www\.)?expat\.com/[a-z]{2}/guide/", re.IGNORECASE),
    # expat.com destination landing pages — same problem
    re.compile(r"^https?://(?:www\.)?expat\.com/[a-z]{2}/destination/", re.IGNORECASE),
    # indonesiaexpat.id category/tag index pages (not articles)
    re.compile(r"^https?://(?:www\.)?indonesiaexpat\.id/category/", re.IGNORECASE),
    re.compile(r"^https?://(?:www\.)?indonesiaexpat\.id/tag/", re.IGNORECASE),
    # Reddit subreddit homepages (not individual posts)
    re.compile(r"^https?://(?:www\.)?reddit\.com/r/[^/]+/?$", re.IGNORECASE),
    # nomadlist score/cost-of-living pages — evergreen
    re.compile(r"^https?://(?:www\.)?nomadlist\.com/scores/", re.IGNORECASE),
    # InterNations country landing (same problem as expat.com destination)
    re.compile(r"^https?://(?:www\.)?internations\.org/[^/]+-expats/?$", re.IGNORECASE),
    # Long-stay visa aggregator directory pages
    re.compile(r"^https?://(?:www\.)?asialongstay\.com/(?:long-stay-guide|guides)/", re.IGNORECASE),
]


def is_blacklisted(url: str) -> bool:
    """Return True if URL matches any blacklist pattern."""
    if not url:
        return False
    return any(p.search(url) for p in _BLACKLIST_PATTERNS)


def filter_articles(articles: Iterable[dict]) -> tuple[list[dict], int]:
    """Drop blacklisted articles. Returns (kept, dropped_count)."""
    kept: list[dict] = []
    dropped = 0
    for art in articles:
        url = art.get("url") or art.get("source_url") or ""
        if is_blacklisted(url):
            dropped += 1
            continue
        kept.append(art)
    return kept, dropped
