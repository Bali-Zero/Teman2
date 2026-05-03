"""
Unit tests for PromptManager
Target: 100% coverage
"""

import sys
from pathlib import Path

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

    def test_load_system_prompt(self):
        """Test loading system prompt via get_system_prompt (uses ZANTARA_MASTER_TEMPLATE)"""
        manager = PromptManager()
        prompt = manager.get_system_prompt()
        assert prompt is not None
        assert isinstance(prompt, str)

    def test_load_system_prompt_not_found(self):
        """Test get_system_prompt always returns a string (template-based, no file I/O)"""
        manager = PromptManager()
        prompt = manager.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_prompt_with_tone(self):
        """Test building prompt with tone via build_system_prompt"""
        manager = PromptManager()
        prompt = manager.build_system_prompt(style="professional")
        assert prompt is not None
        assert isinstance(prompt, str)

    def test_build_prompt_without_tone(self):
        """Test building prompt without tone"""
        manager = PromptManager()
        prompt = manager.build_system_prompt()
        assert prompt is not None
        assert isinstance(prompt, str)

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
