"""
Mata Garuda — .go.id OSINT scraping helpers.

Shared HTTP + extraction primitives for the four .go.id harvesters:
imigrasi, bkpm, kemlu, kemkumham. CLI-only: uses `curl` subprocess
to respect the Mata Garuda stack rule (no httpx/requests runtime dep).

Contract:
- Single exported UA string identifying Mata Garuda with contact email
- `fetch_goid(url)` — 15s timeout, 1 req/2s rate limit per-site, retry 0
- `extract_links(html, allow_prefix)` — regex-based anchor extractor
  that returns [{url, title}] pairs, restricted to the given prefix
  (domain or path root). Minimal — no bs4 dependency.
"""
from __future__ import annotations

import logging
import re
import subprocess
import time
from typing import Iterable

logger = logging.getLogger("mata_garuda.tools.goid")

USER_AGENT = (
    "Mata-Garuda/0.1 (Intelligence research; contact: zero@balizero.com)"
)
TIMEOUT_S = 15
MIN_INTERVAL_S = 2.0
MAX_ITEMS = 10

# domain -> last fetch monotonic seconds
_LAST_FETCH: dict[str, float] = {}


def _domain(url: str) -> str:
    tail = url.split("://", 1)[-1]
    return tail.split("/", 1)[0].lower()


def _throttle(domain: str) -> None:
    last = _LAST_FETCH.get(domain, 0.0)
    now = time.monotonic()
    delta = now - last
    if delta < MIN_INTERVAL_S:
        time.sleep(MIN_INTERVAL_S - delta)
    _LAST_FETCH[domain] = time.monotonic()


def fetch_goid(url: str, timeout: int = TIMEOUT_S) -> tuple[int, str]:
    """Fetch URL via curl. Returns (http_code, body).

    code == 0 on transport failure (timeout, DNS, connection refused).
    Applies per-domain rate limit (>=2s between calls to same host).
    """
    _throttle(_domain(url))
    try:
        proc = subprocess.run(
            [
                "curl",
                "-sL",
                url,
                "-A", USER_AGENT,
                "--connect-timeout", str(timeout),
                "--max-time", str(timeout),
                "-w", "\n__HTTP_CODE__%{http_code}",
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
    except subprocess.TimeoutExpired:
        return 0, ""
    except FileNotFoundError:
        return 0, ""

    body = proc.stdout
    code = 0
    marker = "\n__HTTP_CODE__"
    if marker in body:
        idx = body.rfind(marker)
        try:
            code = int(body[idx + len(marker):].strip())
        except ValueError:
            code = 0
        body = body[:idx]
    return code, body


def extract_links(
    html: str,
    allow_prefixes: Iterable[str],
    max_items: int = MAX_ITEMS,
) -> list[dict[str, str]]:
    """Pull <a href="..." ...>Title</a> whose href starts with any allowed
    prefix (absolute URL prefix like 'https://www.imigrasi.go.id/berita/').

    Returns first `max_items` unique by url. Minimal regex — sufficient
    for landing pages of .go.id portals. Titles HTML-stripped; skipped
    when empty.
    """
    allowed = tuple(p for p in allow_prefixes if p)
    if not allowed:
        return []

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    pattern = re.compile(
        r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(html):
        href = m.group(1).strip()
        title_raw = m.group(2)
        # normalize protocol-relative
        if href.startswith("//"):
            href = "https:" + href
        if not href.startswith(allowed):
            continue
        if href in seen:
            continue
        title = re.sub(r"<[^>]+>", "", title_raw)
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            continue
        seen.add(href)
        out.append({"url": href, "title": title[:300]})
        if len(out) >= max_items:
            break
    return out
