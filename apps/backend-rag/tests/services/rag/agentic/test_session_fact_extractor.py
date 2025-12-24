"""
Unit tests for SessionFactExtractor (agentic RAG).
"""

import pytest

from services.rag.agentic.session_fact_extractor import SessionFactExtractor, SessionFacts


@pytest.mark.unit
class TestSessionFactExtractor:
    def test_extract_from_history_empty(self) -> None:
        extractor = SessionFactExtractor()
        facts = extractor.extract_from_history([])
        assert isinstance(facts, SessionFacts)
        assert facts.facts == []
        assert facts.to_prompt_block() == ""

    def test_extract_from_history_company_budget(self) -> None:
        extractor = SessionFactExtractor()
        history = [
            {"role": "assistant", "content": "Ok, dimmi di più."},
            {"role": "user", "content": "Company: Bali Zero\nBudget: 1000 USD\nLocation: Bali"},
        ]
        facts = extractor.extract_from_history(history)
        block = facts.to_prompt_block()
        assert "Company: Bali Zero" in block
        assert "Budget: 1000 USD" in block
        assert "Location: Bali" in block

    def test_extract_from_history_dedup(self) -> None:
        extractor = SessionFactExtractor()
        history = [
            {"role": "user", "content": "Budget: 1000 USD"},
            {"role": "user", "content": "Budget: 1000 USD"},
        ]
        facts = extractor.extract_from_history(history)
        assert len(facts.facts) == 1
