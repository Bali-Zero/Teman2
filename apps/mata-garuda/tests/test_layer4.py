"""Tests for Layer 4 analyst agents — AI Digest and Code Patch Proposer."""
import pytest
from pathlib import Path


class TestAIDigestAgent:
    def test_agent_registered(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        assert "AI Digest Agent" in registry.agents_info

    def test_agent_instantiates(self):
        from mata_garuda.agents.ai_digest_agent import get_ai_digest_agent

        agent = get_ai_digest_agent()
        assert agent.layer == "analista"
        assert agent.genome_path.endswith("ai_digest_agent_GENOME.md")
        assert len(agent.functions) >= 7

    def test_agent_has_nlm_tools(self):
        from mata_garuda.agents.ai_digest_agent import get_ai_digest_agent

        agent = get_ai_digest_agent()
        tool_names = [f.__name__ for f in agent.functions]
        assert "nlm_query" in tool_names
        assert "kb_search" in tool_names
        assert "send_tg_alert" in tool_names

    def test_genome_exists(self):
        genome = Path(__file__).parent.parent / "mata_garuda" / "agents" / "ai_digest_agent_GENOME.md"
        assert genome.exists()
        content = genome.read_text()
        assert "analista" in content
        assert "5 bullet" in content.lower() or "5" in content


class TestCodePatchProposer:
    def test_agent_registered(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        assert "Code Patch Proposer" in registry.agents_info

    def test_agent_instantiates(self):
        from mata_garuda.agents.code_patch_proposer import get_code_patch_proposer

        agent = get_code_patch_proposer()
        assert agent.layer == "analista"
        assert agent.genome_path.endswith("code_patch_proposer_GENOME.md")

    def test_agent_has_tg_and_kb_tools(self):
        from mata_garuda.agents.code_patch_proposer import get_code_patch_proposer

        agent = get_code_patch_proposer()
        tool_names = [f.__name__ for f in agent.functions]
        assert "send_tg_alert" in tool_names
        assert "kb_store" in tool_names
        assert "kb_search" in tool_names

    def test_genome_enforces_option_b(self):
        genome = Path(__file__).parent.parent / "mata_garuda" / "agents" / "code_patch_proposer_GENOME.md"
        content = genome.read_text()
        assert "NEVER modify" in content or "NEVER apply" in content
        assert "staged" in content.lower() or "STAGED" in content

    def test_patch_dir_constant(self):
        from mata_garuda.agents.code_patch_proposer import PATCH_DIR

        assert str(PATCH_DIR) == "/tmp/mata_garuda_patches"


class TestNLMTools:
    def test_nlm_query_tool_registered(self):
        import mata_garuda.tools.nlm_tools  # noqa: F401
        from mata_garuda.registry import registry

        assert "nlm_query" in registry.tools

    def test_nlm_add_source_registered(self):
        from mata_garuda.registry import registry

        assert "nlm_add_source" in registry.tools

    def test_nlm_add_text_registered(self):
        from mata_garuda.registry import registry

        assert "nlm_add_text" in registry.tools


class TestTGTools:
    def test_tg_alert_registered(self):
        import mata_garuda.tools.tg_tools  # noqa: F401
        from mata_garuda.registry import registry

        assert "send_tg_alert" in registry.tools
