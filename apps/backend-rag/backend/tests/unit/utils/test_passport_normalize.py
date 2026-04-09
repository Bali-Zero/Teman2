"""Unit tests for passport field normalization utilities."""

import pytest

from backend.utils.passport_normalize import (
    normalize_date,
    normalize_nationality,
    title_case_name,
)


class TestTitleCaseName:
    """Tests for title_case_name()."""

    def test_basic_uppercase_to_title_case(self):
        assert title_case_name("KIRMASOV") == "Kirmasov"

    def test_already_title_case_passthrough(self):
        assert title_case_name("Kirmasov") == "Kirmasov"

    def test_apostrophe_handling(self):
        assert title_case_name("O'BRIAN") == "O'Brian"

    def test_hyphen_handling(self):
        assert title_case_name("JEAN-PIERRE") == "Jean-Pierre"

    def test_mrz_double_chevron_format(self):
        assert title_case_name("KIRMASOV<<MAKSIM") == "Kirmasov Maksim"

    def test_none_input_returns_none(self):
        assert title_case_name(None) is None

    def test_empty_string_returns_none(self):
        assert title_case_name("") is None


class TestNormalizeNationality:
    """Tests for normalize_nationality()."""

    def test_iso3_code(self):
        assert normalize_nationality("RUS") == "Russian"

    def test_full_country_name(self):
        assert normalize_nationality("Russian Federation") == "Russian"

    def test_already_normalized(self):
        assert normalize_nationality("Russian") == "Russian"

    def test_uppercase_country(self):
        assert normalize_nationality("AUSTRALIA") == "Australian"

    def test_unknown_nationality_fallback(self):
        assert normalize_nationality("XYZLAND") == "Xyzland"

    def test_none_returns_none(self):
        assert normalize_nationality(None) is None

    def test_indonesian_term(self):
        assert normalize_nationality("JERMAN") == "German"


class TestNormalizeDate:
    """Tests for normalize_date()."""

    def test_iso_format_passthrough(self):
        assert normalize_date("1990-05-12") == "1990-05-12"

    def test_yymmdd_past(self):
        assert normalize_date("900512") == "1990-05-12"

    def test_yymmdd_future(self):
        assert normalize_date("301117") == "2030-11-17"

    def test_invalid_returns_none(self):
        assert normalize_date("not-a-date") is None

    def test_none_returns_none(self):
        assert normalize_date(None) is None

    def test_dd_mon_yyyy_format(self):
        assert normalize_date("15 AUG 2029") == "2029-08-15"

    def test_dd_month_yyyy_full_name(self):
        assert normalize_date("15 AUGUST 2029") == "2029-08-15"
