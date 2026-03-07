#!/usr/bin/env python3
"""
FASE 1 — Social Media Scraper (Exa API + CDP fallback)
Target: X (Twitter Indonesia) + Reddit (r/bali, r/indonesia) — last 72h
Output: raw sentiment JSON

Uses Exa API 'tweet' category for X/Twitter (no login needed).
Falls back to Chrome CDP + Grok only if EXA_API_KEY is missing.
"""
import json
import argparse
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

KEYWORDS = [
    "#OSS", "#Coretax", "#Imigrasi", "#KITAS", "KBLI",
    "coretax error", "kitas delay", "OSS stuck",
    "izin usaha", "perizinan", "pajak frustasi",
    "KBLI salah", "imigrasi masalah"
]

EXA_QUERIES = [
    "OSS Coretax Indonesia frustration problems errors",
    "KITAS KBLI perizinan izin usaha Indonesia Bali",
    "Indonesia immigration visa delay complaint expat Bali",
    "Indonesia business permit stuck error regulation",
]

REDDIT_SUBS = ["bali", "indonesia"]


def scrape_twitter_via_exa(api_key: str, cutoff: datetime) -> list:
    """Scrape X/Twitter via Exa API tweet category."""
    try:
        from exa_py import Exa
    except ImportError:
        print("  exa_py not installed, skipping Exa", file=sys.stderr)
        return []

    exa = Exa(api_key)
    cutoff_str = cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')
    all_tweets = []

    for query in EXA_QUERIES:
        try:
            r = exa.search(
                query=query,
                category='tweet',
                num_results=15,
                start_published_date=cutoff_str,
            )
            for res in r.results:
                all_tweets.append({
                    "source": "x.com/twitter",
                    "text": res.title or "",
                    "author": getattr(res, 'author', ''),
                    "url": res.url if res.url.startswith("http") else f"https://{res.url}",
                    "timestamp": res.published_date or "",
                    "sentiment": None,
                    "pain_point": None,
                })
            print(f"  Exa tweet: {query[:40]}... -> {len(r.results)} results", file=sys.stderr)
        except Exception as e:
            print(f"  Exa tweet error: {query[:40]}... -> {e}", file=sys.stderr)

    return all_tweets


def scrape_reddit_via_exa(api_key: str, cutoff: datetime) -> list:
    """Scrape Reddit via Exa API with domain filter."""
    try:
        from exa_py import Exa
    except ImportError:
        return []

    exa = Exa(api_key)
    cutoff_str = cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')
    results = []

    queries = [
        "visa KITAS immigration business Bali Indonesia",
        "OSS Coretax KBLI perizinan Indonesia expat",
    ]

    for query in queries:
        try:
            r = exa.search(
                query=query,
                num_results=10,
                start_published_date=cutoff_str,
                include_domains=["reddit.com"],
            )
            for res in r.results:
                results.append({
                    "source": "reddit",
                    "text": res.title or "",
                    "url": res.url,
                    "timestamp": res.published_date or "",
                    "sentiment": None,
                    "pain_point": None,
                })
            print(f"  Exa reddit: {query[:40]}... -> {len(r.results)} results", file=sys.stderr)
        except Exception as e:
            print(f"  Exa reddit error: {query[:40]}... -> {e}", file=sys.stderr)

    return results


def scrape_xcom_via_grok_cdp(topic: str, keywords: list, cutoff: datetime) -> list:
    """Fallback: Use Chrome CDP + x.com/grok (requires login session)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  playwright not installed, skipping CDP fallback", file=sys.stderr)
        return []

    cdp_url = "http://localhost:9222"
    try:
        import httpx
        resp = httpx.get(f"{cdp_url}/json/version", timeout=3)
        if resp.status_code != 200:
            print("  Chrome CDP not available, skipping", file=sys.stderr)
            return []
    except Exception:
        print("  Chrome CDP not available, skipping", file=sys.stderr)
        return []

    print("  X/Twitter via Grok CDP fallback...", file=sys.stderr)
    tweets = []

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()

        try:
            page.goto("https://x.com/grok", timeout=30000)
            time.sleep(4)

            since_date = cutoff.strftime('%Y-%m-%d')
            query = (
                f"Search X (Twitter) for posts in the last 3 days (since {since_date}) "
                f"about: {topic}, {', '.join(keywords[:8])}. "
                f"Return JSON array with fields: tweet_text, author_handle, sentiment_tag, pain_point_category."
            )

            input_el = page.locator("textarea, [contenteditable='true']").first
            input_el.click()
            input_el.fill(query)
            page.keyboard.press("Enter")
            page.wait_for_timeout(30000)

            response_els = page.locator("[data-testid='bot-message'], .message, .response").all()
            response_text = ""
            for el in response_els:
                try:
                    response_text = el.inner_text()
                except Exception:
                    pass

            if "[" in response_text and "]" in response_text:
                try:
                    start = response_text.find("[")
                    end = response_text.rfind("]") + 1
                    tweets = json.loads(response_text[start:end])
                except json.JSONDecodeError:
                    tweets = [{"raw_text": response_text[:2000], "source": "grok_raw"}]
            elif response_text.strip():
                tweets = [{"raw_text": response_text[:2000], "source": "grok_raw"}]

            for t in tweets:
                t["source"] = "x.com/twitter"

        except Exception as e:
            print(f"  Grok CDP error: {e}", file=sys.stderr)
        finally:
            page.close()

    return tweets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    cutoff = datetime.now() - timedelta(hours=72)
    print(f"Social scraper — topic: {args.topic}", file=sys.stderr)
    print(f"  Window: last 72h (since {cutoff.strftime('%Y-%m-%d %H:%M')})", file=sys.stderr)

    all_results = []
    exa_key = os.environ.get("EXA_API_KEY", "")

    if exa_key:
        print("  Mode: Exa API (tweet + reddit)", file=sys.stderr)
        tweets = scrape_twitter_via_exa(exa_key, cutoff)
        all_results.extend(tweets)
        print(f"  X/Twitter: {len(tweets)} results", file=sys.stderr)

        reddit = scrape_reddit_via_exa(exa_key, cutoff)
        all_results.extend(reddit)
        print(f"  Reddit: {len(reddit)} results", file=sys.stderr)
    else:
        print("  EXA_API_KEY not set — trying Chrome CDP fallback", file=sys.stderr)
        tweets = scrape_xcom_via_grok_cdp(args.topic, KEYWORDS, cutoff)
        all_results.extend(tweets)
        print(f"  Grok CDP: {len(tweets)} results", file=sys.stderr)

    # Dedup by URL
    seen_urls = set()
    deduped = []
    for r in all_results:
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(r)
        elif not url:
            deduped.append(r)
    all_results = deduped

    output = {
        "topic": args.topic,
        "scraped_at": datetime.now().isoformat(),
        "sources": ["X/Twitter (Exa API)" if exa_key else "X/Twitter (Grok CDP)", "Reddit"],
        "window_hours": 72,
        "keywords": KEYWORDS,
        "count": len(all_results),
        "data": all_results,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"{len(all_results)} posts scraped -> {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
