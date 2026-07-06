from __future__ import annotations

from backend.services.rag.agentic.session_fact_extractor import (
    SessionFactExtractor,
    SessionFacts,
)


def test_session_facts_to_prompt_block_empty_and_bullets() -> None:
    assert SessionFacts([]).to_prompt_block() == ""

    block = SessionFacts(["Company: Bali Zero", "Budget: USD 10000"]).to_prompt_block()

    assert block == (
        "### KEY FACTS (THIS SESSION)\n"
        "- Company: Bali Zero\n"
        "- Budget: USD 10000\n\n"
    )


def test_extract_from_history_reads_recent_user_messages_only() -> None:
    history = [
        {"role": "user", "content": "company: Old Company"},
        {"role": "assistant", "content": "company: Wrong Assistant"},
        {"role": "human", "content": "deadline=Friday"},
        {"role": "user", "content": "company: Bali Zero\nbudget: USD 10000"},
    ]

    facts = SessionFactExtractor().extract_from_history(history)

    assert facts.facts == [
        "Company: Bali Zero",
        "Budget: USD 10000",
        "Deadline: Friday",
        "Company: Old Company",
    ]


def test_extract_from_history_deduplicates_and_truncates_values() -> None:
    extractor = SessionFactExtractor(max_facts=2, max_value_len=10)
    history = [
        {
            "role": "user",
            "content": (
                "company: Bali Zero\n"
                "company: Bali Zero\n"
                "passport: 12345678901234567890\n"
                "location: Canggu"
            ),
        }
    ]

    facts = extractor.extract_from_history(history)

    assert facts.facts == ["Company: Bali Zero", "Passport: 1234567890..."]


def test_extract_from_history_ignores_malformed_or_empty_history() -> None:
    extractor = SessionFactExtractor()

    assert extractor.extract_from_history([]).facts == []
    assert extractor.extract_from_history(None).facts == []  # type: ignore[arg-type]
    assert (
        extractor.extract_from_history(
            [
                "bad",
                {"role": "user", "content": ""},
                {"role": "user", "content": ["not text"]},
                {"role": "system", "content": "budget: USD 1"},
            ]
        ).facts
        == []
    )
