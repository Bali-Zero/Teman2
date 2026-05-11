"""NB-INTEL-Regulation feeder — fix-of-broken pipeline (Task 2).

Strategy (R2 SOTA-validated):

  primary_layer:
    - PasalIdClient (Phase 0, 40k regs, may be auth-disabled — degrade gracefully)
    - JDIHN portal aggregator (1212 sites integrated)
  secondary_scraping:
    - setkab.go.id press signals (Perpres/PP)

Scorer fast-path (skip LLM 70-80% per R5 lesson):
  regex: PMK[\\s-]?\\d+ | PER[\\s-]?\\d+ | KEP[\\s-]?\\d+ | SE[\\s-]?\\d+ |
         PP[\\s-]?\\d+ | Perpres[\\s-]?\\d+
  date filter: last `days` (default 30) only
  domain whitelist: setkab.go.id, peraturan.bpk.go.id, peraturan.go.id, jdihn.go.id

Output: list[Regulation] deduplicated by source_id.

Design notes:
- The pasal.id token is often unset in CI / dev. We swallow PasalIdAuthError
  and continue with the JDIHN + setkab fallback — better to ship 2/3 layers
  than fail the whole feeder.
- Each layer is wrapped in its own try/except so one dead source can't kill
  the others. Errors logged via stdlib logging at WARNING (not ERROR — these
  portals being flaky is the steady state, per R2 28% infra-dead finding).
- dedupe is by (domain, source_id). The source_id construction differs per
  layer; we prefix to keep them disjoint.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import httpx

from mata_garuda.domains.setup_team.types import Regulation
from mata_garuda.foundations.pasal_id_client import PasalIdAuthError, PasalIdClient

logger = logging.getLogger(__name__)

# Endpoint correction 2026-05-08 (live cron run revealed /search/site → 404).
# Current JDIHN navigation exposes /dokumen-hukum (HTTP 200 verified).
JDIHN_SEARCH_URL = "https://jdihn.go.id/dokumen-hukum"
SETKAB_PRESS_URL = "https://setkab.go.id/category/berita/"

# Phase 1.5 PR-C tier-2 sources (national).
# BPK = Badan Pemeriksa Keuangan, official gov regulation index. Search
# parametrized by `type=peraturan` returns the index page with links to
# /Details/<id>/<slug>. Live verified 2026-05-08.
BPK_SEARCH_URL = "https://peraturan.bpk.go.id/Search?type=peraturan"
# peraturan.go.id apex returns 500 (server-side bug); www subdomain is the
# working canonical. Live verified 2026-05-08.
PERATURAN_GO_ID_URL = "https://www.peraturan.go.id/"

DEFAULT_TIMEOUT_SECONDS = 20.0

# Domains we trust as tier-1 gov direct.
TRUSTED_TIER1_HOSTS = {
    "setkab.go.id",
    "peraturan.bpk.go.id",
    "peraturan.go.id",
    "jdihn.go.id",
    "pasal.id",
}

# Regex fast-path — matches PMK 81/2024, KEP-71/PJ/2026, PP No 28/2025,
# Perpres 5/2021, UU 27/2022 PDP, etc. Tolerates "No"/"Nomor" between marker
# and number; tolerates space, hyphen, or "No "/"Nomor " separator.
REGULATION_REGEX = re.compile(
    r"\b(PMK|PER|KEP|SE|PP|Perpres|UU|UUD)(?:[\s\-]+(?:No\.?|Nomor)?[\s\-]*)?\d+\b",
    re.IGNORECASE,
)


def _matches_regulation_regex(text: str) -> bool:
    """Scorer fast-path — True if text contains at least one regulation marker."""
    if not text:
        return False
    return REGULATION_REGEX.search(text) is not None


def _classify_tier(url: str) -> int:
    """Tier 1 if hostname is in TRUSTED_TIER1_HOSTS, else tier 2 (gov press)."""
    if not url:
        return 2
    host = url.split("//", 1)[-1].split("/", 1)[0].lower()
    for trusted in TRUSTED_TIER1_HOSTS:
        if host == trusted or host.endswith("." + trusted):
            return 1
    return 2


def _within_window(published_at: date | None, days: int) -> bool:
    """True if published_at is within the last `days` (None = include, generous)."""
    if published_at is None:
        return True
    today = datetime.now(timezone.utc).date()
    return (today - published_at).days <= days


async def _fetch_pasal_id(client: PasalIdClient, days: int) -> list[Regulation]:
    """Layer 1: pasal.id search for recent regs. Returns empty on auth error."""
    out: list[Regulation] = []
    try:
        # No date filter on pasal.id search; we filter client-side.
        results = await client.search_laws(query="2026", limit=50)
    except PasalIdAuthError as exc:
        logger.warning("pasal.id auth disabled (%s) — skipping layer 1", exc)
        return out
    except Exception as exc:  # network/timeout/4xx/5xx — degrade
        logger.warning("pasal.id fetch failed: %s", exc)
        return out

    for r in results:
        # pasal.id ids are like "uu-2022-27" — no published_at in search shape;
        # we keep them all and let the scorer/regex filter.
        title = r.title or ""
        if not _matches_regulation_regex(title):
            continue
        out.append(
            Regulation(
                source_id=f"pasal-id:{r.id}",
                domain="regulation",
                tier=1,
                title=title,
                url=f"https://pasal.id/laws/{r.id}",
                published_at=None,
                body_excerpt="",
                tags=("layer:pasal-id", f"kind:{r.kind}"),
            )
        )
    return out


async def _fetch_jdihn(http: httpx.AsyncClient, days: int) -> list[Regulation]:
    """Layer 2: JDIHN aggregator HTML scrape. Best-effort.

    JDIHN exposes a search portal HTML (no public JSON API). We scrape link
    list with a forgiving regex; if the page shape changes we silently
    return [] and the other layers carry the load.
    """
    out: list[Regulation] = []
    try:
        # `type=regulation` causes the portal to 404 (verified live 2026-05-08).
        # Plain keyword search returns 200 with the regulation index page.
        resp = await http.get(JDIHN_SEARCH_URL, params={"keyword": "2026"})
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("JDIHN fetch failed: %s", exc)
        return out
    if resp.status_code != 200:
        logger.warning("JDIHN returned %s, skipping", resp.status_code)
        return out

    body = resp.text
    # Forgiving link extractor — matches <a href="..."> wrapping a regulation marker.
    link_re = re.compile(
        r'<a[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>[^<]+)</a>',
        re.IGNORECASE,
    )
    for m in link_re.finditer(body):
        title = m.group("title").strip()
        url = m.group("url").strip()
        if not _matches_regulation_regex(title):
            continue
        # Construct stable source_id — hash(url) keeps it short and unique.
        sid = f"jdihn:{abs(hash(url))}"
        out.append(
            Regulation(
                source_id=sid,
                domain="regulation",
                tier=_classify_tier(url),
                title=title,
                url=url,
                published_at=None,
                body_excerpt="",
                tags=("layer:jdihn",),
            )
        )
    return out


async def _fetch_generic_html(
    http: httpx.AsyncClient,
    url: str,
    layer_tag: str,
    base_host: str,
) -> list[Regulation]:
    """Generic best-effort HTML link harvester for regulation portals.

    Resolves relative hrefs against `base_host` (e.g. "https://peraturan.bpk.go.id")
    so the resulting Regulation.url is always absolute. Filters by
    REGULATION_REGEX on the link's anchor text.

    Used by Phase 1.5 PR-C BPK + peraturan.go.id layers.
    """
    out: list[Regulation] = []
    try:
        resp = await http.get(url)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("%s fetch failed: %s", layer_tag, exc)
        return out
    if resp.status_code != 200:
        logger.warning("%s returned %s, skipping", layer_tag, resp.status_code)
        return out

    body = resp.text
    link_re = re.compile(
        r'<a[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>[^<]+)</a>',
        re.IGNORECASE,
    )
    seen_urls: set[str] = set()
    for m in link_re.finditer(body):
        title = m.group("title").strip()
        href = m.group("url").strip()
        # Resolve relative → absolute against base_host
        if href.startswith("/"):
            href_abs = f"{base_host.rstrip('/')}{href}"
        elif href.startswith("http"):
            href_abs = href
        else:
            continue  # Skip mailto:/javascript:/etc.
        if href_abs in seen_urls:
            continue
        seen_urls.add(href_abs)
        if not _matches_regulation_regex(title):
            continue
        sid = f"{layer_tag}:{abs(hash(href_abs))}"
        out.append(
            Regulation(
                source_id=sid,
                domain="regulation",
                tier=_classify_tier(href_abs),
                title=title,
                url=href_abs,
                published_at=None,
                body_excerpt="",
                tags=(f"layer:{layer_tag}",),
            )
        )
    return out


async def _fetch_bpk(http: httpx.AsyncClient, days: int) -> list[Regulation]:
    """Layer 4 (PR-C): peraturan.bpk.go.id Search index."""
    return await _fetch_generic_html(
        http, BPK_SEARCH_URL, "bpk", "https://peraturan.bpk.go.id"
    )


async def _fetch_peraturan_go_id(
    http: httpx.AsyncClient, days: int
) -> list[Regulation]:
    """Layer 5 (PR-C): www.peraturan.go.id homepage scrape."""
    return await _fetch_generic_html(
        http, PERATURAN_GO_ID_URL, "peraturan_go_id", "https://www.peraturan.go.id"
    )


async def _fetch_setkab(http: httpx.AsyncClient, days: int) -> list[Regulation]:
    """Layer 3: setkab.go.id press signals (Perpres/PP). Best-effort scrape."""
    out: list[Regulation] = []
    try:
        resp = await http.get(SETKAB_PRESS_URL)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("setkab fetch failed: %s", exc)
        return out
    if resp.status_code != 200:
        logger.warning("setkab returned %s, skipping", resp.status_code)
        return out

    body = resp.text
    link_re = re.compile(
        r'<a[^>]+href="(?P<url>https?://setkab\.go\.id/[^"]+)"[^>]*>(?P<title>[^<]+)</a>',
        re.IGNORECASE,
    )
    seen_urls: set[str] = set()
    for m in link_re.finditer(body):
        title = m.group("title").strip()
        url = m.group("url").strip()
        if url in seen_urls:
            continue
        seen_urls.add(url)
        if not _matches_regulation_regex(title):
            continue
        sid = f"setkab:{abs(hash(url))}"
        out.append(
            Regulation(
                source_id=sid,
                domain="regulation",
                tier=1,  # setkab is gov direct
                title=title,
                url=url,
                published_at=None,
                body_excerpt="",
                tags=("layer:setkab",),
            )
        )
    return out


def _dedupe(regulations: Iterable[Regulation]) -> list[Regulation]:
    """Remove duplicate (domain, source_id) pairs — first occurrence wins."""
    seen: set[tuple[str, str]] = set()
    out: list[Regulation] = []
    for r in regulations:
        key = (r.domain, r.source_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


async def fetch_recent_regulations(
    days: int = 30,
    *,
    pasal_id_client: PasalIdClient | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> list[Regulation]:
    """Fetch regulations published in the last `days`, deduplicated.

    Args:
        days: window in days (default 30). Layer-side filtering is best-effort
              because most sources don't return published_at structured.
        pasal_id_client: dependency-inject for tests. Defaults to a fresh
                         PasalIdClient (token from env).
        http_client: dependency-inject for tests. Defaults to a one-shot
                     httpx.AsyncClient.

    Returns:
        list[Regulation] deduped by (domain, source_id), filtered by:
          1. regex fast-path (REGULATION_REGEX matches title)
          2. _within_window(published_at, days)

    Raises:
        Nothing user-facing — each layer wraps its own errors.
    """
    pid_client = pasal_id_client or PasalIdClient()
    own_http = http_client is None
    http = http_client or httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    try:
        layer_pasal = await _fetch_pasal_id(pid_client, days)
        layer_jdihn = await _fetch_jdihn(http, days)
        layer_bpk = await _fetch_bpk(http, days)
        layer_peraturan = await _fetch_peraturan_go_id(http, days)
        layer_setkab = await _fetch_setkab(http, days)
    finally:
        if own_http:
            await http.aclose()

    combined = (
        list(layer_pasal)
        + list(layer_jdihn)
        + list(layer_bpk)
        + list(layer_peraturan)
        + list(layer_setkab)
    )
    deduped = _dedupe(combined)
    in_window = [r for r in deduped if _within_window(r.published_at, days)]
    return in_window


__all__ = [
    "REGULATION_REGEX",
    "TRUSTED_TIER1_HOSTS",
    "fetch_recent_regulations",
]
