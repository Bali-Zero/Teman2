"""Unit tests for scripts/kbli_filiera/bps_crosswalk_parser.py — pure logic
only (no PDF), plus one opt-in integration test gated on the vault PDF.

The load-bearing invariants under test:
  * watermark recovery is LOSSLESS but still FAIL-CLOSED (scar #3 — a guard
    needs both a guilt test that it recovers real codes and an innocence test
    that it never invents one from noise/ambiguity);
  * header/label rows never read as data;
  * ancestry accumulation is order-preserving, dedup, reverse-only, and pins
    printed_page = pdf_page - 14;
  * the relation digest is deterministic (sorted-key canonical form).
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import bps_crosswalk_parser as p  # noqa: E402
from kbli_filiera import vault_common as common  # noqa: E402


# ---------------------------------------------------------------------------
# extract_code — the fail-closed watermark-recovery guard (scar #3)
# ---------------------------------------------------------------------------

class TestExtractCode:
    def test_pristine_code_returned_verbatim(self):
        assert p.extract_code("49213") == "49213"

    def test_leading_zero_preserved_as_string(self):
        # int() would drop the leading zero — codes MUST stay strings.
        assert p.extract_code("01121") == "01121"
        assert p.extract_code("01121") != "1121"

    @pytest.mark.parametrize(
        "raw,expected",
        [
            # GUILT: real watermark-corrupted cells observed on pp325-328.
            ("s p01121", "01121"),
            ("01270. s", "01270"),
            ("b 01122", "01122"),
            ("01414g .", "01414"),
            (". 01725", "01725"),
            ("s p 01729 b", "01729"),
            ("01119 g .", "01119"),
            ("p b01270 .", "01270"),
        ],
    )
    def test_watermark_noise_recovered_to_five_digits(self, raw, expected):
        assert p.extract_code(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", None, "https://www.bps.go.id"])
    def test_innocence_no_code_no_digits(self, raw):
        # A blank or pure-watermark cell has ZERO digits — never a false code.
        assert p.extract_code(raw) is None

    @pytest.mark.parametrize("raw", ["0112", "011213", "0121 0122", "47911 S.D. 47913"])
    def test_innocence_wrong_digit_count_fails_closed(self, raw):
        # 4, 6, two merged codes (10), a title-range spill — none is exactly
        # five digits, so all fail closed to an unresolved row, never guessed.
        assert p.extract_code(raw) is None

    def test_innocence_title_with_stray_number_not_coerced(self):
        # A title fragment carrying a golongan number must not become a code.
        assert p.extract_code("golongan 072") is None


# ---------------------------------------------------------------------------
# normalize_cell / classify_direction / is_header_or_label_row
# ---------------------------------------------------------------------------

class TestNormalizeCell:
    def test_collapses_wrapped_newlines(self):
        assert p.normalize_cell("Perdagangan Eceran\nSepeda Motor") == "Perdagangan Eceran Sepeda Motor"

    def test_none_is_empty(self):
        assert p.normalize_cell(None) == ""


class TestClassifyDirection:
    def test_forward_2020_precedes_2025(self):
        assert p.classify_direction(["KBLI\n2020", "Judul KBLI 2020", "KBLI\n2025", "Judul KBLI 2025"]) == "fwd"

    def test_reverse_2025_precedes_2020(self):
        assert p.classify_direction(["KBLI\n2025", "Judul KBLI 2025", "KBLI\n2020", "Judul KBLI 2020"]) == "rev"

    def test_no_years_is_none(self):
        assert p.classify_direction(["foo", "bar"]) is None
        assert p.classify_direction(None) is None


class TestHeaderOrLabelRow:
    def test_column_header_detected(self):
        assert p.is_header_or_label_row(["KBLI\n2025", "Judul KBLI 2025", "KBLI\n2020", "Judul KBLI 2020"])

    def test_column_number_legend_detected(self):
        assert p.is_header_or_label_row(["(1)", "(2)", "(3)", "(4)"])

    def test_data_row_not_flagged(self):
        assert not p.is_header_or_label_row(["49213", "Angkutan Perkotaan", "49214", "Angkutan Bus Kota"])

    def test_empty_row_flagged(self):
        assert p.is_header_or_label_row(None)
        assert p.is_header_or_label_row([])


# ---------------------------------------------------------------------------
# parse_table_rows — edges + fail-closed unresolved
# ---------------------------------------------------------------------------

class TestParseTableRows:
    def _rev_table(self):
        return [
            ["KBLI\n2025", "Judul KBLI 2025", "KBLI\n2020", "Judul KBLI 2020"],
            ["(1)", "(2)", "(3)", "(4)"],
            ["49213", "Angkutan Perkotaan", "49214", "Angkutan Bus Kota"],
            ["49213", "Angkutan Perkotaan", "49219", "Angkutan Bus Dalam Trayek Lainnya"],
            ["49213", "Angkutan Perkotaan", ". 49413", "Angkutan Perkotaan Bukan Bus"],  # watermark
        ]

    def test_reverse_edges_extracted_and_header_filtered(self):
        edges, unresolved = p.parse_table_rows(self._rev_table(), "rev", 399)
        assert [(e.left_code, e.right_code) for e in edges] == [
            ("49213", "49214"), ("49213", "49219"), ("49213", "49413"),
        ]
        assert unresolved == []
        assert edges[0].pdf_page == 399

    def test_forward_columns_same_positions(self):
        table = [
            ["KBLI\n2020", "Judul KBLI 2020", "KBLI\n2025", "Judul KBLI 2025"],
            ["25931", "Industri Perkakas Tangan", "25931", "Industri Perkakas Tangan"],
            ["25931", "Industri Perkakas Tangan", "28210", "Industri Mesin Pertanian"],
        ]
        edges, _ = p.parse_table_rows(table, "fwd", 161)
        assert [(e.left_code, e.right_code) for e in edges] == [("25931", "25931"), ("25931", "28210")]

    def test_blank_grid_row_dropped_quietly(self):
        table = [["", "", "", ""]]
        edges, unresolved = p.parse_table_rows(table, "rev", 400)
        assert edges == [] and unresolved == []

    def test_title_spill_row_is_unresolved_not_silent(self):
        # Both code columns empty but titles present = a wrapped-title spill.
        # No edge, but it is RECORDED (gate item 8), never silently dropped.
        table = [["", "dan Sejenisnya, Suku Cadang", "", "Dan Sejenisnya, Suku Cadang"]]
        edges, unresolved = p.parse_table_rows(table, "rev", 373)
        assert edges == []
        assert len(unresolved) == 1
        assert unresolved[0].pdf_page == 373
        assert "left+right" in unresolved[0].reason

    def test_short_row_is_unresolved(self):
        edges, unresolved = p.parse_table_rows([["49213", "title"]], "rev", 399)
        assert edges == []
        assert unresolved and unresolved[0].reason == "row_has_fewer_than_4_columns"


# ---------------------------------------------------------------------------
# accumulate_ancestry + edge sets + digest determinism
# ---------------------------------------------------------------------------

def _rev_block():
    b = p.LampiranBlock(lampiran=10, direction="rev", first_page=399, last_page=399)
    b.edges = [
        p.ParsedRow("49213", "49214", "Angkutan Perkotaan", "Angkutan Bus Kota", 399),
        p.ParsedRow("49213", "49219", "Angkutan Perkotaan", "Angkutan Bus Dalam Trayek Lainnya", 399),
        p.ParsedRow("49213", "49214", "Angkutan Perkotaan", "Angkutan Bus Kota", 399),  # dup
    ]
    return b


class TestAccumulateAncestry:
    def test_order_preserving_and_dedup(self):
        out = p.accumulate_ancestry(_rev_block())
        assert out["49213"]["codes"] == ["49214", "49219"]  # dup collapsed, order kept

    def test_printed_page_offset_pinned(self):
        out = p.accumulate_ancestry(_rev_block())
        loc = out["49213"]["locators"][0]
        assert loc["pdf_page"] == 399 and loc["printed_page"] == 385  # 399 - 14

    def test_forward_block_rejected(self):
        fwd = p.LampiranBlock(lampiran=5, direction="fwd", first_page=131, last_page=131)
        with pytest.raises(ValueError):
            p.accumulate_ancestry(fwd)


class TestCrossDirectionConsistency:
    def test_matched_edges_have_zero_diff(self):
        fwd = p.LampiranBlock(lampiran=5, direction="fwd", first_page=131, last_page=131)
        fwd.edges = [p.ParsedRow("49214", "49213", "t", "t", 161)]  # 2020->2025
        rev = p.LampiranBlock(lampiran=10, direction="rev", first_page=399, last_page=399)
        rev.edges = [p.ParsedRow("49213", "49214", "t", "t", 399)]  # 2025->2020 (same edge)
        diff = p.cross_direction_diff(fwd, rev)
        assert diff["only_in_forward_L5"] == [] and diff["only_in_reverse_L10"] == []

    def test_one_directional_edge_surfaced(self):
        fwd = p.LampiranBlock(lampiran=5, direction="fwd", first_page=131, last_page=131)
        fwd.edges = [p.ParsedRow("49214", "49213", "t", "t", 161)]
        rev = p.LampiranBlock(lampiran=10, direction="rev", first_page=399, last_page=399)
        rev.edges = []
        diff = p.cross_direction_diff(fwd, rev)
        assert diff["only_in_forward_L5"] == [["49214", "49213"]]


class TestDigestDeterminism:
    def test_same_payload_same_digest(self):
        payload = {"relation": {"49213": {"codes": ["49214", "49219"]}}}
        assert p._relation_digest(payload) == p._relation_digest(dict(payload))

    def test_key_order_does_not_change_digest(self):
        a = {"relation": {"a": 1, "b": 2}}
        b = {"relation": {"b": 2, "a": 1}}
        assert p._relation_digest(a) == p._relation_digest(b)


# ---------------------------------------------------------------------------
# Integration — opt-in, gated on the vault PDF (skips in CI where it is absent)
# ---------------------------------------------------------------------------

_VAULT_PDF = common.DEFAULT_VAULT_ROOT / p.BPS_PDF_REL_PATH


@pytest.mark.skipif(not _VAULT_PDF.exists(), reason="vault BPS PDF not present (local-only)")
class TestIntegrationAgainstRealPDF:
    def test_relation_covers_full_canonical_and_is_consistent(self):
        result = p.extract(common.DEFAULT_VAULT_ROOT)
        m = result["manifest"]
        # 100% L5<->L10 consistency and full canonical coverage were the
        # validated ground-truth facts; pin them so a parser regression trips.
        assert m["counts"]["codes_2025_with_ancestry"] == 1559
        assert m["consistency_L5_vs_L10"]["only_in_forward_L5"] == 0
        assert m["consistency_L5_vs_L10"]["only_in_reverse_L10"] == 0
        assert result["relation"]["49213"]["codes"] == ["49214", "49219", "49413"]
        assert m["bps_pdf"]["sha256"] == p.BPS_PDF_SHA256
