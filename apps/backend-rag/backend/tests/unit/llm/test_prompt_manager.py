"""
Unit tests for PromptManager
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import patch

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.llm.prompt_manager import (
    PromptManager,
    _get_tone_prompt,
    _TonePromptsDict,
)


class TestPromptManager:
    """Tests for PromptManager"""

    def test_init(self):
        """Test initialization"""
        manager = PromptManager()
        assert manager is not None

    @patch("backend.llm.prompt_manager.SYSTEM_PROMPT_FILE")
    def test_load_system_prompt(self, mock_file):
        """Test loading system prompt"""
        mock_file.read_text.return_value = "# System Prompt\nTest content"
        manager = PromptManager()
        prompt = manager.load_system_prompt()
        assert prompt is not None
        assert "System Prompt" in prompt

    @patch("backend.llm.prompt_manager.SYSTEM_PROMPT_FILE")
    def test_load_system_prompt_not_found(self, mock_file):
        """Test loading system prompt when file not found"""
        mock_file.read_text.side_effect = FileNotFoundError()
        manager = PromptManager()
        prompt = manager.load_system_prompt()
        # Should return fallback or empty string
        assert isinstance(prompt, str)

    def test_build_prompt_with_tone(self):
        """Test building prompt with tone"""
        manager = PromptManager()
        base_prompt = "Base prompt"
        tone = "professional"

        prompt = manager.build_prompt(base_prompt, tone=tone)
        assert prompt is not None
        assert isinstance(prompt, str)

    def test_build_prompt_without_tone(self):
        """Test building prompt without tone"""
        manager = PromptManager()
        base_prompt = "Base prompt"

        prompt = manager.build_prompt(base_prompt)
        assert prompt == base_prompt

    def test_get_tone_prompt_string(self):
        """Test getting tone prompt with string"""
        result = _get_tone_prompt("professional")
        assert result is not None
        assert isinstance(result, str)

    def test_get_tone_prompt_enum(self):
        """Test getting tone prompt with enum-like object"""

        class MockToneStyle:
            value = "warm"

        result = _get_tone_prompt(MockToneStyle())
        assert result is not None

    def test_get_tone_prompt_none(self):
        """Test getting tone prompt with None"""
        result = _get_tone_prompt(None)
        assert result is None

    def test_get_tone_prompt_invalid(self):
        """Test getting tone prompt with invalid value"""
        result = _get_tone_prompt("invalid_tone")
        assert result is None

    def test_tone_prompts_dict_get(self):
        """Test TonePromptsDict get method"""
        tone_dict = _TonePromptsDict()
        result = tone_dict.get("professional")
        assert result is not None

    def test_tone_prompts_dict_get_default(self):
        """Test TonePromptsDict get with default"""
        tone_dict = _TonePromptsDict()
        result = tone_dict.get("invalid", "default")
        assert result == "default"
