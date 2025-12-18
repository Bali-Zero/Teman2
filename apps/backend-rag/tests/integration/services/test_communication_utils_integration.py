"""
Integration Tests for Communication Utils
Tests language detection, procedural questions, and emotional content
"""

import os
import sys
from pathlib import Path

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCommunicationUtilsIntegration:
    """Comprehensive integration tests for communication_utils"""

    def test_detect_language_italian(self):
        """Test detecting Italian language"""
        from services.communication import detect_language

        assert detect_language("Ciao, come posso ottenere un visto?") == "it"
        assert detect_language("Voglio aprire un'azienda") == "it"
        assert detect_language("Grazie per l'aiuto") == "it"

    def test_detect_language_english(self):
        """Test detecting English language"""
        from services.communication import detect_language

        assert detect_language("Hello, how can I get a visa?") == "en"
        assert detect_language("I want to open a business") == "en"
        assert detect_language("Thank you for your help") == "en"

    def test_detect_language_indonesian(self):
        """Test detecting Indonesian language"""
        from services.communication import detect_language

        assert detect_language("Apa kabar? Bagaimana cara mendapatkan visa?") == "id"
        assert detect_language("Saya ingin membuka bisnis") == "id"
        assert detect_language("Terima kasih atas bantuannya") == "id"

    def test_detect_language_empty(self):
        """Test detecting language with empty text"""
        from services.communication import detect_language

        assert detect_language("") == "it"  # Default to Italian

    def test_is_procedural_question(self):
        """Test detecting procedural questions"""
        from services.communication import is_procedural_question

        assert is_procedural_question("Come faccio a ottenere un visto?") is True
        assert is_procedural_question("How can I get a visa?") is True
        assert is_procedural_question("What is a visa?") is False

    def test_has_emotional_content(self):
        """Test detecting emotional content"""
        from services.communication import has_emotional_content

        assert has_emotional_content("Sono molto stressato") is True
        assert has_emotional_content("I'm very worried") is True
        assert has_emotional_content("What is PT PMA?") is False

    def test_get_language_instruction(self):
        """Test getting language instruction"""
        from services.communication import get_language_instruction

        instruction = get_language_instruction("it")
        assert instruction is not None
        assert "italian" in instruction.lower() or "italiano" in instruction.lower()

    def test_get_procedural_format_instruction(self):
        """Test getting procedural format instruction"""
        from services.communication import get_procedural_format_instruction

        instruction = get_procedural_format_instruction("it")
        assert instruction is not None
        assert "step" in instruction.lower() or "passo" in instruction.lower()

    def test_get_emotional_response_instruction(self):
        """Test getting emotional response instruction"""
        from services.communication import get_emotional_response_instruction

        instruction = get_emotional_response_instruction("it")
        assert instruction is not None
        assert "emotional" in instruction.lower() or "emotivo" in instruction.lower()
