"""
Comprehensive test coverage for response_processor.py
Target: Maximum coverage for all code paths
"""

from unittest.mock import patch

from services.rag.agentic.response_processor import (
    _add_emotional_acknowledgment,
    _format_as_numbered_list,
    _has_emotional_acknowledgment,
    _has_numbered_list,
    post_process_response,
)


class TestHasNumberedList:
    """Test suite for _has_numbered_list helper function"""

    def test_has_numbered_list_with_dots(self):
        """Test detecting numbered list with dots"""
        text = "1. First item\n2. Second item\n3. Third item"
        assert _has_numbered_list(text) is True

    def test_has_numbered_list_with_parentheses(self):
        """Test detecting numbered list with parentheses"""
        text = "1) First item\n2) Second item\n3) Third item"
        assert _has_numbered_list(text) is True

    def test_has_numbered_list_no_list(self):
        """Test text without numbered list"""
        text = "This is just regular text without any numbers."
        assert _has_numbered_list(text) is False

    def test_has_numbered_list_single_digit(self):
        """Test detecting single digit numbered list"""
        text = "1. Single item"
        assert _has_numbered_list(text) is True

    def test_has_numbered_list_double_digit(self):
        """Test detecting double digit numbered list (pattern only matches 1-9)"""
        text = "10. Item ten\n11. Item eleven"
        # Pattern only matches single digits 1-9, so double digits won't match
        assert _has_numbered_list(text) is False

    def test_has_numbered_list_in_middle(self):
        """Test detecting numbered list in middle of text"""
        text = "Introduction text. 1. First step. More text."
        assert _has_numbered_list(text) is True

    def test_has_numbered_list_empty(self):
        """Test empty text"""
        text = ""
        assert _has_numbered_list(text) is False


class TestFormatAsNumberedList:
    """Test suite for _format_as_numbered_list helper function"""

    def test_format_italian_actionable_sentences(self):
        """Test formatting Italian sentences with action verbs"""
        text = "Prepara tutti i documenti necessari. Trova il modulo online. Compila il modulo con attenzione. Invia la richiesta."
        result = _format_as_numbered_list(text, "it")
        assert "1." in result
        assert "2." in result

    def test_format_english_actionable_sentences(self):
        """Test formatting English sentences with action verbs"""
        text = "Prepare all necessary documents. Find the online form. Fill out the form carefully. Submit the request."
        result = _format_as_numbered_list(text, "en")
        assert "1." in result
        assert "2." in result

    def test_format_indonesian_actionable_sentences(self):
        """Test formatting Indonesian sentences with action verbs"""
        text = "Siapkan semua dokumen yang diperlukan. Cari formulir online. Isi formulir dengan hati-hati. Kirim permintaan."
        result = _format_as_numbered_list(text, "id")
        assert "1." in result

    def test_format_insufficient_sentences(self):
        """Test text with insufficient actionable sentences"""
        text = "This is just a regular sentence without action verbs."
        result = _format_as_numbered_list(text, "en")
        assert result == text  # Should return original text

    def test_format_short_sentences(self):
        """Test text with short sentences (less than 20 chars)"""
        text = "Prepare docs. Submit."
        result = _format_as_numbered_list(text, "en")
        assert result == text  # Should return original (too short)

    def test_format_unknown_language(self):
        """Test formatting with unknown language (falls back to English)"""
        text = "Prepare all necessary documents. Find the online form. Fill out the form carefully."
        result = _format_as_numbered_list(text, "xx")
        assert "1." in result  # Should use English verbs


class TestHasEmotionalAcknowledgment:
    """Test suite for _has_emotional_acknowledgment helper function"""

    def test_has_acknowledgment_italian(self):
        """Test detecting Italian emotional acknowledgment"""
        text = "Capisco la tua frustrazione. Ecco la soluzione."
        assert _has_emotional_acknowledgment(text, "it") is True

    def test_has_acknowledgment_english(self):
        """Test detecting English emotional acknowledgment"""
        text = "I understand your frustration. Here is the solution."
        assert _has_emotional_acknowledgment(text, "en") is True

    def test_has_acknowledgment_indonesian(self):
        """Test detecting Indonesian emotional acknowledgment"""
        text = "Saya mengerti frustrasinya. Inilah solusinya."
        assert _has_emotional_acknowledgment(text, "id") is True

    def test_no_acknowledgment(self):
        """Test text without emotional acknowledgment"""
        text = "Here is the information you requested."
        assert _has_emotional_acknowledgment(text, "en") is False

    def test_acknowledgment_in_middle(self):
        """Test acknowledgment keyword in middle of text"""
        text = "The solution is available. I understand the problem. Let me help."
        assert _has_emotional_acknowledgment(text, "en") is True

    def test_unknown_language(self):
        """Test with unknown language (falls back to English)"""
        text = "I understand the issue. Here is the solution."
        assert _has_emotional_acknowledgment(text, "xx") is True


class TestAddEmotionalAcknowledgment:
    """Test suite for _add_emotional_acknowledgment helper function"""

    def test_add_acknowledgment_italian(self):
        """Test adding Italian emotional acknowledgment"""
        text = "Ecco la soluzione al tuo problema."
        result = _add_emotional_acknowledgment(text, "it")
        assert result.startswith("Capisco")
        assert "soluzione" in result

    def test_add_acknowledgment_english(self):
        """Test adding English emotional acknowledgment"""
        text = "Here is the solution to your problem."
        result = _add_emotional_acknowledgment(text, "en")
        assert result.startswith("I understand")
        assert "solution" in result

    def test_add_acknowledgment_indonesian(self):
        """Test adding Indonesian emotional acknowledgment"""
        text = "Inilah solusinya."
        result = _add_emotional_acknowledgment(text, "id")
        assert result.startswith("Saya mengerti")

    def test_already_has_acknowledgment(self):
        """Test text that already has acknowledgment (should not duplicate)"""
        text = "Capisco la frustrazione, ma tranquillo - quasi ogni situazione ha una soluzione. Ecco la risposta."
        result = _add_emotional_acknowledgment(text, "it")
        # Should not add duplicate
        assert result.count("Capisco") == 1

    def test_unknown_language(self):
        """Test with unknown language (falls back to Italian)"""
        text = "Ecco la soluzione."
        result = _add_emotional_acknowledgment(text, "xx")
        assert result.startswith("Capisco")


class TestPostProcessResponse:
    """Test suite for post_process_response function"""

    @patch("services.rag.agentic.response_processor.has_emotional_content")
    @patch("services.rag.agentic.response_processor.is_procedural_question")
    @patch("services.rag.agentic.response_processor.detect_language")
    @patch("services.rag.agentic.response_processor.clean_response")
    def test_simple_processing(
        self, mock_clean, mock_detect_lang, mock_is_procedural, mock_has_emotional
    ):
        """Test simple processing without special formatting"""
        mock_clean.return_value = "Cleaned response"
        mock_detect_lang.return_value = "en"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = False

        result = post_process_response("Raw response", "test query")
        assert result == "Cleaned response"
        mock_clean.assert_called_once_with("Raw response")

    @patch("services.rag.agentic.response_processor._add_emotional_acknowledgment")
    @patch("services.rag.agentic.response_processor._has_emotional_acknowledgment")
    @patch("services.rag.agentic.response_processor.has_emotional_content")
    @patch("services.rag.agentic.response_processor.is_procedural_question")
    @patch("services.rag.agentic.response_processor.detect_language")
    @patch("services.rag.agentic.response_processor.clean_response")
    def test_with_emotional_processing(
        self,
        mock_clean,
        mock_detect_lang,
        mock_is_procedural,
        mock_has_emotional,
        mock_has_ack,
        mock_add_ack,
    ):
        """Test processing with emotional content"""
        mock_clean.return_value = "Response text"
        mock_detect_lang.return_value = "en"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = True
        mock_has_ack.return_value = False
        mock_add_ack.return_value = "Acknowledgment. Response text"

        result = post_process_response("Raw response", "I'm frustrated query")
        assert "Acknowledgment" in result
        mock_add_ack.assert_called_once()

    @patch("services.rag.agentic.response_processor._format_as_numbered_list")
    @patch("services.rag.agentic.response_processor._has_numbered_list")
    @patch("services.rag.agentic.response_processor.has_emotional_content")
    @patch("services.rag.agentic.response_processor.is_procedural_question")
    @patch("services.rag.agentic.response_processor.detect_language")
    @patch("services.rag.agentic.response_processor.clean_response")
    def test_with_procedural_processing(
        self,
        mock_clean,
        mock_detect_lang,
        mock_is_procedural,
        mock_has_emotional,
        mock_has_numbered,
        mock_format_numbered,
    ):
        """Test processing with procedural question"""
        mock_clean.return_value = "Prepare documents. Submit form."
        mock_detect_lang.return_value = "en"
        mock_is_procedural.return_value = True
        mock_has_emotional.return_value = False
        mock_has_numbered.return_value = False
        mock_format_numbered.return_value = "1. Prepare documents. 2. Submit form."

        result = post_process_response("Raw response", "How do I apply?")
        assert "1." in result
        mock_format_numbered.assert_called_once()

    @patch("services.rag.agentic.response_processor._has_numbered_list")
    @patch("services.rag.agentic.response_processor.has_emotional_content")
    @patch("services.rag.agentic.response_processor.is_procedural_question")
    @patch("services.rag.agentic.response_processor.detect_language")
    @patch("services.rag.agentic.response_processor.clean_response")
    def test_procedural_already_has_numbered_list(
        self,
        mock_clean,
        mock_detect_lang,
        mock_is_procedural,
        mock_has_emotional,
        mock_has_numbered,
    ):
        """Test procedural question that already has numbered list"""
        mock_clean.return_value = "1. First step. 2. Second step."
        mock_detect_lang.return_value = "en"
        mock_is_procedural.return_value = True
        mock_has_emotional.return_value = False
        mock_has_numbered.return_value = True

        result = post_process_response("Raw response", "How do I apply?")
        assert "1." in result
        # Should not call _format_as_numbered_list

    @patch("services.rag.agentic.response_processor._has_emotional_acknowledgment")
    @patch("services.rag.agentic.response_processor.has_emotional_content")
    @patch("services.rag.agentic.response_processor.is_procedural_question")
    @patch("services.rag.agentic.response_processor.detect_language")
    @patch("services.rag.agentic.response_processor.clean_response")
    def test_emotional_already_has_acknowledgment(
        self,
        mock_clean,
        mock_detect_lang,
        mock_is_procedural,
        mock_has_emotional,
        mock_has_ack,
    ):
        """Test emotional query that already has acknowledgment"""
        mock_clean.return_value = "I understand. Here is the solution."
        mock_detect_lang.return_value = "en"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = True
        mock_has_ack.return_value = True

        result = post_process_response("Raw response", "I'm frustrated")
        assert "understand" in result
        # Should not call _add_emotional_acknowledgment

    @patch("services.rag.agentic.response_processor.has_emotional_content")
    @patch("services.rag.agentic.response_processor.is_procedural_question")
    @patch("services.rag.agentic.response_processor.detect_language")
    @patch("services.rag.agentic.response_processor.clean_response")
    def test_both_procedural_and_emotional(
        self,
        mock_clean,
        mock_detect_lang,
        mock_is_procedural,
        mock_has_emotional,
    ):
        """Test query that is both procedural and emotional"""
        mock_clean.return_value = "Prepare documents. Submit form."
        mock_detect_lang.return_value = "en"
        mock_is_procedural.return_value = True
        mock_has_emotional.return_value = True

        result = post_process_response("Raw response", "How do I apply? I'm frustrated!")
        # Should apply both formatting and acknowledgment
        assert isinstance(result, str)

    @patch("services.rag.agentic.response_processor.has_emotional_content")
    @patch("services.rag.agentic.response_processor.is_procedural_question")
    @patch("services.rag.agentic.response_processor.detect_language")
    @patch("services.rag.agentic.response_processor.clean_response")
    def test_empty_response(
        self, mock_clean, mock_detect_lang, mock_is_procedural, mock_has_emotional
    ):
        """Test processing empty response"""
        mock_clean.return_value = ""
        mock_detect_lang.return_value = "en"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = False

        result = post_process_response("", "test query")
        assert result == ""

    @patch("services.rag.agentic.response_processor.has_emotional_content")
    @patch("services.rag.agentic.response_processor.is_procedural_question")
    @patch("services.rag.agentic.response_processor.detect_language")
    @patch("services.rag.agentic.response_processor.clean_response")
    def test_whitespace_stripping(
        self, mock_clean, mock_detect_lang, mock_is_procedural, mock_has_emotional
    ):
        """Test that result is stripped of whitespace"""
        mock_clean.return_value = "   Response text   "
        mock_detect_lang.return_value = "en"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = False

        result = post_process_response("Raw response", "test query")
        assert result == "Response text"

    @patch("services.rag.agentic.response_processor.has_emotional_content")
    @patch("services.rag.agentic.response_processor.is_procedural_question")
    @patch("services.rag.agentic.response_processor.detect_language")
    @patch("services.rag.agentic.response_processor.clean_response")
    def test_italian_language_detection(
        self, mock_clean, mock_detect_lang, mock_is_procedural, mock_has_emotional
    ):
        """Test processing with Italian language"""
        mock_clean.return_value = "Risposta"
        mock_detect_lang.return_value = "it"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = False

        result = post_process_response("Raw response", "domanda italiana")
        assert result == "Risposta"
        mock_detect_lang.assert_called_once_with("domanda italiana")

    @patch("services.rag.agentic.response_processor.has_emotional_content")
    @patch("services.rag.agentic.response_processor.is_procedural_question")
    @patch("services.rag.agentic.response_processor.detect_language")
    @patch("services.rag.agentic.response_processor.clean_response")
    def test_indonesian_language_detection(
        self, mock_clean, mock_detect_lang, mock_is_procedural, mock_has_emotional
    ):
        """Test processing with Indonesian language"""
        mock_clean.return_value = "Jawaban"
        mock_detect_lang.return_value = "id"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = False

        result = post_process_response("Raw response", "pertanyaan indonesia")
        assert result == "Jawaban"
        mock_detect_lang.assert_called_once_with("pertanyaan indonesia")
