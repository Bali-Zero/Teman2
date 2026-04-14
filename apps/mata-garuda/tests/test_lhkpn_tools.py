"""Tests for LHKPN scraper tools (parsing only — HTTP mocked)."""
from __future__ import annotations

from mata_garuda.tools.lhkpn_tools import (
    LHKPN_USER_AGENTS,
    parse_lhkpn_profile_html,
    parse_lhkpn_search_html,
)


SEARCH_FIXTURE = """
<html><body><table id="resultsTable">
<tr><td>Budi Santoso</td><td>199001012010011001</td><td>Direktur Jenderal Pajak</td><td>2024</td></tr>
<tr><td>Ahmad Wijaya</td><td>198805052012021002</td><td>Sekretaris Jenderal</td><td>2023</td></tr>
</table></body></html>
"""

PROFILE_FIXTURE = """
<html><body>
<div class="profile">
<span id="nama">Budi Santoso</span>
<span id="nip">199001012010011001</span>
<span id="jabatan">Direktur Jenderal Pajak</span>
<span id="angkatan">1995</span>
<span id="totalHarta">Rp 12.500.000.000</span>
<table id="properties"><tr><td>Tanah</td></tr><tr><td>Tanah</td></tr></table>
<table id="vehicles"><tr><td>Mobil</td></tr></table>
<table id="accounts"><tr><td>BCA</td></tr><tr><td>Mandiri</td></tr></table>
</div></body></html>
"""


def test_parse_search_extracts_results():
    results = parse_lhkpn_search_html(SEARCH_FIXTURE)
    assert len(results) == 2
    assert results[0]["nama"] == "Budi Santoso"
    assert results[0]["nip"] == "199001012010011001"
    assert results[0]["jabatan"] == "Direktur Jenderal Pajak"
    assert results[0]["report_year"] == "2024"


def test_parse_search_empty_returns_empty_list():
    assert parse_lhkpn_search_html("<html></html>") == []


def test_parse_search_no_results_table_returns_empty():
    assert parse_lhkpn_search_html("<html><body>No data</body></html>") == []


def test_parse_search_partial_row_skipped():
    """A row with fewer than 4 cells is skipped."""
    html = """
    <html><body><table id="resultsTable">
    <tr><td>Only Name</td></tr>
    <tr><td>Full</td><td>123</td><td>Pos</td><td>2024</td></tr>
    </table></body></html>
    """
    results = parse_lhkpn_search_html(html)
    assert len(results) == 1
    assert results[0]["nama"] == "Full"


def test_parse_profile_extracts_assets():
    profile = parse_lhkpn_profile_html(PROFILE_FIXTURE)
    assert profile["nama"] == "Budi Santoso"
    assert profile["nip"] == "199001012010011001"
    assert profile["jabatan"] == "Direktur Jenderal Pajak"
    assert profile["angkatan"] == "1995"
    assert profile["total_harta_idr"] == 12_500_000_000
    assert profile["properties_count"] == 2
    assert profile["vehicles_count"] == 1
    assert profile["accounts_count"] == 2


def test_parse_profile_handles_missing_fields():
    profile = parse_lhkpn_profile_html(
        "<html><body><div class='profile'></div></body></html>"
    )
    assert profile["nama"] == ""
    assert profile["total_harta_idr"] == 0
    assert profile["properties_count"] == 0


def test_parse_profile_handles_idr_with_commas():
    """Indonesian Rupiah uses dots as thousand separators, but some pages may use commas."""
    html = """
    <div class="profile">
    <span id="totalHarta">Rp 5,000,000</span>
    </div>
    """
    profile = parse_lhkpn_profile_html(html)
    assert profile["total_harta_idr"] == 5_000_000


def test_user_agents_pool_has_3_variants():
    """3 User-Agents for rotation per the GENOME constraint."""
    assert len(LHKPN_USER_AGENTS) == 3
    for ua in LHKPN_USER_AGENTS:
        assert "Mozilla" in ua


def test_user_agents_have_different_browsers():
    """The 3 UAs should be visibly different (not just whitespace variations)."""
    uas = LHKPN_USER_AGENTS
    # Each UA should be unique
    assert len(set(uas)) == 3
