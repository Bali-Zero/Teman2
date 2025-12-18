"""
Unit Tests for Communication Utilities
Tests for language detection, procedural questions, and emotional content detection
"""

from services.communication import (
    detect_language,
    get_emotional_response_instruction,
    get_language_instruction,
    get_procedural_format_instruction,
    has_emotional_content,
    is_procedural_question,
)


class TestLanguageDetection:
    """Test language detection functionality"""

    def test_detect_italian_basic(self):
        """Test detecting Italian from basic phrases"""
        assert detect_language("Ciao, come stai?") == "it"
        assert detect_language("Come posso aiutarti?") == "it"
        assert detect_language("Grazie mille") == "it"

    def test_detect_italian_complex(self):
        """Test detecting Italian from complex sentences"""
        assert detect_language("Vorrei sapere come richiedere il KITAS") == "it"
        assert detect_language("Sono disperato, ho bisogno di aiuto") == "it"
        assert detect_language("Cosa devo fare per aprire una PT PMA?") == "it"

    def test_detect_english_basic(self):
        """Test detecting English from basic phrases"""
        assert detect_language("Hello, how are you?") == "en"
        assert detect_language("What is KITAS?") == "en"
        assert detect_language("I need help") == "en"

    def test_detect_english_complex(self):
        """Test detecting English from complex sentences"""
        assert detect_language("How do I apply for a visa?") == "en"
        assert detect_language("I am frustrated with the process") == "en"
        assert detect_language("What are the requirements?") == "en"

    def test_detect_indonesian_basic(self):
        """Test detecting Indonesian from basic phrases"""
        assert detect_language("Apa kabar?") == "id"
        assert detect_language("Bagaimana cara mengajukan visa?") == "id"
        assert detect_language("Terima kasih") == "id"

    def test_detect_indonesian_complex(self):
        """Test detecting Indonesian from complex sentences"""
        assert detect_language("Saya ingin tahu bagaimana cara mengajukan KITAS") == "id"
        assert detect_language("Saya putus asa, butuh bantuan") == "id"

    def test_detect_empty_string(self):
        """Test empty string defaults to Italian"""
        assert detect_language("") == "it"

    def test_detect_mixed_content(self):
        """Test mixed content detection"""
        # Test with clear Italian marker
        assert detect_language("ciao come stai") == "it"  # Clear Italian marker
        # No clear markers returns "auto" (as per implementation)
        result = detect_language("KITAS visa")
        assert result == "auto"  # Function returns "auto" when no markers found

    def test_detect_no_markers(self):
        """Test content with no language markers returns auto"""
        # When no markers found, function returns "auto"
        assert detect_language("123456") == "auto"
        assert detect_language("KITAS E33G") == "auto"


class TestProceduralQuestionDetection:
    """Test procedural question detection"""

    def test_detect_italian_procedural(self):
        """Test detecting Italian procedural questions"""
        assert is_procedural_question("Come faccio a richiedere il KITAS?") is True
        assert is_procedural_question("Come posso applicare?") is True
        assert is_procedural_question("Come si fa?") is True
        assert is_procedural_question("Quali sono i passi?") is True

    def test_detect_english_procedural(self):
        """Test detecting English procedural questions"""
        assert is_procedural_question("How do I apply?") is True
        assert is_procedural_question("How can I get a visa?") is True
        assert is_procedural_question("What are the steps?") is True
        assert is_procedural_question("How to apply for KITAS?") is True

    def test_detect_indonesian_procedural(self):
        """Test detecting Indonesian procedural questions"""
        assert is_procedural_question("Bagaimana cara mengajukan?") is True
        assert is_procedural_question("Langkah-langkah apa saja?") is True

    def test_detect_non_procedural(self):
        """Test non-procedural questions return False"""
        assert is_procedural_question("Ciao") is False
        assert is_procedural_question("What is KITAS?") is False
        assert is_procedural_question("Quanto costa?") is False
        assert is_procedural_question("") is False


class TestEmotionalContentDetection:
    """Test emotional content detection"""

    def test_detect_italian_emotional(self):
        """Test detecting Italian emotional words"""
        assert has_emotional_content("Sono disperato!") is True
        assert has_emotional_content("Sono frustrato") is True
        assert has_emotional_content("Sono arrabbiato") is True
        assert has_emotional_content("Sono felice") is True
        assert has_emotional_content("Sono preoccupato") is True

    def test_detect_english_emotional(self):
        """Test detecting English emotional words"""
        assert has_emotional_content("I am desperate") is True
        assert has_emotional_content("I am frustrated") is True
        assert has_emotional_content("I am angry") is True
        assert has_emotional_content("I am happy") is True
        assert has_emotional_content("I am worried") is True

    def test_detect_indonesian_emotional(self):
        """Test detecting Indonesian emotional words"""
        assert has_emotional_content("Saya putus asa") is True
        assert has_emotional_content("Saya frustrasi") is True
        assert has_emotional_content("Saya marah") is True

    def test_detect_non_emotional(self):
        """Test non-emotional content returns False"""
        assert has_emotional_content("What is KITAS?") is False
        assert has_emotional_content("Come faccio a richiedere?") is False
        assert has_emotional_content("") is False


class TestLanguageInstructions:
    """Test language instruction generation"""

    def test_get_italian_instruction(self):
        """Test getting Italian language instruction"""
        instruction = get_language_instruction("it")
        assert "LINGUA OBBLIGATORIA" in instruction
        assert "italiano" in instruction.lower()
        assert "Ciao" in instruction

    def test_get_english_instruction(self):
        """Test getting English language instruction"""
        instruction = get_language_instruction("en")
        assert "MANDATORY LANGUAGE" in instruction
        assert "english" in instruction.lower()
        assert "Hello" in instruction

    def test_get_indonesian_instruction(self):
        """Test getting Indonesian language instruction"""
        instruction = get_language_instruction("id")
        assert "BAHASA WAJIB" in instruction
        assert "indonesia" in instruction.lower()

    def test_get_default_instruction(self):
        """Test default instruction for unknown language"""
        instruction = get_language_instruction("unknown")
        assert "LINGUA OBBLIGATORIA" in instruction  # Defaults to Italian


class TestProceduralFormatInstructions:
    """Test procedural format instruction generation"""

    def test_get_italian_procedural_instruction(self):
        """Test getting Italian procedural format instruction"""
        instruction = get_procedural_format_instruction("it")
        assert "FORMATTAZIONE" in instruction
        assert "lista numerata" in instruction.lower()
        assert "1." in instruction or "2." in instruction

    def test_get_english_procedural_instruction(self):
        """Test getting English procedural format instruction"""
        instruction = get_procedural_format_instruction("en")
        assert "PROCEDURAL" in instruction
        assert "numbered list" in instruction.lower()
        assert "1." in instruction or "2." in instruction

    def test_get_indonesian_procedural_instruction(self):
        """Test getting Indonesian procedural format instruction"""
        instruction = get_procedural_format_instruction("id")
        assert "FORMAT" in instruction
        assert "daftar bernomor" in instruction.lower()


class TestEmotionalResponseInstructions:
    """Test emotional response instruction generation"""

    def test_get_italian_emotional_instruction(self):
        """Test getting Italian emotional response instruction"""
        instruction = get_emotional_response_instruction("it")
        assert "EMOTIVI" in instruction or "emotivo" in instruction.lower()
        assert "capisco" in instruction.lower()
        assert "tranquillo" in instruction.lower()

    def test_get_english_emotional_instruction(self):
        """Test getting English emotional response instruction"""
        instruction = get_emotional_response_instruction("en")
        assert "EMOTIONAL" in instruction
        assert "understand" in instruction.lower()
        assert "don't worry" in instruction.lower()

    def test_get_indonesian_emotional_instruction(self):
        """Test getting Indonesian emotional response instruction"""
        instruction = get_emotional_response_instruction("id")
        assert "EMOSIONAL" in instruction
        assert "mengerti" in instruction.lower()


class TestIntegrationScenarios:
    """Test integration scenarios matching the prompt requirements"""

    def test_scenario_1_same_language(self):
        """Test Scenario 1: Response in same language"""
        query = "Ciao, come stai?"
        language = detect_language(query)
        assert language == "it"

        instruction = get_language_instruction(language)
        assert "italiano" in instruction.lower()
        assert "Ciao" in instruction

    def test_scenario_2_emotional_tone(self):
        """Test Scenario 2: Empathetic tone"""
        query = "Ho sbagliato tutto con il mio visto, sono disperato!"

        assert has_emotional_content(query) is True
        assert detect_language(query) == "it"

        instruction = get_emotional_response_instruction("it")
        assert "capisco" in instruction.lower()
        assert "tranquillo" in instruction.lower()

    def test_scenario_3_step_by_step(self):
        """Test Scenario 3: Step-by-step instructions"""
        query = "Come faccio a richiedere il KITAS E33G?"

        assert is_procedural_question(query) is True
        assert detect_language(query) == "it"

        instruction = get_procedural_format_instruction("it")
        assert "lista numerata" in instruction.lower()
        assert "1." in instruction or "2." in instruction
