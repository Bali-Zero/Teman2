"""
Mata Garuda — Smoke tests per il registry singleton.

Sprint 1: verifica che il pattern registry funzioni end-to-end:
- Singleton
- Decorator @register_agent / @register_tool
- FunctionInfo metadata
- Callable retrieval
- JSON serializable display
"""
import json

import pytest

from mata_garuda.registry import (
    Registry,
    register_agent,
    register_tool,
    registry,
)
from mata_garuda.types import Agent


def test_registry_is_singleton():
    """Two instances should be the same object."""
    r1 = Registry()
    r2 = Registry()
    assert r1 is r2
    assert r1 is registry


def test_register_agent_decorator():
    """@register_agent should add function to registry.agents."""

    @register_agent(name="Unit Test Agent", func_name="get_unit_test_agent")
    def get_unit_test_agent(model: str = "claude") -> Agent:
        """A test agent for unit testing."""
        return Agent(name="Unit Test Agent", model=model)

    assert "get_unit_test_agent" in registry.agents
    assert "Unit Test Agent" in registry.agents_info


def test_function_info_populated():
    """FunctionInfo should contain metadata from the decorated function."""
    info = registry.agents_info["Unit Test Agent"]
    assert info.func_name == "get_unit_test_agent"
    assert info.docstring == "A test agent for unit testing."
    assert "model" in info.args


def test_callable_roundtrip():
    """Retrieving and calling the registered agent should work."""
    fn = registry.agents["get_unit_test_agent"]
    result = fn(model="gemini")
    assert isinstance(result, Agent)
    assert result.name == "Unit Test Agent"
    assert result.model == "gemini"


def test_display_agents_info_json_safe():
    """display_agents_info should return JSON-serializable dict (no 'func' field)."""
    display = registry.display_agents_info()
    json_str = json.dumps(display, default=str)
    parsed = json.loads(json_str)
    assert "Unit Test Agent" in parsed
    assert "func" not in parsed["Unit Test Agent"]


def test_register_tool_decorator():
    """@register_tool should add function to registry.tools."""

    @register_tool(name="unit_test_echo")
    def unit_test_echo(text: str) -> str:
        return text

    assert "unit_test_echo" in registry.tools


def test_dummy_agent_registered():
    """The dummy_agent should be auto-registered via recursive import."""
    import mata_garuda.agents  # noqa: F401 — triggers auto-import

    assert "get_dummy_agent" in registry.agents
    assert "Dummy Agent" in registry.agents_info


def test_dummy_agent_instantiates():
    """Calling get_dummy_agent() should return a valid Agent with GENOME path."""
    from mata_garuda.agents.dummy_agent import get_dummy_agent

    agent = get_dummy_agent(model="claude")
    assert isinstance(agent, Agent)
    assert agent.name == "Dummy Agent"
    assert agent.model == "claude"
    assert agent.layer == "meta"
    assert agent.genome_path is not None
    assert agent.genome_path.endswith("dummy_agent_GENOME.md")


def test_dummy_agent_instructions_callable():
    """Dummy agent instructions should be a callable that accepts context_variables."""
    from mata_garuda.agents.dummy_agent import get_dummy_agent

    agent = get_dummy_agent()
    assert callable(agent.instructions)
    result = agent.instructions({"user_name": "Zero"})
    assert "Zero" in result
    assert "case_resolved" in result


def test_run_outcome_model():
    from mata_garuda.types import RunOutcome

    outcome = RunOutcome(
        agent_name="Regulation Watcher",
        success=True,
        tokens_used=1500,
        duration_ms=4200,
    )
    assert outcome.success is True
    assert outcome.tokens_used == 1500
    assert outcome.efficiency == pytest.approx(1500 / 4200, rel=0.01)


def test_run_outcome_defaults():
    from mata_garuda.types import RunOutcome

    outcome = RunOutcome(agent_name="test", success=False)
    assert outcome.tokens_used is None
    assert outcome.duration_ms is None
    assert outcome.efficiency is None
