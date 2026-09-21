"""
Guard for pajak_parse.py — pajak.go.id (DJP) now serves regulation/press
hrefs as `/index.php/id/peraturan/<slug>`. The OLD parser (still embedded
below, verbatim, as `_LEGACY_PRIMARY`) anchored on `href="/id/...` and
never matched — Source 1 of pajak_monitor.py returned 0 items silently.

Fixtures under scripts/tests/fixtures/pajak/ are trimmed real pajak.go.id
HTML (index-peraturan and siaran-pers-page), captured 2026-09-21.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pajak"
MODULE_PATH = Path(__file__).parent.parent / "cron-agent-python" / "pajak_parse.py"

spec = importlib.util.spec_from_file_location("pajak_parse", MODULE_PATH)
pajak_parse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pajak_parse)

INDEX_HTML = (FIXTURES_DIR / "index.html").read_text()
SIARAN_HTML = (FIXTURES_DIR / "siaran.html").read_text()

# Verbatim copy of the regression's PRIMARY regex, before this fix
# (pajak_monitor.py, pre-fix _parse_pajak_html) — documents the defect.
_LEGACY_PRIMARY = re.compile(
    r'href="(/id/(?:peraturan|siaran-pers|berita)[^"]+)"[^>]*>[^<]*</a>'
    r'.*?<span[^>]*>([^<]{10,})</span>',
    re.DOTALL | re.IGNORECASE,
)


def test_index_yields_five_rows():
    rows = pajak_parse.parse_peraturan_index(INDEX_HTML)
    assert len(rows) == 5


def test_1488_row_fields_belong_to_its_own_row():
    rows = pajak_parse.parse_peraturan_index(INDEX_HTML)
    row = next(r for r in rows if r["url"].endswith("-1488"))
    assert row["nomor"] == "41/MK/EF.2/2026"
    assert row["jenis"] == "Keputusan Menteri Keuangan"
    assert row["regulation_date"] == "2026-09-01T12:00:00Z"
    assert row["title"].startswith("NILAI KURS")
    assert "8 SEPTEMBER 2026" in row["title"]


def test_no_url_carries_index_php():
    rows = pajak_parse.parse_peraturan_index(INDEX_HTML)
    for row in rows:
        assert "index.php" not in row["url"]


def test_no_title_is_pager_text():
    rows = pajak_parse.parse_peraturan_index(INDEX_HTML)
    for row in rows:
        assert "Halaman sekarang" not in row["title"]


def test_legacy_primary_regex_finds_nothing_on_current_html():
    """Guilt: the pre-fix regex is blind to the /index.php prefix DJP now serves."""
    matches = _LEGACY_PRIMARY.findall(INDEX_HTML)
    assert matches == []


def test_canonical_url_accepts_href_already_in_id_form():
    """Innocence: an href already in the target form canonicalizes unchanged."""
    assert (
        pajak_parse.canonical_pajak_url("/id/peraturan/some-slug")
        == "https://pajak.go.id/id/peraturan/some-slug"
    )


def test_canonical_url_strips_index_php_prefix():
    assert (
        pajak_parse.canonical_pajak_url("/index.php/id/peraturan/some-slug")
        == "https://pajak.go.id/id/peraturan/some-slug"
    )


def test_canonical_url_accepts_absolute_and_www():
    assert (
        pajak_parse.canonical_pajak_url("https://pajak.go.id/index.php/id/peraturan/x")
        == "https://pajak.go.id/id/peraturan/x"
    )
    assert (
        pajak_parse.canonical_pajak_url("https://www.pajak.go.id/id/peraturan/x")
        == "https://pajak.go.id/id/peraturan/x"
    )


def test_siaran_link_items_dedup_and_skip_pager():
    items = pajak_parse.parse_link_items(SIARAN_HTML)
    assert len(items) == 5
    urls = [u for u, _ in items]
    assert len(urls) == len(set(urls))
    for url, title in items:
        assert "index.php" not in url
        assert "Halaman sekarang" not in title


def test_siaran_index_php_href_canonicalizes():
    items = pajak_parse.parse_link_items(SIARAN_HTML)
    url, _ = items[0]
    assert url == "https://pajak.go.id/id/siaran-pers/djp-catat-penerimaan-pajak-ekonomi-digital-rp5723-triliun"


def test_a_short_chrome_link_never_shadows_the_headline_that_follows_it():
    html = (
        '<a href="/index.php/id/siaran-pers/djp-rilis-aturan-baru-pph">Detail</a>'
        '<a href="/id/siaran-pers/djp-rilis-aturan-baru-pph">DJP Rilis Aturan Baru PPh Pasal 22</a>'
    )
    assert pajak_parse.parse_link_items(html) == [
        (
            "https://pajak.go.id/id/siaran-pers/djp-rilis-aturan-baru-pph",
            "DJP Rilis Aturan Baru PPh Pasal 22",
        )
    ]


def test_an_english_twin_is_not_a_second_item():
    html = (
        '<a href="/index.php/en/siaran-pers/djp-releases-new-rule">DJP Releases New Income Tax Rule</a>'
        '<a href="/id/siaran-pers/djp-rilis-aturan-baru">DJP Rilis Aturan Baru PPh Pasal 22</a>'
    )
    assert [u for u, _ in pajak_parse.parse_link_items(html)] == [
        "https://pajak.go.id/id/siaran-pers/djp-rilis-aturan-baru"
    ]


# ─── source_host — the label a Source-3 (Brave web_search) item gets in ────
# `intel_lake` `source_domain`, not the pajak.go.id job that fetched it.


def test_source_host_pajak_variants():
    assert pajak_parse.source_host("https://pajak.go.id/id/peraturan/x") == "pajak.go.id"
    assert pajak_parse.source_host("https://www.pajak.go.id/id/peraturan/x") == "pajak.go.id"
    assert (
        pajak_parse.source_host("https://PAJAK.GO.ID/index.php/id/peraturan/x")
        == "pajak.go.id"
    )


def test_source_host_press_and_consulting_sites():
    assert (
        pajak_parse.source_host("https://www.cnbcindonesia.com/news/x")
        == "cnbcindonesia.com"
    )
    assert (
        pajak_parse.source_host("https://bangka.tribunnews.com/news/1")
        == "bangka.tribunnews.com"
    )


def test_source_host_drops_port():
    assert pajak_parse.source_host("http://example.com:8080/a") == "example.com"


def test_source_host_returns_empty_for_unparseable_value():
    assert pajak_parse.source_host("nb: NB-INTEL-Tax") == ""


def test_monitor_source_text_no_longer_hardcodes_pajak_domain():
    """pajak_monitor.py cannot be imported here (agent_job/browser_job are
    not in this repo) — read its source text instead."""
    monitor_path = Path(__file__).parent.parent / "cron-agent-python" / "pajak_monitor.py"
    text = monitor_path.read_text()
    assert '"source_domain": "pajak.go.id"' not in text
    assert "source_host(" in text
