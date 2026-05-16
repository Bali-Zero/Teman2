"""Tests for the LHKPN harvester agent (registration + harvest functions)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from mata_garuda.agents.lhkpn_harvester import (
    harvest_lhkpn_by_name,
    harvest_lhkpn_for_nip,
)


def test_harvest_by_nip_publishes_to_garuda_raw():
    """Successful profile fetch publishes harvest.lhkpn to garuda:raw."""
    profile = {
        "nama": "Budi Santoso",
        "nip": "199001012010011001",
        "jabatan": "Dirjen Pajak",
        "angkatan": "1995",
        "total_harta_idr": 12_500_000_000,
        "properties_count": 7,
        "vehicles_count": 3,
        "accounts_count": 12,
    }

    with patch("mata_garuda.agents.lhkpn_harvester.scrape_lhkpn_profile", return_value=profile), \
         patch("mata_garuda.agents.lhkpn_harvester.stream_publish_redis", return_value="1-0") as fake_publish:
        result = harvest_lhkpn_for_nip("199001012010011001")

    assert result["case_resolved"] is True
    assert result["nip"] == "199001012010011001"
    fake_publish.assert_called_once()
    stream, fields = fake_publish.call_args.args
    assert stream == "garuda:raw"
    assert fields["agent"] == "lhkpn_harvester"
    assert "Budi Santoso" in fields["title"]
    # Portal migrated 2026-04-26: antv.kpk.go.id is NXDOMAIN, KPK now
    # serves at elhkpn.kpk.go.id (see research/2026-05-16-lhkpn-flow-triage.md).
    assert fields["source"] == "elhkpn.kpk.go.id"
    assert fields["source_type"] == "lhkpn"


def test_harvest_by_nip_empty_result_fails():
    """Empty profile (HTTP failure or NIP not found) returns case_not_resolved."""
    with patch("mata_garuda.agents.lhkpn_harvester.scrape_lhkpn_profile", return_value={}), \
         patch("mata_garuda.agents.lhkpn_harvester.stream_publish_redis") as fake_publish:
        result = harvest_lhkpn_for_nip("000")

    assert result["case_resolved"] is False
    assert "empty" in result.get("reason", "").lower() or "no data" in result.get("reason", "").lower() or "not found" in result.get("reason", "").lower()
    fake_publish.assert_not_called()


def test_harvest_by_nip_missing_nip_field_fails():
    """Profile dict without 'nip' field is treated as failure."""
    bad_profile = {"nama": "X", "jabatan": "Y"}  # no nip
    with patch("mata_garuda.agents.lhkpn_harvester.scrape_lhkpn_profile", return_value=bad_profile), \
         patch("mata_garuda.agents.lhkpn_harvester.stream_publish_redis") as fake_publish:
        result = harvest_lhkpn_for_nip("000")

    assert result["case_resolved"] is False
    fake_publish.assert_not_called()


def test_harvest_by_name_picks_first_then_fetches_profile():
    """Search returns hits → fetch first NIP's profile → publish."""
    search_hits = [
        {"nama": "Ahmad Wijaya", "nip": "111", "jabatan": "x", "report_year": "2024"},
    ]
    profile = {
        "nama": "Ahmad Wijaya", "nip": "111", "jabatan": "x", "angkatan": "1990",
        "total_harta_idr": 5_000_000, "properties_count": 1,
        "vehicles_count": 0, "accounts_count": 1,
    }

    with patch("mata_garuda.agents.lhkpn_harvester.scrape_lhkpn_search", return_value=search_hits), \
         patch("mata_garuda.agents.lhkpn_harvester.scrape_lhkpn_profile", return_value=profile), \
         patch("mata_garuda.agents.lhkpn_harvester.stream_publish_redis", return_value="2-0") as fake_publish:
        result = harvest_lhkpn_by_name("Ahmad")

    assert result["case_resolved"] is True
    fake_publish.assert_called_once()


def test_harvest_by_name_no_results_fails():
    """Empty search returns case_not_resolved."""
    with patch("mata_garuda.agents.lhkpn_harvester.scrape_lhkpn_search", return_value=[]), \
         patch("mata_garuda.agents.lhkpn_harvester.stream_publish_redis") as fake_publish:
        result = harvest_lhkpn_by_name("nonexistent")

    assert result["case_resolved"] is False
    fake_publish.assert_not_called()


def test_harvest_by_name_first_hit_no_nip_fails():
    """Search hit without NIP → no profile fetch."""
    bad_hits = [{"nama": "X", "nip": "", "jabatan": "Y", "report_year": "2024"}]
    with patch("mata_garuda.agents.lhkpn_harvester.scrape_lhkpn_search", return_value=bad_hits), \
         patch("mata_garuda.agents.lhkpn_harvester.scrape_lhkpn_profile") as fake_profile, \
         patch("mata_garuda.agents.lhkpn_harvester.stream_publish_redis") as fake_publish:
        result = harvest_lhkpn_by_name("X")

    assert result["case_resolved"] is False
    fake_profile.assert_not_called()
    fake_publish.assert_not_called()


def test_agent_registered_in_registry():
    """Importing the module registers lhkpn_harvester in the global registry."""
    # Trigger registration by importing the module
    import mata_garuda.agents.lhkpn_harvester  # noqa: F401
    from mata_garuda.registry import get_agent

    agent = get_agent("lhkpn_harvester")
    assert agent is not None
    assert agent.name == "lhkpn_harvester"
    assert agent.layer == "harvester"
    # Tools are functions; check by name
    fn_names = {fn.__name__ for fn in agent.functions}
    assert "harvest_lhkpn_for_nip" in fn_names
    assert "harvest_lhkpn_by_name" in fn_names


def test_genome_md_exists_and_has_constraints():
    """GENOME.md exists alongside the agent file with required constraints."""
    p = (
        Path(__file__).parent.parent
        / "mata_garuda" / "agents" / "lhkpn_harvester_GENOME.md"
    )
    assert p.exists(), f"Missing GENOME at {p}"
    text = p.read_text()
    # Must mention rate limit + UA rotation + escalation
    assert "rate" in text.lower() or "10 req" in text.lower() or "6 second" in text.lower()
    assert "User-Agent" in text or "user-agent" in text.lower()
    assert "escalat" in text.lower()
