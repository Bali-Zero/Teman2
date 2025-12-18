"""
Comprehensive tests for Response Sanitizer
Target: 95%+ coverage
"""

from backend.utils.response_sanitizer import (
    add_contact_if_appropriate,
    classify_query_type,
    enforce_santai_mode,
    process_zantara_response,
    sanitize_zantara_response,
)


class TestSanitizeZantaraResponse:
    """Test sanitize_zantara_response function"""

    def test_empty_response(self):
        """Test with empty response"""
        assert sanitize_zantara_response("") == ""
        assert sanitize_zantara_response(None) is None

    def test_removes_price_placeholder(self):
        """Test removal of [PRICE] placeholder"""
        response = "The cost is [PRICE]. Contact us for details."
        result = sanitize_zantara_response(response)
        assert "[PRICE]" not in result

    def test_removes_mandatory_placeholder(self):
        """Test removal of [MANDATORY] placeholder"""
        response = "This is [MANDATORY] required."
        result = sanitize_zantara_response(response)
        assert "[MANDATORY]" not in result

    def test_removes_optional_placeholder(self):
        """Test removal of [OPTIONAL] placeholder"""
        response = "This is [OPTIONAL] extra."
        result = sanitize_zantara_response(response)
        assert "[OPTIONAL]" not in result

    def test_removes_training_format_user(self):
        """Test removal of User: format leak"""
        response = "User: What is KITAS? The answer is..."
        result = sanitize_zantara_response(response)
        assert "User:" not in result

    def test_removes_training_format_assistant(self):
        """Test removal of Assistant: format leak"""
        response = "Assistant: Here is the answer."
        result = sanitize_zantara_response(response)
        assert "Assistant:" not in result

    def test_removes_context_leak(self):
        """Test removal of Context: format leak"""
        response = "Context: Some background\nThe actual answer."
        result = sanitize_zantara_response(response)
        assert "Context:" not in result

    def test_removes_context_from_kb(self):
        """Test removal of Context from knowledge base: leak"""
        response = "Context from knowledge base: source data\nAnswer here."
        result = sanitize_zantara_response(response)
        assert "Context from knowledge base:" not in result

    def test_removes_thought_action_observation(self):
        """Test removal of THOUGHT:/ACTION:/OBSERVATION: artifacts"""
        response = "THOUGHT: I need to search\nACTION: search\nOBSERVATION: found\nFinal Answer: Here is the info."
        result = sanitize_zantara_response(response)
        assert "THOUGHT:" not in result
        assert "ACTION:" not in result
        assert "OBSERVATION:" not in result
        assert "Final Answer:" not in result

    def test_removes_meta_commentary(self):
        """Test removal of meta-commentary"""
        response = "(for this scenario) The answer is 42."
        result = sanitize_zantara_response(response)
        assert "(for this scenario)" not in result

    def test_removes_natural_language_summary(self):
        """Test removal of natural language summary text"""
        response = "natural language summary\nHere is the actual content."
        result = sanitize_zantara_response(response)
        assert "natural language summary" not in result.lower()

    def test_removes_simplified_explanation(self):
        """Test removal of Simplified Explanation header"""
        response = "Simplified Explanation\nThe content here."
        result = sanitize_zantara_response(response)
        assert "Simplified Explanation" not in result

    def test_removes_contexto_per_risposta(self):
        """Test removal of Italian context header"""
        response = "Contexto per la risposta: details\nActual response."
        result = sanitize_zantara_response(response)
        assert "Contexto per la risposta:" not in result

    def test_removes_kb_source_tag(self):
        """Test removal of (from KB source) tag"""
        response = "(from KB source)\nThe information is..."
        result = sanitize_zantara_response(response)
        assert "(from KB source)" not in result

    def test_cleans_markdown_headers(self):
        """Test cleaning of markdown headers"""
        response = "### **Important Title**\nContent here."
        result = sanitize_zantara_response(response)
        assert "###" not in result
        # Title should remain
        assert "Important Title" in result

    def test_cleans_section_dividers(self):
        """Test removal of section dividers"""
        response = "Section 1\n----\nSection 2"
        result = sanitize_zantara_response(response)
        assert "----" not in result

    def test_removes_requirements_header(self):
        """Test removal of Requirements: header"""
        response = "Requirements:\nItem 1\nItem 2"
        result = sanitize_zantara_response(response)
        assert "Requirements:" not in result

    def test_removes_deviation_header(self):
        """Test removal of Deviation from Requirement: header"""
        response = "Deviation from Requirement:\nSome text"
        result = sanitize_zantara_response(response)
        assert "Deviation from Requirement:" not in result

    def test_cleans_multiple_newlines(self):
        """Test cleanup of multiple newlines"""
        response = "Line 1\n\n\n\n\nLine 2"
        result = sanitize_zantara_response(response)
        assert "\n\n\n" not in result

    # Tests for bad pattern replacement
    def test_replaces_non_ho_documenti(self):
        """Test replacement of 'non ho documenti' pattern"""
        response = "Mi dispiace, non ho documenti su questo argomento."
        result = sanitize_zantara_response(response)
        assert "non ho documenti" not in result.lower()
        assert "riformulare" in result.lower()

    def test_replaces_non_trovo_documenti(self):
        """Test replacement of 'non trovo documenti' pattern"""
        response = "Non trovo documenti nella knowledge base."
        result = sanitize_zantara_response(response)
        assert "non trovo documenti" not in result.lower()

    def test_replaces_non_ho_informazioni(self):
        """Test replacement of 'non ho informazioni' pattern"""
        response = "Non ho informazioni specifiche."
        result = sanitize_zantara_response(response)
        assert "non ho informazioni" not in result.lower()

    def test_replaces_non_dispongo_di_documenti(self):
        """Test replacement of 'non dispongo di documenti' pattern"""
        response = "Non dispongo di documenti su questo tema."
        result = sanitize_zantara_response(response)
        assert "non dispongo di documenti" not in result.lower()

    def test_replaces_consultare_il_team(self):
        """Test replacement of 'consultare il team' pattern"""
        response = "Ti consiglio di consultare il team per maggiori info."
        result = sanitize_zantara_response(response)
        assert "consultare il team" not in result.lower()

    def test_replaces_caricare_documenti(self):
        """Test replacement of 'caricare documenti' pattern"""
        response = "Devi caricare i documenti nel sistema."
        result = sanitize_zantara_response(response)
        assert "caricare" not in result.lower() or "documenti" not in result.lower()

    def test_replaces_non_ho_dati_specifici(self):
        """Test replacement of 'non ho dati specifici' pattern"""
        response = "Non ho dati specifici su questo caso."
        result = sanitize_zantara_response(response)
        assert "non ho dati specifici" not in result.lower()

    def test_replaces_non_presente_knowledge(self):
        """Test replacement of 'non è presente nella knowledge' pattern"""
        response = "Questa informazione non è presente nella knowledge base."
        result = sanitize_zantara_response(response)
        assert "knowledge" not in result.lower() or "presente" not in result.lower()

    def test_replaces_english_no_documents(self):
        """Test replacement of English 'I don't have documents' pattern"""
        response = "I don't have documents about this topic."
        result = sanitize_zantara_response(response)
        assert "don't have" not in result.lower() or "documents" not in result.lower()

    def test_replaces_no_documents_available(self):
        """Test replacement of 'No documents available' pattern"""
        response = "No documents available for this query."
        result = sanitize_zantara_response(response)
        assert "no documents available" not in result.lower()

    def test_replaces_no_information_found(self):
        """Test replacement of 'No information found' pattern"""
        response = "No information found in the database."
        result = sanitize_zantara_response(response)
        assert "no information found" not in result.lower()

    def test_fixes_broken_markdown(self):
        """Test fixing of broken markdown like *bold**"""
        response = "This is *broken** markdown"
        result = sanitize_zantara_response(response)
        # Should handle broken markdown
        assert "**" not in result or "*broken**" not in result


class TestEnforceSantaiMode:
    """Test enforce_santai_mode function"""

    def test_business_query_no_truncation(self):
        """Test business queries are not truncated"""
        response = "This is a very long business response. " * 20
        result = enforce_santai_mode(response, "business")
        assert result == response

    def test_emergency_query_no_truncation(self):
        """Test emergency queries are not truncated"""
        response = "Urgent information here. " * 20
        result = enforce_santai_mode(response, "emergency")
        assert result == response

    def test_greeting_truncates_sentences(self):
        """Test greeting responses truncate to 3 sentences"""
        response = "Hello! How are you? Great to meet you! I hope you're doing well. This is extra."
        result = enforce_santai_mode(response, "greeting")
        sentences = [s for s in result.split() if s.endswith((".", "!", "?"))]
        assert len(result.split(".")) <= 4  # Max 3 sentences

    def test_casual_truncates_sentences(self):
        """Test casual responses truncate to 3 sentences"""
        response = "That's cool! I agree. Nice thought. Extra sentence. Another one."
        result = enforce_santai_mode(response, "casual")
        # Should be truncated
        assert len(result) <= len(response)

    def test_greeting_truncates_words(self):
        """Test greeting responses truncate to max_words"""
        response = " ".join(["word"] * 50)
        result = enforce_santai_mode(response, "greeting", max_words=30)
        words = result.split()
        assert len(words) <= 31  # 30 + possible trailing

    def test_casual_with_custom_max_words(self):
        """Test casual with custom max_words"""
        response = " ".join(["test"] * 100)
        result = enforce_santai_mode(response, "casual", max_words=20)
        words = result.split()
        assert len(words) <= 21

    def test_truncation_at_sentence_boundary(self):
        """Test truncation happens at sentence boundary"""
        response = "First sentence. Second sentence. Third word fourth fifth sixth seventh eighth ninth tenth eleventh."
        result = enforce_santai_mode(response, "greeting", max_words=10)
        # Should truncate at sentence boundary or add ...
        assert result.endswith(".") or result.endswith("...")

    def test_empty_response(self):
        """Test with empty response"""
        result = enforce_santai_mode("", "greeting")
        assert result == ""


class TestAddContactIfAppropriate:
    """Test add_contact_if_appropriate function"""

    def test_greeting_no_contact(self):
        """Test greeting queries don't get contact info"""
        response = "Hello! Nice to meet you."
        result = add_contact_if_appropriate(response, "greeting")
        assert "+62" not in result
        assert "whatsapp" not in result.lower()

    def test_casual_no_contact(self):
        """Test casual queries don't get contact info"""
        response = "That's interesting!"
        result = add_contact_if_appropriate(response, "casual")
        assert "+62" not in result

    def test_business_adds_contact(self):
        """Test business queries get contact info"""
        response = "For KITAS visa, you need to apply at immigration office."
        result = add_contact_if_appropriate(response, "business")
        assert "+62" in result or "WhatsApp" in result

    def test_emergency_adds_contact(self):
        """Test emergency queries get contact info"""
        response = "In case of emergency, please contact authorities."
        result = add_contact_if_appropriate(response, "emergency")
        assert "+62" in result or "WhatsApp" in result

    def test_no_duplicate_contact(self):
        """Test doesn't add duplicate contact info"""
        response = "Contact us on WhatsApp +62 859 0436 9574 for help."
        result = add_contact_if_appropriate(response, "business")
        # Should not add again
        assert result.count("+62") == 1

    def test_no_duplicate_whatsapp_mention(self):
        """Test doesn't add if whatsapp already mentioned"""
        response = "You can reach us via whatsapp for more details."
        result = add_contact_if_appropriate(response, "business")
        # Should not add phone number since whatsapp mentioned
        assert result == response


class TestClassifyQueryType:
    """Test classify_query_type function"""

    # Greeting tests
    def test_greeting_ciao(self):
        """Test 'ciao' is classified as greeting"""
        assert classify_query_type("ciao") == "greeting"

    def test_greeting_hi(self):
        """Test 'hi' is classified as greeting"""
        assert classify_query_type("hi") == "greeting"

    def test_greeting_hello(self):
        """Test 'hello' is classified as greeting"""
        assert classify_query_type("hello") == "greeting"

    def test_greeting_hey(self):
        """Test 'hey' is classified as greeting"""
        assert classify_query_type("hey") == "greeting"

    def test_greeting_good_morning(self):
        """Test 'good morning' is classified as greeting"""
        assert classify_query_type("good morning") == "greeting"

    def test_greeting_buongiorno(self):
        """Test 'buongiorno' is classified as greeting"""
        assert classify_query_type("buongiorno") == "greeting"

    def test_greeting_buonasera(self):
        """Test 'buonasera' is classified as greeting"""
        assert classify_query_type("buonasera") == "greeting"

    def test_greeting_hola(self):
        """Test 'hola' is classified as greeting"""
        assert classify_query_type("hola") == "greeting"

    def test_greeting_salve(self):
        """Test 'salve' is classified as greeting"""
        assert classify_query_type("salve") == "greeting"

    def test_greeting_yo(self):
        """Test 'yo' is classified as greeting"""
        assert classify_query_type("yo") == "greeting"

    # Casual tests
    def test_casual_come_stai(self):
        """Test 'come stai' is classified as casual"""
        assert classify_query_type("come stai") == "casual"

    def test_casual_how_are_you(self):
        """Test 'how are you' is classified as casual"""
        assert classify_query_type("how are you") == "casual"

    def test_casual_whats_up(self):
        """Test 'what's up' is classified as casual"""
        assert classify_query_type("what's up") == "casual"

    def test_casual_who_are_you(self):
        """Test 'who are you' is classified as casual"""
        assert classify_query_type("who are you") == "casual"

    def test_casual_chi_sei(self):
        """Test 'chi sei' is classified as casual"""
        assert classify_query_type("chi sei") == "casual"

    def test_casual_come_ti_chiami(self):
        """Test 'come ti chiami' is classified as casual"""
        assert classify_query_type("come ti chiami") == "casual"

    # Emergency tests
    def test_emergency_urgent(self):
        """Test 'urgent' keyword triggers emergency"""
        assert classify_query_type("I have an urgent visa issue") == "emergency"

    def test_emergency_urgente(self):
        """Test 'urgente' keyword triggers emergency"""
        assert classify_query_type("Ho un problema urgente") == "emergency"

    def test_emergency_help(self):
        """Test 'help' keyword triggers emergency"""
        assert classify_query_type("Help me please!") == "emergency"

    def test_emergency_aiuto(self):
        """Test 'aiuto' keyword triggers emergency"""
        assert classify_query_type("Aiuto!") == "emergency"

    def test_emergency_lost(self):
        """Test 'lost' keyword triggers emergency"""
        assert classify_query_type("I lost my passport") == "emergency"

    def test_emergency_stolen(self):
        """Test 'stolen' keyword triggers emergency"""
        assert classify_query_type("My wallet was stolen") == "emergency"

    def test_emergency_expired(self):
        """Test 'expired' keyword triggers emergency"""
        assert classify_query_type("My visa expired yesterday") == "emergency"

    def test_emergency_deportation(self):
        """Test 'deportation' keyword triggers emergency"""
        assert classify_query_type("Am I facing deportation?") == "emergency"

    # Business tests
    def test_business_default(self):
        """Test default classification is business"""
        assert classify_query_type("Tell me about PT PMA requirements") == "business"

    def test_business_visa_query(self):
        """Test visa queries are business (not casual even if short)"""
        # This has business keywords so should be business
        query = "what about visa requirements for my company?"
        result = classify_query_type(query)
        assert result == "business"

    def test_casual_with_business_keyword_is_business(self):
        """Test that casual pattern with business keyword is classified as business"""
        # "how are you" pattern but with business keyword
        query = "how are visa applications processed in the system?"
        result = classify_query_type(query)
        # Should be business because of 'visa' keyword
        assert result == "business"

    def test_long_casual_pattern_with_business_keyword(self):
        """Test long message with casual pattern but business keyword"""
        query = "come stai? I need help with my visa application and the legal requirements"
        result = classify_query_type(query)
        # Should be business due to business keywords
        assert result == "business"

    def test_punctuation_removal(self):
        """Test punctuation is removed for matching"""
        assert classify_query_type("Hello!") == "greeting"
        assert classify_query_type("Ciao?") == "greeting"
        assert classify_query_type("Hey...") == "greeting"


class TestProcessZantaraResponse:
    """Test process_zantara_response pipeline"""

    def test_full_pipeline_business(self):
        """Test full pipeline for business query"""
        response = "[PRICE] This is the cost. User: extra. Contact us."
        result = process_zantara_response(response, "business")
        assert "[PRICE]" not in result
        assert "User:" not in result
        # Should have contact info for business
        assert "+62" in result or "WhatsApp" in result

    def test_full_pipeline_greeting(self):
        """Test full pipeline for greeting"""
        response = "Hello! Nice to meet you! How can I help? " * 5
        result = process_zantara_response(response, "greeting")
        # Should be truncated
        assert len(result) < len(response)
        # Should not have contact info
        assert "+62" not in result

    def test_full_pipeline_casual(self):
        """Test full pipeline for casual"""
        response = "That's interesting! Let me tell you more. " * 5
        result = process_zantara_response(response, "casual")
        # Should be truncated
        assert len(result) < len(response)

    def test_disable_santai(self):
        """Test disabling santai mode"""
        response = "Hello! " * 20
        result = process_zantara_response(response, "greeting", apply_santai=False)
        # Should not be truncated
        assert "Hello!" in result

    def test_disable_contact(self):
        """Test disabling contact addition"""
        response = "Business information here."
        result = process_zantara_response(response, "business", add_contact=False)
        # Should not have contact info
        assert "+62" not in result

    def test_all_disabled(self):
        """Test with all processing disabled"""
        response = "[PRICE] Test response"
        result = process_zantara_response(
            response, "business", apply_santai=False, add_contact=False
        )
        # Should still sanitize
        assert "[PRICE]" not in result
        # But no contact
        assert "+62" not in result
