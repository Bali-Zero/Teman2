"""
Tests for verification_service.py - RAG response verification against source context.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from backend.llm.genai_client import LLMStructuredOutputError
from backend.services.rag.verification_service import (
    VerificationResult,
    VerificationService,
    VerificationStatus,
    VerifierVerdict,
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


class TestVerifierVerdict:
    """Round-2 red-team fixes (Codex, verified independently): the schema
    the verifier LLM is constrained to must ITSELF reject out-of-range/
    unknown values, not rely on downstream code to catch them — an
    unconstrained VerifierVerdict let a malformed model output (e.g.
    score=1.2) pass generate_structured() cleanly and then blow up
    VerificationResult's Field(ge=0.0, le=1.0) UNCAUGHT (outside the
    try/except in verify_response)."""

    def test_score_above_one_rejected(self):
        with pytest.raises(ValidationError):
            VerifierVerdict(reasoning="x", status="verified", score=1.2)

    def test_score_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            VerifierVerdict(reasoning="x", status="verified", score=-0.1)

    def test_unknown_status_rejected(self):
        with pytest.raises(ValidationError):
            VerifierVerdict(reasoning="x", status="bogus", score=0.5)


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
    async def test_model_unavailable_is_no_verdict(self):
        """Round-2 fix (Codex red-team, verified independently): renamed
        from test_returns_verified_when_model_unavailable. The old behavior
        minted a false "verified" (status=VERIFIED, score=1.0,
        verdict_available defaulting True) when the verifier itself was
        dead — inconsistent with every OTHER no-verdict path in this file
        (empty/malformed verdict, generic error), which all correctly set
        verdict_available=False. This is a deliberate behavior change, not
        a regression: "model unavailable" is a no-verdict case like the
        rest, never a real "verified" judgment."""
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
        assert result.status == VerificationStatus.PARTIALLY_VERIFIED
        assert result.score == 0.5
        assert result.verdict_available is False
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

    # NOTE: the old empty-response / unparseable-JSON tests that lived here
    # exercised generate_content()'s raw-text + json.loads() path — the
    # exact markdown-fence bug this fix retires (see TestVerificationServiceWithLLM
    # .test_structured_error_is_no_verdict for the replacement: generate_structured()
    # now owns parsing/validation and raises LLMStructuredOutputError instead of
    # ever handing back unparseable text).


class TestVerificationServiceWithLLM:
    """Tests for VerificationService with mocked LLM — migrated to
    generate_structured() (JSON mode, PR #311 pattern). generate_content()
    + prompt-engineered JSON + json.loads() is RETIRED: Gemini wraps
    unschematized JSON asks in a markdown ```json fence, which made
    json.loads() raise Expecting value: line 1 column 1 (char 0) on every
    call in prod — the fact-check gate was dead. generate_structured() sets
    response_mime_type="application/json" + response_schema so the fence
    can't happen."""

    @pytest.mark.asyncio
    async def test_structured_verdict_pass(self):
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_structured = AsyncMock(
            return_value=VerifierVerdict(
                reasoning="All claims supported by context",
                status="verified",
                score=0.92,
            )
        )
        service._genai_client = mock_client

        result = await service.verify_response(
            query="What is KITAS?",
            draft_answer="KITAS is a temporary stay permit in Indonesia.",
            context_chunks=["KITAS is a temporary stay permit issued by Indonesian immigration."],
        )
        assert result.is_valid is True
        assert result.status == VerificationStatus.VERIFIED
        assert result.score == 0.92
        # Innocence: a normal, schema-valid verdict is a REAL verdict.
        assert result.verdict_available is True

    @pytest.mark.asyncio
    async def test_structured_verdict_fail_gates(self):
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_structured = AsyncMock(
            return_value=VerifierVerdict(
                reasoning="Claims fabricated law UU 999/2025",
                status="unverified",
                score=0.3,
                corrections="Remove reference to UU 999/2025",
                missing_citations=["UU 999/2025"],
            )
        )
        service._genai_client = mock_client

        result = await service.verify_response(
            query="test",
            draft_answer="According to UU 999/2025...",
            context_chunks=["Real context about immigration"],
        )
        assert result.is_valid is False  # score < 0.7
        assert result.status == VerificationStatus.UNVERIFIED
        assert result.score == 0.3
        assert result.verdict_available is True
        assert len(result.missing_citations) == 1

    @pytest.mark.asyncio
    async def test_hallucination_detected(self):
        """Coverage for the HALLUCINATION enum value specifically (distinct
        from the generic below-threshold UNVERIFIED case above) — carried
        over from the pre-fix suite, now via generate_structured."""
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_structured = AsyncMock(
            return_value=VerifierVerdict(
                reasoning="Claims fabricated law UU 999/2025",
                status="hallucination",
                score=0.1,
                corrections="Remove reference to UU 999/2025",
                missing_citations=["UU 999/2025"],
            )
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
    async def test_structured_error_is_no_verdict(self):
        """REGRESSION for the prod markdown-fence bug: when the model can't
        produce schema-valid JSON (generate_structured's own one retry
        exhausted), it raises LLMStructuredOutputError — never a real
        verdict. Must degrade SAFELY (verdict_available=False, score=0.5),
        never gate self-correction on a fake/placeholder score."""
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_structured = AsyncMock(
            side_effect=LLMStructuredOutputError(
                "Model failed to produce VerifierVerdict-valid JSON after 2 attempt(s)"
            )
        )
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
    async def test_structured_error_does_not_leak_exception_content(self):
        """Round-2 fix (Codex red-team, verified independently — PII
        boundary is ABSOLUTE per UU PDP / SYMBIOSIS Law 2): genai_client's
        LLMStructuredOutputError embeds pydantic ValidationError's str(),
        which includes input_value=... — the model's malformed output,
        which can itself echo client PII from the verifier prompt
        (draft_answer/context_chunks). Neither the log nor the stored
        `reasoning` may contain the raw exception text."""
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_structured = AsyncMock(
            side_effect=LLMStructuredOutputError(
                "schema error input_value='mario.rossi@example.com passport A1234567'"
            )
        )
        service._genai_client = mock_client

        result = await service.verify_response(
            query="test",
            draft_answer="test answer",
            context_chunks=["context"],
        )
        assert "example.com" not in result.reasoning
        assert "A1234567" not in result.reasoning
        assert result.verdict_available is False
        assert result.score == 0.5

    @pytest.mark.asyncio
    async def test_calls_structured_not_generate_content(self):
        """Guards against regressing to the fence-prone generate_content()
        path: the verifier must always call generate_structured (JSON mode),
        never generate_content."""
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_structured = AsyncMock(
            return_value=VerifierVerdict(reasoning="ok", status="verified", score=0.9)
        )
        mock_client.generate_content = AsyncMock(
            side_effect=AssertionError("verify_response must not call generate_content")
        )
        service._genai_client = mock_client

        await service.verify_response(
            query="test",
            draft_answer="answer",
            context_chunks=["chunk 1", "chunk 2"],
        )

        mock_client.generate_structured.assert_awaited_once()
        mock_client.generate_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_error_returns_partial(self):
        """Generic (non-schema) errors — network/API — also degrade safely,
        never gating self-correction on a placeholder score."""
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_structured = AsyncMock(side_effect=Exception("LLM error"))
        service._genai_client = mock_client

        result = await service.verify_response(
            query="test",
            draft_answer="test answer",
            context_chunks=["context"],
        )
        assert result.is_valid is True
        assert result.status == VerificationStatus.PARTIALLY_VERIFIED
        assert "failed" in result.reasoning.lower()
        assert result.verdict_available is False

    @pytest.mark.asyncio
    async def test_validity_threshold_at_0_7(self):
        service = VerificationService()
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_structured = AsyncMock(
            return_value=VerifierVerdict(
                reasoning="Mostly correct but one claim unsupported",
                status="partial",
                score=0.69,
            )
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
        mock_client.generate_structured = AsyncMock(
            return_value=VerifierVerdict(reasoning="ok", status="verified", score=0.9)
        )
        service._genai_client = mock_client

        await service.verify_response(
            query="test",
            draft_answer="answer",
            context_chunks=["chunk 1", "chunk 2"],
        )

        # Check the prompt contains formatted chunks
        call_args = mock_client.generate_structured.call_args
        prompt = call_args.kwargs.get("contents", call_args.args[0] if call_args.args else "")
        assert "[Source 1]" in prompt
        assert "[Source 2]" in prompt
