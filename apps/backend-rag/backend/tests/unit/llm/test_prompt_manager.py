"""
Unit tests for PromptManager
Target: 100% coverage
"""

import importlib
import sys
from pathlib import Path

import pytest

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


class TestPromptManagerVersionSelection:
    """ZANTARA_PROMPT_VERSION selection (v1/v2/v3/v4) via the module-level
    door in prompt_manager.py. _PROMPT_VERSION is read at IMPORT time, so
    each case sets the env var then importlib.reload()s the module — and
    ALWAYS restores the default (v1) afterwards so later tests/imports in
    this process see the same module state they'd see on a fresh import
    (cicatrix #10-adjacent: don't leave cross-test global state behind).

    2026-07-17 design doc §6 promised "a v4 case mirroring the existing
    v2/v3 coverage" — that coverage never existed, so this adds v1/v2/v3/v4
    together rather than mirroring nothing.
    """

    @pytest.fixture(autouse=True)
    def _restore_default_version(self, monkeypatch):
        """Ensure ZANTARA_PROMPT_VERSION is unset and the module is back on
        its default (v1) import state before AND after every test in this
        class, regardless of pass/fail."""
        import backend.llm.prompt_manager as pm

        monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
        importlib.reload(pm)
        yield
        monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
        importlib.reload(pm)

    def _reload_with_version(self, monkeypatch, version: str | None):
        import backend.llm.prompt_manager as pm

        if version is None:
            monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
        else:
            monkeypatch.setenv("ZANTARA_PROMPT_VERSION", version)
        importlib.reload(pm)
        return pm

    def test_default_no_env_var_resolves_v1(self, monkeypatch):
        pm = self._reload_with_version(monkeypatch, None)
        assert pm.ZANTARA_MASTER_TEMPLATE == pm._TEMPLATE_V1

    def test_v2_env_var_resolves_v2_template(self, monkeypatch):
        pm = self._reload_with_version(monkeypatch, "v2")
        from backend.prompts.zantara_core_v2 import (
            ZANTARA_MASTER_TEMPLATE as template_v2,
        )

        assert pm.ZANTARA_MASTER_TEMPLATE == template_v2
        assert pm.ZANTARA_MASTER_TEMPLATE != pm._TEMPLATE_V1

    def test_v3_env_var_resolves_v3_template(self, monkeypatch):
        pm = self._reload_with_version(monkeypatch, "v3")
        from backend.prompts.zantara_core_v3 import (
            ZANTARA_MASTER_TEMPLATE as template_v3,
        )

        assert pm.ZANTARA_MASTER_TEMPLATE == template_v3

    def test_v4_env_var_resolves_v4_template(self, monkeypatch):
        """The whole point of this PR: ZANTARA_PROMPT_VERSION=v4 must
        actually select zantara_core_v4's template through this door."""
        pm = self._reload_with_version(monkeypatch, "v4")
        from backend.prompts.zantara_core_v4 import (
            ZANTARA_MASTER_TEMPLATE as template_v4,
        )

        assert pm.ZANTARA_MASTER_TEMPLATE == template_v4
        assert "unified prompt door" in pm.ZANTARA_MASTER_TEMPLATE
        assert "{today_wita}" in pm.ZANTARA_MASTER_TEMPLATE

    def test_v4_get_today_wita_is_bound_and_callable(self, monkeypatch):
        pm = self._reload_with_version(monkeypatch, "v4")
        result = pm.get_today_wita()
        assert isinstance(result, str)
        assert "WITA" in result

    def test_unrecognized_version_falls_back_to_v1(self, monkeypatch):
        """An unknown value (typo, e.g. 'v9') is not one of the explicit
        branches — falls to the `else` clause, same as no env var set."""
        pm = self._reload_with_version(monkeypatch, "v9")
        assert pm.ZANTARA_MASTER_TEMPLATE == pm._TEMPLATE_V1
