"""
Unit tests for CRM Enrichment services.

Tests AICRMExtractor, BirthplaceEnrichmentService,
and conversation title generation.
"""

import json

import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


def _make_pool(conn=None):
    pool = MagicMock()
    conn = conn or AsyncMock()

    class _Ctx:
        async def __aenter__(self): return conn
        async def __aexit__(self, *a): pass

    pool.acquire = MagicMock(return_value=_Ctx())
    pool._conn = conn
    return pool, conn


# ---------------------------------------------------------------------------
# AsyncpgJSONEncoder
# ---------------------------------------------------------------------------


class TestAsyncpgJSONEncoder:
    def test_uuid_serialization(self):
        from uuid import UUID
        from backend.services.crm.enrichment import AsyncpgJSONEncoder
        val = UUID("12345678-1234-5678-1234-567812345678")
        result = json.dumps(val, cls=AsyncpgJSONEncoder)
        assert "12345678-1234-5678-1234-567812345678" in result

    def test_datetime_serialization(self):
        from datetime import datetime, timezone
        from backend.services.crm.enrichment import AsyncpgJSONEncoder
        result = json.dumps(datetime(2026, 1, 1, tzinfo=timezone.utc), cls=AsyncpgJSONEncoder)
        assert "2026-01-01" in result

    def test_date_serialization(self):
        from datetime import date
        from backend.services.crm.enrichment import AsyncpgJSONEncoder
        result = json.dumps(date(2026, 6, 15), cls=AsyncpgJSONEncoder)
        assert "2026-06-15" in result

    def test_unknown_type_raises(self):
        from backend.services.crm.enrichment import AsyncpgJSONEncoder
        with pytest.raises(TypeError):
            json.dumps(set([1, 2]), cls=AsyncpgJSONEncoder)


# ---------------------------------------------------------------------------
# AICRMExtractor
# ---------------------------------------------------------------------------


def _make_extractor():
    mock_client = AsyncMock()
    from backend.services.crm.enrichment import AICRMExtractor
    ext = AICRMExtractor(ai_client=mock_client)
    return ext, mock_client


@pytest.mark.asyncio
class TestAICRMExtractor:
    async def test_extract_from_conversation_success(self):
        ext, client = _make_extractor()
        client.conversational.return_value = {
            "text": json.dumps({
                "client": {"full_name": "John", "email": "j@x.com", "phone": None, "whatsapp": None, "nationality": "US", "confidence": 0.85},
                "practice_intent": {"detected": True, "practice_type_code": "KITAS", "confidence": 0.9, "details": ""},
                "sentiment": "positive", "urgency": "normal", "summary": "KITAS inquiry",
                "action_items": [], "topics_discussed": ["visa"],
                "extracted_entities": {"dates": [], "amounts": [], "locations": [], "documents_mentioned": []},
            }),
        }
        result = await ext.extract_from_conversation([{"role": "user", "content": "I need a KITAS visa"}])
        assert result["client"]["full_name"] == "John"
        assert result["client"]["confidence"] == 0.85

    async def test_extract_low_confidence_flagged(self):
        ext, client = _make_extractor()
        client.conversational.return_value = {
            "text": json.dumps({
                "client": {"full_name": None, "email": None, "phone": None, "whatsapp": None, "nationality": None, "confidence": 0.3},
                "practice_intent": {"detected": False, "practice_type_code": None, "confidence": 0.0, "details": ""},
                "sentiment": "neutral", "urgency": "normal", "summary": "",
                "action_items": [], "topics_discussed": [],
                "extracted_entities": {"dates": [], "amounts": [], "locations": [], "documents_mentioned": []},
            }),
        }
        result = await ext.extract_from_conversation([{"role": "user", "content": "hello"}])
        assert result.get("_low_confidence") is True

    async def test_extract_handles_markdown_json(self):
        ext, client = _make_extractor()
        client.conversational.return_value = {
            "text": '```json\n{"client": {"confidence": 0.9, "full_name": "Test"}, "practice_intent": {"detected": false}}\n```',
        }
        result = await ext.extract_from_conversation([{"role": "user", "content": "test"}])
        assert result["client"]["full_name"] == "Test"

    async def test_extract_json_error_returns_empty(self):
        ext, client = _make_extractor()
        client.conversational.return_value = {"text": "not json at all"}
        result = await ext.extract_from_conversation([{"role": "user", "content": "test"}])
        assert result["client"]["confidence"] == 0.0

    async def test_extract_exception_returns_empty(self):
        ext, client = _make_extractor()
        client.conversational.side_effect = RuntimeError("API down")
        result = await ext.extract_from_conversation([{"role": "user", "content": "test"}])
        assert result["client"]["confidence"] == 0.0

    def test_get_empty_extraction(self):
        ext, _ = _make_extractor()
        result = ext._get_empty_extraction()
        assert result["client"]["confidence"] == 0.0


@pytest.mark.asyncio
class TestEnrichClientData:
    async def test_no_existing_client(self):
        ext, _ = _make_extractor()
        extracted = {"client": {"full_name": "John", "email": "j@x.com", "phone": None, "whatsapp": None, "nationality": "US", "confidence": 0.9}}
        result = await ext.enrich_client_data(extracted, None)
        assert result["full_name"] == "John"

    async def test_merges_with_existing(self):
        ext, _ = _make_extractor()
        extracted = {"client": {"full_name": "John", "email": "new@x.com", "phone": None, "whatsapp": None, "nationality": "US", "confidence": 0.8}}
        existing = {"full_name": "John Doe", "email": None, "phone": "+62123"}
        result = await ext.enrich_client_data(extracted, existing)
        assert result["full_name"] == "John Doe"
        assert result["email"] == "new@x.com"
        assert result["phone"] == "+62123"

    async def test_low_confidence_skips_merge(self):
        ext, _ = _make_extractor()
        extracted = {"client": {"full_name": "Wrong", "email": None, "phone": None, "whatsapp": None, "nationality": None, "confidence": 0.3}}
        existing = {"full_name": None, "email": None}
        result = await ext.enrich_client_data(extracted, existing)
        assert result.get("full_name") is None


@pytest.mark.asyncio
class TestShouldCreatePractice:
    async def test_should_create_high_confidence(self):
        ext, _ = _make_extractor()
        assert await ext.should_create_practice({"practice_intent": {"detected": True, "confidence": 0.85, "practice_type_code": "KITAS"}}) is True

    async def test_should_not_create_low_confidence(self):
        ext, _ = _make_extractor()
        assert await ext.should_create_practice({"practice_intent": {"detected": True, "confidence": 0.5, "practice_type_code": "KITAS"}}) is False

    async def test_should_not_create_not_detected(self):
        ext, _ = _make_extractor()
        assert await ext.should_create_practice({"practice_intent": {"detected": False, "confidence": 0.9, "practice_type_code": "KITAS"}}) is False

    async def test_should_not_create_no_type(self):
        ext, _ = _make_extractor()
        assert await ext.should_create_practice({"practice_intent": {"detected": True, "confidence": 0.9, "practice_type_code": None}}) is False


# ---------------------------------------------------------------------------
# BirthplaceEnrichmentService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBirthplaceEnrichmentService:
    def _make_service(self, conn=None):
        pool, conn = _make_pool(conn)
        from backend.services.crm.enrichment import BirthplaceEnrichmentService
        svc = BirthplaceEnrichmentService(pool)
        return svc, pool, conn

    async def test_get_clients_needing_enrichment(self):
        conn = AsyncMock()
        conn.fetch.return_value = [{"id": 1, "full_name": "John", "birthplace": "Rome", "nationality": "IT", "custom_fields": {}}]
        svc, _, _ = self._make_service(conn)
        result = await svc.get_clients_needing_enrichment(limit=5)
        assert len(result) == 1

    async def test_call_ollama_success(self):
        svc, _, _ = self._make_service()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "test response"}
        mock_client.post.return_value = mock_resp
        svc._client = mock_client
        result = await svc.call_ollama("test prompt")
        assert result == "test response"

    async def test_call_ollama_timeout(self):
        import httpx
        svc, _, _ = self._make_service()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        svc._client = mock_client
        assert await svc.call_ollama("test") is None

    def test_build_enrichment_prompt(self):
        svc, _, _ = self._make_service()
        prompt = svc.build_enrichment_prompt("Rome", "Italian")
        assert "Rome" in prompt and "Italian" in prompt

    def test_parse_enrichment_response_valid(self):
        svc, _, _ = self._make_service()
        result = svc.parse_enrichment_response('{"famous_people": ["Caesar"]}')
        assert result["famous_people"] == ["Caesar"]

    def test_parse_enrichment_response_invalid(self):
        svc, _, _ = self._make_service()
        assert svc.parse_enrichment_response("not json") is None

    async def test_enrich_client_success(self):
        conn = AsyncMock()
        svc, _, _ = self._make_service(conn)
        svc.call_ollama = AsyncMock(return_value='{"famous_people": ["Test"]}')
        client = {"id": 1, "birthplace": "Rome", "nationality": "IT", "custom_fields": {}}
        result = await svc.enrich_client(client)
        assert result is True
        conn.execute.assert_awaited_once()

    async def test_enrich_client_no_ollama_response(self):
        svc, _, _ = self._make_service()
        svc.call_ollama = AsyncMock(return_value=None)
        assert await svc.enrich_client({"id": 1, "birthplace": "Rome", "nationality": "IT"}) is False

    async def test_close(self):
        svc, _, _ = self._make_service()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        svc._client = mock_client
        await svc.close()
        mock_client.aclose.assert_awaited_once()

    async def test_run_batch_enrichment_ollama_unavailable(self):
        svc, _, _ = self._make_service()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.side_effect = Exception("Connection refused")
        svc._client = mock_client
        stats = await svc.run_batch_enrichment()
        assert "error" in stats

    async def test_run_batch_enrichment_no_clients(self):
        svc, _, _ = self._make_service()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_resp = MagicMock(); mock_resp.status_code = 200
        mock_client.get.return_value = mock_resp
        svc._client = mock_client
        svc.get_clients_needing_enrichment = AsyncMock(return_value=[])
        stats = await svc.run_batch_enrichment()
        assert stats["clients_to_process"] == 0


# ---------------------------------------------------------------------------
# Conversation Title Generator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestConversationTitleGenerator:
    async def test_skips_short_message(self):
        from backend.services.crm.enrichment import generate_conversation_title
        assert await generate_conversation_title("c1", "hi") is None

    async def test_generates_via_ollama(self):
        from backend.services.crm.enrichment import generate_conversation_title
        with patch("backend.services.crm.enrichment._generate_title_via_ollama", new_callable=AsyncMock) as m:
            m.return_value = "KITAS Visa Inquiry"
            result = await generate_conversation_title("c1", "I need help with my KITAS visa application")
        assert result == "KITAS Visa Inquiry"

    async def test_falls_back_to_gemini(self):
        from backend.services.crm.enrichment import generate_conversation_title
        with patch("backend.services.crm.enrichment._generate_title_via_ollama", new_callable=AsyncMock) as m_o, \
             patch("backend.services.crm.enrichment._generate_title_via_gemini", new_callable=AsyncMock) as m_g:
            m_o.return_value = None; m_g.return_value = "Company Setup"
            result = await generate_conversation_title("c1", "How do I set up a PT PMA company")
        assert result == "Company Setup"

    async def test_all_methods_fail(self):
        from backend.services.crm.enrichment import generate_conversation_title
        with patch("backend.services.crm.enrichment._generate_title_via_ollama", new_callable=AsyncMock) as m_o, \
             patch("backend.services.crm.enrichment._generate_title_via_gemini", new_callable=AsyncMock) as m_g:
            m_o.return_value = None; m_g.return_value = None
            assert await generate_conversation_title("c1", "A long enough message for generation") is None


class TestCleanTitle:
    def test_strips_quotes(self):
        from backend.services.crm.enrichment import _clean_title
        assert _clean_title('"Hello World"', 50) == "Hello World"

    def test_truncates_to_max(self):
        from backend.services.crm.enrichment import _clean_title
        assert len(_clean_title("A" * 100, 50)) == 50

    def test_strips_think_tags(self):
        from backend.services.crm.enrichment import _clean_title
        assert _clean_title("<think>reasoning</think>Final Title", 50) == "Final Title"
