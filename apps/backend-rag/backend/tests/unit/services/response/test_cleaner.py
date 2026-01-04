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

    def test_is_out_of_domain_sindaco_personal_data(self):
        """Test sindaco + personal data pattern - covers lines 88-89"""
        query = "codice del sindaco di Roma"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "personal_data"

    def test_is_out_of_domain_presidente_telefono(self):
        """Test presidente + telefono pattern"""
        query = "telefono del presidente di Indonesia"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "personal_data"

    def test_is_out_of_domain_ministro_email(self):
        """Test ministro + email pattern"""
        query = "email del ministro di Bali"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "personal_data"

    def test_is_out_of_domain_sindaco_indirizzo(self):
        """Test sindaco + indirizzo pattern"""
        query = "indirizzo del sindaco di Milano"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "personal_data"

    def test_is_out_of_domain_sindaco_without_personal(self):
        """Test sindaco without personal data is allowed"""
        query = "chi è il sindaco di Roma"
        is_out, category = is_out_of_domain(query)
        assert is_out is False
        assert category is None

    def test_clean_response_empty_input(self):
        """Test cleaning empty response - covers line 108"""
        result = clean_response("")
        assert result == ""

    def test_clean_response_none_like_empty(self):
        """Test cleaning whitespace-only response"""
        result = clean_response("   ")
        assert result == ""

    def test_clean_response_very_long(self):
        """Test very long response logging - covers line 201"""
        # Create a response longer than 15000 chars
        long_response = "A" * 16000
        result = clean_response(long_response)
        # Should not truncate, just return the content
        assert len(result) == 16000
        assert result == long_response

    def test_clean_response_removes_okay_patterns(self):
        """Test removing Okay patterns"""
        response = "Okay, since the observation shows nothing. Here is the answer."
        cleaned = clean_response(response)
        assert "Okay" not in cleaned or "observation" not in cleaned

    def test_clean_response_removes_final_answer_prefix(self):
        """Test removing Final Answer prefix"""
        response = "Final Answer: Here is the answer."
        cleaned = clean_response(response)
        assert "Final Answer:" not in cleaned
        assert "Here is the answer" in cleaned

    def test_clean_response_removes_action_pattern(self):
        """Test removing ACTION patterns"""
        response = "ACTION: vector_search(query='test'). Here is the answer."
        cleaned = clean_response(response)
        assert "ACTION:" not in cleaned

    def test_clean_response_multiple_newlines(self):
        """Test collapsing multiple newlines"""
        response = "Line 1\n\n\n\nLine 2"
        cleaned = clean_response(response)
        assert "\n\n\n\n" not in cleaned
        assert "Line 1" in cleaned
        assert "Line 2" in cleaned

    def test_is_out_of_domain_phone_number(self):
        """Test phone number pattern"""
        query = "phone number of John Smith"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "personal_data"

    def test_is_out_of_domain_stock_price(self):
        """Test stock price pattern"""
        query = "what is the stock price of Apple"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "realtime_info"

    def test_is_out_of_domain_crypto_value(self):
        """Test crypto value pattern"""
        query = "what is the crypto value of ethereum"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "realtime_info"

    def test_is_out_of_domain_forex_rate(self):
        """Test forex rate pattern"""
        query = "forex rate for USD to IDR"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "realtime_info"

    def test_is_out_of_domain_risultati_calcio(self):
        """Test calcio results pattern"""
        query = "risultati di calcio di oggi"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "off_topic"

    def test_is_out_of_domain_scrivi_poema(self):
        """Test poetry pattern"""
        query = "scrivi un poema per me"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "off_topic"

    def test_is_out_of_domain_gossip(self):
        """Test gossip pattern"""
        query = "ultimo gossip su celebrities"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "off_topic"

    def test_is_out_of_domain_oroscopo(self):
        """Test horoscope pattern"""
        query = "oroscopo di oggi"
        is_out, category = is_out_of_domain(query)
        assert is_out is True
        assert category == "off_topic"

    def test_clean_response_removes_let_me_check(self):
        """Test removing Let me check patterns"""
        response = "Let me check the database. Here is the answer."
        cleaned = clean_response(response)
        assert "Let me check" not in cleaned

    def test_clean_response_removes_vector_search(self):
        """Test removing vector_search leaks"""
        response = "vector_search(query='test')\nHere is the answer."
        cleaned = clean_response(response)
        assert "vector_search" not in cleaned

    def test_clean_response_removes_critical_leak(self):
        """Test removing CRITICAL leaks"""
        response = "CRITICAL: Do not share this.\nHere is the answer."
        cleaned = clean_response(response)
        assert "CRITICAL:" not in cleaned

    def test_clean_response_removes_user_query_leak(self):
        """Test removing User Query leaks"""
        response = "User Query: original question\nHere is the answer."
        cleaned = clean_response(response)
        assert "User Query:" not in cleaned
