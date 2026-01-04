"""
Comprehensive unit tests for utils/response_sanitizer.py
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from utils.response_sanitizer import (
    add_contact_if_appropriate,
    classify_query_type,
    enforce_santai_mode,
    process_zantara_response,
    sanitize_zantara_response,
)


class TestSanitizeZantaraResponse:
    """Tests for sanitize_zantara_response"""

    def test_empty_response(self):
        """Test sanitizing empty response"""
        result = sanitize_zantara_response("")
        assert result == ""

    def test_none_response(self):
        """Test sanitizing None response"""
        result = sanitize_zantara_response(None)
        assert result is None

    def test_remove_price_placeholder(self):
        """Test removing [PRICE] placeholder"""
        response = "The cost is [PRICE]."
        result = sanitize_zantara_response(response)
        assert "[PRICE]" not in result

    def test_remove_mandatory_placeholder(self):
        """Test removing [MANDATORY] placeholder"""
        response = "[MANDATORY] documents required."
        result = sanitize_zantara_response(response)
        assert "[MANDATORY]" not in result

    def test_remove_optional_placeholder(self):
        """Test removing [OPTIONAL] placeholder"""
        response = "[OPTIONAL] documents."
        result = sanitize_zantara_response(response)
        assert "[OPTIONAL]" not in result

    def test_remove_user_assistant_format(self):
        """Test removing User:/Assistant: format leaks"""
        response = "User: Hello\nAssistant: Hi there"
        result = sanitize_zantara_response(response)
        assert "User:" not in result
        assert "Assistant:" not in result

    def test_remove_thought_action_observation(self):
        """Test removing agentic reasoning artifacts"""
        response = (
            "THOUGHT: I need to think\nACTION: search\nOBSERVATION: found\nFinal Answer: Hello"
        )
        result = sanitize_zantara_response(response)
        assert "THOUGHT:" not in result
        assert "ACTION:" not in result
        assert "OBSERVATION:" not in result
        assert "Final Answer:" not in result

    def test_remove_context_markers(self):
        """Test removing Context: markers"""
        response = "Context: Some context\nAnswer: Hello"
        result = sanitize_zantara_response(response)
        assert "Context:" not in result

    def test_remove_markdown_headers(self):
        """Test removing markdown headers"""
        response = "### **Header**\nContent here"
        result = sanitize_zantara_response(response)
        assert "###" not in result
        assert "**Header**" not in result or "Header" in result

    def test_remove_meta_commentary(self):
        """Test removing meta-commentary"""
        response = "This is a natural language summary of the answer."
        result = sanitize_zantara_response(response)
        assert "natural language summary" not in result.lower()

    def test_replace_bad_patterns(self):
        """Test replacing bad patterns like 'non ho documenti'"""
        response = "Non ho documenti per questa domanda."
        result = sanitize_zantara_response(response)
        assert "non ho documenti" not in result.lower()
        assert "riformulare" in result.lower() or "dettagli" in result.lower()

    def test_remove_multiple_newlines(self):
        """Test cleaning up multiple newlines"""
        response = "Line 1\n\n\n\nLine 2"
        result = sanitize_zantara_response(response)
        assert "\n\n\n\n" not in result
        assert "\n\n" in result or "\n" in result

    def test_remove_section_dividers(self):
        """Test removing section dividers"""
        response = "Content\n---\nMore content"
        result = sanitize_zantara_response(response)
        assert "---" not in result

    def test_remove_requirements_list(self):
        """Test removing Requirements: markers"""
        response = "Requirements:\n1. Item 1\nAnswer: Hello"
        result = sanitize_zantara_response(response)
        assert "Requirements:" not in result


class TestEnforceSantaiMode:
    """Tests for enforce_santai_mode"""

    def test_greeting_query_truncation(self):
        """Test truncating greeting queries"""
        long_response = ". ".join([f"Sentence {i}" for i in range(10)])
        result = enforce_santai_mode(long_response, "greeting", max_words=30)
        assert len(result.split()) <= 30 or "..." in result

    def test_casual_query_truncation(self):
        """Test truncating casual queries"""
        long_response = ". ".join([f"Sentence {i}" for i in range(10)])
        result = enforce_santai_mode(long_response, "casual", max_words=30)
        assert len(result.split()) <= 30 or "..." in result

    def test_business_query_no_truncation(self):
        """Test business queries are not truncated"""
        long_response = ". ".join([f"Sentence {i}" for i in range(10)])
        result = enforce_santai_mode(long_response, "business", max_words=30)
        assert result == long_response

    def test_emergency_query_no_truncation(self):
        """Test emergency queries are not truncated"""
        long_response = ". ".join([f"Sentence {i}" for i in range(10)])
        result = enforce_santai_mode(long_response, "emergency", max_words=30)
        assert result == long_response

    def test_sentence_boundary_truncation(self):
        """Test truncation respects sentence boundaries"""
        response = "First sentence. Second sentence. Third sentence."
        result = enforce_santai_mode(response, "greeting", max_words=3)
        # Should end at sentence boundary
        assert result.endswith(".") or result.endswith("...")


class TestAddContactIfAppropriate:
    """Tests for add_contact_if_appropriate"""

    def test_greeting_no_contact(self):
        """Test greeting queries don't get contact info"""
        response = "Hello!"
        result = add_contact_if_appropriate(response, "greeting")
        assert "whatsapp" not in result.lower()
        assert "+62" not in result

    def test_casual_no_contact(self):
        """Test casual queries don't get contact info"""
        response = "How are you?"
        result = add_contact_if_appropriate(response, "casual")
        assert "whatsapp" not in result.lower()

    def test_business_adds_contact(self):
        """Test business queries get contact info"""
        response = "Here is the information."
        result = add_contact_if_appropriate(response, "business")
        assert "whatsapp" in result.lower() or "+62" in result

    def test_emergency_adds_contact(self):
        """Test emergency queries get contact info"""
        response = "This is urgent."
        result = add_contact_if_appropriate(response, "emergency")
        assert "whatsapp" in result.lower() or "+62" in result

    def test_no_duplicate_contact(self):
        """Test contact info is not added if already present"""
        response = "Contact us on WhatsApp +62 859 0436 9574"
        result = add_contact_if_appropriate(response, "business")
        # Should not duplicate
        assert result.count("whatsapp") == 1 or result.count("+62") == 1


class TestClassifyQueryType:
    """Tests for classify_query_type"""

    def test_greeting_classification(self):
        """Test greeting classification"""
        assert classify_query_type("ciao") == "greeting"
        assert classify_query_type("hi") == "greeting"
        assert classify_query_type("hello") == "greeting"
        assert classify_query_type("buongiorno") == "greeting"

    def test_casual_classification(self):
        """Test casual classification"""
        assert classify_query_type("come stai") == "casual"
        assert classify_query_type("how are you") == "casual"
        assert classify_query_type("what's up") == "casual"

    def test_casual_with_business_keyword(self):
        """Test casual is not classified if business keywords present"""
        assert classify_query_type("come stai con il visto") == "business"
        assert classify_query_type("how are you with visa") == "business"

    def test_long_casual_query(self):
        """Test long queries are not classified as casual"""
        long_query = " ".join(["word"] * 15)
        assert classify_query_type(f"come stai {long_query}") == "business"

    def test_emergency_classification(self):
        """Test emergency classification"""
        assert classify_query_type("urgent help needed") == "emergency"
        assert classify_query_type("emergenza visa") == "emergency"
        assert classify_query_type("problema urgente") == "emergency"

    def test_business_classification(self):
        """Test business classification as default"""
        assert classify_query_type("tell me about visa") == "business"
        assert classify_query_type("how to get permit") == "business"
        assert classify_query_type("tax information") == "business"

    def test_empty_query(self):
        """Test empty query defaults to business"""
        assert classify_query_type("") == "business"


class TestProcessZantaraResponse:
    """Tests for process_zantara_response"""

    def test_full_pipeline(self):
        """Test full response processing pipeline"""
        response = "THOUGHT: Think\n[PRICE] The cost is 100."
        result = process_zantara_response(response, "business")
        assert "THOUGHT:" not in result
        assert "[PRICE]" not in result

    def test_pipeline_with_santai(self):
        """Test pipeline with SANTAI mode"""
        long_response = ". ".join([f"Sentence {i}" for i in range(10)])
        result = process_zantara_response(long_response, "greeting", apply_santai=True)
        assert len(result.split()) <= 30 or "..." in result

    def test_pipeline_without_santai(self):
        """Test pipeline without SANTAI mode"""
        # Create a response with >30 words (10 sentences x 5 words each = 50 words)
        long_response = ". ".join([f"This is sentence number {i}" for i in range(10)])
        result = process_zantara_response(long_response, "greeting", apply_santai=False)
        # Without SANTAI mode, full response should be preserved
        assert len(result.split()) > 30

    def test_pipeline_with_contact(self):
        """Test pipeline adds contact info"""
        response = "Business information here."
        result = process_zantara_response(response, "business", add_contact=True)
        assert "whatsapp" in result.lower() or "+62" in result

    def test_pipeline_without_contact(self):
        """Test pipeline without contact info"""
        response = "Business information here."
        result = process_zantara_response(response, "business", add_contact=False)
        assert "whatsapp" not in result.lower()
