"""Bounded, gentle, async crawler for the imigrasi.go.id scoped mirror.

Guardrails (Zero mandate + fs_usage firehose lesson, CLAUDE.md host rules):
  - httpx async (Golden Rule #4), never requests / sync sockets.
  - Honest User-Agent naming us + a contact address.
  - Global rate limit: no more than one request DISPATCHED every
    `rate_limit_s` seconds, even with several requests in flight
    (`--concurrency` caps how many are in flight at once; the limiter caps
    how fast new ones start — the two combine, they don't substitute).
  - Per-request timeout + bounded retries with backoff on transient errors
    only (timeouts, 5xx, 429) — a permanent error (404/403) is not retried.
  - An OVERALL wall-clock deadline bounds the whole crawl. Anything not
    reached by the deadline is reported as skipped, never silently dropped
    (W97: "no silent caps" — a truncated result must say N of M).
  - robots.txt is honored per-host, fail-OPEN on a fetch/parse error (a
    public government list page must not go dark because robots.txt itself
    timed out) — cached once per host per run.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from urllib import robotparser

import httpx

from extract import extract_text
from urls import Page

USER_AGENT = "BaliZero-visa-mirror/1.0 (+https://balizero.com; contact: zero@balizero.com)"

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


@dataclass
class FetchResult:
    page: Page
    ok: bool
    status_code: int | None
    text: str | None
    error: str | None
    content_bytes: int


class RateLimiter:
    """Serializes request DISPATCH to at least `min_interval_s` apart, globally."""

    def __init__(self, min_interval_s: float):
        self._min = max(0.0, min_interval_s)
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delta = now - self._last
            if delta < self._min:
                await asyncio.sleep(self._min - delta)
            self._last = time.monotonic()


class RobotsCache:
    """Per-host robots.txt, fetched once per run. Fail-open on any error."""

    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self._cache: dict[str, robotparser.RobotFileParser | None] = {}

    async def allowed(self, url: str) -> bool:
        u = httpx.URL(url)
        origin = f"{u.scheme}://{u.host}"
        if origin not in self._cache:
            parsed: robotparser.RobotFileParser | None = None
            try:
                resp = await self._client.get(f"{origin}/robots.txt", timeout=10.0)
                if resp.status_code == 200 and resp.text.strip():
                    rp = robotparser.RobotFileParser()
                    rp.parse(resp.text.splitlines())
                    parsed = rp
            except Exception:
                parsed = None  # fail-open: a robots.txt hiccup must not black out a public gov page
            self._cache[origin] = parsed
        rp = self._cache[origin]
        if rp is None:
            return True
        return rp.can_fetch(USER_AGENT, url)


async def _fetch_one(
    client: httpx.AsyncClient,
    limiter: RateLimiter,
    robots: RobotsCache,
    page: Page,
    *,
    retries: int,
    timeout_s: float,
) -> FetchResult:
    if not await robots.allowed(page.url):
        return FetchResult(page, False, None, None, "robots_disallowed", 0)

    last_err: str | None = None
    for attempt in range(1, retries + 1):
        await limiter.wait()
        try:
            resp = await client.get(page.url, timeout=timeout_s)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                await asyncio.sleep(2**attempt)
            continue

        if resp.status_code == 200:
            text = extract_text(resp.text)
            return FetchResult(page, True, 200, text, None, len(resp.content))

        if resp.status_code in RETRYABLE_STATUS:
            last_err = f"http_{resp.status_code}"
            if attempt < retries:
                await asyncio.sleep(2**attempt)
            continue

        # Permanent client error (404, 403, ...) — retrying will not help.
        return FetchResult(page, False, resp.status_code, None, f"http_{resp.status_code}", 0)

    return FetchResult(page, False, None, None, last_err or "unknown_error", 0)


async def crawl(
    pages: list[Page],
    *,
    concurrency: int = 4,
    rate_limit_s: float = 2.0,
    timeout_s: float = 30.0,
    retries: int = 3,
    overall_timeout_s: float = 1200.0,
) -> tuple[list[FetchResult], list[Page]]:
    """Returns (results, skipped_due_to_deadline). `results` covers every
    page NOT skipped — including failed fetches, so callers can report them
    rather than lose them silently."""
    limiter = RateLimiter(rate_limit_s)
    sem = asyncio.Semaphore(max(1, concurrency))
    deadline = time.monotonic() + overall_timeout_s
    skipped: list[Page] = []

    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        robots = RobotsCache(client)

        async def worker(page: Page) -> FetchResult | None:
            async with sem:
                if time.monotonic() > deadline:
                    skipped.append(page)
                    return None
                return await _fetch_one(client, limiter, robots, page, retries=retries, timeout_s=timeout_s)

        done = await asyncio.gather(*(worker(p) for p in pages))

    results = [r for r in done if r is not None]
    return results, skipped
