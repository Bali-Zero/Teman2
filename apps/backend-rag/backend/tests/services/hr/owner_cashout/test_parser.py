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
