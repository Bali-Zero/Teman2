#!/usr/bin/env python3
"""
FASE 1 — Exa AI Researcher
API-based search: news Indonesia, legal/gov sources, deep research.
Runs standalone or in parallel with ChatGPT researcher. Zero browser automation = 100% reliable.

Usage:
    python 09_exa_researcher.py --topic "Coretax 2025" --output output/raw/exa_dump.json
    python 09_exa_researcher.py --topic "KBLI visa" --output output/raw/exa_dump.json --deep
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
EXA_BASE_URL = "https://api.exa.ai"
SEARCH_WINDOW_DAYS = 3  # last 72h

# Indonesian news & legal domains
NEWS_DOMAINS = [
    "cnnindonesia.com", "detik.com", "kompas.com", "tempo.co",
    "cnbcindonesia.com", "bisnis.com", "liputan6.com",
    "thejakartapost.com", "jawapos.com", "antaranews.com",
]
LEGAL_DOMAINS = [
    "hukumonline.com", "ddtc.co.id", "bkpm.go.id",
    "pajak.go.id", "djp.go.id", "oss.go.id",
    "kemenkumham.go.id", "imigrasi.go.id",
]
BALI_DOMAINS = [
    "baliprovince.go.id", "bali.go.id",
    "nowbali.co.id", "thebalitimes.com", "balidiscovery.com",
]


def log(msg: str, level: str = "INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Exa API client
# ---------------------------------------------------------------------------
def _exa_search(
    query: str,
    num_results: int = 10,
    category: Optional[str] = None,
    include_domains: Optional[list] = None,
    search_type: str = "auto",
    start_date: Optional[str] = None,
) -> list:
    """Call Exa search API and return results."""
    if not EXA_API_KEY:
        log("EXA_API_KEY not set!", "ERROR")
        return []

    payload = {
        "query": query,
        "numResults": num_results,
        "type": search_type,
        "contents": {
            "text": {"maxCharacters": 3000},
            "highlights": {
                "numSentences": 3,
                "highlightsPerUrl": 2,
            },
            "summary": {"query": query},
        },
    }

    if category:
        payload["category"] = category
    if include_domains:
        payload["includeDomains"] = include_domains
    if start_date:
        payload["startPublishedDate"] = start_date

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{EXA_BASE_URL}/search",
                json=payload,
                headers={"x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])
    except Exception as e:
        log(f"Exa search error: {e}", "ERROR")
        return []


def _exa_deep_research(topic: str) -> Optional[dict]:
    """Exa deep research endpoint — disabled (API removed, returns 404 since Mar 2026)."""
    return None


# ---------------------------------------------------------------------------
# Search tasks
# ---------------------------------------------------------------------------
def search_news(topic: str, start_date: str) -> dict:
    """Search Indonesian news about the topic."""
    log(f"Searching news: {topic}")
    results = _exa_search(
        query=f"{topic} Indonesia",
        num_results=15,
        category="news",
        include_domains=NEWS_DOMAINS,
        start_date=start_date,
    )
    log(f"News: {len(results)} results")
    return {"type": "news", "results": results}


def search_legal(topic: str, start_date: str) -> dict:
    """Search Indonesian legal/government sources."""
    log(f"Searching legal/gov: {topic}")
    results = _exa_search(
        query=f"{topic} regulasi peraturan Indonesia 2026",
        num_results=10,
        include_domains=LEGAL_DOMAINS,
        start_date=start_date,
    )
    log(f"Legal: {len(results)} results")
    return {"type": "legal", "results": results}


def search_bali(topic: str, start_date: str) -> dict:
    """Search Bali-specific sources."""
    log(f"Searching Bali sources: {topic}")
    results = _exa_search(
        query=f"{topic} Bali",
        num_results=10,
        include_domains=BALI_DOMAINS + NEWS_DOMAINS,
        search_type="neural",
        start_date=start_date,
    )
    log(f"Bali: {len(results)} results")
    return {"type": "bali", "results": results}


# ---------------------------------------------------------------------------
# Output formatter
# ---------------------------------------------------------------------------
def format_output(
    topic: str,
    news: dict,
    legal: dict,
    bali: dict,
    deep: Optional[dict],
) -> dict:
    """Format all Exa results into war room compatible structure."""
    facts = []

    for search_result in [news, legal, bali]:
        for r in search_result.get("results", []):
            facts.append({
                "title": r.get("title", ""),
                "brief": r.get("summary", r.get("text", "")[:500]),
                "category": search_result["type"],
                "source": r.get("url", ""),
                "published": r.get("publishedDate", ""),
                "domain": r.get("url", "").split("/")[2] if r.get("url") else "",
                "highlights": r.get("highlights", []),
                "score": r.get("score", 0),
            })

    # Dedup by title similarity
    seen_titles = set()
    unique_facts = []
    for f in facts:
        title_key = f["title"].lower()[:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_facts.append(f)

    # Sort by score descending
    unique_facts.sort(key=lambda x: x.get("score", 0), reverse=True)

    output = {
        "topic": topic,
        "scraped_at": datetime.now().isoformat(),
        "source": "exa_ai",
        "facts": unique_facts,
        "topics": list(set(f["category"] for f in unique_facts)),
        "stats": {
            "news_count": len(news.get("results", [])),
            "legal_count": len(legal.get("results", [])),
            "bali_count": len(bali.get("results", [])),
            "total_unique": len(unique_facts),
        },
    }

    if deep and deep.get("status") == "completed":
        output["deep_research"] = {
            "report": deep.get("report", ""),
            "sources": [s.get("url", "") for s in deep.get("sources", [])],
        }

    return output


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Exa AI Researcher for War Room")
    parser.add_argument("--topic", required=True, help="Research topic")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--deep", action="store_true", help="Include deep research (slower, ~60s)")
    parser.add_argument("--days", type=int, default=SEARCH_WINDOW_DAYS, help="Search window in days")
    args = parser.parse_args()

    global EXA_API_KEY
    if not EXA_API_KEY:
        # Try .env file
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("EXA_API_KEY="):
                    EXA_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not EXA_API_KEY:
        log("EXA_API_KEY not found in env or .env file", "ERROR")
        # Write empty result so pipeline can continue
        Path(args.output).write_text(json.dumps({"facts": [], "error": "no_api_key"}, indent=2))
        sys.exit(1)

    start_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
    log(f"Exa research: '{args.topic}' (last {args.days} days)")

    t0 = time.time()

    # Run searches in parallel
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(search_news, args.topic, start_date): "news",
            pool.submit(search_legal, args.topic, start_date): "legal",
            pool.submit(search_bali, args.topic, start_date): "bali",
        }

        if args.deep:
            futures[pool.submit(_exa_deep_research, args.topic)] = "deep"

        results = {}
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                log(f"{key} search failed: {e}", "ERROR")
                results[key] = {"type": key, "results": []} if key != "deep" else None

    output = format_output(
        topic=args.topic,
        news=results.get("news", {"type": "news", "results": []}),
        legal=results.get("legal", {"type": "legal", "results": []}),
        bali=results.get("bali", {"type": "bali", "results": []}),
        deep=results.get("deep"),
    )

    elapsed = time.time() - t0
    output["stats"]["elapsed_seconds"] = round(elapsed, 1)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))

    log(f"Done in {elapsed:.1f}s — {output['stats']['total_unique']} unique facts")
    log(f"Output: {args.output}")


if __name__ == "__main__":
    main()
