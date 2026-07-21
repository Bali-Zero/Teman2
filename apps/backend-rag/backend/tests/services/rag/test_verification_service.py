"""
Tests for verification_service.py - RAG response verification against source context.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from backend.services.rag.verification_service import (
    VerificationResult,
    VerificationService,
    VerificationStatus,
)


class TestVerificationStatus:
    """Tests for VerificationStatus enum."""

    def test_all_statuses_defined(self):
        assert VerificationStatus.VERIFIED == "verified"
        assert VerificationStatus.PARTIALLY_VERIFIED == "partial"
        assert VerificationStatus.UNVERIFIED == "unverified"
        assert VerificationStatus.HALLUCINATION == "hallucination"


class TestVerificationResult:
    """Tests for VerificationResult model."""

    def test_valid_result(self):
        result = VerificationResult(
            is_valid=True,
            status=VerificationStatus.VERIFIED,
            score=0.95,
            reasoning="All claims supported",
        )
        assert result.is_valid is True
        assert result.score == 0.95

    def test_score_bounds_enforced(self):
        with pytest.raises(ValidationError, match="score"):
            VerificationResult(
                is_valid=True,
                status=VerificationStatus.VERIFIED,
                score=1.5,  # Over max
                reasoning="test",
            )

    def test_optional_fields_default(self):
        result = VerificationResult(
            is_valid=True,
            status=VerificationStatus.VERIFIED,
            score=0.8,
            reasoning="test",
        )
        assert result.corrected_answer is None
        assert result.missing_citations == []
        assert result.verdict_available is True


class TestVerificationServiceModelConfig:
    """VERIFIER_MODEL env override (increment-1, self-correction latency —
    self-correction-speed-design.md). Default behavior MUST be unchanged
    until an operator sets the env var."""

    def test_honors_verifier_model_env(self, monkeypatch):
        monkeypatch.setenv("VERIFIER_MODEL", "gemini-2.5-flash")
        service = VerificationService()
        assert service.model_name == "gemini-2.5-flash"

    def test_falls_back_to_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("VERIFIER_MODEL", raising=False)
        service = VerificationService()
        assert service.model_name == "gemini-3.5-flash"


class TestVerificationServiceFallbacks:
    """Tests for VerificationService without LLM available."""

    @pytest.mark.asyncio
    async def test_returns_verified_when_model_unavailable(self):
        service = VerificationService()
        # Patch google_api_key to None so _get_genai_client() returns None
        # (simulates deployment environment where key is absent)
        with patch("backend.services.rag.verification_service.settings") as mock_settings:
            mock_settings.google_api_key = None
            result = await service.verify_response(
                query="What is KITAS?",
                draft_answer="KITAS is a temporary stay permit.",
                context_chunks=["KITAS is a temporary stay permit in Indonesia."],
            )
        assert result.is_valid is True
        assert result.status == VerificationStatus.VERIFIED
        assert "unavailable" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_empty_context_returns_partial(self):
        service = VerificationService()
        # Mock client as available
        mock_client = MagicMock()
        mock_client.is_available = True
        service._genai_client = mock_client

        result = await service.verify_response(
            query="What is KITAS?",
            draft_answer="KITAS is a temporary stay permit.",
            context_chunks=[],
        )
        assert result.status == VerificationStatus.PARTIALLY_VERIFIED
        assert result.score == 0.5

    @pytest.mark.asyncio
    async def test_llm_error_returns_partial(self):
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_content = AsyncMock(side_effect=Exception("LLM error"))
        service._genai_client = mock_client

        result = await service.verify_response(
            query="test",
            draft_answer="test answer",
            context_chunks=["context"],
        )
        assert result.is_valid is True
        assert result.status == VerificationStatus.PARTIALLY_VERIFIED
        assert "failed" in result.reasoning.lower()
        # Placeholder score — never a real verdict, must never gate
        # self-correction downstream (reasoning.py).
        assert result.verdict_available is False

    @pytest.mark.asyncio
    async def test_empty_llm_response_marks_verdict_unavailable(self):
        """2026-07-18 fix: Gemini can return text="" (safety block / content
        filter). json.loads("") used to raise and fall into the blanket
        except, minting a score=0.5 that reasoning.py's self-correction gate
        treated as a real verdict — wasting a rephrase+re-verify round-trip
        (~23s, live timeout repro). Guard must catch this BEFORE json.loads
        and mark verdict_available=False, never raise.
        """
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_content = AsyncMock(return_value={"text": ""})
        service._genai_client = mock_client

        result = await service.verify_response(
            query="test",
            draft_answer="test answer",
            context_chunks=["context"],
        )
        assert result.is_valid is True
        assert result.status == VerificationStatus.PARTIALLY_VERIFIED
        assert result.score == 0.5
        assert result.verdict_available is False

    @pytest.mark.asyncio
    async def test_unparseable_json_marks_verdict_unavailable(self):
        """Malformed JSON from the verifier LLM must also be treated as
        'no verdict available', not a real score=0.5."""
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_content = AsyncMock(return_value={"text": "{not valid json"})
        service._genai_client = mock_client

        result = await service.verify_response(
            query="test",
            draft_answer="test answer",
            context_chunks=["context"],
        )
        assert result.is_valid is True
        assert result.status == VerificationStatus.PARTIALLY_VERIFIED
        assert result.score == 0.5
        assert result.verdict_available is False


class TestVerificationServiceWithLLM:
    """Tests for VerificationService with mocked LLM."""

    @pytest.mark.asyncio
    async def test_verified_response(self):
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_content = AsyncMock(
            return_value={
                "text": json.dumps(
                    {
                        "status": "verified",
                        "score": 0.95,
                        "reasoning": "All claims supported by context",
                        "corrections": None,
                        "missing_citations": [],
                    }
                )
            }
        )
        service._genai_client = mock_client

        result = await service.verify_response(
            query="What is KITAS?",
            draft_answer="KITAS is a temporary stay permit in Indonesia.",
            context_chunks=["KITAS is a temporary stay permit issued by Indonesian immigration."],
        )
        assert result.is_valid is True
        assert result.status == VerificationStatus.VERIFIED
        assert result.score == 0.95
        # Innocence: a normal, successfully-parsed verdict is a REAL verdict.
        assert result.verdict_available is True

    @pytest.mark.asyncio
    async def test_hallucination_detected(self):
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_content = AsyncMock(
            return_value={
                "text": json.dumps(
                    {
                        "status": "hallucination",
                        "score": 0.1,
                        "reasoning": "Claims fabricated law UU 999/2025",
                        "corrections": "Remove reference to UU 999/2025",
                        "missing_citations": ["UU 999/2025"],
                    }
                )
            }
        )
        service._genai_client = mock_client

        result = await service.verify_response(
            query="test",
            draft_answer="According to UU 999/2025...",
            context_chunks=["Real context about immigration"],
        )
        assert result.is_valid is False  # score < 0.7
        assert result.status == VerificationStatus.HALLUCINATION
        assert len(result.missing_citations) == 1

    @pytest.mark.asyncio
    async def test_validity_threshold_at_0_7(self):
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_content = AsyncMock(
            return_value={
                "text": json.dumps(
                    {
                        "status": "partial",
                        "score": 0.69,
                        "reasoning": "Mostly correct but one claim unsupported",
                    }
                )
            }
        )
        service._genai_client = mock_client

        result = await service.verify_response(
            query="test",
            draft_answer="test",
            context_chunks=["ctx"],
        )
        assert result.is_valid is False  # 0.69 < 0.7

    @pytest.mark.asyncio
    async def test_context_chunks_formatted_in_prompt(self):
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_content = AsyncMock(
            return_value={
                "text": json.dumps({"status": "verified", "score": 0.9, "reasoning": "ok"})
            }
        )
        service._genai_client = mock_client

        await service.verify_response(
            query="test",
            draft_answer="answer",
            context_chunks=["chunk 1", "chunk 2"],
        )

        # Check the prompt contains formatted chunks
        call_args = mock_client.generate_content.call_args
        prompt = call_args.kwargs.get("contents", call_args.args[0] if call_args.args else "")
        assert "[Source 1]" in prompt
        assert "[Source 2]" in prompt
