"""
Unit tests for SystemPromptBuilder
Target: 100% coverage
Composer: 1
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.rag.agentic.prompt_builder import SystemPromptBuilder


@pytest.fixture
def prompt_builder():
    """Create prompt builder instance"""
    return SystemPromptBuilder()


class TestSystemPromptBuilder:
    """Tests for SystemPromptBuilder"""

    def test_init(self):
        """Test initialization"""
        builder = SystemPromptBuilder()
        assert builder is not None

    def test_build_prompt_basic(self, prompt_builder):
        """Test basic prompt building"""
        user_profile = {"email": "test@example.com", "name": "Test User"}
        query = "What is KITAS?"

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile},
            query=query,
        )

        assert prompt is not None
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_prompt_with_memory_facts(self, prompt_builder):
        """Test prompt building with memory facts"""
        user_profile = {"email": "test@example.com"}
        memory_facts = [{"fact": "User is interested in KITAS", "category": "interest"}]

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile, "memory_facts": memory_facts},
            query="Tell me about KITAS",
        )

        assert "KITAS" in prompt

    def test_build_prompt_with_collective_facts(self, prompt_builder):
        """Test prompt building with collective facts"""
        user_profile = {"email": "test@example.com"}
        collective_facts = [{"fact": "KITAS costs 15M IDR", "confidence": 0.9}]

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile, "collective_facts": collective_facts},
            query="What is KITAS?",
        )

        assert prompt is not None

    def test_build_prompt_with_rag_results(self, prompt_builder):
        """Test prompt building with RAG results"""
        user_profile = {"email": "test@example.com"}
        rag_results = "[1] KITAS is a work permit..."

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile, "rag_results": rag_results},
            query="What is KITAS?",
        )

        assert "KITAS" in prompt

    def test_build_prompt_italian_language(self, prompt_builder):
        """Test prompt building for Italian query"""
        user_profile = {"email": "test@example.com"}
        query = "Cos'è il KITAS?"

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile},
            query=query,
        )

        assert prompt is not None

    def test_build_prompt_english_language(self, prompt_builder):
        """Test prompt building for English query"""
        user_profile = {"email": "test@example.com"}
        query = "What is KITAS?"

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile},
            query=query,
        )

        assert prompt is not None

    def test_build_prompt_with_deep_think(self, prompt_builder):
        """Test prompt building with deep think mode"""
        user_profile = {"email": "test@example.com"}

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile},
            query="Complex question",
            deep_think_mode=True,
        )

        assert prompt is not None

    def test_build_prompt_caching(self, prompt_builder):
        """Test prompt caching"""
        user_profile = {"email": "test@example.com"}

        prompt1 = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile},
            query="test",
        )

        prompt2 = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile},
            query="test",
        )

        # Should use cache (same inputs)
        assert prompt1 == prompt2

    def test_build_prompt_cache_invalidation(self, prompt_builder):
        """Test cache invalidation on facts change"""
        user_profile = {"email": "test@example.com"}

        prompt1 = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile, "facts": []},
            query="test",
        )

        prompt2 = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile, "facts": ["new fact"]},
            query="test",
        )

        # Should be different (facts changed) - the cache key includes len(facts)
        # So prompts should differ when facts change
        assert prompt1 != prompt2
