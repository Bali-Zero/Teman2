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
