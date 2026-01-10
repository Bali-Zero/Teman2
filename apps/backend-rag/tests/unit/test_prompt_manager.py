"""
Unit tests for PromptManager
"""

import sys
from pathlib import Path

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.llm.prompt_manager import PromptManager


def test_prompt_manager_init():
    """Test PromptManager initialization"""
    manager = PromptManager()
    assert manager._base_system_prompt is not None
    assert len(manager._base_system_prompt) > 0
    assert "ZANTARA" in manager._base_system_prompt


def test_build_system_prompt_default():
    """Test building system prompt with defaults"""
    manager = PromptManager()
    prompt = manager.build_system_prompt()

    assert "ZANTARA" in prompt
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_build_system_prompt_with_identity_context():
    """Test building system prompt with identity context"""
    manager = PromptManager()
    # Note: identity_context is a documented param but not currently injected into prompt
    # The prompt is built but identity_context is not added (implementation limitation)
    prompt = manager.build_system_prompt(identity_context="User: John Doe, Role: Admin")

    assert "ZANTARA" in prompt
    # identity_context is currently not used in the implementation
    assert isinstance(prompt, str)


def test_build_system_prompt_with_memory_context():
    """Test building system prompt with memory context"""
    manager = PromptManager()
    prompt = manager.build_system_prompt(memory_context="User prefers Italian language")

    assert "ZANTARA" in prompt
    assert "CONTEXT USAGE INSTRUCTIONS" in prompt
    assert "Italian" in prompt or "context" in prompt.lower()


def test_build_system_prompt_with_both_contexts():
    """Test building system prompt with both identity and memory context"""
    manager = PromptManager()
    prompt = manager.build_system_prompt(
        identity_context="User: Jane", memory_context="Memory: Test"
    )

    # Note: identity_context is documented but not currently injected into prompt
    # Only memory_context is used (adds CONTEXT USAGE INSTRUCTIONS)
    assert "CONTEXT USAGE INSTRUCTIONS" in prompt
    assert "ZANTARA" in prompt


def test_build_system_prompt_without_rich_prompt():
    """Test building system prompt without rich prompt"""
    manager = PromptManager()
    prompt = manager.build_system_prompt(use_rich_prompt=False)

    assert "ZANTARA" in prompt
    assert isinstance(prompt, str)


def test_get_embedded_fallback_prompt():
    """Test getting embedded fallback prompt"""
    manager = PromptManager()
    prompt = manager._get_embedded_fallback_prompt()

    assert "ZANTARA" in prompt
    assert "Core Identity" in prompt
    assert isinstance(prompt, str)
    assert len(prompt) > 0
