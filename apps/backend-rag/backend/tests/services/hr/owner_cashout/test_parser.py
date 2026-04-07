"""Tests for owner cashout sheet parser."""
import json
from pathlib import Path

from backend.services.hr.owner_cashout.parser import (
    CashoutRow,
    parse_bs_tab,
    parse_bz_tab,
    parse_idr,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> list[list[str]]:
    data = json.loads((FIXTURES / name).read_text())
    return data["rows"]


class TestParseIdr:
    def test_standard_format(self):
        assert parse_idr("Rp1,000,000") == 1_000_000

    def test_large_amount(self):
        assert parse_idr("Rp10,500,000") == 10_500_000

    def test_empty_string(self):
        assert parse_idr("") == 0

    def test_none(self):
        assert parse_idr(None) == 0

    def test_whitespace_only(self):
        assert parse_idr("   ") == 0

    def test_dash_placeholder(self):
        assert parse_idr("-") == 0
        assert parse_idr("—") == 0

    def test_plain_number_no_prefix(self):
        assert parse_idr("500000") == 500_000

    def test_with_dot_separator(self):
        assert parse_idr("Rp1.000.000") == 1_000_000

    def test_invalid_returns_zero(self):
        assert parse_idr("not a number") == 0


class TestParseBzTab:
    def test_skips_title_and_header(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        # Title (row 1), header (row 2) must be skipped
        assert all(r.client_name not in ("NEW CASHOUT 22 AUGUST 2025", "NAME") for r in result)

    def test_skips_empty_rows(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        assert all(r.client_name for r in result)

    def test_extracts_all_clients(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        assert len(result) == 6
        names = {r.client_name for r in result}
        assert "JULIANNA JANOSI" in names
        assert "EVA MARIE CASTEL" in names
        assert "JAMES ANTHONY KOSTRO" in names
        assert "MOHAMED REDA BOUZIANE" in names

    def test_parses_amounts_for_first_row(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        julianna = next(r for r in result if r.client_name == "JULIANNA JANOSI")
        assert julianna.process == "BRIDGING VISA"
        assert julianna.pnbp_idr == 1_000_000
        assert julianna.urgent_idr == 0
        assert julianna.rptka_imta_idr == 0
        assert julianna.total_income_idr == 5_000_000
        assert julianna.margin_bs_idr == 3_000_000
        assert julianna.margin_bz_idr == 1_000_000
        assert julianna.final_price_idr == 0  # BZ doesn't populate this
        assert julianna.entity == "BZ"

    def test_extracts_note_when_present(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        ryan = next(r for r in result if r.client_name == "RYAN RALPH HEATHCOTE")
        assert ryan.note == "DISCOUNT 200K"

    def test_urgent_amount_parsed(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        urgent = next(r for r in result if "MOHAMED" in r.client_name)
        assert urgent.urgent_idr == 1_000_000

    def test_row_index_preserves_sheet_position(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        julianna = next(r for r in result if r.client_name == "JULIANNA JANOSI")
        assert julianna.row_index == 3  # 1-indexed, row 3 in sheet

    def test_empty_rows_list(self):
        assert parse_bz_tab([]) == []

    def test_only_header_no_data(self):
        rows = [
            ["NEW CASHOUT"],
            ["NAME", "PROCESS"],
        ]
        assert parse_bz_tab(rows) == []


class TestParseBsTab:
    def test_extracts_clients(self):
        rows = load_fixture("bs_22_aug_sample.json")
        result = parse_bs_tab(rows)
        assert len(result) == 3
        names = [r.client_name for r in result]
        assert "JULIANNA JANOSI" in names
        assert "EVA MARIE CASTEL" in names

    def test_parses_bs_schema_amounts(self):
        rows = load_fixture("bs_22_aug_sample.json")
        result = parse_bs_tab(rows)
        julianna = next(r for r in result if r.client_name == "JULIANNA JANOSI")
        assert julianna.entity == "BS"
        assert julianna.process == "BRIDGING VISA"
        assert julianna.pnbp_idr == 1_000_000
        assert julianna.margin_bs_idr == 3_000_000
        assert julianna.final_price_idr == 4_000_000
        assert julianna.total_income_idr == 0  # BS doesn't populate this
        assert julianna.margin_bz_idr == 0     # BS doesn't populate this
        assert julianna.note is None

    def test_skips_empty_rows(self):
        rows = load_fixture("bs_22_aug_sample.json")
        result = parse_bs_tab(rows)
        assert all(r.client_name for r in result)

    def test_row_index_preserved(self):
        rows = load_fixture("bs_22_aug_sample.json")
        result = parse_bs_tab(rows)
        julianna = next(r for r in result if r.client_name == "JULIANNA JANOSI")
        assert julianna.row_index == 3

    def test_empty_input(self):
        assert parse_bs_tab([]) == []
