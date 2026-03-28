"""
Pytest configuration for orchestrator tests with Ollama Qwen local LLM.
Provides real LLM testing when Ollama is available, falls back to mocks otherwise.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.llm.providers.ollama import OllamaProvider
from backend.services.rag.agentic.llm_gateway import LLMGateway

# Create a mock settings instance that will be used
_mock_settings = MagicMock()
_mock_settings.database_url = "postgresql://test:5432/test"
_mock_settings.google_api_key = "test-api-key"
_mock_settings.environment = "test"
_mock_settings.api_keys = "test_key_1,test_key_2"
_mock_settings.api_auth_enabled = False
_mock_settings.jwt_secret_key = "test_secret_key_minimum_32_characters"
_mock_settings.jwt_algorithm = "HS256"
_mock_settings.ollama_url = "http://localhost:11434"
_mock_settings.ollama_model = "qwen2.5:latest"

# Patch the config module before it's imported
if "backend.app.core.config" not in sys.modules:
    fake_config = type(sys)("backend.app.core.config")
    fake_config.settings = _mock_settings

    class FakeSettings:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __call__(self, *args, **kwargs):
            return _mock_settings

    fake_config.Settings = FakeSettings
    sys.modules["backend.app.core.config"] = fake_config
else:
    from unittest.mock import patch

    with patch("backend.app.core.config.settings", _mock_settings):
        pass


@pytest.fixture(scope="session")
def ollama_available():
    """Check if Ollama is available - always try to ensure it's ready"""
    import os
    import subprocess

    # Try to ensure Ollama is ready
    script_dir = Path(__file__).parent.parent.parent.parent.parent.parent.parent / "scripts"
    ensure_script = script_dir / "ensure_ollama_ready.sh"

    if ensure_script.exists():
        try:
            # Run ensure script (non-blocking check)
            result = subprocess.run(
                [str(ensure_script)], capture_output=True, timeout=10, cwd=str(script_dir.parent)
            )
            if result.returncode == 0:
                # Ollama is ready
                pass
        except Exception:
            # Script failed, try direct check
            pass

    # Check if Ollama is available
    try:
        provider = OllamaProvider(model=os.getenv("OLLAMA_MODEL", "qwen2.5:latest"))
        return provider.is_available
    except Exception:
        return False


@pytest.fixture
def ollama_provider(ollama_available):
    """Create Ollama provider if available"""
    if ollama_available:
        return OllamaProvider(model="qwen2.5:latest")
    return None


@pytest.fixture
def llm_gateway_with_ollama(ollama_available, ollama_provider):
    """Create LLMGateway with Ollama if available, otherwise mock"""
    if ollama_available and ollama_provider:
        # Use real Ollama provider wrapped in LLMGateway-like interface
        gateway = MagicMock(spec=LLMGateway)

        async def send_message_real(*args, **kwargs):
            """Real Ollama call"""
            messages = kwargs.get("conversation_messages", [])
            if not messages and args:
                # Convert to LLMMessage format
                from backend.llm.base import LLMMessage

                messages = [LLMMessage(role="user", content=str(args[1]))]

            response = await ollama_provider.generate(messages)
            return (
                response.content,
                "qwen2.5:latest",
                MagicMock(),
                MagicMock(total_tokens=response.total_tokens),
            )

        gateway.send_message = send_message_real
        gateway.create_chat_with_history = MagicMock(return_value=MagicMock())
        return gateway
    else:
        # Fallback to mock
        gateway = MagicMock()
        gateway.create_chat_with_history = MagicMock(return_value=MagicMock())
        gateway.send_message = MagicMock(
            return_value=(
                "Mock response",
                "gemini-3-flash",
                MagicMock(),
                MagicMock(total_tokens=100),
            )
        )
        return gateway


@pytest.fixture
def mock_llm_gateway(llm_gateway_with_ollama):
    """Alias for backward compatibility - uses Ollama if available"""
    return llm_gateway_with_ollama
