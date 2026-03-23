"""Tests for War Room A2A agent registration.

Verifies that all 7 war-room agents are correctly registered
in a2a_service.py, launcher.py, and discovery.py with matching
agent cards on disk.

Run with: PYTHONPATH=. pytest apps/federation/tests/test_war_room_agents.py -v
"""

import json
from pathlib import Path

import pytest

WAR_ROOM_AGENTS = [
    "war-room-topic",
    "war-room-researcher",
    "war-room-strategist",
    "war-room-director",
    "war-room-image-gen",
    "war-room-canva",
    "war-room-delivery",
]

EXPECTED_PORTS = {
    "war-room-topic": 8100,
    "war-room-researcher": 8101,
    "war-room-strategist": 8102,
    "war-room-director": 8103,
    "war-room-image-gen": 8104,
    "war-room-canva": 8105,
    "war-room-delivery": 8106,
}

FEDERATION_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = FEDERATION_ROOT / "agents"


class TestWarRoomAgentCards:
    """Verify agent cards exist and have valid structure."""

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_agent_card_exists(self, agent_id: str) -> None:
        card_path = AGENTS_DIR / agent_id / "agent_card.json"
        assert card_path.exists(), f"Missing agent card: {card_path}"

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_agent_card_valid_json(self, agent_id: str) -> None:
        card_path = AGENTS_DIR / agent_id / "agent_card.json"
        card = json.loads(card_path.read_text())
        assert "name" in card
        assert "url" in card
        assert "skills" in card
        assert len(card["skills"]) > 0
        assert card["protocol_version"] == "0.3.0"

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_agent_card_has_extensions(self, agent_id: str) -> None:
        card_path = AGENTS_DIR / agent_id / "agent_card.json"
        card = json.loads(card_path.read_text())
        assert "extensions" in card
        assert len(card["extensions"]) > 0
        ext = card["extensions"][0]
        assert ext["uri"] == "urn:nuzantara:dispatch"

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_agent_card_port_matches(self, agent_id: str) -> None:
        card_path = AGENTS_DIR / agent_id / "agent_card.json"
        card = json.loads(card_path.read_text())
        expected_port = EXPECTED_PORTS[agent_id]
        assert f":{expected_port}/" in card["url"], (
            f"Card URL {card['url']} doesn't contain port {expected_port}"
        )


class TestWarRoomCLICommands:
    """Verify CLI commands are registered in a2a_service.py."""

    def test_all_agents_in_cli_commands(self) -> None:
        from apps.federation.a2a_service import AGENT_CLI_COMMANDS
        for agent_id in WAR_ROOM_AGENTS:
            assert agent_id in AGENT_CLI_COMMANDS, f"{agent_id} not in AGENT_CLI_COMMANDS"

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_cli_command_has_required_keys(self, agent_id: str) -> None:
        from apps.federation.a2a_service import AGENT_CLI_COMMANDS
        cmd = AGENT_CLI_COMMANDS[agent_id]
        assert "cmd_template" in cmd
        assert "timeout" in cmd
        assert cmd["timeout"] > 0


class TestWarRoomLauncher:
    """Verify ports are registered in launcher.py."""

    def test_all_agents_in_launcher(self) -> None:
        from apps.federation.launcher import AGENT_PORTS
        for agent_id in WAR_ROOM_AGENTS:
            assert agent_id in AGENT_PORTS, f"{agent_id} not in AGENT_PORTS"

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_port_matches_expected(self, agent_id: str) -> None:
        from apps.federation.launcher import AGENT_PORTS
        assert AGENT_PORTS[agent_id] == EXPECTED_PORTS[agent_id]


class TestWarRoomDiscovery:
    """Verify agents are registered in discovery.py."""

    def test_all_agents_in_registry(self) -> None:
        from apps.federation.discovery import AGENT_REGISTRY
        for agent_id in WAR_ROOM_AGENTS:
            assert agent_id in AGENT_REGISTRY, f"{agent_id} not in AGENT_REGISTRY"

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_agent_on_pro_machine(self, agent_id: str) -> None:
        from apps.federation.discovery import AGENT_REGISTRY
        assert AGENT_REGISTRY[agent_id]["machine"] == "pro"

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_port_consistent_across_modules(self, agent_id: str) -> None:
        from apps.federation.discovery import AGENT_REGISTRY
        from apps.federation.launcher import AGENT_PORTS
        assert AGENT_REGISTRY[agent_id]["port"] == AGENT_PORTS[agent_id], (
            f"Port mismatch for {agent_id}: "
            f"discovery={AGENT_REGISTRY[agent_id]['port']}, "
            f"launcher={AGENT_PORTS[agent_id]}"
        )
