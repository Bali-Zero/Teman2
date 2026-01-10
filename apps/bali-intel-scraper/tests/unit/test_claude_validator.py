"""
Unit Tests for Claude Validator
Tests for the validation gate between LLAMA and enrichment
"""

import pytest
from unittest.mock import patch
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from claude_validator import ClaudeValidator, ValidationResult


class TestValidationResult:
    """Test ValidationResult dataclass"""

    def test_create_result(self):
        """Test creating ValidationResult"""
        result = ValidationResult(
            approved=True, confidence=85, reason="Relevant for expats"
        )
        assert result.approved is True
        assert result.confidence == 85
        assert result.reason == "Relevant for expats"

    def test_result_with_overrides(self):
        """Test with category and priority overrides"""
        result = ValidationResult(
            approved=True,
            confidence=90,
            reason="Immigration related",
            category_override="immigration",
            priority_override="high",
        )
        assert result.category_override == "immigration"
        assert result.priority_override == "high"

    def test_result_defaults(self):
        """Test default values"""
        result = ValidationResult(approved=False, confidence=70, reason="Rejected")
        assert result.category_override is None
        assert result.priority_override is None
        assert result.enrichment_hints is None


class TestClaudeValidatorInit:
    """Test ClaudeValidator initialization"""

    def test_default_init(self):
        """Test default initialization"""
        validator = ClaudeValidator()
        assert validator.AUTO_APPROVE_THRESHOLD == 75
        assert validator.AUTO_REJECT_THRESHOLD == 40
        assert validator.use_web_research is True

    def test_init_without_research(self):
        """Test initialization without web research"""
        validator = ClaudeValidator(use_web_research=False)
        assert validator.use_web_research is False

    def test_stats_initialized(self):
        """Test stats are initialized"""
        validator = ClaudeValidator()
        assert "auto_approved" in validator.stats
        assert "auto_rejected" in validator.stats
        assert "validated_approved" in validator.stats
        assert "validated_rejected" in validator.stats


class TestThresholds:
    """Test threshold values"""

    def test_thresholds_order(self):
        """Thresholds should be properly ordered"""
        validator = ClaudeValidator()
        assert validator.AUTO_APPROVE_THRESHOLD > validator.AUTO_REJECT_THRESHOLD


class TestStats:
    """Test statistics tracking"""

    def test_initial_stats(self):
        """Test initial stats are zero"""
        validator = ClaudeValidator()
        assert validator.stats["auto_approved"] == 0
        assert validator.stats["auto_rejected"] == 0
        assert validator.stats["validated_approved"] == 0
        assert validator.stats["validated_rejected"] == 0


class TestAutoApprove:
    """Test automatic approval for high scores"""

    @pytest.mark.asyncio
    async def test_auto_approve_high_score(self):
        """High scores should auto-approve"""
        validator = ClaudeValidator()

        result = await validator.validate_article(
            title="New KITAS Requirements",
            summary="Immigration policy update",
            content="Full article content...",
            source="Jakarta Post",
            llama_score=85,
            llama_category="immigration",
            llama_reason="visa policy",
        )

        assert result.approved is True
        assert result.confidence >= 90
        assert "auto" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_auto_approve_at_threshold(self):
        """Score at threshold should auto-approve"""
        validator = ClaudeValidator()

        result = await validator.validate_article(
            title="Tax Update",
            summary="NPWP changes",
            content="Content...",
            source="Bisnis",
            llama_score=75,
            llama_category="tax",
        )

        assert result.approved is True

    @pytest.mark.asyncio
    async def test_stats_updated_on_approve(self):
        """Stats should update on auto-approve"""
        validator = ClaudeValidator()

        await validator.validate_article(
            title="Test",
            summary="Test",
            content="Content",
            source="Test",
            llama_score=90,
            llama_category="general",
        )

        assert validator.stats["auto_approved"] == 1


class TestAutoReject:
    """Test automatic rejection for low scores"""

    @pytest.mark.asyncio
    async def test_auto_reject_low_score(self):
        """Low scores should auto-reject"""
        validator = ClaudeValidator()

        result = await validator.validate_article(
            title="Celebrity News",
            summary="Entertainment",
            content="Content...",
            source="Blog",
            llama_score=25,
            llama_category="general",
        )

        assert result.approved is False

    @pytest.mark.asyncio
    async def test_auto_reject_below_threshold(self):
        """Score below threshold should auto-reject"""
        validator = ClaudeValidator()

        result = await validator.validate_article(
            title="Random",
            summary="Not relevant",
            content="Content",
            source="Unknown",
            llama_score=39,
            llama_category="general",
        )

        assert result.approved is False

    @pytest.mark.asyncio
    async def test_stats_updated_on_reject(self):
        """Stats should update on auto-reject"""
        validator = ClaudeValidator()

        await validator.validate_article(
            title="Test",
            summary="Test",
            content="Content",
            source="Test",
            llama_score=30,
            llama_category="general",
        )

        assert validator.stats["auto_rejected"] == 1


class TestClaudeValidation:
    """Test Claude-based validation for ambiguous scores"""

    @pytest.mark.asyncio
    async def test_validate_ambiguous_approved(self):
        """Ambiguous score calls Claude and approves"""
        validator = ClaudeValidator()

        mock_response = json.dumps(
            {
                "approved": True,
                "confidence": 78,
                "reason": "Affects expat requirements",
                "category_override": None,
                "priority_override": "high",
                "enrichment_hints": ["Focus on timeline"],
            }
        )

        with patch.object(validator, "_call_claude_cli", return_value=mock_response):
            result = await validator.validate_article(
                title="Policy Update",
                summary="New rules for visitors",
                content="Content...",
                source="News",
                llama_score=55,
                llama_category="lifestyle",
            )

            assert result.approved is True
            assert result.confidence == 78

    @pytest.mark.asyncio
    async def test_validate_ambiguous_rejected(self):
        """Ambiguous score calls Claude and rejects"""
        validator = ClaudeValidator()

        mock_response = json.dumps(
            {
                "approved": False,
                "confidence": 85,
                "reason": "No actionable info",
                "category_override": None,
                "priority_override": None,
            }
        )

        with patch.object(validator, "_call_claude_cli", return_value=mock_response):
            result = await validator.validate_article(
                title="Festival",
                summary="Cultural event",
                content="Content...",
                source="Local",
                llama_score=50,
                llama_category="lifestyle",
            )

            assert result.approved is False

    @pytest.mark.asyncio
    async def test_category_override(self):
        """Test category override from validation"""
        validator = ClaudeValidator()

        mock_response = json.dumps(
            {
                "approved": True,
                "confidence": 82,
                "reason": "Immigration related",
                "category_override": "immigration",
                "priority_override": "high",
            }
        )

        with patch.object(validator, "_call_claude_cli", return_value=mock_response):
            result = await validator.validate_article(
                title="Entry Requirements",
                summary="Border changes",
                content="Content...",
                source="Gov",
                llama_score=60,
                llama_category="general",
            )

            assert result.category_override == "immigration"

    @pytest.mark.asyncio
    async def test_fallback_on_claude_error(self):
        """Fallback when Claude fails"""
        validator = ClaudeValidator()

        with patch.object(validator, "_call_claude_cli", return_value=None):
            result = await validator.validate_article(
                title="Test",
                summary="Test",
                content="Content",
                source="Test",
                llama_score=55,
                llama_category="general",
            )

            # Score >= 55 should approve on fallback
            assert result.approved is True
            assert result.confidence == 30

    @pytest.mark.asyncio
    async def test_fallback_on_json_error(self):
        """Fallback when JSON parsing fails"""
        validator = ClaudeValidator()

        with patch.object(validator, "_call_claude_cli", return_value="invalid"):
            result = await validator.validate_article(
                title="Test",
                summary="Test",
                content="Content",
                source="Test",
                llama_score=45,
                llama_category="general",
            )

            # Score < 55 should reject on fallback
            assert result.approved is False


class TestBuildPrompt:
    """Test prompt building"""

    def test_prompt_contains_info(self):
        """Prompt contains article information"""
        validator = ClaudeValidator()

        prompt = validator._build_validation_prompt(
            title="Test Title",
            summary="Test Summary",
            content="Test Content",
            source="Test Source",
            llama_score=60,
            llama_category="immigration",
            llama_reason="visa related",
        )

        assert "Test Title" in prompt
        assert "Test Summary" in prompt
        assert "Test Source" in prompt
        assert "60" in prompt
        assert "immigration" in prompt


class TestEdgeCases:
    """Test edge cases"""

    @pytest.mark.asyncio
    async def test_empty_title(self):
        """Handle empty title"""
        validator = ClaudeValidator()

        result = await validator.validate_article(
            title="",
            summary="Summary",
            content="Content",
            source="Source",
            llama_score=80,
            llama_category="general",
        )

        assert isinstance(result, ValidationResult)

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """Handle empty content"""
        validator = ClaudeValidator()

        result = await validator.validate_article(
            title="Title",
            summary="Summary",
            content="",
            source="Source",
            llama_score=85,
            llama_category="general",
        )

        assert isinstance(result, ValidationResult)

    @pytest.mark.asyncio
    async def test_boundary_40(self):
        """Score 40 goes to validation"""
        validator = ClaudeValidator()

        mock_response = json.dumps(
            {"approved": True, "confidence": 50, "reason": "Approved"}
        )

        with patch.object(validator, "_call_claude_cli", return_value=mock_response):
            result = await validator.validate_article(
                title="Test",
                summary="Summary",
                content="Content",
                source="Source",
                llama_score=40,
                llama_category="general",
            )

            assert isinstance(result, ValidationResult)

    @pytest.mark.asyncio
    async def test_boundary_74(self):
        """Score 74 goes to validation (not auto-approve)"""
        validator = ClaudeValidator()

        mock_response = json.dumps(
            {"approved": False, "confidence": 70, "reason": "Rejected"}
        )

        with patch.object(validator, "_call_claude_cli", return_value=mock_response):
            result = await validator.validate_article(
                title="Test",
                summary="Summary",
                content="Content",
                source="Source",
                llama_score=74,
                llama_category="general",
            )

            # 74 should go to Claude (not auto-approve at 75)
            assert result.approved is False


class TestGetStats:
    """Test statistics retrieval"""

    def test_initial_stats(self):
        """Initial stats are zero"""
        validator = ClaudeValidator()
        stats = validator.get_stats()

        assert stats["total_processed"] == 0
        assert stats["approval_rate"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_processing(self):
        """Stats update after processing"""
        validator = ClaudeValidator()

        # Auto approve
        await validator.validate_article(
            title="High",
            summary="S",
            content="C",
            source="S",
            llama_score=90,
            llama_category="general",
        )

        # Auto reject
        await validator.validate_article(
            title="Low",
            summary="S",
            content="C",
            source="S",
            llama_score=30,
            llama_category="general",
        )

        stats = validator.get_stats()

        assert stats["auto_approved"] == 1
        assert stats["auto_rejected"] == 1
        assert stats["total_processed"] == 2
        assert stats["approval_rate"] == 50.0


class TestCallClaudeCli:
    """Test _call_claude_cli method"""

    def test_successful_call(self):
        """Test successful Claude CLI call"""
        from unittest.mock import MagicMock

        validator = ClaudeValidator()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"approved": true, "confidence": 80}'

        with patch("subprocess.run", return_value=mock_result):
            response = validator._call_claude_cli("test prompt")

        assert response == '{"approved": true, "confidence": 80}'

    def test_error_return_code(self):
        """Test handling of non-zero return code"""
        from unittest.mock import MagicMock

        validator = ClaudeValidator()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error message"

        with patch("subprocess.run", return_value=mock_result):
            response = validator._call_claude_cli("test prompt")

        assert response is None

    def test_extract_json_from_markdown(self):
        """Test extracting JSON from markdown code block"""
        from unittest.mock import MagicMock

        validator = ClaudeValidator()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'Some text\n```json\n{"approved": true}\n```\nMore text'

        with patch("subprocess.run", return_value=mock_result):
            response = validator._call_claude_cli("test prompt")

        assert response == '{"approved": true}'

    def test_extract_json_from_plain_codeblock(self):
        """Test extracting JSON from plain code block"""
        from unittest.mock import MagicMock

        validator = ClaudeValidator()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'Text\n```\n{"approved": false}\n```'

        with patch("subprocess.run", return_value=mock_result):
            response = validator._call_claude_cli("test prompt")

        assert response == '{"approved": false}'

    def test_extract_bare_json(self):
        """Test extracting bare JSON"""
        from unittest.mock import MagicMock

        validator = ClaudeValidator()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'Here is the result: {"approved": true, "confidence": 90}'

        with patch("subprocess.run", return_value=mock_result):
            response = validator._call_claude_cli("test prompt")

        assert response == '{"approved": true, "confidence": 90}'

    def test_timeout_handling(self):
        """Test handling of timeout"""
        import subprocess

        validator = ClaudeValidator()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 120)):
            response = validator._call_claude_cli("test prompt")

        assert response is None

    def test_file_not_found(self):
        """Test handling of missing Claude CLI"""
        validator = ClaudeValidator()

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            response = validator._call_claude_cli("test prompt")

        assert response is None

    def test_generic_exception(self):
        """Test handling of generic exception"""
        validator = ClaudeValidator()

        with patch("subprocess.run", side_effect=Exception("Unknown error")):
            response = validator._call_claude_cli("test prompt")

        assert response is None


class TestValidateBatch:
    """Test validate_batch method"""

    @pytest.mark.asyncio
    async def test_validate_batch_empty(self):
        """Test empty batch"""
        validator = ClaudeValidator()

        results = await validator.validate_batch([])

        assert results == []

    @pytest.mark.asyncio
    async def test_validate_batch_single(self):
        """Test batch with single article"""
        validator = ClaudeValidator()

        articles = [
            {
                "title": "Test",
                "summary": "Summary",
                "content": "Content",
                "source": "Source",
                "relevance_score": 80,
                "category": "general",
            }
        ]

        results = await validator.validate_batch(articles)

        assert len(results) == 1
        assert results[0][0] == articles[0]
        assert isinstance(results[0][1], ValidationResult)
        assert results[0][1].approved is True  # High score auto-approved

    @pytest.mark.asyncio
    async def test_validate_batch_multiple(self):
        """Test batch with multiple articles"""
        validator = ClaudeValidator()

        articles = [
            {
                "title": "High",
                "summary": "S",
                "content": "C",
                "source": "S",
                "relevance_score": 90,
                "category": "general",
            },
            {
                "title": "Low",
                "summary": "S",
                "content": "C",
                "source": "S",
                "relevance_score": 30,
                "category": "general",
            },
        ]

        results = await validator.validate_batch(articles)

        assert len(results) == 2
        assert results[0][1].approved is True  # High score approved
        assert results[1][1].approved is False  # Low score rejected

    @pytest.mark.asyncio
    async def test_validate_batch_with_score_reason(self):
        """Test batch with score_reason field"""
        validator = ClaudeValidator()

        articles = [
            {
                "title": "Test",
                "summary": "Summary",
                "content": "Content",
                "source": "Source",
                "relevance_score": 85,
                "category": "immigration",
                "score_reason": "visa related",
            }
        ]

        results = await validator.validate_batch(articles)

        assert len(results) == 1
        assert results[0][1].approved is True

    @pytest.mark.asyncio
    async def test_validate_batch_missing_fields(self):
        """Test batch with missing optional fields"""
        validator = ClaudeValidator()

        articles = [{"title": "Test"}]

        results = await validator.validate_batch(articles)

        assert len(results) == 1
        # Should use defaults

    @pytest.mark.asyncio
    async def test_validate_batch_stats_updated(self):
        """Test that batch updates stats"""
        validator = ClaudeValidator()

        articles = [
            {
                "title": "High",
                "summary": "S",
                "content": "C",
                "source": "S",
                "relevance_score": 90,
                "category": "g",
            },
            {
                "title": "Also High",
                "summary": "S",
                "content": "C",
                "source": "S",
                "relevance_score": 80,
                "category": "g",
            },
        ]

        await validator.validate_batch(articles)

        assert validator.stats["auto_approved"] == 2


class TestTestValidator:
    """Test the test_validator function"""

    @pytest.mark.asyncio
    async def test_test_validator_runs(self):
        """Test that test_validator function runs"""
        from claude_validator import test_validator

        # Mock the validate_article to avoid actual Claude calls
        with patch.object(ClaudeValidator, "validate_article") as mock_validate:
            mock_validate.return_value = ValidationResult(
                approved=True, confidence=85, reason="Test"
            )

            # Should not raise
            await test_validator()


class TestValidationResultWithHints:
    """Test ValidationResult with enrichment hints"""

    def test_result_with_hints(self):
        """Test with enrichment hints"""
        result = ValidationResult(
            approved=True,
            confidence=85,
            reason="Good article",
            enrichment_hints=["Focus on timeline", "Check official sources"],
        )

        assert result.enrichment_hints == [
            "Focus on timeline",
            "Check official sources",
        ]

    def test_result_with_research_notes(self):
        """Test with research notes"""
        result = ValidationResult(
            approved=True,
            confidence=90,
            reason="Verified",
            research_notes="Confirmed by official government website",
        )

        assert result.research_notes == "Confirmed by official government website"


class TestPromptBuilding:
    """Additional prompt building tests"""

    def test_long_content_truncated(self):
        """Long content should be truncated in prompt"""
        validator = ClaudeValidator()

        long_content = "x" * 5000

        prompt = validator._build_validation_prompt(
            title="Title",
            summary="Summary",
            content=long_content,
            source="Source",
            llama_score=50,
            llama_category="general",
            llama_reason="reason",
        )

        # Content should be truncated - not all 5000 x's should appear in prompt
        # Count how many x's appear in a row (the content part)
        x_count = prompt.count("x")
        assert x_count < 5000, f"Content should be truncated but got {x_count} x's"

    def test_long_summary_truncated(self):
        """Long summary should be truncated in prompt"""
        validator = ClaudeValidator()

        long_summary = "y" * 1000

        prompt = validator._build_validation_prompt(
            title="Title",
            summary=long_summary,
            content="Content",
            source="Source",
            llama_score=50,
            llama_category="general",
            llama_reason="reason",
        )

        # Summary truncated to 500
        assert "yyyyyyyy" in prompt

    def test_empty_summary_handled(self):
        """Empty summary handled in prompt"""
        validator = ClaudeValidator()

        prompt = validator._build_validation_prompt(
            title="Title",
            summary="",
            content="Content",
            source="Source",
            llama_score=50,
            llama_category="general",
            llama_reason="",
        )

        assert "No summary" in prompt

    def test_empty_content_handled(self):
        """Empty content handled in prompt"""
        validator = ClaudeValidator()

        prompt = validator._build_validation_prompt(
            title="Title",
            summary="Summary",
            content="",
            source="Source",
            llama_score=50,
            llama_category="general",
            llama_reason="",
        )

        assert "No content" in prompt


class TestValidationStats:
    """Test validated approved/rejected stats"""

    @pytest.mark.asyncio
    async def test_validated_approved_stats(self):
        """Test validated approved increments stats"""
        validator = ClaudeValidator()

        mock_response = json.dumps(
            {"approved": True, "confidence": 80, "reason": "Good"}
        )

        with patch.object(validator, "_call_claude_cli", return_value=mock_response):
            await validator.validate_article(
                title="Test",
                summary="S",
                content="C",
                source="S",
                llama_score=55,
                llama_category="general",
            )

        assert validator.stats["validated_approved"] == 1

    @pytest.mark.asyncio
    async def test_validated_rejected_stats(self):
        """Test validated rejected increments stats"""
        validator = ClaudeValidator()

        mock_response = json.dumps(
            {"approved": False, "confidence": 80, "reason": "Not relevant"}
        )

        with patch.object(validator, "_call_claude_cli", return_value=mock_response):
            await validator.validate_article(
                title="Test",
                summary="S",
                content="C",
                source="S",
                llama_score=55,
                llama_category="general",
            )

        assert validator.stats["validated_rejected"] == 1

    @pytest.mark.asyncio
    async def test_validation_error_stats(self):
        """Test validation error increments stats"""
        validator = ClaudeValidator()

        with patch.object(validator, "_call_claude_cli", return_value=None):
            await validator.validate_article(
                title="Test",
                summary="S",
                content="C",
                source="S",
                llama_score=55,
                llama_category="general",
            )

        assert validator.stats["validation_errors"] == 1

    @pytest.mark.asyncio
    async def test_json_parse_error_stats(self):
        """Test JSON parse error increments stats"""
        validator = ClaudeValidator()

        with patch.object(validator, "_call_claude_cli", return_value="not json"):
            await validator.validate_article(
                title="Test",
                summary="S",
                content="C",
                source="S",
                llama_score=55,
                llama_category="general",
            )

        assert validator.stats["validation_errors"] == 1


class TestEnrichmentHintsFromAutoApprove:
    """Test enrichment hints from auto-approve"""

    @pytest.mark.asyncio
    async def test_auto_approve_includes_llama_reason_as_hint(self):
        """Auto-approve includes LLAMA reason as enrichment hint"""
        validator = ClaudeValidator()

        result = await validator.validate_article(
            title="KITAS Update",
            summary="New rules",
            content="Content",
            source="Gov",
            llama_score=85,
            llama_category="immigration",
            llama_reason="KITAS policy change announced",
        )

        assert result.enrichment_hints == ["KITAS policy change announced"]

    @pytest.mark.asyncio
    async def test_auto_approve_no_hint_without_reason(self):
        """Auto-approve without reason has no hints"""
        validator = ClaudeValidator()

        result = await validator.validate_article(
            title="KITAS Update",
            summary="New rules",
            content="Content",
            source="Gov",
            llama_score=85,
            llama_category="immigration",
        )

        assert result.enrichment_hints is None
