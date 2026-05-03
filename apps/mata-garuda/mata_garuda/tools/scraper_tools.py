"""
Mata Garuda — Scraper Tools.

Lightweight regulation scraping via curl subprocess.
No beautifulsoup, no playwright — CLI-only per vincolo Mata Garuda.

Target: peraturan.go.id (Indonesian regulation database).
Fallback: JDIH Kemenkumham.

For production scraping, use bali-intel-scraper via OpenClaw pipeline.
This tool is for POC: fetch → parse → publish to Redis Stream.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime

from mata_garuda.registry import register_tool

logger = logging.getLogger("mata_garuda.tools")

DEFAULT_URL = "https://peraturan.go.id/harmonpusat"
FALLBACK_URL = "https://jdih.kemenkumham.go.id"
CURL_TIMEOUT = 15


def _curl_fetch(url: str, timeout: int = CURL_TIMEOUT) -> str:
    """Fetch URL content via curl subprocess."""
    try:
        result = subprocess.run(
            ["curl", "-sL", url, "--connect-timeout", str(timeout)],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        if result.returncode != 0:
            return f"[ERROR] curl failed: {result.stderr.strip()}"
        return result.stdout
    except subprocess.TimeoutExpired:
        return f"[ERROR] curl timeout after {timeout}s"
    except FileNotFoundError:
        return "[ERROR] curl not found"


def _extract_regulations(html: str) -> list[dict]:
    """Extract regulation entries from peraturan.go.id HTML.

    Parses the harmonpusat page for regulation data.
    The page uses div-based cards with <p> for type/title and
    <a href="/harmon/{hash}"> for detail links.
    Uses regex — no external HTML parser dependency.
    """
    entries = []

    # 2026-04 structure: <p>TYPE</p> ... <p>TITLE</p> ... <a href="/harmon/HASH">
    blocks = re.findall(
        r'<p>([^<]{3,80})</p>\s*(?:<!--.*?-->\s*)?'
        r'<p>([^<]{10,300})</p>\s*<br>\s*'
        r'<p><a\s+href="(/harmon/[a-f0-9]+)"',
        html,
        re.DOTALL,
    )

    for reg_type, title, link in blocks:
        reg_type = re.sub(r'\s+', ' ', reg_type).strip()
        title = re.sub(r'\s+', ' ', title).strip()

        entry = {
            "url": f"https://peraturan.go.id{link}",
            "title": f"[{reg_type}] {title}",
            "detail": reg_type,
            "source": "peraturan.go.id",
            "scraped_at": datetime.now().isoformat(timespec="seconds"),
        }
        entries.append(entry)

    return entries


@register_tool(name="scrape_regulations")
def scrape_regulations(
    url: str = DEFAULT_URL,
    limit: int = 10,
    context_variables: dict | None = None,
) -> str:
    """Scrape regulation listings from peraturan.go.id.

    Args:
        url: Target URL (default: peraturan.go.id/harmonpusat)
        limit: Maximum number of entries to extract
    """
    logger.info(f"[scraper] Fetching {url}")
    html = _curl_fetch(url)

    if html.startswith("[ERROR]"):
        # Try fallback
        logger.warning(f"[scraper] Primary URL failed, trying fallback")
        html = _curl_fetch(FALLBACK_URL)
        if html.startswith("[ERROR]"):
            return f"[ERROR] Both primary and fallback URLs failed: {html}"

    entries = _extract_regulations(html)

    if not entries:
        return (
            f"[WARNING] No regulations extracted from {url}. "
            f"Page may have changed structure. "
            f"HTML length: {len(html)} chars."
        )

    entries = entries[:limit]

    result_lines = [f"Found {len(entries)} regulations:"]
    for i, entry in enumerate(entries, 1):
        result_lines.append(
            f"  {i}. {entry['title'][:80]}"
            f"\n     URL: {entry['url']}"
        )

    return "\n".join(result_lines)


@register_tool(name="scrape_regulation_detail")
def scrape_regulation_detail(
    url: str,
    context_variables: dict | None = None,
) -> str:
    """Scrape detail page of a specific regulation.

    Args:
        url: Full URL of the regulation detail page
    """
    if not url.startswith("https://peraturan.go.id"):
        return f"[BLOCKED] URL must be from peraturan.go.id, got: {url}"

    html = _curl_fetch(url)
    if html.startswith("[ERROR]"):
        return html

    # Extract title
    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else "Unknown"

    # Extract meta description
    desc_match = re.search(
        r'<meta\s+name="description"\s+content="([^"]*)"',
        html,
        re.IGNORECASE,
    )
    description = desc_match.group(1).strip() if desc_match else ""

    # Extract main content text (rough: body text stripped of tags)
    body_match = re.search(
        r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if body_match:
        content = re.sub(r'<[^>]+>', ' ', body_match.group(1))
        content = re.sub(r'\s+', ' ', content).strip()[:1000]
    else:
        content = "(content extraction failed)"

    return (
        f"Title: {title}\n"
        f"URL: {url}\n"
        f"Description: {description}\n"
        f"Content preview: {content}"
    )


@register_tool(name="check_regulation_source")
def check_regulation_source(
    url: str = DEFAULT_URL,
    context_variables: dict | None = None,
) -> str:
    """Check if a regulation source URL is reachable.

    Args:
        url: URL to check (default: peraturan.go.id)
    """
    try:
        result = subprocess.run(
            [
                "curl", "-sL", url,
                "-o", "/dev/null",
                "-w", "%{http_code}",
                "--connect-timeout", "5",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        code = result.stdout.strip()
        if code.startswith("2"):
            return f"[OK] {url} is reachable (HTTP {code})"
        else:
            return f"[WARNING] {url} returned HTTP {code}"
    except Exception as e:
        return f"[ERROR] Cannot reach {url}: {e}"
