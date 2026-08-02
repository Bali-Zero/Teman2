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
import sys
from pathlib import Path

import pytest

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

from parse_perpres_lampiran2 import (  # noqa: E402
    COLUMN_SPLIT_X,
    SUBSTITUTIONS,
    content_words,
    decode,
    parse,
)
from perpres_umkm_reservation_relation import (  # noqa: E402
    RELATION,
    classify,
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


def test_corroboration_ignores_words_that_head_hundreds_of_titles():
    """INNOCENCE for the second witness: sharing only 'industri' is not
    corroboration, or every industrial row would certify itself."""
    assert content_words("Industri tahu kedelai") & content_words("Industri Tahu Kedelai")
    assert not (content_words("Industri lainnya") & content_words("Industri Tahu Kedelai"))


# -------------------------------------------------------------- relation

_LIVE_OPEN = {"pma_status": "TERBUKA", "pma_max_asing": 100, "judul": "X"}


def test_a_kemitraan_row_is_never_a_divergence():
    """INNOCENCE — a partnership duty leaves foreign ownership intact."""
    bucket, _ = classify({"code": "01122", "column": "kemitraan", "text": "Padi", "page": 1},
                         {"01122": _LIVE_OPEN})
    assert bucket == "kemitraan-no-bar"


def test_an_open_reserved_row_is_the_owner_question():
    """GUILT — live code, readable single activity, catalogue publishes it open."""
    bucket, _ = classify({"code": "01122", "column": "dialokasikan", "text": "Padi inbrida", "page": 1},
                         {"01122": _LIVE_OPEN})
    assert bucket == "whole-row"


def test_a_zero_cap_terbatas_already_agrees():
    """`47111` is TERBATAS/0% — already barred to foreigners. Counting it as a
    divergence would report the one code the backend already names reserved as
    evidence that it is not."""
    rec = {"pma_status": "TERBATAS", "pma_max_asing": 0, "judul": "Minimarket"}
    assert foreign_can_take(rec) is False
    bucket, _ = classify({"code": "47111", "column": "dialokasikan", "text": "Minimarket", "page": 13},
                         {"47111": rec})
    assert bucket == "agree"


def test_an_absent_cap_is_not_a_zero_cap():
    """INNOCENCE — exactly one record lacks `pma_max_asing` (`01122`, TERBUKA).
    Coercing that absence to 0 is what rendered '0% Open' on a live page."""
    assert foreign_can_take({"pma_status": "TERBUKA", "judul": "Padi Inbrida"}) is True


def test_a_grade_qualified_row_is_not_a_whole_code_verdict():
    """'sederhana dan madya' reserves construction GRADES, not the activity."""
    bucket, _ = classify(
        {"code": "01122", "column": "dialokasikan", "text": "sederhana dan madya", "page": 12},
        {"01122": _LIVE_OPEN})
    assert bucket == "segment-qualified"


def test_an_unreadable_activity_is_never_counted_as_a_contradiction():
    """Order matters: a row whose bidang usaha wrapped away is unusable, even
    though its code is certain. Judging it divergent would assert a bar on an
    activity nobody read."""
    bucket, _ = classify({"code": "01122", "column": "dialokasikan", "text": None, "page": 9},
                         {"01122": _LIVE_OPEN})
    assert bucket == "activity-unknown"


def test_a_code_with_no_2025_descendant_is_archaeology():
    bucket, record = classify({"code": "99999", "column": "dialokasikan", "text": "X", "page": 1}, {})
    assert bucket == "retired-2020-code" and record is None


# ------------------------------------------------- pins on the shipped file

def test_committed_relation_declares_what_it_could_not_read():
    """No silent cap (W97): the file must state N of M, not just N."""
    rel = load_relation()
    counts = rel["counts"]
    assert counts["resolved"] + counts["unresolved"] == counts["tick_rows"]
    assert counts["unresolved"] == len(rel["unresolved"]) > 0
    assert counts["resolved"] == len(rel["rows"])


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
    out = report(rel, canonical)
    assert out["buckets"]["kemitraan-no-bar"] == sum(1 for r in rel["rows"] if r["column"] == "kemitraan")
    assert sum(out["buckets"].values()) == out["rows_resolved"]


def test_relation_file_is_where_the_reader_expects_it():
    assert RELATION.name == "perpres-umkm-reservation.json"
    assert json.loads(RELATION.read_text())["instrument"].startswith("Perpres 49/2021")
