"""Tests for the --only per-code selection logic added to both Qdrant indexers.

Pure-function tests only — no network, no Qdrant, no OpenAI.  We exercise the
two pure helpers each script exposes: ``parse_only_codes`` (flag parsing +
validation) and the entry-filter function (``filter_to_codes`` for the gold
indexer, ``filter_entries_to_codes`` for the BPS re-indexer).
"""

import argparse

import pytest

from backend.scripts.index_kbli_gold_content import (
    filter_to_codes,
)
from backend.scripts.index_kbli_gold_content import (
    parse_only_codes as parse_gold_only,
)
from backend.scripts.reindex_kbli_2025_final import (
    filter_entries_to_codes,
)
from backend.scripts.reindex_kbli_2025_final import (
    parse_only_codes as parse_bps_only,
)

# ─── parse_only_codes (shared semantics, two copies) ───────────────────────


class TestParseOnlyCodes:
    """Both copies share identical semantics — parametrise over both."""

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_none_when_flag_absent(self, parser):
        assert parser(None) is None
        assert parser("") is None

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_single_code(self, parser):
        assert parser("56101") == ["56101"]

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_multiple_codes(self, parser):
        assert parser("56101,56210,61108") == ["56101", "56210", "61108"]

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_strips_whitespace(self, parser):
        assert parser(" 56101 , 56210 ") == ["56101", "56210"]

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_deduplicates_preserving_order(self, parser):
        assert parser("56101,56210,56101") == ["56101", "56210"]

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_rejects_too_short(self, parser):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid KBLI code"):
            parser("5610")

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_rejects_too_long(self, parser):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid KBLI code"):
            parser("561011")

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_rejects_alpha(self, parser):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid KBLI code"):
            parser("5610a")

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_rejects_empty_token(self, parser):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid KBLI code"):
            parser("56101,,56210")

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_rejects_junk(self, parser):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid KBLI code"):
            parser("hello")


# ─── filter_to_codes (gold indexer — dict input) ───────────────────────────


class TestFilterToCodes:
    def _entries(self) -> dict[str, dict]:
        return {
            "56101": {"whatItMeans": "Restoran"},
            "56210": {"whatItMeans": "Katering"},
            "61108": {"whatItMeans": "Telekomunikasi"},
        }

    def test_passthrough_when_none(self):
        entries = self._entries()
        assert filter_to_codes(entries, None) is entries

    def test_selects_subset(self):
        result = filter_to_codes(self._entries(), ["56101", "61108"])
        assert set(result.keys()) == {"56101", "61108"}

    def test_preserves_requested_order(self):
        result = filter_to_codes(self._entries(), ["61108", "56101"])
        assert list(result.keys()) == ["61108", "56101"]

    def test_single_code(self):
        result = filter_to_codes(self._entries(), ["56210"])
        assert list(result.keys()) == ["56210"]

    def test_errors_on_missing_code(self):
        with pytest.raises(SystemExit) as exc_info:
            filter_to_codes(self._entries(), ["56101", "99999"])
        assert exc_info.value.code == 1

    def test_errors_name_all_missing(self, caplog):
        with pytest.raises(SystemExit):
            filter_to_codes(self._entries(), ["99999", "88888"])
        msgs = [r.getMessage() for r in caplog.records]
        assert any("99999" in m and "88888" in m for m in msgs)


# ─── filter_entries_to_codes (BPS re-indexer — list input) ──────────────────


class TestFilterEntriesToCodes:
    def _entries(self) -> list[dict]:
        return [
            {"kode_kbli_2025": "56101", "judul": "Restoran"},
            {"kode_kbli_2025": "56210", "judul": "Katering"},
            {"kode_kbli_2025": "61108", "judul": "Telekomunikasi"},
        ]

    def test_passthrough_when_none(self):
        entries = self._entries()
        assert filter_entries_to_codes(entries, None) is entries

    def test_selects_subset(self):
        result = filter_entries_to_codes(self._entries(), ["56101", "61108"])
        assert [e["kode_kbli_2025"] for e in result] == ["56101", "61108"]

    def test_preserves_requested_order(self):
        result = filter_entries_to_codes(self._entries(), ["61108", "56101"])
        assert [e["kode_kbli_2025"] for e in result] == ["61108", "56101"]

    def test_single_code(self):
        result = filter_entries_to_codes(self._entries(), ["56210"])
        assert len(result) == 1
        assert result[0]["kode_kbli_2025"] == "56210"

    def test_errors_on_missing_code(self):
        with pytest.raises(SystemExit) as exc_info:
            filter_entries_to_codes(self._entries(), ["56101", "99999"])
        assert exc_info.value.code == 1

    def test_errors_name_all_missing(self, caplog):
        with pytest.raises(SystemExit):
            filter_entries_to_codes(self._entries(), ["99999", "88888"])
        msgs = [r.getMessage() for r in caplog.records]
        assert any("99999" in m and "88888" in m for m in msgs)
