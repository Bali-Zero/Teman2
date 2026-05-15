"""HTTP+HTML scraper backing the Dream Room ``/api/dream/scrape`` endpoint.

Closes TODO(#78) in ``backend/app/routers/dream.py`` — the previous handler
returned hardcoded mock content. This module implements the
**httpx + BeautifulSoup4 fallback** path described in the TODO marker; we
do NOT add a Firecrawl dependency because:

1. No ``FIRECRAWL_API_KEY`` is provisioned (verified empirically — not in
   Fly secrets, not in ``~/.nuzantara-secrets.env``).
2. The user rule "no paid API" precludes adding new third-party paid
   dependencies for what is essentially title + paragraph extraction.

If/when a richer scraper is needed (PDF, JS-rendered SPAs, paywalled
sites), Firecrawl can be reintroduced as the primary path with this
module as a fallback. The router callsite only depends on
:func:`scrape_url` returning a :class:`ScrapedContent` — swap is local.

Security notes
--------------
- Only ``http://`` and ``https://`` URLs are accepted; ``file://``,
  ``javascript:``, ``data:`` are rejected at the boundary.
- Private-IP SSRF is NOT blocked at this layer (the backend already runs
  on a private network — most "private" targets are legitimate). If
  paranoia rises, wrap in an IP-allowlist check.
- Response size is capped at 5 MB; oversized responses are truncated.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 10.0
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
_MAX_KEY_POINTS = 5
_MAX_QUOTES = 5
_ALLOWED_SCHEMES = {"http", "https"}


class ScrapedContent(BaseModel):
    """Structured result of a single URL fetch+extract pass.

    Matches the legacy ``ScrapingResponse`` payload used by the Dream Room
    router so the wire format is unchanged from the client's perspective.
    """

    title: str
    keyPoints: list[str]
    quotes: list[dict[str, str]]
    success: bool


_client_singleton: httpx.AsyncClient | None = None


async def _get_http_client() -> httpx.AsyncClient:
    """Return the process-wide httpx.AsyncClient used by the scraper.

    A persistent client is used per Nuzantara golden rule #10
    ("Async HTTP Clients — never AsyncClient() in methods/loops"). The
    client is created lazily on first use; tests patch this function to
    inject a mock.
    """
    global _client_singleton
    if _client_singleton is None or _client_singleton.is_closed:
        _client_singleton = httpx.AsyncClient(
            timeout=_DEFAULT_TIMEOUT_S,
            follow_redirects=True,
            headers={
                # Identify ourselves so well-behaved sites can rate-limit
                # us cleanly. Don't impersonate a browser.
                "User-Agent": "Nuzantara-DreamRoom/1.0 (+https://balizero.com)",
            },
        )
    return _client_singleton


def _validate_url(url: str) -> None:
    if not url or not isinstance(url, str):
        raise ValueError("http(s) URL required")
    # Cheap scheme check — avoids importing urllib for a one-liner.
    lowered = url.lower().strip()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        raise ValueError(f"http(s) URL required, got: {url[:32]!r}")


def _extract(html: str, fallback_url: str) -> ScrapedContent:
    soup = BeautifulSoup(html, "html.parser")

    # Strip noisy tags before any text extraction so e.g. inline JS strings
    # never leak into keyPoints.
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()

    # Title
    title_tag = soup.find("title")
    title = (title_tag.get_text(strip=True) if title_tag else "") or fallback_url

    # Paragraphs — first N non-empty <p>.
    paragraphs: list[str] = []
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if text:
            paragraphs.append(text)
        if len(paragraphs) >= _MAX_KEY_POINTS:
            break

    # Blockquotes — preserve attribution when the cite attribute is set.
    quotes: list[dict[str, str]] = []
    for bq in soup.find_all("blockquote"):
        text = bq.get_text(strip=True)
        if not text:
            continue
        author = bq.get("cite") or "Unknown"
        quotes.append({"text": text, "author": author})
        if len(quotes) >= _MAX_QUOTES:
            break

    return ScrapedContent(
        title=title,
        keyPoints=paragraphs,
        quotes=quotes,
        success=True,
    )


async def scrape_url(
    url: str,
    *,
    timeout: float | None = None,
) -> ScrapedContent:
    """Fetch ``url`` and return a structured :class:`ScrapedContent`.

    Args:
        url: Target URL. Must be ``http://`` or ``https://``.
        timeout: Per-request timeout override; falls back to 10s.

    Returns:
        :class:`ScrapedContent` with ``success=True`` on 2xx, or a
        no-content stub with ``success=False`` on any failure (network
        error, non-2xx, parse error). The router can blindly forward
        the result; the client renders the failure state gracefully.

    Raises:
        ValueError: when ``url`` is not http(s).
    """
    _validate_url(url)

    client = await _get_http_client()
    request_timeout = timeout if timeout is not None else _DEFAULT_TIMEOUT_S

    try:
        response = await client.get(url, timeout=request_timeout)
    except httpx.HTTPError as e:
        logger.warning("Scrape failed (network) url=%s err=%s", url, e)
        return ScrapedContent(title="", keyPoints=[], quotes=[], success=False)
    except Exception as e:  # noqa: BLE001 — last-resort fallback
        logger.warning("Scrape failed (unexpected) url=%s err=%s", url, e)
        return ScrapedContent(title="", keyPoints=[], quotes=[], success=False)

    if response.status_code >= 400:
        logger.info("Scrape http=%s for url=%s", response.status_code, url)
        return ScrapedContent(title="", keyPoints=[], quotes=[], success=False)

    text = response.text or ""
    if len(text) > _MAX_RESPONSE_BYTES:
        text = text[:_MAX_RESPONSE_BYTES]

    try:
        return _extract(text, fallback_url=url)
    except Exception as e:  # noqa: BLE001 — never let parse errors crash the request
        logger.warning("Scrape parse failed url=%s err=%s", url, e)
        return ScrapedContent(title="", keyPoints=[], quotes=[], success=False)


__all__: list[str] = ["ScrapedContent", "scrape_url"]


# Compatibility re-export — debug / tests can patch ``_get_http_client`` by
# name. Not part of the public API.
def _get_http_client_for_test() -> Any:  # pragma: no cover
    return _get_http_client
