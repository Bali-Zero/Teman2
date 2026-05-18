"""Tests for scripts/wr3_contracts.py — YAML loader + meta-schema conformance."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wr3_contracts import (  # noqa: E402
    AgentContract,
    ChannelRoute,
    WR3Contracts,
    load_contracts,
)


@pytest.fixture(scope="module")
def contracts() -> WR3Contracts:
    return load_contracts()


def test_load_thirteen_agents(contracts: WR3Contracts) -> None:
    assert len(contracts.agents) == 13


def test_load_six_channels(contracts: WR3Contracts) -> None:
    assert len(contracts.routes) == 6
    expected = {
        "wr3_episode_brief_requested",
        "wr3_episode_pre_render_ready",
        "wr3_episode_gate_passed",
        "wr3_episode_assembly_ready",
        "wr3_episode_critic_verdict",
        "wr3_episode_staged",
    }
    assert set(contracts.routes.keys()) == expected


def test_design_architect_is_gate(contracts: WR3Contracts) -> None:
    arch = contracts.for_agent("wr3-design-architect")
    assert arch.is_gate
    assert arch.is_core
    assert arch.cost.hard_halt_on_exceed is True


def test_brief_interpreter_law_2_declared(contracts: WR3Contracts) -> None:
    bi = contracts.for_agent("wr3-brief-interpreter")
    assert "law_2_osint_blindato" in bi.law_compliance
    # Sentinel phrase from contract YAML — defends against accidental edit
    txt = bi.law_compliance["law_2_osint_blindato"]
    assert "SOLE" in txt or "NEVER" in txt


def test_audio_producer_cartesia_banned(contracts: WR3Contracts) -> None:
    """Law 6 enforcement at contract layer."""
    aap = contracts.for_agent("wr3-audio-asset-producer")
    txt = aap.law_compliance.get("law_6_local_sovereignty", "")
    assert "Cartesia" in txt and "BANNED" in txt


def test_hot_path_channels(contracts: WR3Contracts) -> None:
    hot = contracts.hot_path_channels
    # 5 of 6 channels are hot path (staged is end-of-pipeline, cold)
    assert "wr3_episode_brief_requested" in hot
    assert "wr3_episode_critic_verdict" in hot
    assert "wr3_episode_staged" not in hot


def test_all_agents_have_law_compliance_block(contracts: WR3Contracts) -> None:
    required_laws = {f"law_{i}_" for i in range(1, 9)}
    for name, agent in contracts.agents.items():
        keys = set(agent.law_compliance.keys())
        for prefix in required_laws:
            assert any(k.startswith(prefix) for k in keys), (
                f"{name} missing law starting with {prefix}, has: {keys}"
            )


def test_unknown_agent_raises(contracts: WR3Contracts) -> None:
    with pytest.raises(KeyError, match="Unknown agent"):
        contracts.for_agent("wr3-non-existent")


def test_unknown_channel_raises(contracts: WR3Contracts) -> None:
    with pytest.raises(KeyError, match="Unknown channel"):
        contracts.route_for("wr3_episode_fake_channel")


def test_critic_has_no_agent_tool(contracts: WR3Contracts) -> None:
    """Symbiosis Law 5 + dossier 06 rule — critic cannot recurse (no Agent tool)."""
    critic = contracts.for_agent("wr3-critic")
    assert "Agent" not in critic.allowed_tools, "Critic must not have Agent tool (no recursion)"


def test_clip_renderer_render_cost_class(contracts: WR3Contracts) -> None:
    cr = contracts.for_agent("wr3-clip-renderer")
    assert cr.cost_class == "render"
    assert cr.cost.ceiling_usd is None
    assert "Flow Pro" in cr.cost.ceiling_unit


def test_audio_producer_cost_class(contracts: WR3Contracts) -> None:
    aap = contracts.for_agent("wr3-audio-asset-producer")
    assert aap.cost_class == "audio_gen"


def test_contract_version_semver(contracts: WR3Contracts) -> None:
    import re
    semver_re = re.compile(r"^\d+\.\d+\.\d+$")
    for name, agent in contracts.agents.items():
        assert semver_re.match(agent.contract_version), (
            f"{name} contract_version not semver: {agent.contract_version!r}"
        )
