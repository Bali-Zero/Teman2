"""NB-INTEL-Regulation-Bali sub-stream — 4 jdih portals (Task 4).

Sources (R2 confirmed 90% client coverage):
  - jdih.baliprov.go.id   (provincial)
  - jdih.badungkab.go.id  (kabupaten Badung — Canggu/Kuta/Seminyak)
  - jdih.gianyarkab.go.id (kabupaten Gianyar — Ubud/Sanur/Tegallalang)
  - jdih.denpasarkota.go.id (kota Denpasar)

Already in apps/mata-garuda/data/gov_apis_inventory.json with ids
`jdih_baliprov`, `jdih_badungkab`, `jdih_gianyarkab`, `jdih_denpasarkota`.

Probe each portal via foundations.gov_apis_health.probe_portal BEFORE scraping
— if a portal is dns_failure / cf_challenge / 5xx, skip its layer entirely.
This avoids the false-positive "no Bali regs today" when really 2/4 portals
are dead. The probe results carry forward in the Regulation.tags so a
downstream consumer can decide whether to retry vs alert.

Scorer fast-path categories (per R2):
  bali_tourism: wisata|subak|krama|desa adat|akomodasi pariwisata
  property:     PBG|SLF|sempadan|zonasi|RTH
  business:     KBLI|izin usaha|UMKM
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Iterable

import httpx

from mata_garuda.domains.setup_team.types import Regulation
from mata_garuda.foundations.gov_apis_health import (
    PortalHealth,
    load_inventory,
    probe_portal,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 20.0

# 8 Bali jdih portals + 2 Pemkab homepage fallbacks
# (Phase 1.5 PR-B 2026-05-08: expanded from 4 to 10. The 4 added jdih are
# Tabanan/Buleleng/Klungkung/Karangasem. The 2 Pemkab fallbacks are Bangli
# and Jembrana — their dedicated jdih.<kab>.go.id subdomains DNS-fail or
# timeout from this network, so we scrape Pemkab homepage news instead.)
#
# All 10 entries must exist in gov_apis_inventory.json — load_inventory()
# is the source of truth.
BALI_PORTAL_IDS = (
    # Original 4 jdih (Phase 1).
    "jdih_baliprov",
    "jdih_badungkab",
    "jdih_gianyarkab",
    "jdih_denpasarkota",
    # New jdih (Phase 1.5 PR-B, all verified live 200 on 2026-05-08).
    "jdih_tabanankab",
    "jdih_bulelengkab",
    "jdih_klungkungkab",
    "jdih_karangasemkab",
    # Pemkab homepage fallbacks (the dedicated jdih subdomain was DNS-fail
    # or timeout on 2026-05-08; the Pemkab homepage carries enough Perda/
    # Perbup news in its /berita or /articles section to not lose coverage).
    "pemkab_bangli",
    "pemkab_jembrana",
)

# Tier-1 trusted: all 10 are gov direct (.go.id under provincia/kabupaten/kota).
TRUSTED_TIER1_HOSTS = {
    "jdih.baliprov.go.id",
    "jdih.badungkab.go.id",
    "jdih.gianyarkab.go.id",
    "jdih.denpasarkota.go.id",
    "jdih.tabanankab.go.id",
    "jdih.bulelengkab.go.id",
    "jdih.klungkungkab.go.id",
    "jdih.karangasemkab.go.id",
    "banglikab.go.id",
    "jembranakab.go.id",
}

CATEGORY_REGEXES = {
    "bali_tourism": re.compile(
        r"\b(wisata|subak|krama|desa adat|akomodasi pariwisata)\b", re.IGNORECASE
    ),
    "property": re.compile(r"\b(PBG|SLF|sempadan|zonasi|RTH)\b", re.IGNORECASE),
    "business": re.compile(r"\b(KBLI|izin usaha|UMKM)\b", re.IGNORECASE),
}


def _classify_categories(text: str) -> tuple[str, ...]:
    """Return the matching category tags, or () if none match."""
    if not text:
        return ()
    return tuple(name for name, pattern in CATEGORY_REGEXES.items() if pattern.search(text))


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


def _select_bali_portals(inventory: list[dict]) -> list[dict]:
    """Pull only the 4 Bali jdih entries from the shared inventory."""
    by_id = {e["id"]: e for e in inventory}
    return [by_id[pid] for pid in BALI_PORTAL_IDS if pid in by_id]


async def _scrape_portal(
    http: httpx.AsyncClient, entry: dict
) -> list[Regulation]:
    """Best-effort link harvester for one Bali jdih portal."""
    url = entry["url"]
    portal_id = entry["id"]
    out: list[Regulation] = []
    try:
        resp = await http.get(url)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("Bali portal %s scrape failed: %s", portal_id, exc)
        return out
    if resp.status_code != 200:
        logger.warning("Bali portal %s returned %s", portal_id, resp.status_code)
        return out

    body = resp.text
    link_re = re.compile(
        r'<a[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>[^<]+)</a>',
        re.IGNORECASE,
    )
    seen: set[str] = set()
    for m in link_re.finditer(body):
        href = m.group("url").strip()
        title = m.group("title").strip()
        if href in seen:
            continue
        seen.add(href)
        cats = _classify_categories(title)
        if not cats:
            continue
        # Make absolute URL when href is relative
        if href.startswith("/"):
            host = url.rstrip("/")
            href_abs = f"{host}{href}"
        else:
            href_abs = href
        sid = f"{portal_id}:{abs(hash(href_abs))}"
        out.append(
            Regulation(
                source_id=sid,
                domain="regulation_bali",
                tier=_classify_tier(href_abs),
                title=title,
                url=href_abs,
                published_at=None,
                body_excerpt="",
                tags=(f"layer:{portal_id}", *cats),
            )
        )
    return out


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


async def fetch_recent_regulation_bali(
    days: int = 30,
    *,
    http_client: httpx.AsyncClient | None = None,
    inventory: list[dict] | None = None,
    probe: bool = True,
) -> list[Regulation]:
    """Fetch Bali regulations published in the last `days`, deduplicated.

    Args:
        days: window for date filtering (best-effort — most jdih HTML doesn't
              expose published_at structured).
        http_client: dependency-inject for tests.
        inventory: dependency-inject for tests; defaults to gov_apis_inventory.json.
        probe: if True (default), probe each portal first via probe_portal()
               and skip layers whose status != 'operational'. Set to False
               in tests that want to bypass the probe.

    Returns:
        list[Regulation] with domain='regulation_bali'.
    """
    if inventory is None:
        inventory = load_inventory()
    bali_entries = _select_bali_portals(inventory)
    if not bali_entries:
        logger.warning("No Bali portals in inventory — Phase 0 inventory missing")
        return []

    own_http = http_client is None
    http = http_client or httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    try:
        live_entries: list[dict] = []
        if probe:
            for entry in bali_entries:
                health: PortalHealth = await probe_portal(entry)
                if health.status == "operational":
                    live_entries.append(entry)
                else:
                    logger.info(
                        "Bali portal %s is %s (http=%s) — skipping layer",
                        entry["id"],
                        health.status,
                        health.http_code,
                    )
        else:
            live_entries = bali_entries

        all_regs: list[Regulation] = []
        for entry in live_entries:
            layer = await _scrape_portal(http, entry)
            all_regs.extend(layer)
    finally:
        if own_http:
            await http.aclose()

    deduped = _dedupe(all_regs)
    in_window = [r for r in deduped if _within_window(r.published_at, days)]
    return in_window


__all__ = [
    "BALI_PORTAL_IDS",
    "CATEGORY_REGEXES",
    "TRUSTED_TIER1_HOSTS",
    "fetch_recent_regulation_bali",
]
