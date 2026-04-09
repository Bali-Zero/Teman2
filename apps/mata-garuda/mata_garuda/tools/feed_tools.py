"""
Mata Garuda — RSS/Atom feed tools via curl + regex parse.

Fetches newsletter and blog feeds. No feedparser dependency — pure curl + regex.
"""
from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime

from mata_garuda.registry import register_tool

logger = logging.getLogger("mata_garuda.tools")


@register_tool(name="fetch_rss_feed")
def fetch_rss_feed(
    feed_url: str,
    max_items: int = 10,
    context_variables: dict | None = None,
) -> str:
    """Fetch items from an RSS/Atom feed.

    Args:
        feed_url: URL of the RSS or Atom feed
        max_items: Maximum items to return
    """
    try:
        result = subprocess.run(
            ["curl", "-sL", feed_url, "--connect-timeout", "10"],
            capture_output=True, text=True, timeout=15,
        )

        if result.returncode != 0:
            return f"[ERROR] curl failed for {feed_url}"

        xml = result.stdout
        items = _parse_feed(xml)[:max_items]

        if not items:
            return f"[WARNING] No items found in feed: {feed_url}"

        lines = [f"Found {len(items)} items from {feed_url}:"]
        for i, item in enumerate(items, 1):
            lines.append(
                f"  {i}. {item['title'][:80]}\n"
                f"     URL: {item['url']}\n"
                f"     Date: {item['published']}"
            )
        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        return f"[ERROR] Feed timeout: {feed_url}"
    except Exception as e:
        return f"[ERROR] Feed fetch failed: {e}"


@register_tool(name="fetch_multiple_feeds")
def fetch_multiple_feeds(
    feed_urls: str,
    max_per_feed: int = 5,
    context_variables: dict | None = None,
) -> str:
    """Fetch items from multiple RSS feeds.

    Args:
        feed_urls: Comma-separated feed URLs
        max_per_feed: Max items per feed
    """
    all_items = []
    urls = [u.strip() for u in feed_urls.split(",")]

    for url in urls:
        result = fetch_rss_feed(url, max_per_feed)
        all_items.append(f"\n--- {url} ---\n{result}")

    return "\n".join(all_items)


def _parse_feed(xml: str) -> list[dict]:
    """Parse RSS or Atom XML into list of item dicts."""
    items = []

    # Try RSS format first (<item>)
    rss_items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
    if rss_items:
        for entry in rss_items:
            title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", entry, re.DOTALL)
            link_m = re.search(r"<link>(.*?)</link>", entry)
            pub_m = re.search(r"<pubDate>(.*?)</pubDate>", entry)
            desc_m = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", entry, re.DOTALL)

            if title_m:
                items.append({
                    "title": re.sub(r"\s+", " ", title_m.group(1)).strip(),
                    "url": link_m.group(1).strip() if link_m else "",
                    "published": pub_m.group(1).strip() if pub_m else "",
                    "description": re.sub(r"<[^>]+>", "", desc_m.group(1))[:300] if desc_m else "",
                    "source": "rss",
                })
        return items

    # Try Atom format (<entry>)
    atom_entries = re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL)
    for entry in atom_entries:
        title_m = re.search(r"<title[^>]*>(.*?)</title>", entry, re.DOTALL)
        link_m = re.search(r'<link[^>]*href="([^"]+)"', entry)
        pub_m = re.search(r"<published>(.*?)</published>", entry)
        summary_m = re.search(r"<summary[^>]*>(.*?)</summary>", entry, re.DOTALL)

        if title_m:
            items.append({
                "title": re.sub(r"\s+", " ", title_m.group(1)).strip(),
                "url": link_m.group(1).strip() if link_m else "",
                "published": pub_m.group(1).strip() if pub_m else "",
                "description": re.sub(r"<[^>]+>", "", summary_m.group(1))[:300] if summary_m else "",
                "source": "atom",
            })

    return items
