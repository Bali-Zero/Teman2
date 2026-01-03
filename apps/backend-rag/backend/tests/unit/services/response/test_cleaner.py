"""
Unit tests for Response Cleaner
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.response.cleaner import OUT_OF_DOMAIN_RESPONSES, clean_response, is_out_of_domain


class TestResponseCleaner:
    """Tests for response cleaner functions"""

    def test_is_out_of_domain_personal_data(self):
        """Test detecting personal data queries"""
        query = "codice fiscale di Mario Rossi"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "personal_data"

    def test_is_out_of_domain_realtime_info(self):
        """Test detecting real-time FINANCIAL info queries (blocked)"""
        query = "what's the current bitcoin price"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "realtime_info"

    def test_weather_query_allowed(self):
        """Test that weather queries are NOT blocked (handled by web_search)"""
        query = "che tempo fa a Bali"
        is_out, category = is_out_of_domain(query)
        assert is_out is False
        assert category is None

    def test_is_out_of_domain_off_topic(self):
        """Test detecting off-topic queries"""
        query = "ricetta per la pasta"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "off_topic"

    def test_is_out_of_domain_in_domain(self):
        """Test detecting in-domain queries"""
        query = "come ottenere un visto per l'Indonesia"
        is_out, category = is_out_of_domain(query)
        assert is_out is False
        assert category is None

    def test_clean_response_removes_thought(self):
        """Test cleaning response removes THOUGHT patterns"""
        response = "THOUGHT: I need to think about this.\nAnswer: Here is the answer."
        cleaned = clean_response(response)
        assert "THOUGHT:" not in cleaned
        assert "Here is the answer" in cleaned

    def test_clean_response_removes_observation(self):
        """Test cleaning response removes observation patterns"""
        response = "OBSERVATION: I see this. Answer: Here is the answer."
        cleaned = clean_response(response)
        assert "OBSERVATION:" not in cleaned.lower()

    def test_clean_response_keeps_good_content(self):
        """Test cleaning response keeps good content"""
        response = "Here is a good answer with useful information."
        cleaned = clean_response(response)
        assert cleaned == response

    def test_out_of_domain_responses_dict(self):
        """Test OUT_OF_DOMAIN_RESPONSES dictionary exists"""
        assert isinstance(OUT_OF_DOMAIN_RESPONSES, dict)
        assert "personal_data" in OUT_OF_DOMAIN_RESPONSES
        assert "realtime_info" in OUT_OF_DOMAIN_RESPONSES
        assert "off_topic" in OUT_OF_DOMAIN_RESPONSES

