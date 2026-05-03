#!/usr/bin/env python3
"""
Exa Search Scraper - Semantic search for intel pipeline
Uses Exa API to find high-relevance articles via semantic queries.

Compatible with UnifiedScraper output schema for seamless pipeline integration.

Usage:
    from exa_scraper import ExaScraper
    exa = ExaScraper()
    articles = exa.search_all()
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "exa_queries.json"


def _extract_domain(url: str) -> str:
    """Extract clean domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        return domain or "unknown"
    except Exception:
        return "unknown"


class ExaScraper:
    """Exa semantic search client for the intel pipeline."""

    def __init__(self, categories: Optional[List[str]] = None):
        self.api_key = os.environ.get("EXA_API_KEY", "")
        if not self.api_key:
            raise ValueError("EXA_API_KEY environment variable not set")

        self.config = self._load_config()
        self.queries = [q for q in self.config["queries"] if "name" in q]

        # Filter by categories if specified
        if categories:
            self.queries = [
                q for q in self.queries if q["category"] in categories
            ]

        self.stats: Dict[str, int] = {
            "queries_run": 0,
            "articles_found": 0,
            "errors": 0,
        }

    def _load_config(self) -> Dict:
        """Load query configuration from exa_queries.json."""
        with open(CONFIG_FILE) as f:
            return json.load(f)

    def log(self, message: str, level: str = "INFO") -> None:
        """Log with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [Exa] [{level}] {message}")
        sys.stdout.flush()

    def search_all(self) -> List[Dict]:
        """Run all configured queries and return deduplicated articles.

        Best practices applied (per Exa docs, March 2026):
        - Semantic description-style queries, not keyword stuffing
        - Per-query highlights.query for targeted snippet extraction
        - highlights_per_url to control snippet density
        - exclude_domains for noise filtering (social, booking, video)
        - include_text per-query for hard content filters (max 5 words)
        - user_location "ID" for Indonesia-relevant ranking
        - livecrawl "fallback" for fresh content when cache misses
        - moderation true for content safety
        - Per-query exa_category override (news/tweet/research paper/personal site)
        - Per-query num_results override for budget control
        - Budget: 12 queries × ~8 avg = ~96 results/run, 360 searches/mo (free tier: 1000)
        """
        from exa_py import Exa

        client = Exa(api_key=self.api_key)

        # Global config
        max_age_hours = self.config.get("max_age_hours", 72)
        default_num_results = self.config.get("default_num_results", 10)
        search_type = self.config.get("search_type", "auto")
        user_location = self.config.get("user_location")
        livecrawl = self.config.get("livecrawl")
        moderation = self.config.get("moderation", False)
        exclude_domains = self.config.get("exclude_domains", [])
        hl_config = self.config.get("highlights", {})
        hl_num_sentences = hl_config.get("num_sentences", 3)
        hl_per_url = hl_config.get("highlights_per_url", 2)

        start_date = (
            datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        all_articles: List[Dict] = []
        seen_urls: set[str] = set()

        self.log(f"Running {len(self.queries)} queries (type={search_type}, max_age={max_age_hours}h, loc={user_location})")

        for query_config in self.queries:
            try:
                qname = query_config["name"]
                num_results = query_config.get("num_results", default_num_results)
                exa_category = query_config.get("exa_category", "news")

                self.log(f"  Searching: {qname} (cat={exa_category}, n={num_results})")

                # Build highlights params with optional per-query focus
                highlights_params: Dict = {
                    "num_sentences": hl_num_sentences,
                    "highlights_per_url": hl_per_url,
                }
                if query_config.get("highlights_query"):
                    highlights_params["query"] = query_config["highlights_query"]

                # Build search kwargs
                search_kwargs: Dict = {
                    "category": exa_category,
                    "type": search_type,
                    "num_results": num_results,
                    "start_published_date": start_date,
                    "highlights": highlights_params,
                }

                # exclude_domains not supported on specialized indices (research paper, personal site)
                # NOTE: "tweet" category was deprecated by Exa in 2026-03 — do NOT use it
                specialized_categories = {"research paper", "personal site", "people", "company"}
                if exclude_domains and exa_category not in specialized_categories:
                    search_kwargs["exclude_domains"] = exclude_domains
                if user_location:
                    search_kwargs["user_location"] = user_location
                # livecrawl/moderation not supported on specialized indices
                if livecrawl and exa_category not in specialized_categories:
                    search_kwargs["livecrawl"] = livecrawl
                if moderation and exa_category not in specialized_categories:
                    search_kwargs["moderation"] = moderation

                # Text filters not supported on specialized indices
                if exa_category not in specialized_categories:
                    if query_config.get("include_text"):
                        search_kwargs["include_text"] = query_config["include_text"]
                    if query_config.get("exclude_text"):
                        search_kwargs["exclude_text"] = query_config["exclude_text"]

                response = client.search_and_contents(
                    query=query_config["query"],
                    **search_kwargs,
                )
                self.stats["queries_run"] += 1

                count_new = 0
                for result in response.results:
                    url = result.url
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    count_new += 1

                    title = result.title or ""
                    article_id = hashlib.md5(
                        (url + title).encode()
                    ).hexdigest()[:16]

                    highlights = getattr(result, "highlights", None) or []
                    summary = " ".join(highlights) if highlights else ""
                    text = (result.text[:2000] if result.text else "")

                    score = getattr(result, "score", None)
                    quality_score = max(50, int(score * 100)) if score else 60

                    article = {
                        "id": article_id,
                        "title": title,
                        "url": url,
                        "summary": summary,
                        "text": text,
                        "published": getattr(result, "published_date", "") or "",
                        "source_name": f"Exa: {_extract_domain(url)}",
                        "source_url": url,
                        "category": query_config["category"],
                        "tier": query_config["tier"],
                        "exa_query": qname,
                        "exa_category": exa_category,
                        "scraped_at": datetime.now().isoformat(),
                        "quality_score": quality_score,
                    }
                    all_articles.append(article)

                self.log(f"    {len(response.results)} results, {count_new} new")

            except Exception as e:
                self.stats["errors"] += 1
                self.log(f"    Error on '{query_config['name']}': {e}", "ERROR")

        self.stats["articles_found"] = len(all_articles)
        self.log(
            f"Total: {len(all_articles)} unique articles from {self.stats['queries_run']} queries "
            f"({self.stats['errors']} errors)"
        )
        return all_articles


if __name__ == "__main__":
    exa = ExaScraper()
    articles = exa.search_all()
    print(f"\nFound {len(articles)} articles:")
    for a in articles[:5]:
        print(f"  [{a['quality_score']}] {a['title'][:70]}")
        print(f"       {a['url']}")
