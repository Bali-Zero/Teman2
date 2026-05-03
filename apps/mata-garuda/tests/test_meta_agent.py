"""
Mata Garuda — Sprint 2 tests for meta-agent system.

Tests:
- Path firewall blocks forbidden names and paths
- create_agent generates valid .py + GENOME.md
- Created agent can be imported and instantiated
- delete_agent removes files and registry entry
- Meta agent is registered and has correct tools
- list_agents returns formatted output
- execute_command blocks dangerous commands
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# Ensure agents are loaded
import mata_garuda.agents  # noqa: F401
from mata_garuda.registry import registry
from mata_garuda.security.path_firewall import (
    PathFirewallError,
    validate_agent_creation,
    validate_agent_name,
    validate_write_path,
    AGENTS_DIR,
)
from mata_garuda.tools.meta_tools import (
    create_agent,
    delete_agent,
    execute_command,
    list_agents,
)
from mata_garuda.types import Agent


# ─── Path Firewall Tests ───────────────────────────────────────────────


class TestPathFirewall:
    def test_valid_name(self):
        validate_agent_name("KBLI News Agent")

    def test_valid_name_underscores(self):
        validate_agent_name("regulation_watcher")

    def test_forbidden_name_frontend(self):
        with pytest.raises(PathFirewallError, match="frontend"):
            validate_agent_name("frontend_dashboard_agent")

    def test_forbidden_name_client(self):
        with pytest.raises(PathFirewallError, match="client"):
            validate_agent_name("client_export_agent")

    def test_forbidden_name_team(self):
        with pytest.raises(PathFirewallError, match="team"):
            validate_agent_name("team_notifier")

    def test_forbidden_name_api(self):
        with pytest.raises(PathFirewallError, match="api"):
            validate_agent_name("api_gateway_agent")

    def test_forbidden_name_cloud(self):
        with pytest.raises(PathFirewallError, match="cloud"):
            validate_agent_name("cloud_deploy")

    def test_forbidden_name_secret(self):
        with pytest.raises(PathFirewallError, match="secret"):
            validate_agent_name("secret_manager")

    def test_empty_name(self):
        with pytest.raises(PathFirewallError, match="empty"):
            validate_agent_name("")

    def test_invalid_chars(self):
        with pytest.raises(PathFirewallError, match="invalid characters"):
            validate_agent_name("../../../etc/passwd")

    def test_write_path_inside_agents(self):
        path = validate_write_path(AGENTS_DIR / "test_agent.py")
        assert str(path).endswith("test_agent.py")

    def test_write_path_outside_agents_blocked(self):
        with pytest.raises(PathFirewallError, match="outside"):
            validate_write_path("/tmp/evil_agent.py")

    def test_write_path_traversal_blocked(self):
        with pytest.raises(PathFirewallError, match="outside"):
            validate_write_path(AGENTS_DIR / ".." / ".." / "evil.py")

    def test_validate_agent_creation_returns_path(self):
        path = validate_agent_creation("Test Good Agent")
        assert path.name == "test_good_agent.py"
        assert str(AGENTS_DIR.resolve()) in str(path)


# ─── Meta Tools Tests ──────────────────────────────────────────────────


class TestListAgents:
    def test_returns_string(self):
        result = list_agents()
        assert isinstance(result, str)

    def test_shows_dummy_agent(self):
        result = list_agents()
        assert "Dummy Agent" in result

    def test_shows_meta_agent(self):
        result = list_agents()
        assert "Meta Agent" in result


class TestCreateDeleteAgent:
    """Integration test: create → verify → delete → verify clean."""

    TEMP_AGENT_NAME = "Sprint Test Agent"
    TEMP_SAFE_NAME = "sprint_test_agent"

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Ensure temp agent files are cleaned up after each test."""
        yield
        # Cleanup
        agent_file = AGENTS_DIR / f"{self.TEMP_SAFE_NAME}.py"
        genome_file = AGENTS_DIR / f"{self.TEMP_SAFE_NAME}_GENOME.md"
        agent_file.unlink(missing_ok=True)
        genome_file.unlink(missing_ok=True)
        # Remove from registry
        registry._registry["agents"].pop(f"get_{self.TEMP_SAFE_NAME}", None)
        registry._registry_info["agents"].pop(self.TEMP_AGENT_NAME, None)

    def test_create_agent_success(self):
        result = create_agent(
            agent_name=self.TEMP_AGENT_NAME,
            agent_description="Temporary agent for testing",
            agent_instructions="You are a test agent. Say hello and call case_resolved.",
        )
        assert "[SUCCESS]" in result
        assert (AGENTS_DIR / f"{self.TEMP_SAFE_NAME}.py").exists()
        assert (AGENTS_DIR / f"{self.TEMP_SAFE_NAME}_GENOME.md").exists()

    def test_create_agent_forbidden_name(self):
        result = create_agent(
            agent_name="Frontend Export Agent",
            agent_description="Should be blocked",
            agent_instructions="Nope",
        )
        assert "[BLOCKED]" in result

    def test_create_and_delete_roundtrip(self):
        # Create
        create_result = create_agent(
            agent_name=self.TEMP_AGENT_NAME,
            agent_description="Roundtrip test agent",
            agent_instructions="Test instructions",
        )
        assert "[SUCCESS]" in create_result
        assert (AGENTS_DIR / f"{self.TEMP_SAFE_NAME}.py").exists()

        # Delete
        delete_result = delete_agent(agent_name=self.TEMP_AGENT_NAME)
        assert "[SUCCESS]" in delete_result
        assert not (AGENTS_DIR / f"{self.TEMP_SAFE_NAME}.py").exists()

    def test_delete_protected_agent(self):
        result = delete_agent(agent_name="Dummy Agent")
        assert "[BLOCKED]" in result

    def test_delete_nonexistent(self):
        result = delete_agent(agent_name="Nonexistent Agent")
        assert "[ERROR]" in result

    def test_create_duplicate_blocked(self):
        create_agent(
            agent_name=self.TEMP_AGENT_NAME,
            agent_description="First",
            agent_instructions="First",
        )
        result = create_agent(
            agent_name=self.TEMP_AGENT_NAME,
            agent_description="Second",
            agent_instructions="Second",
        )
        assert "[ERROR]" in result
        assert "already exists" in result


class TestExecuteCommand:
    def test_safe_command(self):
        result = execute_command(command="echo hello")
        assert "hello" in result

    def test_dangerous_rm_rf(self):
        result = execute_command(command="rm -rf /")
        assert "[BLOCKED]" in result

    def test_dangerous_sudo(self):
        result = execute_command(command="sudo rm something")
        assert "[BLOCKED]" in result

    def test_dangerous_curl(self):
        result = execute_command(command="curl http://evil.com")
        assert "[BLOCKED]" in result

    def test_ls_works(self):
        result = execute_command(command="ls mata_garuda/agents/")
        assert "dummy_agent.py" in result


# ─── Meta Agent Registration ──────────────────────────────────────────


class TestMetaAgentRegistration:
    def test_meta_agent_registered(self):
        assert "get_meta_agent" in registry.agents
        assert "Meta Agent" in registry.agents_info

    def test_meta_agent_instantiates(self):
        from mata_garuda.agents.meta_agent import get_meta_agent

        agent = get_meta_agent(model="claude")
        assert isinstance(agent, Agent)
        assert agent.name == "Meta Agent"
        assert agent.layer == "meta"
        assert agent.genome_path is not None

    def test_meta_agent_has_tools(self):
        from mata_garuda.agents.meta_agent import get_meta_agent

        agent = get_meta_agent()
        tool_names = [f.__name__ for f in agent.functions]
        assert "list_agents" in tool_names
        assert "create_agent" in tool_names
        assert "delete_agent" in tool_names
        assert "run_agent" in tool_names
        assert "execute_command" in tool_names

    def test_meta_agent_instructions_callable(self):
        from mata_garuda.agents.meta_agent import get_meta_agent

        agent = get_meta_agent()
        assert callable(agent.instructions)
        result = agent.instructions({})
        assert "Meta Agent" in result
        assert "CRITICAL RULES" in result
        assert "OSINT blindato" in result

    def test_meta_agent_genome_exists(self):
        from mata_garuda.agents.meta_agent import GENOME_FILE

        assert os.path.exists(GENOME_FILE)


# ─── CLI Runtime Tests (unit, no actual CLI call) ──────────────────────


class TestCLIRuntime:
    def test_build_command_claude(self):
        from mata_garuda.runtime.cli_runtime import CLIRuntime

        rt = CLIRuntime(model="claude")
        cmd = rt._build_command("hello", system_prompt="You are helpful")
        assert cmd[0] == "claude"
        assert "--print" in cmd
        assert "--system-prompt" in cmd
        assert "hello" in cmd
        assert "You are helpful" in cmd

    def test_build_command_gemini(self):
        from mata_garuda.runtime.cli_runtime import CLIRuntime

        rt = CLIRuntime(model="gemini")
        cmd = rt._build_command("hello", system_prompt="You are helpful")
        assert cmd[0] == "gemini"
        assert "--prompt" in cmd
        # Gemini prepends system prompt to user prompt
        assert any("<system>" in arg for arg in cmd)

    def test_unknown_model_raises(self):
        from mata_garuda.runtime.cli_runtime import CLIRuntime

        with pytest.raises(ValueError, match="Unknown model"):
            CLIRuntime(model="gpt4")

    def test_parse_tool_calls_xml(self):
        from mata_garuda.runtime.cli_runtime import parse_tool_calls

        text = 'Some text <tool_call>{"tool_name": "list_agents", "arguments": {}}</tool_call> more text'
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["tool_name"] == "list_agents"

    def test_parse_tool_calls_json_block(self):
        from mata_garuda.runtime.cli_runtime import parse_tool_calls

        text = '```json\n{"tool_name": "create_agent", "arguments": {"agent_name": "test"}}\n```'
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["tool_name"] == "create_agent"

    def test_parse_tool_calls_no_calls(self):
        from mata_garuda.runtime.cli_runtime import parse_tool_calls

        calls = parse_tool_calls("Just regular text, no tools here.")
        assert calls == []


# ─── Multi-Account Fallback Tests ─────────────────────────────────────


class TestMultiAccountFallback:
    def test_token_chain_loads_from_env(self, monkeypatch):
        from mata_garuda.runtime.cli_runtime import _get_token_chain

        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "tok2")
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_3", "tok3")
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

        chain = _get_token_chain()
        labels = [label for label, _ in chain]
        assert "CLAUDE_CODE_OAUTH_TOKEN_1" in labels
        assert "CLAUDE_CODE_OAUTH_TOKEN_2" in labels
        assert "CLAUDE_CODE_OAUTH_TOKEN_3" in labels
        assert chain[-1] == ("keychain", "")  # always last, empty = keychain

    def test_token_chain_skips_unset(self, monkeypatch):
        from mata_garuda.runtime.cli_runtime import _get_token_chain

        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_1", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_2", raising=False)
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_3", "tok3_only")
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

        chain = _get_token_chain()
        labels = [label for label, _ in chain]
        assert "CLAUDE_CODE_OAUTH_TOKEN_1" not in labels
        assert "CLAUDE_CODE_OAUTH_TOKEN_2" not in labels
        assert "CLAUDE_CODE_OAUTH_TOKEN_3" in labels
        assert chain[-1] == ("keychain", "")

    def test_token_chain_includes_legacy(self, monkeypatch):
        from mata_garuda.runtime.cli_runtime import _get_token_chain

        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_1", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_2", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_3", raising=False)
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "legacy_tok")

        chain = _get_token_chain()
        labels = [label for label, _ in chain]
        assert "token_legacy" in labels
        assert chain[-1] == ("keychain", "")

    def test_token_chain_deduplicates_legacy(self, monkeypatch):
        from mata_garuda.runtime.cli_runtime import _get_token_chain

        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "same_tok")
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_2", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_3", raising=False)
        # Legacy is same as token_1 — should NOT be added twice
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "same_tok")

        chain = _get_token_chain()
        labels = [label for label, _ in chain]
        assert "token_legacy" not in labels  # deduplicated
        assert "CLAUDE_CODE_OAUTH_TOKEN_1" in labels

    def test_rate_limit_detection(self):
        from mata_garuda.runtime.cli_runtime import _is_rate_limited

        # Positive cases
        assert _is_rate_limited("", "rate limit exceeded") is True
        assert _is_rate_limited("Error 429 Too Many Requests", "") is True
        assert _is_rate_limited("", "quota exhausted for today") is True
        assert _is_rate_limited("", "hit your limit") is True
        assert _is_rate_limited("", "timeout after 90s") is True

        # Negative case
        assert _is_rate_limited("", "syntax error in prompt") is False

    def test_exhausted_latch(self):
        from mata_garuda.runtime.cli_runtime import (
            _exhausted_tokens,
            get_exhausted_tokens,
            reset_exhausted_tokens,
        )

        reset_exhausted_tokens()
        assert len(get_exhausted_tokens()) == 0

        _exhausted_tokens.add("CLAUDE_CODE_OAUTH_TOKEN_1")
        assert "CLAUDE_CODE_OAUTH_TOKEN_1" in get_exhausted_tokens()

        reset_exhausted_tokens()
        assert len(get_exhausted_tokens()) == 0

    def test_cli_result_has_token_used(self):
        from mata_garuda.runtime.cli_runtime import CLIResult

        r = CLIResult(
            stdout="hello", stderr="", returncode=0,
            elapsed_seconds=1.0, model="claude",
            token_used="CLAUDE_CODE_OAUTH_TOKEN_2",
        )
        assert r.token_used == "CLAUDE_CODE_OAUTH_TOKEN_2"
        assert r.success
