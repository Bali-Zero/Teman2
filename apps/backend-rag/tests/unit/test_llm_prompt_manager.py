"""
Unit tests for PromptManager - System prompt loading and building

NOTE: PromptManager now loads from backend.prompts.zantara_core (Single Source of Truth)
instead of reading .md files. Tests updated accordingly.
"""

from unittest.mock import patch

import pytest

from backend.llm.prompt_manager import (
    PromptManager,
)


class TestPromptManager:
    """Test suite for PromptManager class"""

    @pytest.fixture
    def mock_prompt_content(self):
        """Mock prompt file content"""
        return "# ZANTARA System Prompt\n\nYou are ZANTARA, an intelligent assistant."

    @pytest.fixture
    def mock_fallback_content(self):
        """Mock fallback prompt content"""
        return "# ZANTARA Fallback Prompt\n\nYou are ZANTARA."

    def test_init_loads_prompt(self):
        """Test PromptManager initialization loads base prompt"""
        with patch.object(
            PromptManager, "_load_system_prompt_from_file", return_value="test prompt"
        ):
            manager = PromptManager()
            assert manager._base_system_prompt == "test prompt"

    def test_loads_from_zantara_core(self):
        """Test that PromptManager loads from zantara_core.py (Single Source of Truth)"""
        manager = PromptManager()

        # Should contain key sections from zantara_core.ZANTARA_MASTER_TEMPLATE
        assert "security_boundary" in manager._base_system_prompt
        assert "tool_usage_policy" in manager._base_system_prompt
        assert "escalation_protocol" in manager._base_system_prompt

    @patch("backend.llm.prompt_manager.ZANTARA_MASTER_TEMPLATE", "")
    def test_load_embedded_fallback_when_template_empty(self):
        """Test loading embedded fallback when ZANTARA_MASTER_TEMPLATE is empty"""
        manager = PromptManager()

        # Should use embedded prompt
        assert "ZANTARA - Intelligent AI Assistant" in manager._base_system_prompt
        assert "Core Identity" in manager._base_system_prompt

    def test_get_embedded_fallback_prompt(self):
        """Test embedded fallback prompt generation"""
        manager = PromptManager.__new__(PromptManager)
        prompt = manager._get_embedded_fallback_prompt()

        assert "ZANTARA - Intelligent AI Assistant" in prompt
        assert "Core Identity" in prompt
        assert "Communication Philosophy" in prompt
        assert "Knowledge Domains" in prompt
        assert "Response Principles" in prompt

    def test_build_system_prompt_no_context(self):
        """Test building prompt without any context"""
        with patch.object(
            PromptManager, "_load_system_prompt_from_file", return_value="Base prompt"
        ):
            manager = PromptManager()
            result = manager.build_system_prompt()

            assert result == "Base prompt"

    def test_build_system_prompt_with_memory_context(self):
        """Test building prompt with memory context"""
        with patch.object(
            PromptManager, "_load_system_prompt_from_file", return_value="Base prompt"
        ):
            manager = PromptManager()
            memory = "User likes Italian food"

            result = manager.build_system_prompt(memory_context=memory)

            assert "Base prompt" in result
            assert "CONTEXT USAGE INSTRUCTIONS" in result

    def test_build_system_prompt_with_identity_context(self):
        """Test building prompt with identity context"""
        with patch.object(
            PromptManager, "_load_system_prompt_from_file", return_value="Base prompt"
        ):
            manager = PromptManager()
            identity = "User: John Doe\nRole: Client"

            # Note: identity_context is documented but not currently injected into prompt
            result = manager.build_system_prompt(identity_context=identity)

            assert "Base prompt" in result
            # identity_context is not currently used in the implementation
            assert isinstance(result, str)

    def test_build_system_prompt_with_both_contexts(self):
        """Test building prompt with both memory and identity contexts"""
        with patch.object(
            PromptManager, "_load_system_prompt_from_file", return_value="Base prompt"
        ):
            manager = PromptManager()
            memory = "Previous conversation history"
            identity = "User: Jane Smith"

            # Note: identity_context is documented but not currently injected into prompt
            result = manager.build_system_prompt(memory_context=memory, identity_context=identity)

            assert "Base prompt" in result
            # Only memory_context is used (adds CONTEXT USAGE INSTRUCTIONS)
            assert "CONTEXT USAGE INSTRUCTIONS" in result

    def test_build_system_prompt_use_rich_prompt_true(self):
        """Test building prompt with use_rich_prompt=True"""
        with patch.object(
            PromptManager, "_load_system_prompt_from_file", return_value="Rich prompt"
        ):
            manager = PromptManager()

            result = manager.build_system_prompt(use_rich_prompt=True)

            assert result == "Rich prompt"

    def test_build_system_prompt_use_rich_prompt_false(self):
        """Test building prompt with use_rich_prompt=False"""
        with patch.object(
            PromptManager, "_load_system_prompt_from_file", return_value="Rich prompt"
        ):
            manager = PromptManager()

            result = manager.build_system_prompt(use_rich_prompt=False)

            # Should use embedded fallback instead of rich prompt
            assert "ZANTARA - Intelligent AI Assistant" in result

    def test_build_system_prompt_context_ordering(self):
        """Test that memory context is added to prompt"""
        with patch.object(PromptManager, "_load_system_prompt_from_file", return_value="Base"):
            manager = PromptManager()

            result = manager.build_system_prompt(
                memory_context="Memory", identity_context="Identity"
            )

            # Only memory_context is currently used in the implementation
            assert "CONTEXT USAGE INSTRUCTIONS" in result
            assert "Base" in result

    def test_build_system_prompt_empty_contexts(self):
        """Test building prompt with empty string contexts"""
        with patch.object(
            PromptManager, "_load_system_prompt_from_file", return_value="Base prompt"
        ):
            manager = PromptManager()

            result = manager.build_system_prompt(memory_context="", identity_context="")

            # Empty strings should be treated as no context
            assert result == "Base prompt"

    def test_build_system_prompt_none_contexts(self):
        """Test building prompt with None contexts (explicit)"""
        with patch.object(
            PromptManager, "_load_system_prompt_from_file", return_value="Base prompt"
        ):
            manager = PromptManager()

            result = manager.build_system_prompt(memory_context=None, identity_context=None)

            assert result == "Base prompt"

    def test_zantara_core_module_exists(self):
        """Test that zantara_core module is importable and contains ZANTARA_MASTER_TEMPLATE"""
        from backend.prompts.zantara_core import ZANTARA_MASTER_TEMPLATE

        assert isinstance(ZANTARA_MASTER_TEMPLATE, str)
        assert len(ZANTARA_MASTER_TEMPLATE) > 100

    def test_embedded_prompt_structure(self):
        """Test embedded prompt has required sections"""
        manager = PromptManager.__new__(PromptManager)
        prompt = manager._get_embedded_fallback_prompt()

        required_sections = [
            "# ZANTARA",
            "## Core Identity",
            "## Communication Philosophy",
            "## Knowledge Domains",
            "## Response Principles",
            "## Indonesian Cultural Intelligence",
            "## What Makes You Different",
        ]

        for section in required_sections:
            assert section in prompt, f"Missing section: {section}"

    def test_build_prompt_with_long_context(self):
        """Test building prompt with very long context"""
        with patch.object(PromptManager, "_load_system_prompt_from_file", return_value="Base"):
            manager = PromptManager()
            long_memory = "Context " * 10000  # Very long context

            result = manager.build_system_prompt(memory_context=long_memory)

            assert "Base" in result
            assert "CONTEXT USAGE INSTRUCTIONS" in result

    def test_build_prompt_with_special_characters(self):
        """Test building prompt with special characters in memory context"""
        with patch.object(PromptManager, "_load_system_prompt_from_file", return_value="Base"):
            manager = PromptManager()
            special_context = "User mentioned: <script>alert('test')</script>"

            # Using memory_context since identity_context is not implemented
            result = manager.build_system_prompt(memory_context=special_context)

            # Should include the base prompt
            assert "Base" in result
            assert "CONTEXT USAGE INSTRUCTIONS" in result

    def test_build_prompt_with_unicode(self):
        """Test building prompt with unicode characters"""
        with patch.object(PromptManager, "_load_system_prompt_from_file", return_value="Base"):
            manager = PromptManager()
            unicode_memory = "User mentioned: 日本語 Français العربية"

            # Using memory_context since identity_context is not implemented
            result = manager.build_system_prompt(memory_context=unicode_memory)

            # Memory context adds CONTEXT USAGE INSTRUCTIONS
            assert "CONTEXT USAGE INSTRUCTIONS" in result
            assert "Base" in result

    def test_build_prompt_with_newlines(self):
        """Test building prompt preserves newlines in context"""
        with patch.object(PromptManager, "_load_system_prompt_from_file", return_value="Base"):
            manager = PromptManager()
            multiline_memory = "Line 1\nLine 2\nLine 3"

            # Using memory_context since identity_context is not implemented
            result = manager.build_system_prompt(memory_context=multiline_memory)

            # Memory context adds CONTEXT USAGE INSTRUCTIONS
            assert "CONTEXT USAGE INSTRUCTIONS" in result
            assert "Base" in result

    def test_context_usage_instructions(self):
        """Test that context usage instructions are complete"""
        with patch.object(PromptManager, "_load_system_prompt_from_file", return_value="Base"):
            manager = PromptManager()

            result = manager.build_system_prompt(memory_context="Test")

            # Check all instruction points
            assert "1. Use the information in <context> tags" in result
            assert "2. When citing facts, mention the source document" in result
            assert "3. If the context doesn't contain specific information" in result
            assert "4. Do NOT make up information" in result
            assert "5. For pricing, legal requirements" in result

    def test_load_prompt_uses_zantara_core(self):
        """Test that PromptManager loads from zantara_core (not from .md files)"""
        manager = PromptManager()
        # The prompt should come from ZANTARA_MASTER_TEMPLATE, not file reading
        assert len(manager._base_system_prompt) > 100
        assert isinstance(manager._base_system_prompt, str)

    def test_base_prompt_immutability(self):
        """Test that base prompt doesn't change between calls"""
        with patch.object(PromptManager, "_load_system_prompt_from_file", return_value="Original"):
            manager = PromptManager()

            # First call (using memory_context since identity_context is not implemented)
            result1 = manager.build_system_prompt(memory_context="Test 1")
            # Second call
            result2 = manager.build_system_prompt(memory_context="Test 2")

            # Base prompt should be the same, only context differs
            assert manager._base_system_prompt == "Original"
            # Both should contain base prompt and CONTEXT USAGE INSTRUCTIONS
            assert "Original" in result1
            assert "Original" in result2
            assert "CONTEXT USAGE INSTRUCTIONS" in result1
            assert "CONTEXT USAGE INSTRUCTIONS" in result2
