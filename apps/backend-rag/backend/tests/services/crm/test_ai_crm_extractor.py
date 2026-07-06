import json
from datetime import date, datetime
from uuid import UUID

import pytest

from backend.services.crm import enrichment as enrichment_module
from backend.services.crm.ai_crm_extractor import AICRMExtractor, AsyncpgJSONEncoder


class FakeAIClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts: list[str] = []

    async def conversational(self, prompt: str, persona: str, max_tokens: int) -> dict[str, str]:
        self.prompts.append(prompt)
        assert persona == "system_crm_extractor"
        assert max_tokens == 8192
        return {"text": self.text}


def test_asyncpg_json_encoder_serializes_uuid_and_dates() -> None:
    payload = {
        "id": UUID("12345678-1234-5678-1234-567812345678"),
        "created_at": datetime(2026, 1, 2, 3, 4, 5),
        "birth_date": date(2026, 1, 3),
    }

    encoded = json.loads(json.dumps(payload, cls=AsyncpgJSONEncoder))

    assert encoded == {
        "id": "12345678-1234-5678-1234-567812345678",
        "created_at": "2026-01-02T03:04:05",
        "birth_date": "2026-01-03",
    }


@pytest.mark.asyncio
async def test_extract_from_conversation_strips_markdown_and_flags_low_confidence() -> None:
    response = """```json
{
  "client": {"full_name": "Marta Rossi", "email": "marta@example.com", "phone": null, "whatsapp": null, "nationality": "Italian", "confidence": 0.65},
  "practice_intent": {"detected": true, "practice_type_code": "kitas", "confidence": 0.8, "details": "Needs KITAS"},
  "sentiment": "positive",
  "urgency": "normal",
  "summary": "Client asks about KITAS.",
  "action_items": ["follow up"],
  "topics_discussed": ["kitas"],
  "extracted_entities": {"dates": [], "amounts": [], "locations": [], "documents_mentioned": []}
}
```"""
    extractor = AICRMExtractor(ai_client=FakeAIClient(response))

    extracted = await extractor.extract_from_conversation(
        [{"role": "user", "content": "I need a KITAS"}],
        existing_client_data={"email": "old@example.com"},
    )

    assert extracted["client"]["email"] == "marta@example.com"
    assert extracted["practice_intent"]["practice_type_code"] == "kitas"
    assert extracted["_low_confidence"] is True
    assert "EXISTING CLIENT DATA" in extractor.client.prompts[0]


@pytest.mark.asyncio
async def test_extract_from_conversation_returns_empty_payload_on_invalid_json() -> None:
    extractor = AICRMExtractor(ai_client=FakeAIClient("not json"))

    extracted = await extractor.extract_from_conversation(
        [{"role": "user", "content": "hello"}],
    )

    assert extracted["client"]["confidence"] == 0.0
    assert extracted["practice_intent"]["detected"] is False


@pytest.mark.asyncio
async def test_enrich_client_data_only_fills_empty_fields_above_threshold() -> None:
    extractor = AICRMExtractor(ai_client=FakeAIClient("{}"))
    existing = {"full_name": "Existing Name", "email": None, "phone": None}
    extracted = {
        "client": {
            "full_name": "New Name",
            "email": "new@example.com",
            "phone": "+628123456789",
            "whatsapp": None,
            "nationality": "Italian",
            "confidence": 0.7,
        }
    }

    merged = await extractor.enrich_client_data(extracted, existing)

    assert merged["full_name"] == "Existing Name"
    assert merged["email"] == "new@example.com"
    assert merged["phone"] == "+628123456789"
    assert merged["nationality"] == "Italian"


@pytest.mark.asyncio
async def test_should_create_practice_requires_detection_confidence_and_code() -> None:
    extractor = AICRMExtractor(ai_client=FakeAIClient("{}"))

    assert await extractor.should_create_practice(
        {
            "practice_intent": {
                "detected": True,
                "confidence": 0.7,
                "practice_type_code": "pt_pma",
            }
        }
    )
    assert not await extractor.should_create_practice(
        {
            "practice_intent": {
                "detected": True,
                "confidence": 0.69,
                "practice_type_code": "pt_pma",
            }
        }
    )


def test_get_extractor_reuses_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(enrichment_module, "_extractor_instance", None)
    fake_client = FakeAIClient("{}")

    first = enrichment_module.get_extractor(ai_client=fake_client)
    second = enrichment_module.get_extractor(ai_client=FakeAIClient("{}"))

    assert first is second
    assert first.client is fake_client
