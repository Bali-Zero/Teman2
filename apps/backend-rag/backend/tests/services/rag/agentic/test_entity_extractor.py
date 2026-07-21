from __future__ import annotations

import pytest

from backend.services.rag.agentic.entity_extractor import EntityExtractionService


@pytest.mark.asyncio
async def test_extract_entities_returns_general_for_empty_query() -> None:
    service = EntityExtractionService()

    assert await service.extract_entities("") == {"domain": "general", "entity_types": []}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "Need E33G KITAS for an Italian founder",
            {
                "domain": "visa",
                "visa_type": "E33G",
                "nationality": "Italy",
                "primary_entity": "E33G",
                "entity_types": ["visa"],
            },
        ),
        (
            "How does PPh 21 work with NPWP?",
            {
                "domain": "tax",
                "tax_concept": "NPWP",
                "tax_code": "npwp",
                "primary_entity": "NPWP",
                "entity_types": ["tax"],
            },
        ),
        (
            "Can a foreigner use Hak Pakai for a villa in Bali?",
            {
                "domain": "property",
                "property_type": "HAK_PAKAI",
                "primary_entity": "HAK_PAKAI",
                "entity_types": ["property"],
            },
        ),
        (
            "Find KBLI 47911 for a PT PMA retail company",
            {
                "domain": "kbli",
                "kbli_code": "47911",
                "company_type": "PT_PMA",
                "primary_entity": "47911",
                "entity_types": ["kbli", "company"],
            },
        ),
        (
            "Setup PT PMA for a Singaporean shareholder",
            {
                "domain": "company",
                "company_type": "PT_PMA",
                "nationality": "Singapore",
                "primary_entity": "PT_PMA",
                "entity_types": ["company"],
            },
        ),
    ],
)
async def test_extract_entities_classifies_domain_entities_and_primary_entity(
    query: str,
    expected: dict[str, object],
) -> None:
    service = EntityExtractionService()

    entities = await service.extract_entities(query)

    for key, value in expected.items():
        assert entities[key] == value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "What is the overstay penalty on a C1, and if I overstay do I pay for every day?",
        "I heard about overstay fines, is that true?",
        "What is penangkalan in Indonesian immigration law?",
        "Could I face deportation if I stay too long?",
        "Apakah saya bisa kena deportasi karena overstay?",
        "Will I get a re-entry ban if I overstay?",
    ],
)
async def test_extract_entities_classifies_overstay_family_keywords_as_visa(query: str) -> None:
    """GUILT (task #23, injection-gap investigation 2026-07-19) — the exact
    prod probe query plus each new visa keyword ("overstay", "penangkalan",
    "deportation", "deportasi", "re-entry ban") individually must classify
    as domain=visa, so `_inject_curated_qa_grounding()` is reachable instead
    of bailing at the domain==general early-return."""
    service = EntityExtractionService()

    entities = await service.extract_entities(query)

    assert entities["domain"] == "visa"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected_domain"),
    [
        ("How does PPh 21 work with NPWP?", "tax"),
        ("Can a foreigner use Hak Pakai for a villa in Bali?", "property"),
        ("Find KBLI 47911 for a PT PMA retail company", "kbli"),
        ("Setup PT PMA for a Singaporean shareholder", "company"),
    ],
)
async def test_extract_entities_overstay_keywords_do_not_shift_unrelated_domains(
    query: str,
    expected_domain: str,
) -> None:
    """INNOCENCE — representative tax/property/kbli/company queries (none
    containing "overstay"/"penangkalan"/"deportation"/"deportasi"/"re-entry
    ban") must keep their pre-existing classification unchanged by the new
    visa keywords."""
    service = EntityExtractionService()

    entities = await service.extract_entities(query)

    assert entities["domain"] == expected_domain


@pytest.mark.asyncio
async def test_extract_entities_general_query_stays_general_after_overstay_addition() -> None:
    """INNOCENCE — a query matching none of the domain keyword lists
    (including the new overstay-family additions) must remain general."""
    service = EntityExtractionService()

    entities = await service.extract_entities("What is the weather like in Bali today?")

    assert entities["domain"] == "general"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "How do I dissolve my business in Bali?",
        "What are my LKPM obligations?",
        "How to close my PT?",
        "I want to liquidate my company, what's the process?",
        "What is the dissolution procedure for a PT PMA?",
        "Do I still need to pay BPJS after closing my company?",
        "How do I get izin usaha for a new branch?",
        "Bagaimana cara tutup PT saya?",
        "PT saya mau dibubarkan, apa langkahnya?",
        "What does winding up a PT PMA involve?",
    ],
)
async def test_extract_entities_classifies_company_closure_and_compliance_keywords(
    query: str,
) -> None:
    """GUILT (company-domain classifier gap) — `_determine_domain()` only
    matched 4 narrow company-setup phrases, so liquidation/closure/compliance
    queries fell to domain=general and `_inject_curated_qa_grounding()`
    early-returned before curated_qa was ever searched, even though
    company-domain curated Q&A grounding exists for these topics. Each new
    keyword ("liquidation"/"liquidate"/"dissolution"/"dissolve"/"close
    pt"/"close my pt"/"close my company"/"close my business"/"closing
    pt"/"tutup pt"/"bubar"/"compliance"/"lkpm"/"bpjs"/"izin usaha"/"wind
    up"/"winding up") individually must classify as domain=company."""
    service = EntityExtractionService()

    entities = await service.extract_entities(query)

    assert entities["domain"] == "company"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected_domain"),
    [
        ("How much is a KITAS?", "visa"),
        ("How does PPh 21 work with NPWP?", "tax"),
        ("Can a foreigner use Hak Pakai for a villa in Bali?", "property"),
        ("Find KBLI 47911 for a PT PMA retail company", "kbli"),
        ("Setup PT PMA for a Singaporean shareholder", "company"),
    ],
)
async def test_extract_entities_company_closure_keywords_do_not_shift_unrelated_domains(
    query: str,
    expected_domain: str,
) -> None:
    """INNOCENCE — representative visa/tax/property/kbli/company queries
    (none containing the new liquidation/closure/compliance keywords) must
    keep their pre-existing classification unchanged by the company-domain
    keyword expansion."""
    service = EntityExtractionService()

    entities = await service.extract_entities(query)

    assert entities["domain"] == expected_domain


@pytest.mark.asyncio
async def test_extract_entities_general_query_stays_general_after_company_closure_addition() -> (
    None
):
    """INNOCENCE — a query matching none of the domain keyword lists
    (including the new company closure/compliance additions) must remain
    general."""
    service = EntityExtractionService()

    entities = await service.extract_entities("What is the weather like in Bali today?")

    assert entities["domain"] == "general"


@pytest.mark.asyncio
async def test_extract_entities_ignores_invalid_kbli_ranges() -> None:
    service = EntityExtractionService()

    entities = await service.extract_entities("What is code 00001?")

    assert "kbli_code" not in entities
    assert entities["domain"] == "general"
    assert entities["primary_entity"] is None


@pytest.mark.asyncio
async def test_is_non_kbli_domain_is_true_for_visa_tax_and_property() -> None:
    service = EntityExtractionService()

    assert service.is_non_kbli_domain("KITAS", {"domain": "visa"}) is True
    assert service.is_non_kbli_domain("NPWP", {"domain": "tax"}) is True
    assert service.is_non_kbli_domain("HGB", {"domain": "property"}) is True
    assert service.is_non_kbli_domain("KBLI 47911", {"domain": "kbli"}) is False
