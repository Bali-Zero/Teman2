"""
Unit tests for PromptManager - System prompt loading and building
"""

from unittest.mock import patch

import pytest

from backend.llm.prompt_manager import (
    FALLBACK_PROMPT_FILE,
    PROMPTS_DIR,
    SYSTEM_PROMPT_FILE,
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

    @patch("backend.llm.prompt_manager.SYSTEM_PROMPT_FILE")
    def test_load_from_primary_file(self, mock_file, mock_prompt_content):
        """Test loading prompt from primary file"""
        mock_file.exists.return_value = True
        mock_file.read_text.return_value = mock_prompt_content
        mock_file.name = "zantara_system_prompt.md"

        manager = PromptManager()

        assert manager._base_system_prompt == mock_prompt_content

    @patch("backend.llm.prompt_manager.SYSTEM_PROMPT_FILE")
    @patch("backend.llm.prompt_manager.FALLBACK_PROMPT_FILE")
    def test_load_from_fallback_file(self, mock_fallback, mock_primary, mock_fallback_content):
        """Test loading prompt from fallback file when primary not found"""
        mock_primary.exists.return_value = False
        mock_fallback.exists.return_value = True
        mock_fallback.read_text.return_value = mock_fallback_content
        mock_fallback.name = "zantara_system_prompt.md"

        manager = PromptManager()

        assert manager._base_system_prompt == mock_fallback_content

    @patch("backend.llm.prompt_manager.SYSTEM_PROMPT_FILE")
    @patch("backend.llm.prompt_manager.FALLBACK_PROMPT_FILE")
    def test_load_embedded_fallback(self, mock_fallback, mock_primary):
        """Test loading embedded fallback when no files exist"""
        mock_primary.exists.return_value = False
        mock_fallback.exists.return_value = False

        manager = PromptManager()

        # Should use embedded prompt
        assert "ZANTARA - Intelligent AI Assistant" in manager._base_system_prompt
        assert "Core Identity" in manager._base_system_prompt

    @patch("backend.llm.prompt_manager.SYSTEM_PROMPT_FILE")
    def test_load_file_read_error(self, mock_file):
        """Test handling file read error"""
        mock_file.exists.return_value = True
        mock_file.read_text.side_effect = OSError("Read error")

        manager = PromptManager()

        # Should fallback to embedded prompt
        assert "ZANTARA - Intelligent AI Assistant" in manager._base_system_prompt

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

            result = manager.build_system_prompt(identity_context=identity)

            assert "Base prompt" in result
            assert "<user_identity>" in result
            assert "John Doe" in result
            assert "</user_identity>" in result

    def test_build_system_prompt_with_both_contexts(self):
        """Test building prompt with both memory and identity contexts"""
        with patch.object(
            PromptManager, "_load_system_prompt_from_file", return_value="Base prompt"
        ):
            manager = PromptManager()
            memory = "Previous conversation history"
            identity = "User: Jane Smith"

            result = manager.build_system_prompt(memory_context=memory, identity_context=identity)

            assert "Base prompt" in result
            assert "<user_identity>" in result
            assert "Jane Smith" in result
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
        """Test that identity context comes before memory context"""
        with patch.object(PromptManager, "_load_system_prompt_from_file", return_value="Base"):
            manager = PromptManager()

            result = manager.build_system_prompt(
                memory_context="Memory", identity_context="Identity"
            )

            # Identity should appear before memory in the prompt
            identity_pos = result.index("<user_identity>")
            context_pos = result.index("CONTEXT USAGE INSTRUCTIONS")
            assert identity_pos < context_pos

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

    def test_prompts_dir_constant(self):
        """Test PROMPTS_DIR constant points to correct location"""
        assert PROMPTS_DIR.name == "prompts"
        assert PROMPTS_DIR.exists()

    def test_system_prompt_file_constant(self):
        """Test SYSTEM_PROMPT_FILE constant"""
        assert SYSTEM_PROMPT_FILE.name == "zantara_system_prompt.md"
        assert SYSTEM_PROMPT_FILE.parent.name == "prompts"

    def test_fallback_prompt_file_constant(self):
        """Test FALLBACK_PROMPT_FILE constant (same as primary - single source of truth)"""
        assert FALLBACK_PROMPT_FILE.name == "zantara_system_prompt.md"
        assert FALLBACK_PROMPT_FILE.parent.name == "prompts"

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
        """Test building prompt with special characters in context"""
        with patch.object(PromptManager, "_load_system_prompt_from_file", return_value="Base"):
            manager = PromptManager()
            special_context = "User: <script>alert('test')</script>\nRole: Admin"

            result = manager.build_system_prompt(identity_context=special_context)

            assert "<script>alert('test')</script>" in result
            # Should not escape HTML - just include as-is

    def test_build_prompt_with_unicode(self):
        """Test building prompt with unicode characters"""
        with patch.object(PromptManager, "_load_system_prompt_from_file", return_value="Base"):
            manager = PromptManager()
            unicode_identity = "User: 日本語 Français العربية"

            result = manager.build_system_prompt(identity_context=unicode_identity)

            assert "日本語" in result
            assert "Français" in result
            assert "العربية" in result

    def test_build_prompt_with_newlines(self):
        """Test building prompt preserves newlines in context"""
        with patch.object(PromptManager, "_load_system_prompt_from_file", return_value="Base"):
            manager = PromptManager()
            multiline_context = "Line 1\nLine 2\nLine 3"

            result = manager.build_system_prompt(identity_context=multiline_context)

            assert "Line 1\nLine 2\nLine 3" in result

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

    @patch("backend.llm.prompt_manager.SYSTEM_PROMPT_FILE")
    def test_load_prompt_with_utf8_encoding(self, mock_file):
        """Test that prompt files are loaded with UTF-8 encoding"""
        mock_file.exists.return_value = True
        mock_file.read_text.return_value = "Test prompt"
        mock_file.name = "test.md"

        manager = PromptManager()

        # Verify read_text was called with utf-8 encoding
        mock_file.read_text.assert_called_once_with(encoding="utf-8")

    def test_base_prompt_immutability(self):
        """Test that base prompt doesn't change between calls"""
        with patch.object(PromptManager, "_load_system_prompt_from_file", return_value="Original"):
            manager = PromptManager()

            # First call
            result1 = manager.build_system_prompt(identity_context="Test 1")
            # Second call
            result2 = manager.build_system_prompt(identity_context="Test 2")

            # Base prompt should be the same, only context differs
            assert manager._base_system_prompt == "Original"
            assert "Test 1" in result1
            assert "Test 2" in result2
