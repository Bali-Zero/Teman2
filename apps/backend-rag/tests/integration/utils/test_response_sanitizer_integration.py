"""
Integration tests for Response Sanitizer
Target: Improve coverage from 10% to 90%+
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestResponseSanitizerIntegration:
    """Integration tests for response sanitizer"""

    def test_sanitize_zantara_response_empty(self):
        """Test sanitize with empty response"""
        from utils.response_sanitizer import sanitize_zantara_response

        result = sanitize_zantara_response("")
        assert result == ""

    def test_sanitize_zantara_response_none(self):
        """Test sanitize with None response"""
        from utils.response_sanitizer import sanitize_zantara_response

        result = sanitize_zantara_response(None)
        assert result is None

    def test_sanitize_remove_placeholders(self):
        """Test removing [PRICE], [MANDATORY] placeholders"""
        from utils.response_sanitizer import sanitize_zantara_response

        response = "Il costo è [PRICE]. [MANDATORY] documento richiesto."
        result = sanitize_zantara_response(response)
        assert "[PRICE]" not in result
        assert "[MANDATORY]" not in result

    def test_sanitize_remove_training_format(self):
        """Test removing User:/Assistant: format leaks"""
        from utils.response_sanitizer import sanitize_zantara_response

        response = "User: Domanda\nAssistant: Risposta\nContext: Info"
        result = sanitize_zantara_response(response)
        assert "User:" not in result
        assert "Assistant:" not in result
        assert "Context:" not in result

    def test_sanitize_remove_agentic_artifacts(self):
        """Test removing THOUGHT:/ACTION:/OBSERVATION: artifacts"""
        from utils.response_sanitizer import sanitize_zantara_response

        response = (
            "THOUGHT: I need to think\nACTION: search\nOBSERVATION: found\nFinal Answer: Result"
        )
        result = sanitize_zantara_response(response)
        assert "THOUGHT:" not in result
        assert "ACTION:" not in result
        assert "OBSERVATION:" not in result
        assert "Final Answer:" not in result

    def test_sanitize_replace_bad_patterns(self):
        """Test replacing bad patterns like 'non ho documenti'"""
        from utils.response_sanitizer import sanitize_zantara_response

        bad_responses = [
            "Non ho documenti",
            "Non trovo documenti",
            "Non ho informazioni",
            "I don't have documents",
            "No documents available",
        ]

        for bad_response in bad_responses:
            result = sanitize_zantara_response(bad_response)
            assert "non ho documenti" not in result.lower()
            assert "i don't have" not in result.lower()
            assert "no documents" not in result.lower()

    def test_sanitize_remove_markdown_headers(self):
        """Test removing markdown headers"""
        from utils.response_sanitizer import sanitize_zantara_response

        response = "### **Header**\nContent\n### Subheader"
        result = sanitize_zantara_response(response)
        assert "###" not in result
        assert "**Header**" not in result

    def test_sanitize_clean_multiple_newlines(self):
        """Test cleaning multiple newlines"""
        from utils.response_sanitizer import sanitize_zantara_response

        response = "Line 1\n\n\n\nLine 2"
        result = sanitize_zantara_response(response)
        assert "\n\n\n\n" not in result
        assert "\n\n" in result or "\n" in result

    def test_enforce_santai_mode_greeting(self):
        """Test enforcing SANTAI mode for greeting"""
        from utils.response_sanitizer import enforce_santai_mode

        long_response = "Sentence 1. Sentence 2. Sentence 3. Sentence 4. Sentence 5."
        result = enforce_santai_mode(long_response, "greeting", max_words=30)
        # Should be truncated to max 3 sentences
        sentences = result.split(". ")
        assert len(sentences) <= 3

    def test_enforce_santai_mode_casual(self):
        """Test enforcing SANTAI mode for casual query"""
        from utils.response_sanitizer import enforce_santai_mode

        long_response = " ".join(["word"] * 50)  # 50 words
        result = enforce_santai_mode(long_response, "casual", max_words=30)
        words = result.split()
        assert len(words) <= 30

    def test_enforce_santai_mode_business(self):
        """Test that SANTAI mode doesn't apply to business queries"""
        from utils.response_sanitizer import enforce_santai_mode

        long_response = " ".join(["word"] * 100)
        result = enforce_santai_mode(long_response, "business", max_words=30)
        # Should not be truncated
        assert len(result.split()) > 30

    def test_add_contact_if_appropriate_greeting(self):
        """Test that contact info is NOT added to greetings"""
        from utils.response_sanitizer import add_contact_if_appropriate

        response = "Hello!"
        result = add_contact_if_appropriate(response, "greeting")
        assert "whatsapp" not in result.lower()
        assert "+62" not in result

    def test_add_contact_if_appropriate_business(self):
        """Test that contact info IS added to business queries"""
        from utils.response_sanitizer import add_contact_if_appropriate

        response = "Here is the information about visas."
        result = add_contact_if_appropriate(response, "business")
        assert "whatsapp" in result.lower() or "+62" in result

    def test_add_contact_if_appropriate_already_has_contact(self):
        """Test that contact info is not duplicated"""
        from utils.response_sanitizer import add_contact_if_appropriate

        response = "Info here. Contact us on WhatsApp +62 859 0436 9574"
        result = add_contact_if_appropriate(response, "business")
        # Should not add duplicate contact
        assert result.count("+62") == 1

    def test_classify_query_type_greeting(self):
        """Test classifying greeting queries"""
        from utils.response_sanitizer import classify_query_type

        greetings = ["ciao", "hi", "hello", "buongiorno", "good morning"]
        for greeting in greetings:
            result = classify_query_type(greeting)
            assert result == "greeting"

    def test_classify_query_type_casual(self):
        """Test classifying casual queries"""
        from utils.response_sanitizer import classify_query_type

        casual_queries = ["come stai", "how are you", "what's up"]
        for query in casual_queries:
            result = classify_query_type(query)
            assert result == "casual"

    def test_classify_query_type_emergency(self):
        """Test classifying emergency queries"""
        from utils.response_sanitizer import classify_query_type

        emergency_queries = [
            "urgent help needed",
            "emergenza visa",
            "lost passport",
            "expired visa",
        ]
        for query in emergency_queries:
            result = classify_query_type(query)
            assert result == "emergency"

    def test_classify_query_type_business(self):
        """Test classifying business queries"""
        from utils.response_sanitizer import classify_query_type

        business_queries = [
            "informazioni su visa",
            "come ottenere kitas",
            "prezzi servizi",
        ]
        for query in business_queries:
            result = classify_query_type(query)
            assert result == "business"

    def test_classify_query_type_casual_with_business_keyword(self):
        """Test that casual queries with business keywords are classified as business"""
        from utils.response_sanitizer import classify_query_type

        # Long casual query with business keyword should be business
        query = "come stai con le informazioni sui visti"
        result = classify_query_type(query)
        assert result == "business"

    def test_process_zantara_response_complete_pipeline(self):
        """Test complete response processing pipeline"""
        from utils.response_sanitizer import process_zantara_response

        raw_response = "THOUGHT: think\n[PRICE] User: Question\nAssistant: Answer"
        result = process_zantara_response(
            raw_response, query_type="business", apply_santai=True, add_contact=True
        )
        assert "THOUGHT:" not in result
        assert "[PRICE]" not in result
        assert "User:" not in result
        assert "Assistant:" not in result

    def test_process_zantara_response_without_santai(self):
        """Test processing without SANTAI mode"""
        from utils.response_sanitizer import process_zantara_response

        long_response = " ".join(["word"] * 100)
        result = process_zantara_response(
            long_response, query_type="casual", apply_santai=False, add_contact=False
        )
        # Should not be truncated
        assert len(result.split()) > 30

    def test_process_zantara_response_without_contact(self):
        """Test processing without adding contact"""
        from utils.response_sanitizer import process_zantara_response

        response = "Business information here."
        result = process_zantara_response(
            response, query_type="business", apply_santai=False, add_contact=False
        )
        assert "whatsapp" not in result.lower()
        assert "+62" not in result
