"""
Unit tests for MemoryFactExtractor
Target: >95% coverage
"""

import sys
from pathlib import Path
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.memory.memory_fact_extractor import MemoryFactExtractor


@pytest.fixture
def fact_extractor():
    """Create MemoryFactExtractor instance"""
    return MemoryFactExtractor()


class TestMemoryFactExtractor:
    """Tests for MemoryFactExtractor"""

    def test_init(self, fact_extractor):
        """Test initialization"""
        assert len(fact_extractor.preference_patterns) > 0
        assert len(fact_extractor.business_patterns) > 0
        assert len(fact_extractor.personal_patterns) > 0
        assert len(fact_extractor.timeline_patterns) > 0

    def test_extract_facts_from_conversation(self, fact_extractor):
        """Test extracting facts from conversation"""
        user_message = "I am John, I prefer Italian language"
        ai_response = "I'll remember that you prefer Italian"
        facts = fact_extractor.extract_facts_from_conversation(
            user_message, ai_response, "user1"
        )
        assert isinstance(facts, list)

    def test_extract_facts_preference(self, fact_extractor):
        """Test extracting preference facts"""
        text = "I prefer Italian language and want meetings in the morning"
        facts = fact_extractor._extract_from_text(text, source="user")
        assert len(facts) > 0
        assert any(f["type"] == "preference" for f in facts)

    def test_extract_facts_business(self, fact_extractor):
        """Test extracting business facts"""
        text = "I want to set up a PT PMA company with KBLI code 56101"
        facts = fact_extractor._extract_from_text(text, source="user")
        assert len(facts) > 0
        assert any(f["type"] == "company" or f["type"] == "kbli" for f in facts)

    def test_extract_facts_personal(self, fact_extractor):
        """Test extracting personal facts"""
        text = "My name is John, I am Italian, I live in Bali"
        facts = fact_extractor._extract_from_text(text, source="user")
        assert len(facts) > 0
        assert any(f["type"] == "identity" or f["type"] == "nationality" or f["type"] == "location" for f in facts)

    def test_extract_facts_timeline(self, fact_extractor):
        """Test extracting timeline facts"""
        text = "I need this done by next month, it's urgent"
        facts = fact_extractor._extract_from_text(text, source="user")
        assert len(facts) > 0
        assert any(f["type"] == "deadline" or f["type"] == "urgent" for f in facts)

    def test_deduplicate_facts(self, fact_extractor):
        """Test deduplicating facts"""
        facts = [
            {"content": "John", "type": "identity", "confidence": 0.9},
            {"content": "John", "type": "identity", "confidence": 0.8},
        ]
        deduplicated = fact_extractor._deduplicate_facts(facts)
        assert len(deduplicated) == 1
        assert deduplicated[0]["confidence"] == 0.9  # Higher confidence kept

