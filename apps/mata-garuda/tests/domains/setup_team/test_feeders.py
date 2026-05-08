"""Feeder tests — Tasks 2/3/4.

Mock httpx.AsyncClient and PasalIdClient. Verify regex filter, dedup,
auth-degradation, tier classification.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mata_garuda.domains.setup_team.feeders.nb_intel_immigration import (
    IMMIGRATION_REGEX,
    LIFESTYLE_BLOCKLIST,
    _matches_immigration_regex,
    fetch_recent_immigration,
)
from mata_garuda.domains.setup_team.feeders.nb_intel_regulation import (
    REGULATION_REGEX,
    _classify_tier,
    _matches_regulation_regex,
    fetch_recent_regulations,
)
from mata_garuda.domains.setup_team.feeders.nb_intel_regulation_bali import (
    BALI_PORTAL_IDS,
    CATEGORY_REGEXES,
    _classify_categories,
    fetch_recent_regulation_bali,
)
from mata_garuda.foundations.gov_apis_health import PortalHealth
from mata_garuda.foundations.pasal_id_client import (
    LawSearchResult,
    PasalIdAuthError,
)


# ---------------- T2: nb_intel_regulation ---------------- #


def test_regex_matches_known_regulation_markers():
    samples = [
        "PMK 81/2024 tentang ...",
        "KEP-71/PJ/2026",
        "PER-7/PJ/2024",
        "PP No 28/2025",
        "Perpres 5/2021",
        "SE-32/PJ/2024",
    ]
    for s in samples:
        assert _matches_regulation_regex(s), f"should match: {s}"


def test_regex_rejects_lifestyle_titles():
    assert not _matches_regulation_regex("Top 10 cafe di Canggu untuk digital nomad")
    assert not _matches_regulation_regex("")
    assert not _matches_regulation_regex("Ulasan film terbaru")


def test_classify_tier_distinguishes_gov_direct_from_press():
    assert _classify_tier("https://setkab.go.id/something") == 1
    assert _classify_tier("https://peraturan.bpk.go.id/x") == 1
    assert _classify_tier("https://jdihn.go.id/x") == 1
    assert _classify_tier("https://www.tempo.co/imigrasi/x") == 2
    assert _classify_tier("") == 2


@pytest.mark.asyncio
async def test_fetch_recent_regulations_swallows_pasal_id_auth_error():
    """When pasal.id is auth-disabled, the layer returns [] but the feeder
    still returns whatever the other layers find."""
    pid = MagicMock()
    pid.search_laws = AsyncMock(side_effect=PasalIdAuthError("no token"))

    http = AsyncMock()
    # JDIHN response — empty body so no links match.
    jdihn_resp = MagicMock(status_code=200, text="<html><body></body></html>")
    setkab_resp = MagicMock(status_code=200, text="<html><body></body></html>")
    http.get = AsyncMock(side_effect=[jdihn_resp, setkab_resp])

    result = await fetch_recent_regulations(
        days=30,
        pasal_id_client=pid,
        http_client=http,
    )
    assert result == []
    pid.search_laws.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_recent_regulations_dedupes_across_layers():
    """Same source_id from two layers — first occurrence wins."""
    pid = MagicMock()
    pid.search_laws = AsyncMock(
        return_value=[
            LawSearchResult(id="uu-2022-27", title="UU 27/2022 PDP", year=2022, kind="UU"),
            LawSearchResult(id="pmk-81", title="PMK 81/2024 Coretax", year=2024, kind="PMK"),
        ]
    )

    http = AsyncMock()
    jdihn_html = """
    <html><body>
    <a href="https://peraturan.go.id/pmk-81">PMK 81/2024 Coretax mirror</a>
    <a href="https://example.com/lifestyle">Top 10 cafe</a>
    </body></html>
    """
    setkab_resp = MagicMock(status_code=200, text="")
    http.get = AsyncMock(
        side_effect=[
            MagicMock(status_code=200, text=jdihn_html),
            setkab_resp,
        ]
    )

    result = await fetch_recent_regulations(
        days=30,
        pasal_id_client=pid,
        http_client=http,
    )
    # Pasal_id returns 2 regs; JDIHN adds 1 (different source_id since prefixed
    # differently — `pasal-id:pmk-81` vs `jdihn:<hash>`). lifestyle filtered
    # out by regex.
    source_ids = {r.source_id for r in result}
    assert "pasal-id:uu-2022-27" in source_ids
    assert "pasal-id:pmk-81" in source_ids
    assert any(sid.startswith("jdihn:") for sid in source_ids)
    # Lifestyle line filtered by regex
    assert not any("cafe" in r.title.lower() for r in result)


@pytest.mark.asyncio
async def test_fetch_recent_regulations_filters_via_regex_fastpath():
    """Items not matching REGULATION_REGEX must be dropped even from pasal.id."""
    pid = MagicMock()
    pid.search_laws = AsyncMock(
        return_value=[
            LawSearchResult(id="x1", title="Random news no marker", year=2026, kind="UU"),
            LawSearchResult(id="x2", title="PMK 50/2026 valid", year=2026, kind="PMK"),
        ]
    )
    http = AsyncMock()
    http.get = AsyncMock(return_value=MagicMock(status_code=200, text=""))

    result = await fetch_recent_regulations(
        days=30,
        pasal_id_client=pid,
        http_client=http,
    )
    titles = [r.title for r in result]
    assert "PMK 50/2026 valid" in titles
    assert "Random news no marker" not in titles


@pytest.mark.asyncio
async def test_fetch_recent_regulations_jdihn_5xx_does_not_kill_other_layers():
    """One layer returning 5xx must not raise."""
    pid = MagicMock()
    pid.search_laws = AsyncMock(
        return_value=[
            LawSearchResult(id="pmk-50", title="PMK 50/2026", year=2026, kind="PMK"),
        ]
    )
    http = AsyncMock()
    http.get = AsyncMock(
        side_effect=[
            MagicMock(status_code=503, text=""),  # JDIHN dead
            MagicMock(status_code=200, text=""),  # setkab fine
        ]
    )

    result = await fetch_recent_regulations(
        days=30,
        pasal_id_client=pid,
        http_client=http,
    )
    assert len(result) == 1
    assert result[0].source_id == "pasal-id:pmk-50"


@pytest.mark.asyncio
async def test_fetch_recent_regulations_returns_regulation_dataclass():
    """Type-contract — caller relies on Regulation fields."""
    pid = MagicMock()
    pid.search_laws = AsyncMock(
        return_value=[LawSearchResult(id="pp-28", title="PP 28/2025 risk-based", year=2025, kind="PP")]
    )
    http = AsyncMock()
    http.get = AsyncMock(return_value=MagicMock(status_code=200, text=""))

    result = await fetch_recent_regulations(pasal_id_client=pid, http_client=http)
    assert len(result) == 1
    r = result[0]
    assert r.domain == "regulation"
    assert r.tier in (1, 2)
    assert r.title == "PP 28/2025 risk-based"
    assert r.url.startswith("https://pasal.id/")
    assert "layer:pasal-id" in r.tags


# ---------------- T3: nb_intel_immigration ---------------- #


def test_immigration_regex_matches_visa_markers():
    samples = [
        "KITAS untuk WNA professional",
        "Aturan baru VITAS",
        "C-313 visa diluncurkan",
        "VOA exit permit prosedur",
        "e-VISA Bali otomatis",
        "imigrasi memperketat aturan",
        "RPTKA WNA pekerja",
    ]
    for s in samples:
        assert _matches_immigration_regex(s), f"should match: {s}"


def test_immigration_regex_rejects_lifestyle():
    assert not _matches_immigration_regex("Top 10 cafe Canggu untuk digital nomad")
    assert not _matches_immigration_regex("Bali tourism review 2026")
    assert not _matches_immigration_regex("KITAS lifestyle gallery")  # blocklist wins
    assert not _matches_immigration_regex("")


@pytest.mark.asyncio
async def test_fetch_recent_immigration_dedupes_and_filters():
    http = AsyncMock()
    imigrasi_html = """
    <html><body>
    <a href="https://www.imigrasi.go.id/berita/123">KITAS baru untuk digital nomad</a>
    <a href="https://www.imigrasi.go.id/berita/456">VOA exit permit aturan</a>
    <a href="https://example.com/ad">Top 10 cafe Canggu lifestyle</a>
    </body></html>
    """
    kemenkum_html = """
    <html><body>
    <a href="https://www.kemenkum.go.id/berita/789">RPTKA WNA pekerja</a>
    </body></html>
    """
    tempo_html = """
    <html><body>
    <a href="https://www.tempo.co/imigrasi/aturan-baru">imigrasi memperketat aturan WNA</a>
    </body></html>
    """
    http.get = AsyncMock(
        side_effect=[
            MagicMock(status_code=200, text=imigrasi_html),
            MagicMock(status_code=200, text=kemenkum_html),
            MagicMock(status_code=200, text=tempo_html),
        ]
    )

    result = await fetch_recent_immigration(days=30, http_client=http)
    titles = [r.title for r in result]
    assert "KITAS baru untuk digital nomad" in titles
    assert "VOA exit permit aturan" in titles
    assert "RPTKA WNA pekerja" in titles
    # Lifestyle filtered (also fails domain_filter for imigrasi.go.id):
    assert not any("cafe" in t.lower() for t in titles)
    # Tier classification: imigrasi.go.id → 1, tempo.co → 2
    by_url = {r.url: r for r in result}
    assert by_url["https://www.imigrasi.go.id/berita/123"].tier == 1
    if "https://www.tempo.co/imigrasi/aturan-baru" in by_url:
        assert by_url["https://www.tempo.co/imigrasi/aturan-baru"].tier == 2


@pytest.mark.asyncio
async def test_fetch_recent_immigration_one_layer_dead_does_not_kill_others():
    http = AsyncMock()
    http.get = AsyncMock(
        side_effect=[
            MagicMock(status_code=503, text=""),  # imigrasi dead
            MagicMock(
                status_code=200,
                text='<a href="https://www.kemenkum.go.id/x">RPTKA aturan</a>',
            ),
            MagicMock(status_code=500, text=""),  # tempo dead
        ]
    )

    result = await fetch_recent_immigration(days=30, http_client=http)
    assert len(result) == 1
    assert result[0].title == "RPTKA aturan"
    assert result[0].domain == "immigration"


@pytest.mark.asyncio
async def test_fetch_recent_immigration_returns_immigration_domain():
    http = AsyncMock()
    http.get = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            text='<a href="https://www.imigrasi.go.id/x">KITAS baru</a>',
        )
    )
    result = await fetch_recent_immigration(http_client=http)
    assert all(r.domain == "immigration" for r in result)
    assert any("layer:imigrasi" in r.tags for r in result)


# ---------------- T4: nb_intel_regulation_bali ---------------- #


def test_bali_category_regexes_classify_correctly():
    assert _classify_categories("Perda PBG sempadan untuk villa") == ("property",)
    assert _classify_categories("Wisata subak Bali aturan baru") == ("bali_tourism",)
    assert _classify_categories("KBLI 79902 izin usaha digital nomad") == ("business",)
    # Multi-category match
    cats = _classify_categories("PBG dan KBLI untuk akomodasi pariwisata")
    assert "property" in cats
    assert "business" in cats
    assert "bali_tourism" in cats
    # No-category
    assert _classify_categories("Random news") == ()
    assert _classify_categories("") == ()


def test_bali_portal_ids_are_the_4_canonical():
    assert BALI_PORTAL_IDS == (
        "jdih_baliprov",
        "jdih_badungkab",
        "jdih_gianyarkab",
        "jdih_denpasarkota",
    )


def test_bali_inventory_contains_all_4_portals():
    """T4 plan note: portals should already be in gov_apis_inventory.json
    from Phase 0. Verify."""
    from mata_garuda.foundations.gov_apis_health import load_inventory

    inv = load_inventory()
    ids = {e["id"] for e in inv}
    for pid in BALI_PORTAL_IDS:
        assert pid in ids, f"Bali portal {pid} missing from inventory"


@pytest.mark.asyncio
async def test_fetch_recent_regulation_bali_skips_dead_portals():
    """probe=True default: only operational portals get scraped."""
    inventory = [
        {"id": "jdih_baliprov", "url": "https://jdih.baliprov.go.id"},
        {"id": "jdih_badungkab", "url": "https://jdih.badungkab.go.id"},
        {"id": "jdih_gianyarkab", "url": "https://jdih.gianyarkab.go.id"},
        {"id": "jdih_denpasarkota", "url": "https://jdih.denpasarkota.go.id"},
    ]
    http = AsyncMock()

    # Probe will be called once per portal (4 calls), then for each operational one,
    # _scrape_portal will call http.get again. We make jdih_baliprov dead, others alive.
    probe_resp_baliprov = MagicMock(status_code=502)  # http_5xx
    probe_resp_badung = MagicMock(status_code=200)
    probe_resp_gianyar = MagicMock(status_code=200)
    probe_resp_denpasar = MagicMock(status_code=200)
    # Now scrape calls
    scrape_badung = MagicMock(
        status_code=200,
        text='<a href="/p/123">Perda PBG sempadan</a>',
    )
    scrape_gianyar = MagicMock(
        status_code=200,
        text='<a href="https://jdih.gianyarkab.go.id/p/9">Wisata subak Ubud</a>',
    )
    scrape_denpasar = MagicMock(
        status_code=200,
        text='<a href="/p/456">KBLI 79902 izin usaha</a>',
    )

    http.get = AsyncMock(
        side_effect=[
            probe_resp_baliprov,
            probe_resp_badung,
            probe_resp_gianyar,
            probe_resp_denpasar,
            scrape_badung,
            scrape_gianyar,
            scrape_denpasar,
        ]
    )

    # Patch the http.AsyncClient used by probe_portal so it shares our mock.
    import mata_garuda.foundations.gov_apis_health as gah
    from unittest.mock import patch

    with patch.object(gah, "httpx") as mock_httpx:
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = http
        mock_cm.__aexit__.return_value = False
        mock_httpx.AsyncClient.return_value = mock_cm
        # Re-export needed exception types so isinstance checks still work
        import httpx as real_httpx

        mock_httpx.ConnectError = real_httpx.ConnectError
        mock_httpx.TimeoutException = real_httpx.TimeoutException

        result = await fetch_recent_regulation_bali(
            days=30,
            http_client=http,
            inventory=inventory,
            probe=True,
        )

    # We should have 3 results — one per operational portal.
    assert len(result) == 3
    domains = {r.domain for r in result}
    assert domains == {"regulation_bali"}
    # Tier 1 for all (all 4 hosts in TRUSTED_TIER1_HOSTS).
    for r in result:
        assert r.tier == 1
    # Categories tagged
    title_to_tags = {r.title: r.tags for r in result}
    assert "property" in title_to_tags["Perda PBG sempadan"]
    assert "bali_tourism" in title_to_tags["Wisata subak Ubud"]
    assert "business" in title_to_tags["KBLI 79902 izin usaha"]


@pytest.mark.asyncio
async def test_fetch_recent_regulation_bali_filters_uncategorized_titles():
    """Without a category match, the link is dropped."""
    inventory = [
        {"id": "jdih_baliprov", "url": "https://jdih.baliprov.go.id"},
    ]
    http = AsyncMock()
    http.get = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            text='<a href="/random">News with no marker</a>'
                 '<a href="/x">Wisata subak Bali</a>',
        )
    )
    result = await fetch_recent_regulation_bali(
        days=30,
        http_client=http,
        inventory=inventory,
        probe=False,  # bypass probe
    )
    titles = [r.title for r in result]
    assert "Wisata subak Bali" in titles
    assert "News with no marker" not in titles


@pytest.mark.asyncio
async def test_fetch_recent_regulation_bali_relative_url_promoted_to_absolute():
    """Relative href like '/p/123' should be normalised to absolute against
    the portal host, otherwise downstream consumers can't resolve it."""
    inventory = [
        {"id": "jdih_badungkab", "url": "https://jdih.badungkab.go.id"},
    ]
    http = AsyncMock()
    http.get = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            text='<a href="/dokumen/perda-PBG-2026">Perda PBG sempadan terbaru</a>',
        )
    )
    result = await fetch_recent_regulation_bali(
        http_client=http, inventory=inventory, probe=False
    )
    assert len(result) == 1
    assert result[0].url == "https://jdih.badungkab.go.id/dokumen/perda-PBG-2026"
    assert result[0].tier == 1


@pytest.mark.asyncio
async def test_fetch_recent_regulation_bali_empty_inventory_returns_empty():
    """If the Phase-0 inventory hasn't been populated with Bali portals,
    return [] without crashing."""
    result = await fetch_recent_regulation_bali(
        http_client=AsyncMock(), inventory=[], probe=False
    )
    assert result == []
