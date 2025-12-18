"""
Unit Tests for llm/prompt_manager.py - 95% Coverage Target
Tests the PromptManager class
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test PromptManager initialization
# ============================================================================


class TestPromptManagerInit:
    """Test suite for PromptManager initialization"""

    def test_init_loads_system_prompt(self):
        """Test that initialization loads the system prompt"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()

        assert manager._base_system_prompt is not None
        assert len(manager._base_system_prompt) > 0


# ============================================================================
# Test _load_system_prompt_from_file
# ============================================================================


class TestLoadSystemPromptFromFile:
    """Test suite for _load_system_prompt_from_file method"""

    def test_load_from_main_file(self):
        """Test loading prompt from main system prompt file"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()

        # Since the file exists, it should load successfully
        prompt = manager._load_system_prompt_from_file()

        assert prompt is not None
        assert len(prompt) > 0

    def test_load_from_fallback_when_main_missing(self):
        """Test loading from fallback when main file is missing"""
        from llm.prompt_manager import PromptManager

        with patch("llm.prompt_manager.SYSTEM_PROMPT_FILE") as mock_main:
            mock_main.exists.return_value = False

            with patch("llm.prompt_manager.FALLBACK_PROMPT_FILE") as mock_fallback:
                mock_fallback.exists.return_value = True
                mock_fallback.read_text.return_value = "Fallback prompt content"
                mock_fallback.name = "fallback.md"

                manager = PromptManager()
                prompt = manager._load_system_prompt_from_file()

                assert "Fallback prompt content" in prompt or "ZANTARA" in prompt

    def test_load_uses_embedded_when_both_files_missing(self):
        """Test using embedded fallback when both files are missing"""
        from llm.prompt_manager import PromptManager

        with patch("llm.prompt_manager.SYSTEM_PROMPT_FILE") as mock_main:
            mock_main.exists.return_value = False

            with patch("llm.prompt_manager.FALLBACK_PROMPT_FILE") as mock_fallback:
                mock_fallback.exists.return_value = False

                manager = PromptManager()
                prompt = manager._load_system_prompt_from_file()

                # Should use embedded fallback
                assert "ZANTARA" in prompt

    def test_load_handles_file_read_exception(self):
        """Test handling exception when reading file fails"""
        from llm.prompt_manager import PromptManager

        with patch("llm.prompt_manager.SYSTEM_PROMPT_FILE") as mock_file:
            mock_file.exists.return_value = True
            mock_file.read_text.side_effect = IOError("Permission denied")

            manager = PromptManager()
            prompt = manager._load_system_prompt_from_file()

            # Should use embedded fallback
            assert "ZANTARA" in prompt


# ============================================================================
# Test _get_embedded_fallback_prompt
# ============================================================================


class TestGetEmbeddedFallbackPrompt:
    """Test suite for _get_embedded_fallback_prompt method"""

    def test_embedded_prompt_contains_zantara(self):
        """Test embedded prompt contains ZANTARA identity"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager._get_embedded_fallback_prompt()

        assert "ZANTARA" in prompt
        assert "Bali Zero" in prompt

    def test_embedded_prompt_contains_key_sections(self):
        """Test embedded prompt contains key sections"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager._get_embedded_fallback_prompt()

        assert "Core Identity" in prompt
        assert "Communication Philosophy" in prompt
        assert "Knowledge Domains" in prompt
        assert "Response Principles" in prompt

    def test_embedded_prompt_contains_cultural_intelligence(self):
        """Test embedded prompt contains Indonesian cultural intelligence"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager._get_embedded_fallback_prompt()

        assert "Indonesian Cultural Intelligence" in prompt
        assert "Tri Hita Karana" in prompt


# ============================================================================
# Test build_system_prompt
# ============================================================================


class TestBuildSystemPrompt:
    """Test suite for build_system_prompt method"""

    def test_build_prompt_no_context(self):
        """Test building prompt without any context"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager.build_system_prompt()

        assert prompt == manager._base_system_prompt

    def test_build_prompt_with_memory_context(self):
        """Test building prompt with memory context"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        memory = "Previous conversation: User asked about visas"
        prompt = manager.build_system_prompt(memory_context=memory)

        assert "CONTEXT USAGE INSTRUCTIONS" in prompt
        assert manager._base_system_prompt in prompt

    def test_build_prompt_with_identity_context(self):
        """Test building prompt with identity context"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        identity = "User: John Doe, Role: Admin"
        prompt = manager.build_system_prompt(identity_context=identity)

        assert "<user_identity>" in prompt
        assert "John Doe" in prompt
        assert "</user_identity>" in prompt
        assert "personalize your responses" in prompt

    def test_build_prompt_with_both_contexts(self):
        """Test building prompt with both memory and identity context"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        memory = "User asked about KITAS"
        identity = "User: Jane, Role: Client"
        prompt = manager.build_system_prompt(memory_context=memory, identity_context=identity)

        assert "<user_identity>" in prompt
        assert "Jane" in prompt
        assert "CONTEXT USAGE INSTRUCTIONS" in prompt

    def test_build_prompt_use_rich_prompt_false(self):
        """Test building prompt with use_rich_prompt=False"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager.build_system_prompt(use_rich_prompt=False)

        # Should use embedded fallback
        assert "ZANTARA" in prompt
        assert "Intelligent AI Assistant" in prompt

    def test_build_prompt_use_rich_prompt_true_with_context(self):
        """Test building prompt with use_rich_prompt=True and context"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager.build_system_prompt(
            memory_context="Some memory",
            identity_context="Some identity",
            use_rich_prompt=True,
        )

        assert manager._base_system_prompt in prompt
        assert "---" in prompt  # Separator between base and context


# ============================================================================
# Test get_system_prompt
# ============================================================================


class TestGetSystemPrompt:
    """Test suite for get_system_prompt method"""

    def test_get_prompt_no_type(self):
        """Test getting prompt with no type specified"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager.get_system_prompt()

        assert prompt == manager._base_system_prompt

    def test_get_prompt_none_type(self):
        """Test getting prompt with None type"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager.get_system_prompt(prompt_type=None)

        assert prompt == manager._base_system_prompt

    def test_get_prompt_tax_specialist(self):
        """Test getting prompt for tax specialist"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager.get_system_prompt(prompt_type="tax_specialist")

        assert "Tax Specialist Focus" in prompt
        assert "PPh" in prompt
        assert "PPn" in prompt
        assert "VAT" in prompt

    def test_get_prompt_pajak_keyword(self):
        """Test getting prompt with 'pajak' keyword (Indonesian for tax)"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager.get_system_prompt(prompt_type="pajak_consultant")

        assert "Tax Specialist Focus" in prompt

    def test_get_prompt_legal_specialist(self):
        """Test getting prompt for legal specialist"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager.get_system_prompt(prompt_type="legal_specialist")

        assert "Legal Specialist Focus" in prompt
        assert "corporate law" in prompt

    def test_get_prompt_law_keyword(self):
        """Test getting prompt with 'law' keyword"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager.get_system_prompt(prompt_type="business_law")

        assert "Legal Specialist Focus" in prompt

    def test_get_prompt_visa_specialist(self):
        """Test getting prompt for visa specialist"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager.get_system_prompt(prompt_type="visa_specialist")

        assert "Visa Specialist Focus" in prompt
        assert "KITAS" in prompt
        assert "KITAP" in prompt

    def test_get_prompt_immigration_keyword(self):
        """Test getting prompt with 'immigration' keyword"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager.get_system_prompt(prompt_type="immigration_officer")

        assert "Visa Specialist Focus" in prompt

    def test_get_prompt_unrecognized_type(self):
        """Test getting prompt with unrecognized type"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager.get_system_prompt(prompt_type="unknown_specialist")

        # Should return base prompt without extra domain context
        assert prompt == manager._base_system_prompt

    def test_get_prompt_case_insensitive(self):
        """Test prompt type matching is case insensitive"""
        from llm.prompt_manager import PromptManager

        manager = PromptManager()

        prompt_lower = manager.get_system_prompt(prompt_type="tax")
        prompt_upper = manager.get_system_prompt(prompt_type="TAX")
        prompt_mixed = manager.get_system_prompt(prompt_type="TaX")

        # All should have tax specialist content
        assert "Tax Specialist Focus" in prompt_lower
        assert "Tax Specialist Focus" in prompt_upper
        assert "Tax Specialist Focus" in prompt_mixed


# ============================================================================
# Test module-level constants
# ============================================================================


class TestModuleConstants:
    """Test suite for module-level constants"""

    def test_prompts_dir_exists(self):
        """Test PROMPTS_DIR points to existing directory"""
        from llm.prompt_manager import PROMPTS_DIR

        assert PROMPTS_DIR.exists()

    def test_system_prompt_file_constant(self):
        """Test SYSTEM_PROMPT_FILE is defined"""
        from llm.prompt_manager import SYSTEM_PROMPT_FILE

        assert SYSTEM_PROMPT_FILE.name == "zantara_system_prompt.md"

    def test_fallback_prompt_file_constant(self):
        """Test FALLBACK_PROMPT_FILE is defined"""
        from llm.prompt_manager import FALLBACK_PROMPT_FILE

        assert FALLBACK_PROMPT_FILE.name == "zantara_system_prompt.md"
