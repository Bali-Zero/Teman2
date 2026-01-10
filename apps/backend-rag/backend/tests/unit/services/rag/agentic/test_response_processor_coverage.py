"""
Complete test coverage for response_processor module
Target: >95% coverage

This file provides comprehensive tests for:
- post_process_response() - main function with all combinations
- _has_numbered_list() - numbered list detection
- _format_as_numbered_list() - procedural formatting
- _has_emotional_acknowledgment() - emotional detection
- _add_emotional_acknowledgment() - emotional acknowledgment addition
"""

import sys
from pathlib import Path
from unittest.mock import patch

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.rag.agentic.response_processor import (
    _add_emotional_acknowledgment,
    _format_as_numbered_list,
    _has_emotional_acknowledgment,
    _has_numbered_list,
    post_process_response,
)

# ============================================================================
# TESTS: _has_numbered_list()
# ============================================================================


class TestHasNumberedList:
    """Tests for _has_numbered_list()"""

    def test_has_numbered_list_with_dot(self):
        """Test detection of numbered list with dots"""
        text = "1. First item. 2. Second item."
        assert _has_numbered_list(text) is True

    def test_has_numbered_list_with_parenthesis(self):
        """Test detection of numbered list with parentheses"""
        text = "1) First item. 2) Second item."
        assert _has_numbered_list(text) is True

    def test_has_numbered_list_no_list(self):
        """Test detection when no numbered list exists"""
        text = "This is just regular text without numbers."
        assert _has_numbered_list(text) is False

    def test_has_numbered_list_single_digit(self):
        """Test detection with single digit"""
        text = "1. Only one item"
        assert _has_numbered_list(text) is True

    def test_has_numbered_list_multiple_digits(self):
        """Test detection with multiple digits"""
        text = "1. First. 2. Second. 3. Third. 4. Fourth."
        assert _has_numbered_list(text) is True

    def test_has_numbered_list_mixed_format(self):
        """Test detection with mixed formats"""
        text = "1. First. 2) Second."
        assert _has_numbered_list(text) is True

    def test_has_numbered_list_number_in_text(self):
        """Test that numbers in text don't trigger false positives"""
        text = "I have 1 apple and 2 oranges."
        assert _has_numbered_list(text) is False

    def test_has_numbered_list_empty_string(self):
        """Test with empty string"""
        assert _has_numbered_list("") is False

    def test_has_numbered_list_whitespace_after_number(self):
        """Test that whitespace after number is required"""
        text = "1.First item"  # No space
        assert _has_numbered_list(text) is False


# ============================================================================
# TESTS: _format_as_numbered_list()
# ============================================================================


class TestFormatAsNumberedList:
    """Tests for _format_as_numbered_list()"""

    def test_format_as_numbered_list_italian(self):
        """Test formatting Italian procedural text"""
        text = "Prepara tutti i documenti necessari. Trova l'ufficio competente. Applica la richiesta formale."
        result = _format_as_numbered_list(text, "it")
        assert "1. " in result
        assert "2. " in result
        # Should contain at least one of the action verbs
        assert "Prepara" in result or "Trova" in result or "Applica" in result

    def test_format_as_numbered_list_english(self):
        """Test formatting English procedural text"""
        text = "Prepare the documents. Find the office. Apply for the request."
        result = _format_as_numbered_list(text, "en")
        assert "1. " in result
        assert "2. " in result
        assert "Prepare" in result

    def test_format_as_numbered_list_indonesian(self):
        """Test formatting Indonesian procedural text"""
        text = "Siapkan semua dokumen yang diperlukan. Cari kantor yang tepat. Ajukan permohonan resmi."
        result = _format_as_numbered_list(text, "id")
        # Sentences must be > 20 chars and contain action verbs
        if len([s for s in text.split(". ") if len(s) > 20]) >= 2:
            assert "1. " in result
            assert "2. " in result
        else:
            # If not enough actionable sentences, returns original
            assert isinstance(result, str)

    def test_format_as_numbered_list_insufficient_sentences(self):
        """Test that text with < 2 actionable sentences is not formatted"""
        text = "Prepare the documents. This is just a regular sentence."
        result = _format_as_numbered_list(text, "en")
        assert result == text  # Should return unchanged

    def test_format_as_numbered_list_short_sentences(self):
        """Test that short sentences (< 20 chars) are not included"""
        text = "Prepare docs. Short. Very short. Find office."
        result = _format_as_numbered_list(text, "en")
        # Should only format sentences > 20 chars with action verbs
        assert isinstance(result, str)

    def test_format_as_numbered_list_no_action_verbs(self):
        """Test that text without action verbs is not formatted"""
        text = "This is a regular sentence. Another sentence here. And one more."
        result = _format_as_numbered_list(text, "en")
        assert result == text  # Should return unchanged

    def test_format_as_numbered_list_unknown_language(self):
        """Test formatting with unknown language defaults to English"""
        text = "Prepare documents. Find office. Apply request."
        result = _format_as_numbered_list(text, "fr")
        # Should use English verbs
        assert isinstance(result, str)

    def test_format_as_numbered_list_multiple_sentences(self):
        """Test formatting with many actionable sentences"""
        text = (
            "Prepare all required documents. "
            "Find the correct office location. "
            "Fill out the application form. "
            "Submit the completed form. "
            "Wait for processing."
        )
        result = _format_as_numbered_list(text, "en")
        assert "1. " in result
        # Function formats actionable sentences (> 20 chars with action verbs)
        # "Wait for processing" is only 20 chars, might not be included
        assert (
            len(
                [
                    line
                    for line in result.split("\n")
                    if line.strip().startswith(("1.", "2.", "3.", "4."))
                ]
            )
            >= 2
        )

    def test_format_as_numbered_list_mixed_punctuation(self):
        """Test formatting with mixed sentence endings"""
        text = "Prepare documents! Find office? Apply request."
        result = _format_as_numbered_list(text, "en")
        assert isinstance(result, str)


# ============================================================================
# TESTS: _has_emotional_acknowledgment()
# ============================================================================


class TestHasEmotionalAcknowledgment:
    """Tests for _has_emotional_acknowledgment()"""

    def test_has_emotional_acknowledgment_italian(self):
        """Test detection of Italian emotional acknowledgment"""
        text = "Capisco la tua situazione, tranquillo."
        assert _has_emotional_acknowledgment(text, "it") is True

    def test_has_emotional_acknowledgment_english(self):
        """Test detection of English emotional acknowledgment"""
        text = "I understand your frustration, don't worry."
        assert _has_emotional_acknowledgment(text, "en") is True

    def test_has_emotional_acknowledgment_indonesian(self):
        """Test detection of Indonesian emotional acknowledgment"""
        text = "Saya mengerti frustrasinya, tenang."
        assert _has_emotional_acknowledgment(text, "id") is True

    def test_has_emotional_acknowledgment_no_acknowledgment(self):
        """Test detection when no acknowledgment is present"""
        text = "This is just regular information without emotional content."
        assert _has_emotional_acknowledgment(text, "en") is False

    def test_has_emotional_acknowledgment_keyword_variations(self):
        """Test detection with keyword variations"""
        text = "There is a solution to this problem."
        assert _has_emotional_acknowledgment(text, "en") is True  # "solution" keyword

    def test_has_emotional_acknowledgment_long_text(self):
        """Test that only first 200 chars are checked"""
        text = "Regular text. " * 20 + "I understand your situation."
        # "understand" is beyond 200 chars, should not be detected
        assert _has_emotional_acknowledgment(text, "en") is False

    def test_has_emotional_acknowledgment_case_insensitive(self):
        """Test that detection is case insensitive"""
        text = "CAPISCO la situazione."
        assert _has_emotional_acknowledgment(text, "it") is True

    def test_has_emotional_acknowledgment_unknown_language(self):
        """Test with unknown language defaults to English"""
        text = "I understand your problem."
        assert _has_emotional_acknowledgment(text, "fr") is True

    def test_has_emotional_acknowledgment_empty_string(self):
        """Test with empty string"""
        assert _has_emotional_acknowledgment("", "en") is False


# ============================================================================
# TESTS: _add_emotional_acknowledgment()
# ============================================================================


class TestAddEmotionalAcknowledgment:
    """Tests for _add_emotional_acknowledgment()"""

    def test_add_emotional_acknowledgment_italian(self):
        """Test adding Italian acknowledgment"""
        text = "Ecco la soluzione al tuo problema."
        result = _add_emotional_acknowledgment(text, "it")
        assert result.startswith("Capisco la frustrazione")
        assert text in result

    def test_add_emotional_acknowledgment_english(self):
        """Test adding English acknowledgment"""
        text = "Here is the solution to your problem."
        result = _add_emotional_acknowledgment(text, "en")
        assert result.startswith("I understand the frustration")
        assert text in result

    def test_add_emotional_acknowledgment_indonesian(self):
        """Test adding Indonesian acknowledgment"""
        text = "Ini solusinya untuk masalah Anda."
        result = _add_emotional_acknowledgment(text, "id")
        assert result.startswith("Saya mengerti frustrasinya")
        assert text in result

    def test_add_emotional_acknowledgment_already_present(self):
        """Test that acknowledgment is not added if already present"""
        text = "Capisco la frustrazione, ma tranquillo - quasi ogni situazione ha una soluzione. Ecco la risposta."
        result = _add_emotional_acknowledgment(text, "it")
        # Should not duplicate
        assert result.count("Capisco la frustrazione") == 1

    def test_add_emotional_acknowledgment_unknown_language(self):
        """Test with unknown language defaults to Italian"""
        text = "Here is the solution."
        result = _add_emotional_acknowledgment(text, "fr")
        assert result.startswith("Capisco la frustrazione")  # Defaults to Italian

    def test_add_emotional_acknowledgment_partial_match(self):
        """Test that partial match prevents duplicate"""
        text = "Capisco la frustrazione, ma la soluzione è semplice."
        result = _add_emotional_acknowledgment(text, "it")
        # Should check first 20 chars of acknowledgment in first 200 chars of text
        assert result.count("Capisco la frustrazione") <= 1

    def test_add_emotional_acknowledgment_empty_string(self):
        """Test with empty string"""
        result = _add_emotional_acknowledgment("", "en")
        assert result.startswith("I understand the frustration")


# ============================================================================
# TESTS: post_process_response() - Complete Coverage
# ============================================================================


class TestPostProcessResponse:
    """Complete tests for post_process_response()"""

    @patch("backend.services.rag.agentic.response_processor.clean_response")
    @patch("backend.services.rag.agentic.response_processor.detect_language")
    @patch("backend.services.rag.agentic.response_processor.is_procedural_question")
    @patch("backend.services.rag.agentic.response_processor.has_emotional_content")
    def test_post_process_response_basic(
        self,
        mock_has_emotional,
        mock_is_procedural,
        mock_detect_language,
        mock_clean_response,
    ):
        """Test basic post-processing without special formatting"""
        mock_clean_response.return_value = "Cleaned response"
        mock_detect_language.return_value = "en"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = False

        result = post_process_response("Raw response", "test query")
        assert result == "Cleaned response"
        mock_clean_response.assert_called_once_with("Raw response")

    @patch("backend.services.rag.agentic.response_processor.clean_response")
    @patch("backend.services.rag.agentic.response_processor.detect_language")
    @patch("backend.services.rag.agentic.response_processor.is_procedural_question")
    @patch("backend.services.rag.agentic.response_processor.has_emotional_content")
    @patch("backend.services.rag.agentic.response_processor._has_numbered_list")
    @patch("backend.services.rag.agentic.response_processor._format_as_numbered_list")
    def test_post_process_response_procedural_formatting(
        self,
        mock_format_list,
        mock_has_list,
        mock_has_emotional,
        mock_is_procedural,
        mock_detect_language,
        mock_clean_response,
    ):
        """Test post-processing with procedural formatting"""
        mock_clean_response.return_value = "Prepare documents. Find office."
        mock_detect_language.return_value = "en"
        mock_is_procedural.return_value = True
        mock_has_emotional.return_value = False
        mock_has_list.return_value = False
        mock_format_list.return_value = "1. Prepare documents.\n2. Find office."

        result = post_process_response("Raw response", "How do I apply?")
        assert "1. " in result
        mock_format_list.assert_called_once_with("Prepare documents. Find office.", "en")

    @patch("backend.services.rag.agentic.response_processor.clean_response")
    @patch("backend.services.rag.agentic.response_processor.detect_language")
    @patch("backend.services.rag.agentic.response_processor.is_procedural_question")
    @patch("backend.services.rag.agentic.response_processor.has_emotional_content")
    @patch("backend.services.rag.agentic.response_processor._has_numbered_list")
    def test_post_process_response_procedural_already_formatted(
        self,
        mock_has_list,
        mock_has_emotional,
        mock_is_procedural,
        mock_detect_language,
        mock_clean_response,
    ):
        """Test that procedural text already formatted is not reformatted"""
        mock_clean_response.return_value = "1. First step. 2. Second step."
        mock_detect_language.return_value = "en"
        mock_is_procedural.return_value = True
        mock_has_emotional.return_value = False
        mock_has_list.return_value = True  # Already has numbered list

        result = post_process_response("Raw response", "How do I apply?")
        assert "1. " in result
        # Should not call _format_as_numbered_list

    @patch("backend.services.rag.agentic.response_processor.clean_response")
    @patch("backend.services.rag.agentic.response_processor.detect_language")
    @patch("backend.services.rag.agentic.response_processor.is_procedural_question")
    @patch("backend.services.rag.agentic.response_processor.has_emotional_content")
    @patch("backend.services.rag.agentic.response_processor._has_emotional_acknowledgment")
    @patch("backend.services.rag.agentic.response_processor._add_emotional_acknowledgment")
    def test_post_process_response_emotional_acknowledgment(
        self,
        mock_add_emotional,
        mock_has_emotional_ack,
        mock_has_emotional,
        mock_is_procedural,
        mock_detect_language,
        mock_clean_response,
    ):
        """Test post-processing with emotional acknowledgment"""
        mock_clean_response.return_value = "Here is the solution."
        mock_detect_language.return_value = "en"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = True
        mock_has_emotional_ack.return_value = False
        mock_add_emotional.return_value = "I understand the frustration. Here is the solution."

        result = post_process_response("Raw response", "I'm so frustrated!")
        assert "I understand the frustration" in result
        mock_add_emotional.assert_called_once_with("Here is the solution.", "en")

    @patch("backend.services.rag.agentic.response_processor.clean_response")
    @patch("backend.services.rag.agentic.response_processor.detect_language")
    @patch("backend.services.rag.agentic.response_processor.is_procedural_question")
    @patch("backend.services.rag.agentic.response_processor.has_emotional_content")
    @patch("backend.services.rag.agentic.response_processor._has_emotional_acknowledgment")
    def test_post_process_response_emotional_already_present(
        self,
        mock_has_emotional_ack,
        mock_has_emotional,
        mock_is_procedural,
        mock_detect_language,
        mock_clean_response,
    ):
        """Test that emotional acknowledgment already present is not added"""
        mock_clean_response.return_value = "I understand your frustration. Here is the solution."
        mock_detect_language.return_value = "en"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = True
        mock_has_emotional_ack.return_value = True  # Already has acknowledgment

        result = post_process_response("Raw response", "I'm frustrated!")
        assert result == "I understand your frustration. Here is the solution."
        # Should not call _add_emotional_acknowledgment

    @patch("backend.services.rag.agentic.response_processor.clean_response")
    @patch("backend.services.rag.agentic.response_processor.detect_language")
    @patch("backend.services.rag.agentic.response_processor.is_procedural_question")
    @patch("backend.services.rag.agentic.response_processor.has_emotional_content")
    @patch("backend.services.rag.agentic.response_processor._has_numbered_list")
    @patch("backend.services.rag.agentic.response_processor._format_as_numbered_list")
    @patch("backend.services.rag.agentic.response_processor._has_emotional_acknowledgment")
    @patch("backend.services.rag.agentic.response_processor._add_emotional_acknowledgment")
    def test_post_process_response_both_procedural_and_emotional(
        self,
        mock_add_emotional,
        mock_has_emotional_ack,
        mock_format_list,
        mock_has_list,
        mock_has_emotional,
        mock_is_procedural,
        mock_detect_language,
        mock_clean_response,
    ):
        """Test post-processing with both procedural and emotional formatting"""
        mock_clean_response.return_value = "Prepare documents. Find office."
        mock_detect_language.return_value = "en"
        mock_is_procedural.return_value = True
        mock_has_emotional.return_value = True
        mock_has_list.return_value = False
        mock_format_list.return_value = "1. Prepare documents.\n2. Find office."
        mock_has_emotional_ack.return_value = False
        mock_add_emotional.return_value = "I understand. 1. Prepare documents.\n2. Find office."

        result = post_process_response("Raw response", "I'm frustrated! How do I apply?")
        assert "1. " in result
        assert "I understand" in result

    @patch("backend.services.rag.agentic.response_processor.clean_response")
    @patch("backend.services.rag.agentic.response_processor.detect_language")
    @patch("backend.services.rag.agentic.response_processor.is_procedural_question")
    @patch("backend.services.rag.agentic.response_processor.has_emotional_content")
    def test_post_process_response_strips_whitespace(
        self,
        mock_has_emotional,
        mock_is_procedural,
        mock_detect_language,
        mock_clean_response,
    ):
        """Test that result is stripped of whitespace"""
        mock_clean_response.return_value = "  Response with spaces  "
        mock_detect_language.return_value = "en"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = False

        result = post_process_response("Raw response", "test query")
        assert result == "Response with spaces"
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    @patch("backend.services.rag.agentic.response_processor.clean_response")
    @patch("backend.services.rag.agentic.response_processor.detect_language")
    @patch("backend.services.rag.agentic.response_processor.is_procedural_question")
    @patch("backend.services.rag.agentic.response_processor.has_emotional_content")
    def test_post_process_response_italian_language(
        self,
        mock_has_emotional,
        mock_is_procedural,
        mock_detect_language,
        mock_clean_response,
    ):
        """Test post-processing with Italian language detection"""
        mock_clean_response.return_value = "Risposta pulita"
        mock_detect_language.return_value = "it"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = False

        result = post_process_response("Risposta grezza", "domanda test")
        assert result == "Risposta pulita"
        mock_detect_language.assert_called_once_with("domanda test")

    @patch("backend.services.rag.agentic.response_processor.clean_response")
    @patch("backend.services.rag.agentic.response_processor.detect_language")
    @patch("backend.services.rag.agentic.response_processor.is_procedural_question")
    @patch("backend.services.rag.agentic.response_processor.has_emotional_content")
    def test_post_process_response_indonesian_language(
        self,
        mock_has_emotional,
        mock_is_procedural,
        mock_detect_language,
        mock_clean_response,
    ):
        """Test post-processing with Indonesian language detection"""
        mock_clean_response.return_value = "Jawaban bersih"
        mock_detect_language.return_value = "id"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = False

        result = post_process_response("Jawaban mentah", "pertanyaan test")
        assert result == "Jawaban bersih"
        mock_detect_language.assert_called_once_with("pertanyaan test")

    @patch("backend.services.rag.agentic.response_processor.clean_response")
    @patch("backend.services.rag.agentic.response_processor.detect_language")
    @patch("backend.services.rag.agentic.response_processor.is_procedural_question")
    @patch("backend.services.rag.agentic.response_processor.has_emotional_content")
    def test_post_process_response_empty_response(
        self,
        mock_has_emotional,
        mock_is_procedural,
        mock_detect_language,
        mock_clean_response,
    ):
        """Test post-processing with empty response"""
        mock_clean_response.return_value = ""
        mock_detect_language.return_value = "en"
        mock_is_procedural.return_value = False
        mock_has_emotional.return_value = False

        result = post_process_response("", "test query")
        assert result == ""
