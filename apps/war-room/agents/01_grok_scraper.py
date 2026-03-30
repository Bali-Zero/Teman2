#!/usr/bin/env python3
"""
FASE 1 — Intelligence Scraper (xAI + Exa + CDP)
Target: Social sentiment (X/Reddit) + Indonesian news/gov sources — last 72h
Output: raw intelligence JSON

Fallback chain:
  1. xAI x_search (primary) — native X/Twitter firehose, citations, sentiment
  2. Exa (secondary) — neural search, highlights, Reddit coverage
  3. Chrome CDP (last resort) — browser automation via Grok web UI

Best practices applied (Exa docs, Mar 2026):
- Neural queries phrased as statements ending with ":" (not questions)
- highlights mode: 10x more token-efficient than full text for agentic workflows
- category='news' for news sources (native Exa index, not just domain filter)
- maxAgeHours=72 for news (fresh but not always-crawl); 0 for social (real-time)
- type='auto' for highest quality neural+keyword routing
- Single Exa client instance shared across all functions
- tweet category attempted first, falls back to domain filter gracefully
"""
import json
import argparse
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

import httpx

# ── Exa query design: statement-form performs better than question-form ─────
# BAD:  "What are problems with Coretax in Indonesia?"
# GOOD: "Here is a post complaining about Coretax errors in Indonesia:"

SOCIAL_QUERIES = [
    "Here is a post from an expat complaining about KITAS visa delays in Indonesia:",
    "Here is a frustrated tweet about Coretax errors in Indonesia 2025:",
    "Here is a Reddit post about OSS KBLI perizinan problems in Bali:",
    "Here is a social media post about Indonesia business permit stuck:",
    "Here is a complaint from a foreign investor about Indonesian tax compliance:",
]

NEWS_QUERIES = [
    "Here is an article about Coretax DJP Indonesia implementation problems 2025:",
    "Here is a news article about OSS RBA KBLI regulation changes Indonesia:",
    "Here is a report about KITAS immigration policy changes for expats in Bali:",
    "Here is a DDTC or Hukumonline article about Indonesian tax regulation update:",
    "Here is a BKPM article about foreign investment licensing Indonesia 2025:",
]

NEWS_DOMAINS = [
    "cnbcindonesia.com", "bisnis.com", "detik.com", "ddtc.co.id",
    "hukumonline.com", "kompas.com", "kontan.co.id", "tempo.co",
]

REDDIT_QUERIES = [
    "Here is a Reddit post about KITAS visa immigration problems in Bali Indonesia:",
    "Here is a r/bali or r/indonesia post about expat business permit issues:",
]

KEYWORDS = [
    "#OSS", "#Coretax", "#Imigrasi", "#KITAS", "KBLI",
    "coretax error", "kitas delay", "OSS stuck",
    "izin usaha", "perizinan", "pajak frustasi",
]

# ── xAI Responses API configuration ────────────────────────────────────────
XAI_API_URL = "https://api.x.ai/v1/responses"
XAI_MODEL = "grok-4-1-fast-reasoning"


def _parse_xai_response(
    output_text: str,
    annotations: list[dict],
    source: str = "social",
) -> list[dict]:
    """
    Parse xAI response into our standard result format.
    Tries JSON parsing first, falls back to annotation extraction.
    """
    platform = "xai-x_search" if source == "social" else "xai-web_search"
    results: list[dict] = []

    # Attempt 1: Parse structured JSON array from model output
    if "[" in output_text and "]" in output_text:
        try:
            json_str = output_text[output_text.find("["):output_text.rfind("]") + 1]
            raw_items = json.loads(json_str)
            if isinstance(raw_items, list) and len(raw_items) > 0:
                for item in raw_items:
                    results.append({
                        "source": source,
                        "platform": platform,
                        "text": item.get("text", ""),
                        "title": item.get("title", ""),
                        "author": item.get("author", ""),
                        "url": item.get("url", ""),
                        "timestamp": item.get("timestamp", ""),
                        "sentiment": item.get("sentiment"),
                        "pain_point": item.get("pain_point"),
                    })
                return results
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    # Attempt 2: Extract from annotations (url_citation) — the most common path
    # The model returns prose with inline [N](url) citations; annotations list each one
    if annotations:
        seen_urls: set[str] = set()
        for ann in annotations:
            if ann.get("type") == "url_citation":
                url = ann.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Extract surrounding text as snippet
                start = max(0, ann.get("start_index", 0) - 200)
                end = min(len(output_text), ann.get("end_index", 0) + 50)
                snippet = output_text[start:end].strip()
                # Clean markdown citation markers
                snippet = re.sub(r'\[\[\d+\]\]\([^)]+\)', '', snippet).strip()
                snippet = re.sub(r'\[(\d+)\]\([^)]+\)', '', snippet).strip()

                results.append({
                    "source": source,
                    "platform": platform,
                    "text": snippet[:500],
                    "title": ann.get("title", ""),
                    "author": "",
                    "url": url,
                    "timestamp": "",
                    "sentiment": None,
                    "pain_point": None,
                })
        if results:
            return results

    # Attempt 3: Return raw text as single result
    if output_text.strip():
        results.append({
            "source": source,
            "platform": "xai-raw",
            "text": output_text[:2000],
            "title": "",
            "author": "",
            "url": "",
            "timestamp": "",
            "sentiment": None,
            "pain_point": None,
        })

    return results


def scrape_social_via_xai(api_key: str, queries: list[str], cutoff: datetime) -> list[dict]:
    """
    Primary scraper: xAI x_search API for X/Twitter social sentiment.
    Returns results in the same format as Exa functions.
    """
    if not api_key:
        return []

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    from_date = cutoff.strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")
    results: list[dict] = []
    total_cost_usd = 0.0

    for query in queries:
        try:
            payload = {
                "model": XAI_MODEL,
                "input": [
                    {
                        "role": "system",
                        "content": (
                            "You are an intelligence analyst monitoring Indonesian business "
                            "and immigration topics on X/Twitter. For each relevant post found, "
                            "include the post URL as a citation. Focus on sentiment, pain points, "
                            "and specific complaints from expats and businesses."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                "tools": [
                    {
                        "type": "x_search",
                        "from_date": from_date,
                        "to_date": to_date,
                    }
                ],
            }

            resp = httpx.post(
                XAI_API_URL,
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract output text from Responses API format
            output_text = ""
            annotations: list[dict] = []
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            output_text = content.get("text", "")
                            annotations = content.get("annotations", [])

            parsed = _parse_xai_response(output_text, annotations, source="social")
            results.extend(parsed)

            # Track cost
            usage = data.get("usage", {})
            cost_ticks = usage.get("cost_in_usd_ticks", 0)
            cost_usd = cost_ticks / 10_000_000_000
            total_cost_usd += cost_usd
            sources = usage.get("num_sources_used", 0)
            tool_details = usage.get("server_side_tool_usage_details", {})
            x_calls = tool_details.get("x_search_calls", 0)
            print(
                f"  [xai-x_search] {query[:55]}... "
                f"-> {len(parsed)} results, {x_calls} searches, ${cost_usd:.4f}",
                file=sys.stderr,
            )

        except httpx.HTTPStatusError as e:
            print(f"  [xai-x_search] HTTP {e.response.status_code}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"  [xai-x_search] error: {e}", file=sys.stderr)

    if total_cost_usd > 0:
        print(f"  [xai-x_search] total cost: ${total_cost_usd:.4f}", file=sys.stderr)

    return results


def scrape_news_via_xai(api_key: str, queries: list[str], cutoff: datetime) -> list[dict]:
    """
    xAI web_search for Indonesian news sources.
    Filters to our trusted Indonesian news domains (max 5 per request, batched).
    """
    if not api_key:
        return []

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    from_date = cutoff.strftime("%Y-%m-%d")
    results: list[dict] = []

    # Split NEWS_DOMAINS into batches of 5 (API limit)
    domain_batches = [NEWS_DOMAINS[i:i + 5] for i in range(0, len(NEWS_DOMAINS), 5)]

    for query in queries:
        for domains in domain_batches:
            try:
                payload = {
                    "model": XAI_MODEL,
                    "input": [
                        {
                            "role": "system",
                            "content": (
                                "You are an intelligence analyst monitoring Indonesian "
                                "business regulations and government policy. Extract news "
                                "articles about the topic. Include URLs as citations."
                            ),
                        },
                        {"role": "user", "content": query},
                    ],
                    "tools": [
                        {
                            "type": "web_search",
                            "allowed_domains": domains,
                        }
                    ],
                }

                resp = httpx.post(
                    XAI_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                )
                resp.raise_for_status()
                data = resp.json()

                output_text = ""
                annotations: list[dict] = []
                for item in data.get("output", []):
                    if item.get("type") == "message":
                        for content in item.get("content", []):
                            if content.get("type") == "output_text":
                                output_text = content.get("text", "")
                                annotations = content.get("annotations", [])

                parsed = _parse_xai_response(output_text, annotations, source="news")
                results.extend(parsed)

                print(
                    f"  [xai-web_search] {query[:40]}... [{','.join(domains[:2])}...] "
                    f"-> {len(parsed)}",
                    file=sys.stderr,
                )

            except Exception as e:
                print(f"  [xai-web_search] error: {e}", file=sys.stderr)

    return results


def _make_exa(api_key: str):
    try:
        from exa_py import Exa
        return Exa(api_key)
    except ImportError:
        print("  exa_py not installed — pip install exa-py", file=sys.stderr)
        return None


def _extract_highlights(res) -> str:
    """Extract highlights text if available, else fall back to title."""
    highlights = getattr(res, 'highlights', None)
    if highlights:
        if isinstance(highlights, list):
            return " | ".join(str(h) for h in highlights[:3])
        return str(highlights)
    return res.title or ""


def scrape_social_via_exa(exa, cutoff: datetime) -> list:
    """
    Scrape social sentiment via Exa.
    Tries tweet category (Business plan) → falls back to domain filter.
    Uses highlights for token efficiency + maxAgeHours=0 for real-time.
    """
    if not exa:
        return []

    cutoff_str = cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')
    results = []

    for query in SOCIAL_QUERIES:
        try:
            # Attempt tweet category (Business plan feature)
            try:
                r = exa.search(
                    query=query,
                    type="auto",
                    category="tweet",
                    num_results=10,
                    start_published_date=cutoff_str,
                    contents={"highlights": True, "max_age_hours": 72},
                )
                label = "tweet"
            except Exception:
                # Fallback: domain filter on x.com
                r = exa.search(
                    query=query,
                    type="auto",
                    num_results=8,
                    start_published_date=cutoff_str,
                    include_domains=["twitter.com", "x.com"],
                    contents={"highlights": True},
                )
                label = "x-domain"

            for res in r.results:
                results.append({
                    "source": "social",
                    "platform": label,
                    "text": _extract_highlights(res),
                    "title": res.title or "",
                    "author": getattr(res, "author", ""),
                    "url": res.url,
                    "timestamp": res.published_date or "",
                    "sentiment": None,
                    "pain_point": None,
                })
            print(f"  [{label}] {query[:55]}... → {len(r.results)}", file=sys.stderr)
        except Exception as e:
            print(f"  [social] error: {e}", file=sys.stderr)

    return results


def scrape_reddit_via_exa(exa, cutoff: datetime) -> list:
    """
    Scrape Reddit with domain filter + highlights.
    72h window; no livecrawl needed (Reddit posts cached quickly).
    """
    if not exa:
        return []

    cutoff_str = cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')
    results = []

    for query in REDDIT_QUERIES:
        try:
            r = exa.search(
                query=query,
                type="auto",
                num_results=10,
                start_published_date=cutoff_str,
                include_domains=["reddit.com"],
                contents={"highlights": True, "max_age_hours": 72},
            )
            for res in r.results:
                results.append({
                    "source": "social",
                    "platform": "reddit",
                    "text": _extract_highlights(res),
                    "title": res.title or "",
                    "url": res.url,
                    "timestamp": res.published_date or "",
                    "sentiment": None,
                    "pain_point": None,
                })
            print(f"  [reddit] {query[:55]}... → {len(r.results)}", file=sys.stderr)
        except Exception as e:
            print(f"  [reddit] error: {e}", file=sys.stderr)

    return results


def scrape_news_via_exa(exa, cutoff: datetime) -> list:
    """
    Scrape Indonesian news/gov sources using:
    - category='news' (native Exa news index, best quality)
    - domain filter as secondary fallback for Indonesian-specific sources
    - highlights mode: token-efficient excerpts
    - maxAgeHours=72: fresh content, livecrawl if cached content is older
    """
    if not exa:
        return []

    cutoff_str = cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')
    results = []

    for query in NEWS_QUERIES:
        # Pass 1: category='news' (Exa native news index — best semantic quality)
        try:
            r = exa.search(
                query=query,
                type="auto",
                category="news",
                num_results=6,
                start_published_date=cutoff_str,
                contents={"highlights": True, "max_age_hours": 72},
            )
            for res in r.results:
                results.append({
                    "source": "news",
                    "platform": "news-index",
                    "text": _extract_highlights(res),
                    "title": res.title or "",
                    "url": res.url,
                    "timestamp": res.published_date or "",
                    "sentiment": None,
                    "pain_point": None,
                })
            print(f"  [news-cat] {query[:55]}... → {len(r.results)}", file=sys.stderr)
        except Exception as e:
            print(f"  [news-cat] error: {e}", file=sys.stderr)

        # Pass 2: domain filter on Indonesian sources specifically
        try:
            r = exa.search(
                query=query,
                type="auto",
                num_results=5,
                start_published_date=cutoff_str,
                include_domains=NEWS_DOMAINS,
                contents={"highlights": True, "max_age_hours": 72},
            )
            for res in r.results:
                results.append({
                    "source": "news",
                    "platform": "id-domains",
                    "text": _extract_highlights(res),
                    "title": res.title or "",
                    "url": res.url,
                    "timestamp": res.published_date or "",
                    "sentiment": None,
                    "pain_point": None,
                })
            print(f"  [id-domains] {query[:55]}... → {len(r.results)}", file=sys.stderr)
        except Exception as e:
            print(f"  [id-domains] error: {e}", file=sys.stderr)

    return results


def scrape_via_xai_cdp(topic: str, cutoff: datetime) -> list:
    """Fallback: Chrome CDP → x.com/grok (XAI Grok, requires active logged-in Chrome session)."""
    try:
        from playwright.sync_api import sync_playwright
        import httpx
        resp = httpx.get("http://localhost:9222/json/version", timeout=3)
        if resp.status_code != 200:
            raise ConnectionError
    except Exception:
        print("  Chrome CDP not available, skipping", file=sys.stderr)
        return []

    print("  XAI CDP fallback (browser)...", file=sys.stderr)
    results = []

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        try:
            page.goto("https://x.com/grok", timeout=30000)
            time.sleep(4)
            since_date = cutoff.strftime('%Y-%m-%d')
            prompt = (
                f"Search X (Twitter) for posts since {since_date} about: {topic}, "
                f"{', '.join(KEYWORDS[:8])}. "
                f"Return JSON array: [{{tweet_text, author_handle, sentiment_tag, pain_point_category}}]"
            )
            el = page.locator("textarea, [contenteditable='true']").first
            el.click()
            el.fill(prompt)
            page.keyboard.press("Enter")
            page.wait_for_timeout(30000)

            response_text = ""
            for el in page.locator("[data-testid='bot-message'], .message, .response").all():
                try:
                    response_text = el.inner_text()
                except Exception:
                    pass

            if "[" in response_text:
                try:
                    raw = json.loads(response_text[response_text.find("["):response_text.rfind("]") + 1])
                    results = [{**t, "source": "social", "platform": "xai-cdp"} for t in raw]
                except json.JSONDecodeError:
                    results = [{"text": response_text[:2000], "source": "social", "platform": "xai-cdp-raw"}]
        except Exception as e:
            print(f"  XAI CDP error: {e}", file=sys.stderr)
        finally:
            page.close()

    return results


def dedup(items: list) -> list:
    seen = set()
    out = []
    for item in items:
        key = item.get("url", "") or item.get("text", "")[:80]
        if key and key not in seen:
            seen.add(key)
            out.append(item)
        elif not key:
            out.append(item)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="War Room — Intelligence Scraper")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--window-hours", type=int, default=72)
    args = parser.parse_args()

    cutoff = datetime.now() - timedelta(hours=args.window_hours)
    print(f"\n[scraper] Intelligence Scraper", file=sys.stderr)
    print(f"   Topic:  {args.topic}", file=sys.stderr)
    print(f"   Window: {args.window_hours}h (since {cutoff.strftime('%Y-%m-%d %H:%M')})", file=sys.stderr)

    xai_key = os.environ.get("XAI_API_KEY", "")
    exa_key = os.environ.get("EXA_API_KEY", "")
    all_results: list[dict] = []
    mode = "unknown"

    # ── Priority 1: xAI x_search + web_search (API, native X access, cheapest) ──
    if xai_key:
        mode = "xai-api"
        print(f"   Mode:   xAI Responses API (x_search + web_search)", file=sys.stderr)

        social = scrape_social_via_xai(xai_key, SOCIAL_QUERIES, cutoff)
        all_results.extend(social)
        print(f"   Social (xAI): {len(social)} results", file=sys.stderr)

        news = scrape_news_via_xai(xai_key, NEWS_QUERIES, cutoff)
        all_results.extend(news)
        print(f"   News (xAI):   {len(news)} results", file=sys.stderr)

    # ── Priority 2: Exa (neural search, highlights — good for Reddit) ──
    if exa_key:
        exa = _make_exa(exa_key)
        if not xai_key:
            # Exa is secondary: social + news only if no xAI
            mode = "exa-api"
            print(f"   Mode:   Exa API (neural search, highlights)", file=sys.stderr)
            social = scrape_social_via_exa(exa, cutoff)
            all_results.extend(social)
            print(f"   Social (Exa): {len(social)} results", file=sys.stderr)
            news = scrape_news_via_exa(exa, cutoff)
            all_results.extend(news)
            print(f"   News (Exa):   {len(news)} results", file=sys.stderr)

        # Reddit always via Exa (xAI x_search doesn't cover Reddit)
        reddit = scrape_reddit_via_exa(exa, cutoff)
        all_results.extend(reddit)
        print(f"   Reddit (Exa): {len(reddit)} results", file=sys.stderr)

    # ── Priority 3: Chrome CDP fallback (last resort) ──
    if not xai_key and not exa_key:
        mode = "xai-cdp"
        print("   Mode:   XAI CDP fallback (no API keys)", file=sys.stderr)
        all_results = scrape_via_xai_cdp(args.topic, cutoff)

    all_results = dedup(all_results)

    output = {
        "topic": args.topic,
        "scraped_at": datetime.now().isoformat(),
        "window_hours": args.window_hours,
        "mode": mode,
        "count": len(all_results),
        "breakdown": {
            "social_xai": sum(1 for r in all_results if r.get("platform", "").startswith("xai-x")),
            "social_exa": sum(1 for r in all_results if r.get("platform") in ("tweet", "x-domain")),
            "reddit": sum(1 for r in all_results if r.get("platform") == "reddit"),
            "news_xai": sum(1 for r in all_results if r.get("platform") == "xai-web_search"),
            "news_exa": sum(1 for r in all_results if r.get("platform") in ("news-index", "id-domains")),
            "cdp": sum(1 for r in all_results if r.get("platform", "").startswith("xai-cdp")),
            "raw": sum(1 for r in all_results if r.get("platform") == "xai-raw"),
        },
        "data": all_results,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\n[OK] {len(all_results)} items -> {args.output}", file=sys.stderr)
    breakdown = output["breakdown"]
    print(
        f"   xai_social={breakdown['social_xai']} exa_social={breakdown['social_exa']} "
        f"reddit={breakdown['reddit']} xai_news={breakdown['news_xai']} "
        f"exa_news={breakdown['news_exa']}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
