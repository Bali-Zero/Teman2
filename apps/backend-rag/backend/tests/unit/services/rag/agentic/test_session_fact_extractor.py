"""
Comprehensive test coverage for session_fact_extractor.py
Target: Maximum coverage for all code paths
"""

from services.rag.agentic.session_fact_extractor import (
    SessionFactExtractor,
    SessionFacts,
)


class TestSessionFacts:
    """Test suite for SessionFacts dataclass"""

    def test_empty_facts(self):
        """Test SessionFacts with empty facts list"""
        session_facts = SessionFacts(facts=[])
        assert session_facts.facts == []
        assert session_facts.to_prompt_block() == ""

    def test_single_fact(self):
        """Test SessionFacts with single fact"""
        session_facts = SessionFacts(facts=["Company: Test Corp"])
        assert len(session_facts.facts) == 1
        result = session_facts.to_prompt_block()
        assert "KEY FACTS" in result
        assert "Company: Test Corp" in result
        assert result.startswith("###")

    def test_multiple_facts(self):
        """Test SessionFacts with multiple facts"""
        facts = ["Company: Test Corp", "Budget: 100k", "Location: Milano"]
        session_facts = SessionFacts(facts=facts)
        assert len(session_facts.facts) == 3
        result = session_facts.to_prompt_block()
        assert "Company: Test Corp" in result
        assert "Budget: 100k" in result
        assert "Location: Milano" in result
        assert result.count("-") == 3  # One bullet per fact

    def test_to_prompt_block_format(self):
        """Test to_prompt_block format is correct"""
        facts = ["Fact 1", "Fact 2"]
        session_facts = SessionFacts(facts=facts)
        result = session_facts.to_prompt_block()
        assert result.startswith("### KEY FACTS (THIS SESSION)")
        assert "- Fact 1" in result
        assert "- Fact 2" in result
        assert result.endswith("\n\n")


class TestSessionFactExtractor:
    """Test suite for SessionFactExtractor class"""

    def test_init_default(self):
        """Test initialization with default parameters"""
        extractor = SessionFactExtractor()
        assert extractor.max_facts == 8
        assert extractor.max_value_len == 80

    def test_init_custom(self):
        """Test initialization with custom parameters"""
        extractor = SessionFactExtractor(max_facts=5, max_value_len=50)
        assert extractor.max_facts == 5
        assert extractor.max_value_len == 50

    def test_empty_history(self):
        """Test extracting facts from empty history"""
        extractor = SessionFactExtractor()
        result = extractor.extract_from_history([])
        assert isinstance(result, SessionFacts)
        assert result.facts == []

    def test_none_history(self):
        """Test extracting facts from None history"""
        extractor = SessionFactExtractor()
        result = extractor.extract_from_history(None)
        assert isinstance(result, SessionFacts)
        assert result.facts == []

    def test_non_list_history(self):
        """Test extracting facts from non-list history"""
        extractor = SessionFactExtractor()
        result = extractor.extract_from_history("not a list")
        assert isinstance(result, SessionFacts)
        assert result.facts == []

    def test_extract_company_english(self):
        """Test extracting company fact in English"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "company: Test Corp"}]
        result = extractor.extract_from_history(history)
        assert len(result.facts) >= 1
        assert any("Company: Test Corp" in fact for fact in result.facts)

    def test_extract_company_italian(self):
        """Test extracting company fact in Italian"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "azienda: Test Corp"}]
        result = extractor.extract_from_history(history)
        assert len(result.facts) >= 1
        assert any("Company:" in fact for fact in result.facts)

    def test_extract_budget(self):
        """Test extracting budget fact"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "budget: 100000"}]
        result = extractor.extract_from_history(history)
        assert len(result.facts) >= 1
        assert any("Budget:" in fact for fact in result.facts)

    def test_extract_location_english(self):
        """Test extracting location fact in English"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "location: Milano"}]
        result = extractor.extract_from_history(history)
        assert len(result.facts) >= 1
        assert any("Location:" in fact for fact in result.facts)

    def test_extract_location_italian(self):
        """Test extracting location fact in Italian"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "sono a Roma"}]
        result = extractor.extract_from_history(history)
        assert len(result.facts) >= 1
        assert any("Location:" in fact for fact in result.facts)

    def test_extract_nationality(self):
        """Test extracting nationality fact"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "nationality: Italian"}]
        result = extractor.extract_from_history(history)
        assert len(result.facts) >= 1
        assert any("Nationality:" in fact for fact in result.facts)

    def test_extract_passport(self):
        """Test extracting passport fact"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "passport: IT123456"}]
        result = extractor.extract_from_history(history)
        assert len(result.facts) >= 1
        assert any("Passport:" in fact for fact in result.facts)

    def test_extract_deadline(self):
        """Test extracting deadline fact"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "deadline: 2024-12-31"}]
        result = extractor.extract_from_history(history)
        assert len(result.facts) >= 1
        assert any("Deadline:" in fact for fact in result.facts)

    def test_extract_timeline(self):
        """Test extracting timeline fact"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "timeline: 3 months"}]
        result = extractor.extract_from_history(history)
        assert len(result.facts) >= 1
        assert any("Deadline:" in fact for fact in result.facts)

    def test_ignore_assistant_messages(self):
        """Test that assistant messages are ignored"""
        extractor = SessionFactExtractor()
        history = [
            {"role": "assistant", "content": "company: Assistant Corp"},
            {"role": "user", "content": "company: User Corp"},
        ]
        result = extractor.extract_from_history(history)
        # Should only extract from user message
        assert any("User Corp" in fact for fact in result.facts)
        assert not any("Assistant Corp" in fact for fact in result.facts)

    def test_human_role_supported(self):
        """Test that 'human' role is supported (alternative to 'user')"""
        extractor = SessionFactExtractor()
        history = [{"role": "human", "content": "company: Test Corp"}]
        result = extractor.extract_from_history(history)
        assert len(result.facts) >= 1

    def test_reverse_chronological_order(self):
        """Test that facts are extracted from recent messages first"""
        extractor = SessionFactExtractor()
        history = [
            {"role": "user", "content": "company: Old Corp"},
            {"role": "user", "content": "company: New Corp"},
        ]
        result = extractor.extract_from_history(history)
        # Should extract from most recent (last) message first
        assert any("New Corp" in fact for fact in result.facts)

    def test_max_facts_limit(self):
        """Test that max_facts limit is respected"""
        extractor = SessionFactExtractor(max_facts=2)
        history = [
            {"role": "user", "content": "company: Corp1"},
            {"role": "user", "content": "budget: 100k"},
            {"role": "user", "content": "location: Milano"},
        ]
        result = extractor.extract_from_history(history)
        assert len(result.facts) <= 2

    def test_max_value_len_truncation(self):
        """Test that long values are truncated"""
        extractor = SessionFactExtractor(max_value_len=20)
        long_value = "A" * 50
        history = [{"role": "user", "content": f"company: {long_value}"}]
        result = extractor.extract_from_history(history)
        if result.facts:
            fact = result.facts[0]
            # Value should be truncated with "..."
            value_part = fact.split(":")[1] if ":" in fact else ""
            # Should be truncated (original was 50 chars, max is 20, so should be ~20-23 chars with "...")
            assert len(value_part) <= 25  # Allow some margin for formatting
            assert "..." in value_part  # Should have truncation marker

    def test_multiline_content(self):
        """Test extracting from multiline content"""
        extractor = SessionFactExtractor()
        history = [
            {
                "role": "user",
                "content": "company: Test Corp\nbudget: 100k\nlocation: Milano",
            }
        ]
        result = extractor.extract_from_history(history)
        # Should extract multiple facts from multiline
        assert len(result.facts) >= 2

    def test_duplicate_facts_deduplication(self):
        """Test that duplicate facts are deduplicated"""
        extractor = SessionFactExtractor()
        history = [
            {"role": "user", "content": "company: Test Corp"},
            {"role": "user", "content": "company: Test Corp"},
        ]
        result = extractor.extract_from_history(history)
        # Should only have one "Company: Test Corp" fact
        company_facts = [f for f in result.facts if "Test Corp" in f]
        assert len(company_facts) == 1

    def test_case_insensitive_matching(self):
        """Test that pattern matching is case insensitive"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "COMPANY: Test Corp"}]
        result = extractor.extract_from_history(history)
        assert len(result.facts) >= 1

    def test_colon_and_equals_support(self):
        """Test that both colon and equals are supported"""
        extractor = SessionFactExtractor()
        history = [
            {"role": "user", "content": "company: Test Corp"},
            {"role": "user", "content": "budget=100k"},
        ]
        result = extractor.extract_from_history(history)
        assert len(result.facts) >= 2

    def test_empty_content(self):
        """Test message with empty content"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": ""}]
        result = extractor.extract_from_history(history)
        assert result.facts == []

    def test_whitespace_only_content(self):
        """Test message with whitespace-only content"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "   \n\t   "}]
        result = extractor.extract_from_history(history)
        assert result.facts == []

    def test_non_dict_message(self):
        """Test history with non-dict message"""
        extractor = SessionFactExtractor()
        history = ["not a dict", {"role": "user", "content": "company: Test Corp"}]
        result = extractor.extract_from_history(history)
        # Should skip non-dict and process dict
        assert len(result.facts) >= 1

    def test_missing_role_field(self):
        """Test message with missing role field"""
        extractor = SessionFactExtractor()
        history = [{"content": "company: Test Corp"}]
        result = extractor.extract_from_history(history)
        # Should handle gracefully (role defaults to empty string, not "user")
        assert isinstance(result, SessionFacts)

    def test_missing_content_field(self):
        """Test message with missing content field"""
        extractor = SessionFactExtractor()
        history = [{"role": "user"}]
        result = extractor.extract_from_history(history)
        assert result.facts == []

    def test_non_string_content(self):
        """Test message with non-string content"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": 12345}]
        result = extractor.extract_from_history(history)
        assert result.facts == []

    def test_value_normalization(self):
        """Test that values are normalized (multiple spaces collapsed)"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "company: Test    Corp   Inc"}]
        result = extractor.extract_from_history(history)
        if result.facts:
            fact = result.facts[0]
            # Multiple spaces should be normalized
            assert "  " not in fact or "..." in fact  # Either normalized or truncated

    def test_value_stripped(self):
        """Test that values are stripped of leading/trailing whitespace"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "company:   Test Corp   "}]
        result = extractor.extract_from_history(history)
        if result.facts:
            fact = result.facts[0]
            assert "Test Corp" in fact

    def test_empty_value_ignored(self):
        """Test that facts with empty values are ignored"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "company: "}]
        result = extractor.extract_from_history(history)
        # Should not extract fact with empty value
        company_facts = [f for f in result.facts if "Company:" in f and not f.endswith("Company: ")]
        # Either no facts or facts have values
        assert (
            all(":" in f and f.split(":")[1].strip() for f in result.facts)
            if result.facts
            else True
        )

    def test_multiple_patterns_same_line(self):
        """Test line with multiple patterns (should match first)"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "company: Test Corp budget: 100k"}]
        result = extractor.extract_from_history(history)
        # Should match first pattern
        assert len(result.facts) >= 1

    def test_complex_conversation(self):
        """Test extracting from complex conversation"""
        extractor = SessionFactExtractor()
        history = [
            {"role": "assistant", "content": "Hello!"},
            {"role": "user", "content": "company: Test Corp"},
            {"role": "assistant", "content": "Nice company!"},
            {"role": "user", "content": "budget: 100k\nlocation: Milano"},
            {"role": "user", "content": "deadline: 2024-12-31"},
        ]
        result = extractor.extract_from_history(history)
        # Should extract multiple facts
        assert len(result.facts) >= 3

    def test_societa_pattern_italian(self):
        """Test extracting company with Italian 'società' pattern"""
        extractor = SessionFactExtractor()
        history = [{"role": "user", "content": "società: Test Corp"}]
        result = extractor.extract_from_history(history)
        assert len(result.facts) >= 1
        assert any("Company:" in fact for fact in result.facts)
