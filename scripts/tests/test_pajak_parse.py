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


# ─── D1 — HTML entities in titles must be unescaped ────────────────────────


def test_index_title_unescapes_html_entities():
    """Guilt: `&amp;` (and friends) in a `views-field-title` span must decode to `&`, not
    survive as a literal entity — an entity is a markup artifact, not part of the title."""
    html_row = (
        '<div class="peraturan-content views-row row-1">'
        '<div class="views-field views-field-field-nomor-dokumen">'
        '<h3 class="field-content title-custom text-link">'
        '<a href="/index.php/id/peraturan/ppn-dan-pph-terbaru" hreflang="id">99/PMK.02/2026</a>'
        "</h3></div>"
        '<div class="views-field views-field-title">'
        '<span class="field-content content-custom">PPN &amp; PPh Terbaru</span>'
        "</div>"
        '<span class="views-field views-field-field-jenis-dokumen">'
        '<strong class="field-content">Peraturan Menteri Keuangan</strong></span>'
        ' | <span class="views-field views-field-field-tanggal-peraturan">'
        '<strong class="field-content">'
        '<time datetime="2026-09-10T12:00:00Z" class="datetime">2026-09-10</time>'
        "</strong></span>"
        ' | <span class="views-field views-field-field-status-peraturan">'
        '<strong class="field-content">Aktif</strong></span>'
        "</div>"
    )
    rows = pajak_parse.parse_peraturan_index(html_row)
    assert len(rows) == 1
    assert rows[0]["title"] == "PPN & PPh Terbaru"


def _index_row(href: str, nomor: str, title: str) -> str:
    """One `peraturan-content views-row` block, same shape as the real fixture rows."""
    return (
        '<div class="peraturan-content views-row">'
        '<div class="views-field views-field-field-nomor-dokumen">'
        f'<h3 class="field-content title-custom text-link">'
        f'<a href="{href}" hreflang="id">{nomor}</a></h3></div>'
        '<div class="views-field views-field-title">'
        f'<span class="field-content content-custom">{title}</span></div>'
        '<span class="views-field views-field-field-jenis-dokumen">'
        '<strong class="field-content">Peraturan Menteri Keuangan</strong></span>'
        ' | <span class="views-field views-field-field-tanggal-peraturan">'
        '<strong class="field-content">'
        '<time datetime="2026-09-10T12:00:00Z" class="datetime">2026-09-10</time>'
        "</strong></span>"
        ' | <span class="views-field views-field-field-status-peraturan">'
        '<strong class="field-content">Aktif</strong></span>'
        "</div>"
    )


# ─── dedup — pinned to the canonical URL, not raw href or nomor (#7125 G8) ─


def test_index_dedups_by_canonical_url_even_when_raw_hrefs_differ():
    """Guilt (#7125 G8: dedup removed from `parse_peraturan_index` survived every prior test).
    Two blocks whose hrefs canonicalise to the SAME url (one `/index.php`-prefixed, one not) —
    but with DIFFERENT nomor values, so a nomor-keyed dedup would NOT collapse them — must
    still yield exactly one item: the FIRST block's fields, page order preserved."""
    html_dup = _index_row(
        "/index.php/id/peraturan/ppn-dan-pph-terbaru", "99/PMK.02/2026", "PPN Dan PPh Terbaru"
    ) + _index_row(
        "/id/peraturan/ppn-dan-pph-terbaru", "00/DUPLICATE/9999", "Should Be Ignored"
    )
    rows = pajak_parse.parse_peraturan_index(html_dup)
    assert len(rows) == 1
    assert rows[0]["url"] == "https://pajak.go.id/id/peraturan/ppn-dan-pph-terbaru"
    assert rows[0]["nomor"] == "99/PMK.02/2026"
    assert rows[0]["title"] == "PPN Dan PPh Terbaru"


def test_index_does_not_dedup_rows_with_the_same_nomor_but_different_url():
    """Innocence: two DISTINCT regulations that happen to share a nomor value must NOT be
    collapsed — proves the dedup key is the url, not the nomor."""
    html_two = _index_row(
        "/id/peraturan/ppn-dan-pph-terbaru", "99/PMK.02/2026", "PPN Dan PPh Terbaru"
    ) + _index_row(
        "/id/peraturan/pbjt-baru", "99/PMK.02/2026", "PBJT Baru"
    )
    rows = pajak_parse.parse_peraturan_index(html_two)
    assert len(rows) == 2
    assert {r["url"] for r in rows} == {
        "https://pajak.go.id/id/peraturan/ppn-dan-pph-terbaru",
        "https://pajak.go.id/id/peraturan/pbjt-baru",
    }


def test_index_title_without_entities_is_unchanged():
    """Innocence: a real fixture title with no entities passes through byte-for-byte."""
    rows = pajak_parse.parse_peraturan_index(INDEX_HTML)
    row = next(r for r in rows if r["url"].endswith("-1488"))
    assert row["title"] == (
        "NILAI KURS SEBAGAI DASAR PELUNASAN BEA MASUK, PAJAK PERTAMBAHAN NILAI BARANG DAN "
        "JASA DAN PAJAK PENJUALAN ATAS BARANG MEWAH, BEA KELUAR, DAN PAJAK PENGHASILAN YANG "
        "BERLAKU UNTUK TANGGAL 2 SEPTEMBER 2026 SAMPAI DENGAN 8 SEPTEMBER 2026"
    )


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


def test_canonical_url_matches_scheme_and_host_case_insensitively():
    """Gate-7125 survivor G5 (host regex without `re.IGNORECASE`): scheme and host are
    case-insensitive, so an upper-cased absolute href must canonicalise to the same identity
    instead of being kept whole as a path under the pajak domain."""
    assert (
        pajak_parse.canonical_pajak_url("HTTPS://WWW.PAJAK.GO.ID/index.php/id/peraturan/x")
        == "https://pajak.go.id/id/peraturan/x"
    )


# ─── D2 — trailing slash and query string normalise to the same identity ──


def test_canonical_url_normalizes_trailing_slash():
    """Guilt: a trailing slash must not survive as a distinct identity."""
    assert (
        pajak_parse.canonical_pajak_url("https://pajak.go.id/id/peraturan/x/")
        == "https://pajak.go.id/id/peraturan/x"
    )


def test_canonical_url_normalizes_query_string():
    """Guilt: a tracking query string must not survive as a distinct identity."""
    assert (
        pajak_parse.canonical_pajak_url("https://pajak.go.id/id/peraturan/x?utm=1")
        == "https://pajak.go.id/id/peraturan/x"
    )


def test_canonical_url_normalizes_trailing_slash_and_query_together():
    assert (
        pajak_parse.canonical_pajak_url("https://pajak.go.id/index.php/id/peraturan/x/?utm=1")
        == "https://pajak.go.id/id/peraturan/x"
    )


def test_canonical_url_different_slug_still_differs():
    """Innocence: normalisation must not collapse two genuinely different URLs."""
    a = pajak_parse.canonical_pajak_url("https://pajak.go.id/id/peraturan/x/")
    b = pajak_parse.canonical_pajak_url("https://pajak.go.id/id/peraturan/y?utm=1")
    assert a != b
    assert a == "https://pajak.go.id/id/peraturan/x"
    assert b == "https://pajak.go.id/id/peraturan/y"


def test_canonical_url_root_path_trailing_slash_not_stripped_to_empty():
    """Innocence: the trailing-slash strip must not eat the root path's own `/`."""
    assert pajak_parse.canonical_pajak_url("https://pajak.go.id/") == "https://pajak.go.id/"


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


def test_link_items_unescape_html_entities():
    """Guilt: an entity in a siaran-pers headline anchor text must decode to `&`."""
    html = (
        '<a href="/index.php/id/siaran-pers/djp-catat-penerimaan-pajak-ekonomi-digital">'
        "DJP Catat Penerimaan Pajak Tumbuh 5,7% &amp; Ekonomi Digital"
        "</a>"
    )
    items = pajak_parse.parse_link_items(html)
    assert items == [
        (
            "https://pajak.go.id/id/siaran-pers/djp-catat-penerimaan-pajak-ekonomi-digital",
            "DJP Catat Penerimaan Pajak Tumbuh 5,7% & Ekonomi Digital",
        )
    ]


def test_link_items_without_entities_are_unchanged():
    """Innocence: the real fixture's entity-free headline passes through byte-for-byte."""
    items = pajak_parse.parse_link_items(SIARAN_HTML)
    url, title = items[0]
    assert title == "DJP Catat Penerimaan Pajak Ekonomi Digital Rp57,23 Triliun"


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


# ─── extract_regulation — peraturan DETAIL page (citation + excerpt) ───────
#
# DETAIL_HTML is a trimmed real pajak.go.id peraturan page (Keputusan
# Menteri Keuangan Nomor 21/MK/EF.2/2026, captured 2026-09-21): the four
# `field--name-field-*` containers this function reads, kept intact.

DETAIL_HTML = (FIXTURES_DIR / "detail.html").read_text()


def _synthetic_detail_html(*, jenis: str, nomor: str, body_inner: str, with_tanggal: bool = True) -> str:
    tanggal = (
        '<div class="field field--name-field-tanggal-peraturan">'
        '<div class="field__item"><time datetime="2026-01-15T12:00:00Z">15-01-2026</time></div>'
        "</div>"
        if with_tanggal
        else ""
    )
    return (
        f'<div class="field field--name-field-jenis-dokumen">{jenis}</div>'
        f'<div class="field field--name-field-nomor-dokumen">{nomor}</div>'
        f"{tanggal}"
        f'<div class="field field--name-field-body-dalam-html">{body_inner}</div>'
    )


def test_extract_regulation_on_real_fixture():
    result = pajak_parse.extract_regulation(DETAIL_HTML)
    assert result["citation"] == "KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 21/MK/EF.2/2026"
    assert result["citation"] in result["verbatim_excerpt"]
    assert result["regulation_date"] == "2026-05-12T12:00:00Z"
    assert result["jenis"] == "Keputusan Menteri Keuangan"
    assert result["nomor"] == "21/MK/EF.2/2026"


def test_extract_regulation_excerpt_stops_before_menimbang():
    result = pajak_parse.extract_regulation(DETAIL_HTML)
    assert "menimbang" not in result["verbatim_excerpt"].lower()
    assert len(result["verbatim_excerpt"]) <= 700


def test_extract_regulation_falls_back_to_nomor_only_heading():
    """The jenis+nomor heading is absent from the body; the NOMOR-only fallback still finds a
    literal citation."""
    html = _synthetic_detail_html(
        jenis="Peraturan Menteri Keuangan",
        nomor="99/PMK.02/2026",
        body_inner="TENTANG TATA CARA<br />NOMOR 99/PMK.02/2026<br />Menimbang: a. bahwa perlu.",
    )
    result = pajak_parse.extract_regulation(html)
    assert result["citation"] == "NOMOR 99/PMK.02/2026"
    assert result["citation"] in result["verbatim_excerpt"]
    assert "menimbang" not in result["verbatim_excerpt"].lower()


def test_extract_regulation_returns_none_citation_when_nomor_not_in_body():
    """Never fabricate: if the nomor does not occur in the body at all, citation and excerpt
    are both None — fields are still returned from their own containers."""
    html = _synthetic_detail_html(
        jenis="Peraturan Menteri Keuangan",
        nomor="99/PMK.02/2026",
        body_inner="Some unrelated body text with no regulation number in it.",
    )
    result = pajak_parse.extract_regulation(html)
    assert result["citation"] is None
    assert result["verbatim_excerpt"] is None
    assert result["nomor"] == "99/PMK.02/2026"
    assert result["jenis"] == "Peraturan Menteri Keuangan"


def test_extract_regulation_returns_none_when_body_field_absent():
    html = (
        '<div class="field field--name-field-jenis-dokumen">Peraturan Menteri Keuangan</div>'
        '<div class="field field--name-field-nomor-dokumen">99/PMK.02/2026</div>'
    )
    assert pajak_parse.extract_regulation(html) is None


def test_extract_regulation_word_boundary_cutoff_under_700_chars_with_no_menimbang():
    """No Menimbang/Mengingat anywhere: cut at 700 chars, at a word boundary (never mid-word)."""
    filler = " ".join(f"kata{i}" for i in range(300))  # far more than 700 chars, no cut keyword
    html = _synthetic_detail_html(
        jenis="Peraturan Menteri Keuangan",
        nomor="1/PMK.02/2026",
        body_inner=f"PERATURAN MENTERI KEUANGAN NOMOR 1/PMK.02/2026 TENTANG {filler}",
    )
    result = pajak_parse.extract_regulation(html)
    assert len(result["verbatim_excerpt"]) <= 700
    assert result["citation"] in result["verbatim_excerpt"]
    # Word-boundary cut: the excerpt does not end mid-token of the filler.
    assert not result["verbatim_excerpt"].endswith("kata")
    tail = result["verbatim_excerpt"].rsplit(" ", 1)[-1]
    assert tail == "" or tail.startswith("kata") and tail[4:].isdigit() or tail == "TENTANG"


# ─── guilt/innocence — the property `admit()` actually enforces ───────────


def test_innocence_real_citation_is_always_a_literal_token_of_its_excerpt():
    result = pajak_parse.extract_regulation(DETAIL_HTML)
    excerpt = result["verbatim_excerpt"]
    citation = result["citation"]
    start = excerpt.find(citation)
    assert start >= 0
    end = start + len(citation)
    before = excerpt[start - 1] if start > 0 else ""
    after = excerpt[end] if end < len(excerpt) else ""
    assert not before.isalnum()
    assert not after.isalnum()


def test_guilt_naive_titlecase_citation_is_not_a_literal_substring():
    """Guilt: concatenating the jenis/nomor FIELD values (title case, as the Drupal fields
    themselves are cased) instead of reading the body's own upper-case characters produces a
    string that is NOT a literal substring of the excerpt — exactly the defect
    `_statement_is_from_source` (intel_evidence_bridge) rejects as `statement_not_from_source`.
    This is why `extract_regulation` takes the body's own characters, never jenis+nomor field
    values directly."""
    result = pajak_parse.extract_regulation(DETAIL_HTML)
    naive_citation = f"{result['jenis']} Nomor {result['nomor']}"
    assert naive_citation not in result["verbatim_excerpt"]
    assert result["citation"] in result["verbatim_excerpt"]


def test_guilt_excerpt_slice_after_citation_no_longer_contains_it():
    """Guilt: a wrongly-sliced excerpt (starting AFTER the citation) fails the very property
    `extract_regulation` guarantees for its own real output."""
    result = pajak_parse.extract_regulation(DETAIL_HTML)
    citation = result["citation"]
    broken_excerpt = result["verbatim_excerpt"][len(citation):]
    assert citation not in broken_excerpt
    assert citation in result["verbatim_excerpt"]


# ─── R2 — nomor needs a trailing boundary, not just re.escape ─────────────


def test_r2_guilt_short_nomor_does_not_swallow_a_longer_number():
    """Guilt: without a trailing boundary, nomor `12` matches the PREFIX of body `NOMOR 123
    TAHUN 2026`, producing the wrong citation `...NOMOR 12`. With the boundary, neither the
    heading nor the NOMOR-only fallback may match a nomor that is itself a prefix of a longer
    digit run — citation must stay None, never the truncated wrong string."""
    html = _synthetic_detail_html(
        jenis="Peraturan Pemerintah",
        nomor="12",
        body_inner="PERATURAN PEMERINTAH NOMOR 123 TAHUN 2026 TENTANG SESUATU. Menimbang: a. bahwa.",
    )
    result = pajak_parse.extract_regulation(html)
    assert result["citation"] is None
    assert result["verbatim_excerpt"] is None


def test_r2_guilt_truncated_nomor_is_not_a_delimited_prefix_match():
    """Guilt: without a trailing boundary, nomor `PMK-81` matches the prefix of body `NOMOR
    PMK-81/2024` — delimited by `/`, so admission would ADMIT this truncated, wrong citation.
    The boundary must reject a nomor immediately followed by a separator that itself continues
    into another alnum char."""
    html = _synthetic_detail_html(
        jenis="Peraturan Menteri Keuangan",
        nomor="PMK-81",
        body_inner="PERATURAN MENTERI KEUANGAN NOMOR PMK-81/2024 TENTANG SESUATU. Menimbang: a. bahwa.",
    )
    result = pajak_parse.extract_regulation(html)
    assert result["citation"] is None
    assert result["verbatim_excerpt"] is None


def test_r2_innocence_exact_nomor_still_matches_at_end_of_sentence():
    """The boundary must not reject a real, exact nomor match followed by ordinary punctuation
    or whitespace — only a same-token continuation."""
    html = _synthetic_detail_html(
        jenis="Peraturan Pemerintah",
        nomor="12",
        body_inner="PERATURAN PEMERINTAH NOMOR 12 TAHUN 2026 TENTANG SESUATU. Menimbang: a. bahwa.",
    )
    result = pajak_parse.extract_regulation(html)
    assert result["citation"] == "PERATURAN PEMERINTAH NOMOR 12"
    assert result["citation"] in result["verbatim_excerpt"]


# ─── M4 — re.escape(nomor) must treat metacharacters as literal ───────────


def test_m4_guilt_nomor_metacharacter_is_literal_not_a_regex_wildcard():
    """Guilt: if `re.escape(nomor)` were dropped, the `.` in nomor `PMK-81.2024` becomes a regex
    wildcard matching ANY character — so it would wrongly also match body text where that
    position holds a different character (`PMK-81X2024`, no literal dot at all). With escaping,
    only the literal string matches."""
    exact_match_html = _synthetic_detail_html(
        jenis="Peraturan Menteri Keuangan",
        nomor="PMK-81.2024",
        body_inner="PERATURAN MENTERI KEUANGAN NOMOR PMK-81.2024 TENTANG SESUATU. Menimbang: a. bahwa.",
    )
    exact_result = pajak_parse.extract_regulation(exact_match_html)
    assert exact_result["citation"] == "PERATURAN MENTERI KEUANGAN NOMOR PMK-81.2024"

    wildcard_bait_html = _synthetic_detail_html(
        jenis="Peraturan Menteri Keuangan",
        nomor="PMK-81.2024",
        body_inner="PERATURAN MENTERI KEUANGAN NOMOR PMK-81X2024 TENTANG SESUATU. Menimbang: a. bahwa.",
    )
    wildcard_result = pajak_parse.extract_regulation(wildcard_bait_html)
    assert wildcard_result["citation"] is None


def test_m4_innocence_nomor_with_slashes_still_matches_literally():
    """A real DJP nomor like `KEP-185/PJ/2026` (`/` has no regex meaning, but is exactly the
    kind of value a dropped `re.escape` bug report would target) still matches its own literal
    body occurrence."""
    html = _synthetic_detail_html(
        jenis="Keputusan Direktur Jenderal Pajak",
        nomor="KEP-185/PJ/2026",
        body_inner="KEPUTUSAN DIREKTUR JENDERAL PAJAK NOMOR KEP-185/PJ/2026 TENTANG SESUATU. Menimbang: a. bahwa.",
    )
    result = pajak_parse.extract_regulation(html)
    assert result["citation"] == "KEPUTUSAN DIREKTUR JENDERAL PAJAK NOMOR KEP-185/PJ/2026"
    assert result["citation"] in result["verbatim_excerpt"]


# ─── #7087 C2 — excerpt must anchor at the regex match, not body_text.find() ──


def test_c2_guilt_excerpt_anchors_to_the_match_not_the_first_literal_occurrence():
    """Guilt (#7087 C2): the same literal citation string `NOMOR PMK-81` occurs TWICE in the
    body — once as the boundary-REJECTED prefix of a longer, unrelated number (`NOMOR
    PMK-81/2024`), and once as the real, boundary-matching citation later in the text. The
    regex correctly skips the first (rejected by `_NOMOR_BOUNDARY`) and matches the second —
    but `body_text.find(citation)` would find the FIRST literal occurrence of the substring
    `"NOMOR PMK-81"` regardless (it IS a literal prefix of `"NOMOR PMK-81/2024"`), anchoring the
    excerpt on the wrong, unrelated regulation. The excerpt must start at the match's own
    `m.start()`."""
    html = _synthetic_detail_html(
        jenis="Peraturan Menteri Keuangan",  # deliberately absent from body_inner: forces fallback
        nomor="PMK-81",
        body_inner=(
            "SURAT SESUATU NOMOR PMK-81/2024. "
            "KEPUTUSAN LAIN NOMOR PMK-81 TENTANG LAINNYA. Menimbang: a. bahwa."
        ),
    )
    result = pajak_parse.extract_regulation(html)
    assert result["citation"] == "NOMOR PMK-81"
    assert result["verbatim_excerpt"] == "NOMOR PMK-81 TENTANG LAINNYA."
    assert "/2024" not in result["verbatim_excerpt"]
    assert "SESUATU" not in result["verbatim_excerpt"]
