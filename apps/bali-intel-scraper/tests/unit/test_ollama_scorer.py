"""
Unit Tests for Ollama Scorer
Tests for local LLM scoring with mocked HTTP calls
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from ollama_scorer import OllamaScorer


class TestOllamaScorerInit:
    """Test OllamaScorer initialization"""

    def test_default_init(self):
        """Test default initialization"""
        scorer = OllamaScorer()
        assert scorer.model == "llama3.2:3b"
        assert scorer.base_url == "http://localhost:11434"
        assert scorer.api_url == "http://localhost:11434/api/generate"

    def test_custom_init(self):
        """Test custom initialization"""
        scorer = OllamaScorer(model="llama3:8b", base_url="http://custom:1234")
        assert scorer.model == "llama3:8b"
        assert scorer.base_url == "http://custom:1234"
        assert scorer.api_url == "http://custom:1234/api/generate"


class TestScoreArticle:
    """Test article scoring"""

    @pytest.mark.asyncio
    async def test_score_article_success(self):
        """Test successful article scoring"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"score": 85, "reason": "visa policy critical"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article(
                "Indonesia Extends Digital Nomad Visa",
                "New 5-year visa for remote workers",
            )

            assert score == 85
            assert "visa" in reason.lower() or "critical" in reason.lower()

    @pytest.mark.asyncio
    async def test_score_article_with_json_in_text(self):
        """Test parsing JSON embedded in text response"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": 'Here is my analysis: {"score": 72, "reason": "tax update"} based on criteria.'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article("Tax News", "New regulations")

            assert score == 72
            assert reason == "tax update"

    @pytest.mark.asyncio
    async def test_score_article_timeout(self):
        """Test timeout handling"""
        import httpx

        scorer = OllamaScorer()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article("Test", "Test")

            assert score == 50  # Default fallback
            assert "failed" in reason.lower()

    @pytest.mark.asyncio
    async def test_score_article_invalid_json(self):
        """Test handling of invalid JSON response"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "This is not valid JSON at all"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article("Test", "Test")

            assert score == 50  # Default fallback

    @pytest.mark.asyncio
    async def test_score_article_api_error(self):
        """Test handling of API error"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article("Test", "Test")

            assert score == 50  # Default fallback

    @pytest.mark.asyncio
    async def test_score_article_truncates_summary(self):
        """Test that long summaries are truncated"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"score": 60, "reason": "test"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            long_summary = "x" * 500
            await scorer.score_article("Title", long_summary)

            # Verify the call was made (summary should be truncated internally)
            mock_instance.post.assert_called_once()


class TestHealthCheck:
    """Test health check functionality"""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3.2:3b"}, {"name": "other:model"}]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await scorer.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_model_not_found(self):
        """Test health check when model not found"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "other:model"}]}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await scorer.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self):
        """Test health check with connection error"""
        scorer = OllamaScorer()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = Exception("Connection refused")
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await scorer.health_check()

            assert result is False


class TestWarmUp:
    """Test model warm-up functionality"""

    @pytest.mark.asyncio
    async def test_warm_up_success(self):
        """Test successful warm-up"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"score": 50, "reason": "test warmup"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await scorer.warm_up()

            assert result is True

    @pytest.mark.asyncio
    async def test_warm_up_failure(self):
        """Test warm-up with zero score"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"score": 0, "reason": "failed"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await scorer.warm_up()

            assert result is False


class TestScoreArticleEdgeCases:
    """Test edge cases for article scoring"""

    @pytest.mark.asyncio
    async def test_score_article_empty_summary(self):
        """Test scoring with empty summary"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"score": 45, "reason": "limited info"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article("Title Only", "")

            assert score == 45
            mock_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_score_article_none_summary(self):
        """Test scoring with None summary"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"score": 40, "reason": "no summary"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article("Title", None)

            assert score == 40

    @pytest.mark.asyncio
    async def test_score_article_missing_score_field(self):
        """Test response missing score field"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"reason": "only reason, no score"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article("Test", "Test")

            # Should default to 50 when score missing
            assert score == 50

    @pytest.mark.asyncio
    async def test_score_article_missing_reason_field(self):
        """Test response missing reason field"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": '{"score": 80}'}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article("Test", "Test")

            assert score == 80
            assert reason == "scored"  # Default reason

    @pytest.mark.asyncio
    async def test_score_article_long_reason_truncated(self):
        """Test that long reasons are truncated to 50 chars"""
        scorer = OllamaScorer()

        long_reason = "This is a very long reason that exceeds fifty characters and should be truncated"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": f'{{"score": 75, "reason": "{long_reason}"}}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article("Test", "Test")

            assert score == 75
            assert len(reason) <= 50

    @pytest.mark.asyncio
    async def test_score_article_json_decode_error(self):
        """Test handling of malformed JSON"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"score": 80, "reason": broken json'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article("Test", "Test")

            # Should fallback to default on JSON error
            assert score == 50
            assert "failed" in reason.lower()

    @pytest.mark.asyncio
    async def test_score_article_generic_exception(self):
        """Test handling of generic exceptions"""
        scorer = OllamaScorer()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = RuntimeError("Unexpected error")
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article("Test", "Test")

            assert score == 50
            assert "failed" in reason.lower()

    @pytest.mark.asyncio
    async def test_score_article_empty_response(self):
        """Test handling of empty response"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": ""}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article("Test", "Test")

            assert score == 50

    @pytest.mark.asyncio
    async def test_score_article_no_json_braces(self):
        """Test response without JSON braces"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Score is 85 because its about visas"
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            score, reason = await scorer.score_article("Test", "Test")

            # No JSON found, should fallback
            assert score == 50


class TestHealthCheckEdgeCases:
    """Test edge cases for health check"""

    @pytest.mark.asyncio
    async def test_health_check_empty_models_list(self):
        """Test health check with empty models list"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await scorer.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_partial_model_match(self):
        """Test health check with partial model name match"""
        scorer = OllamaScorer(model="llama3.2:3b")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3.2:3b-instruct"}]  # Contains the model name
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await scorer.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_api_error(self):
        """Test health check with non-200 response"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await scorer.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_missing_name_key(self):
        """Test health check with models missing name key"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"version": "1.0"}]  # No name key
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await scorer.health_check()

            assert result is False


class TestPromptConstruction:
    """Test that prompts are constructed correctly"""

    @pytest.mark.asyncio
    async def test_prompt_includes_title_and_summary(self):
        """Verify prompt includes title and summary"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"score": 75, "reason": "test"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            await scorer.score_article("Visa Update", "New immigration policy")

            # Check the call args
            call_args = mock_instance.post.call_args
            json_body = call_args.kwargs.get("json", call_args[1].get("json", {}))
            prompt = json_body.get("prompt", "")

            assert "Visa Update" in prompt
            assert "New immigration policy" in prompt

    @pytest.mark.asyncio
    async def test_prompt_uses_correct_model(self):
        """Verify correct model is used in request"""
        scorer = OllamaScorer(model="custom:model")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"score": 50, "reason": "test"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            await scorer.score_article("Test", "Test")

            call_args = mock_instance.post.call_args
            json_body = call_args.kwargs.get("json", call_args[1].get("json", {}))

            assert json_body.get("model") == "custom:model"

    @pytest.mark.asyncio
    async def test_prompt_options_low_temperature(self):
        """Verify low temperature is set for consistent scoring"""
        scorer = OllamaScorer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"score": 50, "reason": "test"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            await scorer.score_article("Test", "Test")

            call_args = mock_instance.post.call_args
            json_body = call_args.kwargs.get("json", call_args[1].get("json", {}))
            options = json_body.get("options", {})

            assert options.get("temperature") == 0.1


class TestTestScorerFunction:
    """Test the test_scorer standalone function"""

    @pytest.mark.asyncio
    async def test_test_scorer_ollama_not_available(self, capsys):
        """Test test_scorer when Ollama is not available"""
        from ollama_scorer import test_scorer

        with patch("ollama_scorer.OllamaScorer") as MockScorer:
            mock_instance = MagicMock()
            mock_instance.health_check = AsyncMock(return_value=False)
            MockScorer.return_value = mock_instance

            await test_scorer()

            captured = capsys.readouterr()
            assert (
                "not running" in captured.out.lower()
                or "not found" in captured.out.lower()
            )

    @pytest.mark.asyncio
    async def test_test_scorer_full_flow(self, capsys):
        """Test test_scorer with mocked full flow"""
        from ollama_scorer import test_scorer

        with patch("ollama_scorer.OllamaScorer") as MockScorer:
            mock_instance = MagicMock()
            mock_instance.health_check = AsyncMock(return_value=True)
            mock_instance.warm_up = AsyncMock(return_value=True)
            mock_instance.score_article = AsyncMock(return_value=(85, "visa policy"))
            MockScorer.return_value = mock_instance

            await test_scorer()

            captured = capsys.readouterr()
            assert "ready" in captured.out.lower() or "warming" in captured.out.lower()
