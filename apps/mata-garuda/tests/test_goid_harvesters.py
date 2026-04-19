"""Tests for .go.id OSINT harvester contract (imigrasi/bkpm/kemlu/kemkumham).

The 4 agents share `_goid_base.harvest_goid()`. Rather than duplicate
tests, we verify the shared helper publishes correctly and that each
concrete agent wires the right config (URL, prefix, agent name) and
registers with the expected layer + GENOME path.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mata_garuda.agents import (
    bkpm_harvester as bkpm_mod,
    imigrasi_harvester as imi_mod,
    kemkumham_harvester as kum_mod,
    kemlu_harvester as kemlu_mod,
)
from mata_garuda.agents._goid_base import harvest_goid
from mata_garuda.tools import goid_tools as gt


# ── goid_tools ───────────────────────────────────────────────────────────


def test_extract_links_respects_prefix():
    html = """
    <a href="https://www.imigrasi.go.id/berita/post-a">Post A</a>
    <a href="https://www.imigrasi.go.id/about">About (dropped)</a>
    <a href="https://evil.example.com/berita/x">Evil (dropped)</a>
    <a href="//imigrasi.go.id/berita/proto-rel">Rel (kept)</a>
    """
    out = gt.extract_links(
        html,
        ["https://www.imigrasi.go.id/berita/", "https://imigrasi.go.id/berita/"],
    )
    urls = [x["url"] for x in out]
    assert "https://www.imigrasi.go.id/berita/post-a" in urls
    assert "https://imigrasi.go.id/berita/proto-rel" in urls
    assert not any("about" in u for u in urls)
    assert not any("evil.example.com" in u for u in urls)


def test_extract_links_dedup_and_skip_empty_title():
    html = """
    <a href="https://bkpm.go.id/id/publikasi/x"></a>
    <a href="https://bkpm.go.id/id/publikasi/x">Press A</a>
    <a href="https://bkpm.go.id/id/publikasi/x">Press A dup</a>
    """
    out = gt.extract_links(html, ["https://bkpm.go.id/id/publikasi/"])
    assert len(out) == 1
    assert out[0]["title"] == "Press A"


def test_extract_links_max_items_cap():
    html = "\n".join(
        f'<a href="https://kemlu.go.id/portal/id/read/{i}">Item {i}</a>'
        for i in range(25)
    )
    out = gt.extract_links(html, ["https://kemlu.go.id/portal/id/read/"], max_items=10)
    assert len(out) == 10


# ── shared harvest_goid ──────────────────────────────────────────────────


def test_harvest_goid_publishes_to_garuda_osint():
    html = '<a href="https://www.imigrasi.go.id/berita/a">Title A</a>'
    with patch(
        "mata_garuda.agents._goid_base.fetch_goid", return_value=(200, html)
    ), patch(
        "mata_garuda.agents._goid_base.stream_publish_redis",
        return_value="1-0",
    ) as fake_publish:
        result = harvest_goid(
            agent_name="imigrasi_harvester",
            source_domain="imigrasi.go.id",
            landing_url="https://www.imigrasi.go.id/berita/",
            allow_prefixes=["https://www.imigrasi.go.id/berita/"],
        )
    assert result["case_resolved"] is True
    assert result["published"] == 1
    stream, fields = fake_publish.call_args.args
    assert stream == "garuda:osint"
    assert fields["agent"] == "imigrasi_harvester"
    assert fields["source_agent"] == "imigrasi_harvester"
    assert fields["source_type"] == "osint_goid"
    assert fields["source"] == "imigrasi.go.id"
    assert fields["url"] == "https://www.imigrasi.go.id/berita/a"


def test_harvest_goid_transport_failure():
    with patch(
        "mata_garuda.agents._goid_base.fetch_goid", return_value=(0, "")
    ), patch(
        "mata_garuda.agents._goid_base.stream_publish_redis"
    ) as fake_publish:
        result = harvest_goid(
            agent_name="bkpm_harvester",
            source_domain="bkpm.go.id",
            landing_url="https://www.bkpm.go.id/id/publikasi/siaran-pers",
            allow_prefixes=["https://www.bkpm.go.id/id/publikasi/"],
        )
    assert result["case_resolved"] is False
    assert "transport" in result["reason"]
    fake_publish.assert_not_called()


def test_harvest_goid_http_error_code():
    with patch(
        "mata_garuda.agents._goid_base.fetch_goid", return_value=(503, "")
    ), patch(
        "mata_garuda.agents._goid_base.stream_publish_redis"
    ) as fake_publish:
        result = harvest_goid(
            agent_name="kemlu_harvester",
            source_domain="kemlu.go.id",
            landing_url="https://kemlu.go.id/portal/id/list/berita",
            allow_prefixes=["https://kemlu.go.id/portal/id/read/"],
        )
    assert result["case_resolved"] is False
    assert "503" in result["reason"]
    fake_publish.assert_not_called()


def test_harvest_goid_structure_drift():
    with patch(
        "mata_garuda.agents._goid_base.fetch_goid",
        return_value=(200, "<html>empty</html>"),
    ), patch(
        "mata_garuda.agents._goid_base.stream_publish_redis"
    ) as fake_publish:
        result = harvest_goid(
            agent_name="kemkumham_harvester",
            source_domain="kemenkumham.go.id",
            landing_url="https://www.kemenkumham.go.id/berita",
            allow_prefixes=["https://www.kemenkumham.go.id/berita/"],
        )
    assert result["case_resolved"] is False
    assert "structure drift" in result["reason"] or "no matching" in result["reason"]
    fake_publish.assert_not_called()


# ── each concrete agent wires the right helper ──────────────────────────

AGENTS = [
    (imi_mod, "imigrasi_harvester", "imigrasi.go.id"),
    (bkpm_mod, "bkpm_harvester", "bkpm.go.id"),
    (kemlu_mod, "kemlu_harvester", "kemlu.go.id"),
    (kum_mod, "kemkumham_harvester", "kemenkumham.go.id"),
]


@pytest.mark.parametrize("mod,agent_name,source_domain", AGENTS)
def test_agent_registers_and_wires_config(mod, agent_name, source_domain):
    from mata_garuda.registry import get_agent

    agent = get_agent(agent_name)
    assert agent is not None
    assert agent.layer == "harvester"
    assert agent.name == agent_name

    # Wiring: SOURCE_DOMAIN matches expected, allow prefixes non-empty
    assert mod.SOURCE_DOMAIN == source_domain
    assert mod.ALLOW_PREFIXES and all(
        source_domain in p or p.startswith("https://www.") for p in mod.ALLOW_PREFIXES
    )

    # GENOME file co-located
    genome = Path(mod.__file__).parent / f"{agent_name}_GENOME.md"
    assert genome.exists()
    text = genome.read_text()
    assert "garuda:osint" in text
    assert "OSINT blindato" in text
    assert "rate" in text.lower()


@pytest.mark.parametrize("mod,agent_name,_", AGENTS)
def test_each_agent_delegates_to_harvest_goid(mod, agent_name, _):
    # The concrete `harvest_*` wrapper must call the shared harvest_goid
    # with its own AGENT_NAME + prefixes.
    wrapper_name = f"harvest_{agent_name.replace('_harvester', '')}"
    # kemkumham agent is named harvest_kemkumham
    if agent_name == "kemkumham_harvester":
        wrapper_name = "harvest_kemkumham"
    wrapper = getattr(mod, wrapper_name)

    with patch.object(mod, "harvest_goid") as fake:
        fake.return_value = {"case_resolved": True, "published": 1, "reason": ""}
        result = wrapper()
    fake.assert_called_once()
    kwargs = fake.call_args.kwargs
    assert kwargs["agent_name"] == agent_name
    assert kwargs["source_domain"] == mod.SOURCE_DOMAIN
    assert kwargs["landing_url"] == mod.LANDING_URL
    assert kwargs["allow_prefixes"] == mod.ALLOW_PREFIXES
    assert result["case_resolved"] is True
