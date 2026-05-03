"""Tests for Meta-Evolution agents — SourceHealth + MetaCognition."""
import pytest
from pathlib import Path


class TestSourceHealthAgent:
    def test_agent_registered(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        assert "Source Health Agent" in registry.agents_info

    def test_agent_instantiates(self):
        from mata_garuda.agents.source_health_agent import get_source_health_agent

        agent = get_source_health_agent()
        assert agent.layer == "analista"
        assert agent.genome_path.endswith("source_health_agent_GENOME.md")

    def test_agent_has_required_tools(self):
        from mata_garuda.agents.source_health_agent import get_source_health_agent

        agent = get_source_health_agent()
        tool_names = [f.__name__ for f in agent.functions]
        assert "kb_search" in tool_names
        assert "send_tg_alert" in tool_names

    def test_genome_exists(self):
        genome = Path(__file__).parent.parent / "mata_garuda" / "agents" / "source_health_agent_GENOME.md"
        assert genome.exists()
        content = genome.read_text()
        assert "Thompson Sampling" in content or "DEACTIVATE" in content


class TestMetaCognitionAgent:
    def test_agent_registered(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        assert "Meta-Cognition Agent" in registry.agents_info

    def test_agent_instantiates(self):
        from mata_garuda.agents.meta_cognition_agent import get_meta_cognition_agent

        agent = get_meta_cognition_agent()
        assert agent.layer == "meta"
        assert agent.genome_path.endswith("meta_cognition_agent_GENOME.md")

    def test_agent_has_required_tools(self):
        from mata_garuda.agents.meta_cognition_agent import get_meta_cognition_agent

        agent = get_meta_cognition_agent()
        tool_names = [f.__name__ for f in agent.functions]
        assert "kb_search" in tool_names
        assert "kb_get_skills" in tool_names
        assert "send_tg_alert" in tool_names

    def test_genome_enforces_l3(self):
        genome = Path(__file__).parent.parent / "mata_garuda" / "agents" / "meta_cognition_agent_GENOME.md"
        content = genome.read_text()
        assert "L3" in content
        assert "NEVER modify" in content or "Read-only" in content.lower() or "read-only" in content.lower()


class TestFullRegistry:
    def test_total_agents(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        # 3 original (Dummy, Meta, RegWatcher) + 5 AI harvesters + 2 Layer 4 + 2 Meta = 12
        assert len(registry.agents_info) >= 12

    def test_all_agents_have_genome(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        agents_dir = Path(__file__).parent.parent / "mata_garuda" / "agents"
        for name, info in registry.agents_info.items():
            agent_fn = info.func
            agent = agent_fn(model="claude")
            if agent.genome_path:
                assert Path(agent.genome_path).exists(), f"Missing GENOME for {name}: {agent.genome_path}"

    def test_layers_represented(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        layers = set()
        for info in registry.agents_info.values():
            agent = info.func(model="claude")
            if agent.layer:
                layers.add(agent.layer)

        assert "harvester" in layers
        assert "analista" in layers
        assert "meta" in layers
