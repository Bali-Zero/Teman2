"""Guilt and innocence on the Koperasi/UMKM reservation axis.

Two things are pinned here, and they fail in opposite directions.

The PARSER is a compiler over a corrupted text layer, so its two derived
constants — the substitution table and the column split — are the whole method.
A change to either silently re-reads the law, so both are exercised on the
decisive shapes rather than on the happy path.

The RELATION is a reporter whose buckets carry the meaning. The regression it
exists to prevent is collapsing KEMITRAAN into DIALOKASIKAN: a partnership duty
is not a bar, and asserting one on those 57 rows is the same over-match
`kbli_eye.is_umkm_reserved` carried until 2026-07-27.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

from parse_perpres_lampiran2 import (  # noqa: E402
    COLUMN_SPLIT_X,
    IMAGE_READ,
    SUBSTITUTIONS,
    content_words,
    decode,
    governing_headings,
    parse,
)
from perpres_umkm_reservation_relation import (  # noqa: E402
    RELATION,
    _PARENT_QUALIFIER_RE,
    classify,
    live_heirs,
    load_canonical,
    load_crosswalk,
    foreign_can_take,
    load_relation,
    report,
)

# A tick line is column-positional: text, then the KBLI cell, then the V.
def _line(text: str, code: str, tick_x: int) -> str:
    left = f"{text}".ljust(tick_x - 12)[: tick_x - 12]
    return f"{left}{code.ljust(11)}"[:tick_x] .ljust(tick_x) + "V"


_TITLES = {"01122": "Pertanian Padi Inbrida", "10392": "Industri Tahu Kedelai",
           "47111": "Perdagangan Eceran Berbagai Macam Barang"}
_KNOWN = frozenset(_TITLES)


# ---------------------------------------------------------------- parser

def test_substitution_table_is_a_function_never_ambiguous():
    """Each corrupted glyph maps to exactly one digit — the property that made
    deriving the table legitimate. A second mapping for any key would mean the
    inversion is not decidable and every decoded code becomes a guess."""
    assert all(len(v) == 1 and v.isdigit() for v in SUBSTITUTIONS.values())
    assert len(SUBSTITUTIONS) == len(set(SUBSTITUTIONS))


def test_decode_inverts_the_observed_corruptions():
    assert decode("oLt22") == "01122"     # 0->o, 1->L, 1->t
    assert decode("to392") == "10392"
    assert decode("47ttt") == "47111"     # the row that a contiguous-token regex missed


def test_decode_leaves_surviving_digits_untouched():
    """INNOCENCE — the table must never rewrite a digit that arrived intact."""
    assert decode("13122") == "13122"


def test_tick_left_of_the_split_is_the_reservation_column():
    out = parse(_line("Padi inbrida", "oLt22", 93), _TITLES, _KNOWN)
    assert [r["column"] for r in out["rows"]] == ["dialokasikan"]


def test_tick_right_of_the_split_is_partnership_not_reservation():
    """INNOCENCE — THE regression this axis exists to avoid. A tick in the
    second cluster is a KEMITRAAN duty; reading it as a reservation invents a
    foreign-ownership bar out of a partnership obligation."""
    out = parse(_line("Padi inbrida", "oLt22", 108), _TITLES, _KNOWN)
    assert [r["column"] for r in out["rows"]] == ["kemitraan"]
    assert COLUMN_SPLIT_X == 105  # inside the measured empty band 101..107


def test_code_is_read_from_the_right_edge_of_the_window():
    """The KBLI cell abuts the tick; bidang usaha text SPILLS into the same
    window. Anchoring left takes the spill and produces no code — that
    under-match cost 33 rows before it was found.

    The text here is long enough that its tail genuinely lands inside the
    45-char window: with a short label the two anchors coincide and this test
    passes against the very defect it names (measured — it did).
    """
    spilling = "kulit kayu lawang, kayu manis dan getah-getahan lainnya, sarang"
    line = _line(spilling, "o23o9", 93)
    assert "sarang" in line[93 - 45:93], "fixture no longer exercises the spill"
    out = parse(line, {"02309": "Pertanian Tanaman Rempah"}, frozenset({"02309"}))
    assert [r["code"] for r in out["rows"]] == ["02309"]


def test_a_code_no_catalogue_knows_is_unresolved_never_a_row():
    """GUILT — a 5-digit string that decodes cleanly is still not a code. The
    membership test is what stops a stray number in the prose from being
    reported as law."""
    out = parse(_line("Industri kerupuk", "70794", 93), _TITLES, _KNOWN)
    assert out["rows"] == []
    assert [u["page"] for u in out["unresolved"]] == [1]


def test_a_line_with_no_tick_is_not_a_row():
    """INNOCENCE — the annex is mostly prose and headers; only a tick makes a
    row, and a code appearing in running text must not manufacture one."""
    assert parse("        oLt22 appears in a heading\n", _TITLES, _KNOWN)["rows"] == []


# --------------------------------------------------- multi-line table rows

# The page-7 shape, verbatim in structure: a tall cell whose tick, code and text
# land on three different lines.
_TALL_ROW = [
    "                gedung penginapan meliputi hostel dan losmen                                    V",
    "                                                                                  4tot7",
    "                lainnya",
]


def test_a_code_one_line_below_its_tick_is_still_the_rows_code():
    """GUILT — reading only the tick's own line loses these. Five rows on page 7
    (`41016`-`41020`) are shaped exactly like this and were reported unresolved
    until the row span existed."""
    out = parse("\n".join(_TALL_ROW), {"41017": "Konstruksi Gedung Penginapan"}, frozenset({"41017"}))
    assert [r["code"] for r in out["rows"]] == ["41017"]


def test_the_row_text_is_the_whole_cell_not_the_tick_line():
    """The grade qualifier decides the bucket and it wraps: `42201` reads
    '…menggunakan teknologi' on the tick line and 'sederhana dan madya' on the
    next. Truncating does not lose a bucket, it produces the WRONG one."""
    lines = [
        "              - Konstruksi jaringan irigasi yang menggunakan teknologi            4220t         V",
        "                 sederhana dan madya",
    ]
    out = parse("\n".join(lines), {"42201": "Konstruksi Jaringan Irigasi"}, frozenset({"42201"}))
    assert "sederhana dan madya" in out["rows"][0]["text"]


def test_the_span_stops_at_the_next_numbered_row():
    """INNOCENCE — and the dangerous direction. Walking past the row boundary
    would graft the NEXT activity's 'teknologi sederhana' onto this row and
    bucket a whole-code reservation as grade-qualified, hiding it from the
    owner's list."""
    lines = [
        "                jasa pekerjaan konstruksi prafabrikasi bangunan gedung             41020         V",
        "                perakitan untuk bangunan gedung",
        "      26     Konstruksi bangunan sipil jalan yang menggunakan teknologi sederhana",
        "             dan madya",
    ]
    out = parse("\n".join(lines), {"41020": "Konstruksi Prafabrikasi"}, frozenset({"41020"}))
    assert "sederhana" not in out["rows"][0]["text"]


def test_the_span_walks_up_when_the_tick_line_has_no_text():
    """`42101`'s tick sits on a line carrying only the code — its activity is
    entirely ABOVE it. Downward-only would report an empty activity for a row
    the annex describes in full."""
    lines = [
        "      26     Konstruksi bangunan sipil jalan meliputi pemeliharaan,",
        "             bangunan jalan raya yang menggunakan teknologi sederhana",
        "                                                                                  42tOt         V",
        "             dan madya",
    ]
    out = parse("\n".join(lines), {"42101": "Konstruksi Jalan"}, frozenset({"42101"}))
    text = out["rows"][0]["text"]
    assert text.startswith("Konstruksi bangunan sipil jalan") and text.endswith("dan madya")


def test_page_furniture_is_not_activity():
    """INNOCENCE — the printing-office mark below the table is not part of the
    last row; it was measured bleeding into `42201`."""
    lines = [
        "              - Konstruksi jaringan irigasi                                       4220t         V",
        "                 sederhana dan madya",
        "",
        "SK No 054252C",
    ]
    out = parse("\n".join(lines), {"42201": "Konstruksi Jaringan Irigasi"}, frozenset({"42201"}))
    assert "SK No" not in out["rows"][0]["text"]


def test_the_activity_is_cut_where_the_kbli_cell_begins_not_at_a_fixed_margin():
    """GUILT — the code column floats, so a fixed margin slices mid-word and the
    words it eats are exactly the ones that decide the bucket."""
    line = "                kursus, laboratorium dan bangunan penunjang pendidikan            41016         V"
    out = parse(line, {"41016": "Konstruksi Gedung Pendidikan"}, frozenset({"41016"}))
    assert out["rows"][0]["text"] == "kursus, laboratorium dan bangunan penunjang pendidikan"


def test_a_line_with_no_kbli_cell_keeps_its_full_width():
    """INNOCENCE for the same cut: on a continuation line there is no code to
    walk back over, and trimming anyway would drop the final word."""
    lines = [
        "                gedung penginapan meliputi hostel                                 4tot7         V",
        "                dan losmen sederhana",
    ]
    out = parse("\n".join(lines), {"41017": "Gedung Penginapan"}, frozenset({"41017"}))
    assert out["rows"][0]["text"].endswith("dan losmen sederhana")


def test_the_span_stops_at_a_second_kbli_cell():
    """GUILT, and the worst failure this parser had. A row has exactly one KBLI
    cell, so a second code line is the next row. Without this bound the `47911`
    row ran on and took `47912` from the row below — not a missing code but a
    WRONG one, which no `unresolved` list would have declared."""
    lines = [
        "                 minuman, tembakau, kimia, farmasi, kosmetik dan alat          479tt           V",
        "                 laboratorium",
        "             - Perdagangan eceran melalui media untuk komoditi tekstil,        47912",
    ]
    out = parse("\n".join(lines), {"47911": "Perdagangan Eceran Melalui Media"},
                frozenset({"47911", "47912"}))
    assert [r["code"] for r in out["rows"]] == ["47911"]
    assert "tekstil" not in out["rows"][0]["text"]


def test_a_dash_bullet_is_not_a_row_boundary():
    """INNOCENCE — treating dashes as boundaries was tried and it COST a code:
    annex row 13 lists four dashed products inside ONE cell, so the layer cannot
    tell a sibling row's dash from a sub-item's."""
    lines = [
        "       13    Industri perlengkapan pakaian dari tekstil, yaitu:                 t4t3t           V",
        "             - Industri peci/kopiah/songkok",
        "             - Industri ikat kepala tradisional",
    ]
    out = parse("\n".join(lines), {"14131": "Industri Perlengkapan Pakaian"}, frozenset({"14131"}))
    assert "kopiah" in out["rows"][0]["text"]


def test_an_image_read_row_is_labelled_as_such():
    """Every row says where it came from, so a reader can tell a parsed row from
    a hand-read one without going back to the commit that added it."""
    rows = load_relation()["rows"]
    assert sorted(r["code"] for r in rows if r["read_from"] == "page-image") == \
        ["10794", "14111", "14131", "42913", "43291", "47911"]
    assert {r["read_from"] for r in rows} == {"text-layer", "page-image"}


def test_a_stale_image_read_override_is_reported_not_silently_dropped():
    """GUILT — if the layer's output moves, an override stops matching and its
    hand-read code would vanish from a table still claiming 0 unresolved. The
    parse reports the orphans; `build()` refuses on them."""
    out = parse("        nothing here\n", {}, frozenset())
    assert set(out["image_read_unused"]) == set(IMAGE_READ)


def test_an_override_that_matches_is_not_reported_as_unused():
    """INNOCENCE for the same guard — otherwise it would refuse every real run.
    The two leading form feeds put the line on page 3, which is half the
    override's key: an override is bound to a page, not to a junk string that
    could recur elsewhere in a 22-page annex."""
    line = "             - Industri kerupuk, keripik, peyek dan                            70794           V"
    out = parse("\f\f" + line, {"10794": "Industri Kerupuk"}, frozenset({"10794"}))
    assert [r["code"] for r in out["rows"]] == ["10794"]
    assert out["rows"][0]["read_from"] == "page-image"
    assert (3, "70794") not in out["image_read_unused"]


def test_corroboration_ignores_words_that_head_hundreds_of_titles():
    """INNOCENCE for the second witness: sharing only 'industri' is not
    corroboration, or every industrial row would certify itself."""
    assert content_words("Industri tahu kedelai") & content_words("Industri Tahu Kedelai")
    assert not (content_words("Industri lainnya") & content_words("Industri Tahu Kedelai"))


# -------------------------------------------------------------- relation

_LIVE_OPEN = {"pma_status": "TERBUKA", "pma_max_asing": 100, "judul": "X"}


def test_a_kemitraan_row_is_never_a_divergence():
    """INNOCENCE — a partnership duty leaves foreign ownership intact."""
    bucket, _, _heirs = classify({"code": "01122", "column": "kemitraan", "text": "Padi", "page": 1},
                         {"01122": _LIVE_OPEN}, {})
    assert bucket == "kemitraan-no-bar"


def test_an_open_reserved_row_is_the_owner_question():
    """GUILT — live code, readable single activity, catalogue publishes it open."""
    bucket, _, _heirs = classify({"code": "01122", "column": "dialokasikan", "text": "Padi inbrida", "page": 1},
                         {"01122": _LIVE_OPEN}, {})
    assert bucket == "whole-row"


def test_a_zero_cap_terbatas_already_agrees():
    """`47111` is TERBATAS/0% — already barred to foreigners. Counting it as a
    divergence would report the one code the backend already names reserved as
    evidence that it is not."""
    rec = {"pma_status": "TERBATAS", "pma_max_asing": 0, "judul": "Minimarket"}
    assert foreign_can_take(rec) is False
    bucket, _, _heirs = classify({"code": "47111", "column": "dialokasikan", "text": "Minimarket", "page": 13},
                         {"47111": rec}, {})
    assert bucket == "agree"


def test_an_absent_cap_is_not_a_zero_cap():
    """INNOCENCE — exactly one record lacks `pma_max_asing` (`01122`, TERBUKA).
    Coercing that absence to 0 is what rendered '0% Open' on a live page."""
    assert foreign_can_take({"pma_status": "TERBUKA", "judul": "Padi Inbrida"}) is True


def test_a_grade_qualified_row_is_not_a_whole_code_verdict():
    """'sederhana dan madya' reserves construction GRADES, not the activity."""
    bucket, _, _heirs = classify(
        {"code": "01122", "column": "dialokasikan", "text": "sederhana dan madya", "page": 12},
        {"01122": _LIVE_OPEN}, {})
    assert bucket == "segment-qualified"


def test_an_unreadable_activity_is_never_counted_as_a_contradiction():
    """Order matters: a row whose bidang usaha wrapped away is unusable, even
    though its code is certain. Judging it divergent would assert a bar on an
    activity nobody read."""
    bucket, _, _heirs = classify({"code": "01122", "column": "dialokasikan", "text": None, "page": 9},
                         {"01122": _LIVE_OPEN}, {})
    assert bucket == "activity-unknown"


def test_a_code_with_no_2025_descendant_is_archaeology():
    bucket, record, _heirs = classify({"code": "99999", "column": "dialokasikan", "text": "X", "page": 1}, {}, {})
    assert bucket == "retired-2020-code" and record is None


# --- the bucket must mean what its name says: RETIRED, not merely RENUMBERED ---
#
# The test above is the whole reason this defect lived: it proves the bucket
# FIRES when there is genuinely no descendant, and nothing proved it does NOT
# fire when there is one under a different number. Guilt without innocence.
# Measured on the shipped data before the fix: 30 of 30 rows in this bucket had
# a live heir, reaching 66 live pages, every one published TERBUKA/100%.

_RENUMBERED = {"pma_status": "TERBUKA", "pma_max_asing": 100, "judul": "Aktivitas Vila"}


def test_a_renumbered_code_is_not_archaeology():
    """GUILT for the real regression. `55193 Vila` (2020) is `55203` (2025):
    the number is gone, the page is live and published open. Classifying it as
    retired files a live client-facing reservation under 'not client-facing' —
    failure in the invisible direction."""
    bucket, record, heirs = classify(
        {"code": "55193", "column": "dialokasikan", "text": "Vila", "page": 15},
        {"55203": _RENUMBERED},
        {"55193": ["55203"]},
    )
    assert bucket == "whole-row"
    assert heirs == ["55203"] and record is _RENUMBERED


def test_a_split_activity_is_never_collapsed_onto_its_heirs():
    """GUILT. `55110` is reserved as 'Hotel Bintang I' and the crosswalk sends
    it to all five star ratings. Reporting that as a whole-row divergence would
    manufacture a reservation on five-star hotels out of a conversion table."""
    stars = {f"5510{i}": {"pma_status": "TERBUKA", "pma_max_asing": 100, "judul": f"Hotel {i}"}
             for i in range(1, 6)}
    bucket, record, heirs = classify(
        {"code": "55110", "column": "dialokasikan", "text": "Hotel Bintang I", "page": 14},
        stars,
        {"55110": list(stars)},
    )
    assert bucket == "split-heirs"
    assert record is None, "a split row has no single record to judge"
    assert len(heirs) == 5


def test_number_identity_beats_a_crosswalk_edge_when_both_exist():
    """The corrected direction, and the reversal is the lesson.

    This test first asserted the OPPOSITE — that the crosswalk must win, on the
    hypothetical that a 2025 catalogue might reuse a 2020 number for a different
    activity. Cross-family review measured the other risk and found it real: the
    shipped edge file carries `14111 Industri Pakaian Jadi -> 17091 Industri
    Kertas Tisu` next to the correct `14111 -> 14111`. Under crosswalk-wins that
    single bad edge demoted a correctly-judged row into `split-heirs`, where
    nothing evaluates it — 34 rows left the evaluated buckets that way.

    A measured defect beats a hypothetical one. It is also the safer failure: a
    reused number yields a wrong single record, printed for a human to catch; a
    false split yields NO record at all."""
    canon = {"14111": {"pma_status": "TERBUKA", "pma_max_asing": 100, "judul": "Pakaian Jadi"},
             "17091": {"pma_status": "TERBUKA", "pma_max_asing": 100, "judul": "Kertas Tisu"}}
    bucket, rec, heirs = classify(
        {"code": "14111", "column": "dialokasikan", "text": "Industri ikat kepala", "page": 4},
        canon,
        {"14111": ["14111", "17091"]},
    )
    assert heirs == ["14111"], "a spurious edge must not manufacture a split"
    assert bucket == "whole-row" and rec is canon["14111"]


def test_identity_is_the_fallback_when_the_crosswalk_is_silent():
    """INNOCENCE. A gap in the edges must degrade to the old reading, never
    erase a live page: a missing edge is ignorance, not extinction."""
    bucket, record, heirs = classify(
        {"code": "01122", "column": "dialokasikan", "text": "Padi inbrida", "page": 1},
        {"01122": _LIVE_OPEN},
        {},
    )
    assert bucket == "whole-row" and heirs == ["01122"] and record is _LIVE_OPEN


def test_a_missing_crosswalk_file_is_cannot_verify_not_a_clean_report():
    """The annex speaks 2020 and the catalogue speaks 2025. With no crosswalk
    the module cannot tell retired from renumbered, and a report that says
    'nothing renumbered' is then indistinguishable from a healthy one (W84).
    Exit 4, not 0."""
    from pathlib import Path as _P
    import pytest as _pytest
    with _pytest.raises(FileNotFoundError):
        load_crosswalk(_P("/nonexistent/edges-lampiran5.json"))


# ------------------------------------------------- pins on the shipped file

def test_the_tick_population_is_reported_separately_from_the_rows_emitted():
    """`rows_emitted` EXCEEDS `ticks` — annex row 13 carries two codes under one
    tick. Folding them into a single `tick_rows` field made the output read
    "181 of 180", i.e. a population that appeared to grow. Two fields, so the
    excess is legible instead of alarming."""
    counts = load_relation()["counts"]
    assert counts["ticks"] == 180
    assert counts["rows_emitted"] == 181 == counts["dialokasikan"] + counts["kemitraan"]


def test_the_unresolved_list_is_reported_even_when_empty():
    """No silent cap (W97). It is 0 today; the FIELD must still be there, since
    a gap that leaves no trace in the output is indistinguishable from no gap."""
    rel = load_relation()
    assert "unresolved" in rel and rel["counts"]["unresolved"] == len(rel["unresolved"])
    assert rel["counts"]["rows_emitted"] == len(rel["rows"])


def test_the_column_gap_that_justifies_the_split_is_still_empty():
    """The split at 105 is only defensible while no tick lands in 101..107. If a
    re-parse ever puts one there, the two columns overlap and every
    reservation verdict in this file is suspect — fail loudly instead."""
    histogram = load_relation()["tick_x_histogram"]
    assert not [x for x in map(int, histogram) if 100 < x < 108]
    assert min(map(int, histogram)) < COLUMN_SPLIT_X < max(map(int, histogram))


def test_the_relation_pins_the_vaulted_artifact_it_was_read_from():
    """A transcription whose artifact is unpinned is a claim, not evidence —
    the defect this whole module set was built to close."""
    source = load_relation()["source"]
    assert source["vault_id"] == 161564
    assert source["vault_rel_path"].endswith("Lampiran II.pdf")


def test_report_never_gates():
    """Deliberate: divergence here is a legal reading reserved to the owner."""
    rel = load_relation()
    canonical = {r["code"]: dict(_LIVE_OPEN) for r in rel["rows"]}
    out = report(rel, canonical, {})
    assert out["buckets"]["kemitraan-no-bar"] == sum(1 for r in rel["rows"] if r["column"] == "kemitraan")
    assert sum(out["buckets"].values()) == out["rows_emitted"]


def test_no_row_of_the_shipped_annex_is_actually_retired():
    """The measurement that names the defect, run on the SHIPPED data rather
    than a fixture — a fixture proves the branch, only the real annex proves the
    world. Before the crosswalk, `retired-2020-code` held 30 rows and its own
    docstring called them 'archaeology, not client-facing'; every one of the 30
    had a live 2025 heir. If this bucket ever refills, the claim must be
    re-measured before it is believed."""
    out = report(load_relation(), load_canonical(), load_crosswalk())
    assert out["buckets"].get("retired-2020-code", 0) == 0


def test_every_split_row_names_more_than_one_live_heir():
    """INNOCENCE for the new bucket: `split-heirs` must never hold a row that a
    single page answers — that row belongs in the owner's main question list,
    and parking it here would hide it exactly as `retired-2020-code` did."""
    out = report(load_relation(), load_canonical(), load_crosswalk())
    for row in out["detail"].get("split-heirs", []):
        assert len(row["heirs_2025"]) > 1, row["code"]


def test_relation_file_is_where_the_reader_expects_it():
    assert RELATION.name == "perpres-umkm-reservation.json"
    assert json.loads(RELATION.read_text())["instrument"].startswith("Perpres 49/2021")


def test_live_heirs_deduplicates_repeated_edges():
    """The crosswalk carries one edge per PDF row, so a 2020 code split across
    pages repeats an heir. Counting duplicates would push a 1:1 carry-over into
    `split-heirs` and hide it from the owner's main list."""
    canon = {"55203": {"pma_status": "TERBUKA", "judul": "Vila"}}
    assert live_heirs("55193", canon, {"55193": ["55203", "55203"]}) == ["55203"]


def test_live_heirs_drops_edges_to_codes_the_catalogue_does_not_publish():
    """An edge to a code with no live page is not an heir — counting it would
    manufacture a split out of a page nobody can open."""
    canon = {"55203": {"pma_status": "TERBUKA", "judul": "Vila"}}
    assert live_heirs("55193", canon, {"55193": ["55203", "99999"]}) == ["55203"]


def test_the_command_the_operator_runs_exits_zero():
    """The 43 tests above exercise helpers; none of them ran the CLI. Flipping
    `main()`'s return to EXIT_CANNOT_VERIFY left every one of them green while
    breaking the only command anybody types (cross-family review, 2026-08-03).
    A reporter that starts refusing must fail a test, not a user."""
    from perpres_umkm_reservation_relation import EXIT_OK, main  # noqa: PLC0415

    assert main(["--check", "--json"]) == EXIT_OK


# ---------------------------------------------------------------------------
# parent-qualified — the scope the annex writes ONCE, on the heading
# ---------------------------------------------------------------------------


def _row(code="01111", text="Jagung", parent=None):
    r = {"code": code, "column": "dialokasikan", "page": 1, "text": text,
         "read_from": "text-layer", "title_corroborated": True}
    if parent is not None:
        r["parent_heading"] = parent
    return r


def test_guilt_a_restricting_parent_takes_the_row_out_of_whole_row():
    """The defect this bucket exists for: "Jagung" reads like a whole activity,
    and it is reserved only as part of "…dengan luas kurang dari 25 Ha"."""
    canon = {"01111": {"pma_status": "TERBUKA", "pma_max_asing": 100, "judul": "Jagung"}}
    bucket, _, _ = classify(
        _row(parent="Pertanian tanaman pangan dengan luas kurang dari 25 Ha"), canon, {}
    )
    assert bucket == "parent-qualified"


def test_guilt_the_technology_grade_heading_qualifies_too():
    canon = {"43215": {"pma_status": "TERBUKA", "pma_max_asing": 100, "judul": "Instalasi"}}
    bucket, _, _ = classify(
        _row(code="43215", text="43215",
             parent="Instalasi yang menggunakan teknologi sederhana dan madya"),
        canon, {},
    )
    assert bucket == "parent-qualified"


def test_innocence_an_unrestricting_parent_leaves_the_row_in_whole_row():
    """A heading that merely GROUPS ("Pemungutan hasil hutan:") narrows nothing.
    Treating every parent as a qualifier would empty the owner's list, which is
    the error the prose caveat was right to fear."""
    canon = {"02303": {"pma_status": "TERBUKA", "pma_max_asing": 100, "judul": "Getah"}}
    bucket, _, _ = classify(
        _row(code="02303", text="Getah pinus", parent="Pemungutan hasil hutan"), canon, {}
    )
    assert bucket == "whole-row"


def test_innocence_a_row_with_no_parent_is_unaffected():
    canon = {"47111": {"pma_status": "TERBUKA", "pma_max_asing": 100, "judul": "Minimarket"}}
    bucket, _, _ = classify(_row(code="47111", text="Minimarket", parent=None), canon, {})
    assert bucket == "whole-row"


def test_the_live_artifact_carries_the_parent_that_was_missing():
    """TRIPWIRE on the DATA, not the classifier. The adjudication that had to be
    withdrawn was handed rows whose cell said only "Jagung": the 25-Ha scope was
    in the annex, visible to anyone reading the PDF, and absent from every row
    we emitted. If a re-parse ever drops `parent_heading` again, this fails —
    the classifier above would go on passing, because it takes the parent as an
    argument."""
    rows = load_relation()["rows"]
    jagung = next(r for r in rows if r["code"] == "01111")
    assert "kurang dari 25 Ha" in (jagung.get("parent_heading") or ""), jagung
    # …and the field is emitted for every row, so "no parent" is distinguishable
    # from "parents were never looked for".
    assert all("parent_heading" in r for r in rows)
    qualified = [r for r in rows if "kurang dari" in (r.get("parent_heading") or "")]
    assert {r["code"] for r in qualified} == {
        "01111", "01113", "01114", "01115", "01121", "01122",
    }


def test_guilt_a_dotted_item_number_is_a_heading_like_any_other():
    """The annex numbers items BOTH ways, two rows apart: `48.  Jasa Penginapan:`
    and `49  Aktivitas konsultansi ...`. A rule that required whitespace right
    after the digits saw only the second, and `Jasa Penginapan:` — the heading
    that governs every hotel, homestay, guest house and villa row in Lampiran II
    — was invisible."""
    text = "  48.   Jasa Penginapan:\n       - Hotel Bintang I    55110    V\n"
    h = governing_headings(text)
    assert h[(1, 1)] == "Jasa Penginapan"


def test_guilt_a_dotted_item_CLOSES_the_parent_above_it():
    """The worse half, and the one that put a false fact in the data rather than
    merely omitting a true one. A numbered item always ends the previous parent;
    when the dotted form was not recognised as an item, its rows kept inheriting
    the heading above. Live instance: `10214` (fish processing, item `3.`) was
    carrying `Pemungutan hasil hutan` — forest harvesting, item 2."""
    text = (
        "   2   Pemungutan hasil hutan:\n"
        "        Rotan                  02302   V\n"
        "   3.   Industri pemindangan ikan   10214   V\n"
    )
    h = governing_headings(text)
    assert h[(1, 1)] == "Pemungutan hasil hutan", "the child of item 2 keeps its parent"
    assert h[(1, 2)] is None, "item 3. is its own item and inherits nothing"


def test_innocence_the_undotted_form_still_governs_its_children():
    """The fix must not trade one form for the other.

    This one passes against the OLD rule too, and that is what an innocence test
    is for — it pins behaviour the change must leave alone. It has no power to
    catch a regression of the DOTTED form; do not read it as a guard for that.
    The two `test_guilt_…` cases above are the guards.
    """
    text = "   4   Industri pengolahan kedelai:\n       Industri tempe kedelai  10391  V\n"
    h = governing_headings(text)
    assert h[(1, 1)] == "Industri pengolahan kedelai"


def test_innocence_a_decimal_amount_at_the_head_of_a_line_is_not_an_item():
    """The widened boundary's own hazard, exercised where it actually lives.

    An earlier version of this test began the line with `Nilai`, so `^\\s*\\d`
    never matched and it could not have failed however the rule was written — it
    asserted a condition on a literal string instead of an outcome of the parser
    (named by an independent review of this diff). These three lines all BEGIN
    with digits, which is the only place the rule can be fooled:

      `1.500  juta`  — a dot with no space after it is a decimal separator
      `1. 500 juta:` — a dot WITH a space is the shape the fix admits, and the
                       heading it would open starts with a digit, which no real
                       item in this annex does
      `12 Besar`     — a bare number needs two spaces, as it always did
    """
    text = (
        "   1.500  juta rupiah:\n"
        "   1. 500 juta rupiah:\n"
        "   12 Besar saja:\n"
        "        Sesuatu   12345   V\n"
    )
    h = governing_headings(text)
    assert h[(1, 3)] is None, f"a row after three non-items must be parentless, got {h[(1, 3)]!r}"


def test_guilt_a_bare_number_with_one_space_does_not_close_a_parent():
    """The tightening, and why it is not cosmetic.

    Written as `\\d{1,3}\\.?\\s{1,}` the rule admits a bare `2 body` — a line the
    annex never numbered — and a numbered item ALWAYS closes the parent above it.
    So the child on the following line would be orphaned by a false sibling. The
    dotted form gets the single space; the bare form still demands two.
    """
    text = (
        "   7   Jasa Penginapan:\n"
        "   2 keterangan lanjutan\n"
        "        Hotel Melati    55120   V\n"
    )
    h = governing_headings(text)
    assert h[(1, 2)] == "Jasa Penginapan", (
        "a line that is not an item number must not close the heading above it"
    )


def test_the_live_artifact_attributes_the_accommodation_family_and_not_the_fish():
    """TRIPWIRE on the DATA for both halves of the dotted-number defect, on the
    rows that carry commercial weight: the accommodation family is Bali Zero's
    own market, and `Jasa Penginapan` is what says these rows are a family at
    all. It carries NO restricting qualifier — which is the point: recovering a
    parent is not the same as finding a restriction, and this test asserts the
    parent is present AND that it does not narrow anything."""
    rows = load_relation()["rows"]
    by = {}
    for r in rows:
        by.setdefault(r["code"], []).append(r)
    for code in ("55110", "55120", "55130", "55193", "55199"):
        assert all(r.get("parent_heading") == "Jasa Penginapan" for r in by[code]), code
    assert not _PARENT_QUALIFIER_RE.search("Jasa Penginapan"), (
        "a recovered parent must not be assumed restrictive"
    )
    # …and the phantom is gone: item `3.` inherits nothing from item 2.
    assert all(r.get("parent_heading") is None for r in by["10214"])


# ---------------------------------------------------------------------------
# The phantom article — Pasal 3(3) names nothing
# ---------------------------------------------------------------------------

_PHANTOM_RE = re.compile(r"Pasal 3\s*(?:ayat\s*)?\(3\)|art\.?\s*3\(3\)", re.IGNORECASE)
# A mention is absolved only when the SAME line disowns it. "Pasal 3(3)" written
# beside "does not exist" is a correction; written alone it is a citation, and a
# citation of an article that has no third ayat supports nothing. Deliberately
# same-line: a window would let the colpevole sentence borrow an absolution from
# a neighbouring paragraph, which is how the retracted-claims guard first failed.
_DISOWNED_RE = re.compile(r"does not exist|phantom|no third ayat|names nothing", re.IGNORECASE)


def phantom_citations(text: str) -> list[int]:
    """1-indexed lines citing Pasal 3(3) without disowning it on the same line."""
    return [
        n for n, line in enumerate(text.splitlines(), 1)
        if _PHANTOM_RE.search(line) and not _DISOWNED_RE.search(line)
    ]


def test_guilt_a_bare_citation_of_the_phantom_is_caught():
    assert phantom_citations("the rule is Pasal 3(3): it attaches to the named bidang usaha") == [1]
    assert phantom_citations("the body says so explicitly (art. 3(3): where one KBLI") == [1]


def test_innocence_a_sentence_that_disowns_it_is_allowed():
    """Correcting the phantom requires writing it. A guard that forbids naming
    what it bans makes the correction uncommittable — and this one bit its own
    author on the first run, which is how the rule got written down."""
    assert phantom_citations("This cited `art. 3(3)` until then, which does not exist.") == []
    assert phantom_citations("`Pasal 3(3)` does not exist. It was a phantom.") == []


def test_innocence_the_real_articles_are_not_touched():
    for ok in ("Pasal 5 ayat (5)", "Pasal 6(3)", "Pasal 3 ayat (1) huruf b", "Pasal 3(1)(b)"):
        assert phantom_citations(f"the rule is {ok} and it governs the annex") == [], ok


def test_the_kbli_tooling_and_prose_carry_no_bare_phantom_citation():
    """Perpres 10/2021 writes the "one KBLI, several bidang usaha" rule ONCE PER
    ANNEX — Pasal 5(5) for Lampiran II, Pasal 6(3) for Lampiran III — and Pasal 3
    has only two ayat.

    The phantom sat in five files for five days, including the corner skill every
    KBLI session loads, because one remembered number was reused for both
    annexes. Lexical guard, and it knows it: it cannot tell a right citation from
    a wrong one, only a citation that cannot exist from everything else.
    """
    root = Path(__file__).resolve().parents[2].parent
    targets = [root / "scripts" / "kbli_filiera", root / "research" / "compliance",
               root / ".agents" / "skills" / "kbli-navigator"]
    scanned, offenders = 0, []
    for base in (b for b in targets if b.exists()):
        for f in list(base.rglob("*.py")) + list(base.rglob("*.md")):
            if f.name == Path(__file__).name:
                continue  # this file writes the phantom in order to ban it
            scanned += 1
            for n in phantom_citations(f.read_text(encoding="utf-8", errors="replace")):
                offenders.append(f"{f.relative_to(root)}:{n}")
    # A blind scan must not look like a clean one (W84).
    assert scanned > 5, f"only {scanned} files scanned — the scan, not the repo, is empty"
    assert not offenders, (
        "Pasal 3(3) does not exist. Lampiran II -> Pasal 5(5); "
        f"Lampiran III -> Pasal 6(3). Found: {offenders}"
    )


# ---------------------------------------------------------------------------
# Row fusion — two rows cannot both own the lines between their ticks
# ---------------------------------------------------------------------------


def test_guilt_a_row_no_longer_swallows_the_next_rows_cell():
    """`42912` (pelabuhan bukan perikanan) had recorded its own activity PLUS
    the whole of `42913`'s (pelabuhan perikanan), which reads as one activity
    wider than the annex reserves — the direction that turns a segment into a
    whole code."""
    rows = {r["code"]: r for r in load_relation()["rows"]}
    assert rows["42912"]["text"] == "pelabuhan bukan perikanan"
    assert rows["42913"]["text"] == "pelabuhan perikanan"


def test_innocence_a_cell_that_wraps_past_its_tick_keeps_its_qualifier():
    """The bound is a BLANK LINE, the annex's own row separator — not "stop at
    the tick". Two narrower rules were measured and discarded because they cut
    real wraps: `42209` and `71102` carry "teknologi sederhana dan madya" on
    lines BELOW their tick, and losing those words produces a wrong bucket in
    the dangerous direction."""
    rows = load_relation()["rows"]
    # Keyed by (code, column), NOT by code: `71102` sits in the annex TWICE
    # under different bidang usaha — dialokasikan on p15 and kemitraan on p21 —
    # and a dict keyed by code alone keeps only the last, which made the first
    # draft of this test report a loss the parser had not caused (W107).
    by_pair = {(r["code"], r["column"]): r for r in rows}
    for code in ("42209", "71102", "71202", "71204", "43905"):
        r = by_pair[(code, "dialokasikan")]
        blob = (r["text"] or "") + (r.get("parent_heading") or "")
        assert "madya" in blob, f"{code} lost its grade qualifier: {r['text']!r}"
    # `16101` carries a CAPACITY limit ("kurang dari 2000 m3 per tahun") and sits
    # in the KEMITRAAN column — a partnership duty, not a reservation. Named with
    # its real column rather than assumed into the other one: the two columns are
    # the over-match this whole module is built to keep apart.
    assert "kurang dari" in (by_pair[("16101", "kemitraan")]["text"] or "")


def test_the_parse_still_accounts_for_every_tick():
    """A span rule that cuts too early drops rows silently. One discarded
    attempt lost `41020` entirely and turned 0 unresolved into 1 — measured
    before shipping, which is the only reason it is not in the artifact."""
    rel = load_relation()
    assert rel["counts"]["ticks"] == 180
    assert rel["counts"]["rows_emitted"] == 181  # annex row 13 carries two codes
    assert rel["counts"]["unresolved"] == 0
    assert rel["unresolved"] == []
