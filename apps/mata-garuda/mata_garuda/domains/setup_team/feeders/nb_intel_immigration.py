"""NB-INTEL-Immigration feeder — fix-of-broken pipeline (Task 3).

Sources stream:
  - imigrasi.go.id/berita
  - kemenkum.go.id/berita (was kemenkumham.go.id — domain rebranded after
    Oct 2024 cabinet reshuffle that split the old Ministry of Law and Human
    Rights into 3 separate ministries; old DNS no longer resolves)
  - Tempo "Imigrasi" tag
  - Hukumonline immigration tag (deferred — unstable selectors)

Scorer fast-path:
  regex: KITAS|VITAS|C-?\\d{3}|VOA|e-?VISA|exit ?permit|imigrasi|kemenkum|RPTKA
  skip if `lifestyle|tourism|review` in title

Pattern is identical to nb_intel_regulation: 3 best-effort layers, dedup by
(domain, source_id), regex fast-path filter.

Endpoint corrections (live verification 2026-05-08):
  - kemenkumham.go.id → kemenkum.go.id (DNS rebrand post-2024 ministry split)
  - kemenkum.go.id/berita → /berita-utama (the /berita path now 404s; news
    articles live under /berita-utama/<slug>)
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Iterable

import httpx

from mata_garuda.domains.setup_team.types import Regulation

logger = logging.getLogger(__name__)

IMIGRASI_BERITA_URL = "https://www.imigrasi.go.id/berita"
KEMENKUM_BERITA_URL = "https://www.kemenkum.go.id/berita-utama"
TEMPO_IMIGRASI_TAG_URL = "https://www.tempo.co/tag/imigrasi"

# Phase 1.5 PR-C: 3 Bali Kantor Imigrasi (regional offices). Each entry is
# (layer_tag, news_url, host_filter). Live verified 2026-05-08:
#   - Ngurah Rai (airport) uses /berita-dan-siaran-pers/
#   - Denpasar (city) uses /kat/berita
#   - Singaraja (north) uses /berita-keimigrasian/
# Path varies per office — don't assume a uniform schema. All Kanim sites
# render article links with relative hrefs (e.g. href="/berita/123") so the
# harvester resolves them against the source URL host.
KANIM_BALI_LAYERS: tuple[tuple[str, str, str], ...] = (
    (
        "kanim_ngurahrai",
        "https://ngurahrai.imigrasi.go.id/berita-dan-siaran-pers/",
        "ngurahrai.imigrasi.go.id",
    ),
    (
        "kanim_denpasar",
        "https://denpasar.imigrasi.go.id/kat/berita",
        "denpasar.imigrasi.go.id",
    ),
    (
        "kanim_singaraja",
        "https://singaraja.imigrasi.go.id/berita-keimigrasian/",
        "singaraja.imigrasi.go.id",
    ),
)

DEFAULT_TIMEOUT_SECONDS = 20.0

TRUSTED_TIER1_HOSTS = {
    "imigrasi.go.id",
    "kemenkum.go.id",  # post-2024 rebrand
    # Phase 1.5 PR-C — 3 Bali Kantor Imigrasi subdomains.
    "ngurahrai.imigrasi.go.id",
    "denpasar.imigrasi.go.id",
    "singaraja.imigrasi.go.id",
}

IMMIGRATION_REGEX = re.compile(
    r"\b(KITAS|VITAS|C[\-\s]?\d{3}|VOA|e[\-\s]?VISA|exit\s?permit|imigrasi|kemenkum(?:ham)?|RPTKA)\b",
    re.IGNORECASE,
)
LIFESTYLE_BLOCKLIST = re.compile(r"\b(lifestyle|tourism|review|gallery|cuisine)\b", re.IGNORECASE)


def _matches_immigration_regex(text: str) -> bool:
    if not text:
        return False
    if LIFESTYLE_BLOCKLIST.search(text):
        return False
    return IMMIGRATION_REGEX.search(text) is not None


def _classify_tier(url: str) -> int:
    if not url:
        return 2
    host = url.split("//", 1)[-1].split("/", 1)[0].lower()
    for trusted in TRUSTED_TIER1_HOSTS:
        if host == trusted or host.endswith("." + trusted):
            return 1
    return 2


def _within_window(published_at: date | None, days: int) -> bool:
    if published_at is None:
        return True
    today = datetime.now(timezone.utc).date()
    return (today - published_at).days <= days


async def _fetch_url_links(
    http: httpx.AsyncClient,
    url: str,
    layer_tag: str,
    domain_filter: str | None = None,
) -> list[Regulation]:
    """Generic best-effort link harvester. Returns immigration-matching <a> tags.

    domain_filter: if set, only links whose URL contains this string are kept
                   (e.g. "imigrasi.go.id" to drop ad/cdn links).
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
    # Resolve relative hrefs against the source URL's scheme+host. The
    # Kanim Bali portals (PR-C) emit href="/berita/123" not absolute URLs,
    # and the central imigrasi.go.id site occasionally does the same.
    base_host = _extract_base_host(url)

    link_re = re.compile(
        r'<a[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>[^<]+)</a>',
        re.IGNORECASE,
    )
    seen: set[str] = set()
    for m in link_re.finditer(body):
        href = m.group("url").strip()
        title = m.group("title").strip()
        # Resolve relative → absolute
        if href.startswith("/"):
            href = f"{base_host}{href}"
        elif not href.startswith("http"):
            continue  # Skip mailto:/javascript:/anchor refs.
        if domain_filter and domain_filter not in href:
            continue
        if href in seen:
            continue
        seen.add(href)
        if not _matches_immigration_regex(title):
            continue
        sid = f"{layer_tag}:{abs(hash(href))}"
        out.append(
            Regulation(
                source_id=sid,
                domain="immigration",
                tier=_classify_tier(href),
                title=title,
                url=href,
                published_at=None,
                body_excerpt="",
                tags=(f"layer:{layer_tag}",),
            )
        )
    return out


def _extract_base_host(url: str) -> str:
    """Return scheme+host from a URL, e.g.
    'https://ngurahrai.imigrasi.go.id/berita-dan-siaran-pers/' →
    'https://ngurahrai.imigrasi.go.id'.
    Used to resolve relative hrefs back to absolute URLs."""
    if not url.startswith("http"):
        return ""
    scheme_end = url.find("://")
    if scheme_end == -1:
        return ""
    host_start = scheme_end + 3
    host_end = url.find("/", host_start)
    if host_end == -1:
        return url
    return url[:host_end]


def _dedupe(regulations: Iterable[Regulation]) -> list[Regulation]:
    seen: set[tuple[str, str]] = set()
    out: list[Regulation] = []
    for r in regulations:
        key = (r.domain, r.source_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


async def fetch_recent_immigration(
    days: int = 30,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list[Regulation]:
    """Fetch immigration news/regs published in the last `days`, deduplicated."""
    own_http = http_client is None
    http = http_client or httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    try:
        layer_imigrasi = await _fetch_url_links(
            http, IMIGRASI_BERITA_URL, "imigrasi", domain_filter="imigrasi.go.id"
        )
        layer_kemenkum = await _fetch_url_links(
            http, KEMENKUM_BERITA_URL, "kemenkum", domain_filter="kemenkum.go.id"
        )
        kanim_results: list[list[Regulation]] = []
        for layer_tag, kanim_url, host_filter in KANIM_BALI_LAYERS:
            kanim_results.append(
                await _fetch_url_links(
                    http, kanim_url, layer_tag, domain_filter=host_filter
                )
            )
        layer_tempo = await _fetch_url_links(
            http, TEMPO_IMIGRASI_TAG_URL, "tempo", domain_filter="tempo.co"
        )
    finally:
        if own_http:
            await http.aclose()

    combined: list[Regulation] = list(layer_imigrasi) + list(layer_kemenkum)
    for kanim_layer in kanim_results:
        combined.extend(kanim_layer)
    combined.extend(layer_tempo)
    deduped = _dedupe(combined)
    in_window = [r for r in deduped if _within_window(r.published_at, days)]
    return in_window


__all__ = [
    "IMMIGRATION_REGEX",
    "KANIM_BALI_LAYERS",
    "KEMENKUM_BERITA_URL",
    "LIFESTYLE_BLOCKLIST",
    "TRUSTED_TIER1_HOSTS",
    "fetch_recent_immigration",
]
