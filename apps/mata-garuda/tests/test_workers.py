"""Tests for Layer 2 workers — normalizer and scorer."""
import pytest
from unittest.mock import patch, MagicMock


class TestNormalizer:
    def test_normalize_item(self):
        from mata_garuda.workers.normalizer import normalize_item

        raw = {
            "title": "  New PMK Regulation  ",
            "content": "Details about PMK",
            "url": "https://peraturan.go.id/123",
            "source": "peraturan.go.id",
            "agent": "regulation_watcher",
        }
        result = normalize_item(raw)
        assert result["title"] == "New PMK Regulation"
        assert result["content"] == "Details about PMK"
        assert result["source"] == "peraturan.go.id"
        assert len(result["content_hash"]) == 16
        assert "normalized_at" in result

    def test_content_hash_deterministic(self):
        from mata_garuda.workers.base_worker import content_hash

        h1 = content_hash("test content")
        h2 = content_hash("test content")
        h3 = content_hash("different content")
        assert h1 == h2
        assert h1 != h3

    def test_is_duplicate_check(self, tmp_path):
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.workers.normalizer import is_duplicate

        kb = KnowledgeBase(db_path=tmp_path / "test.db")
        assert is_duplicate(kb, "abc123") is False

        kb.store("normalizer", "hash", "abc123", "url", 1.0)
        assert is_duplicate(kb, "abc123") is True
        kb.close()


class TestScorer:
    def test_score_prompt_has_required_fields(self):
        from mata_garuda.workers.scorer import SCORE_PROMPT_TEMPLATE

        prompt = SCORE_PROMPT_TEMPLATE.format(
            title="Test", content="Content", source="src"
        )
        assert "Score 1-5" in prompt
        assert "immigration_visa" in prompt
        assert "JSON" in prompt

    @patch("mata_garuda.workers.scorer.subprocess.run")
    def test_score_with_ollama_fallback(self, mock_run):
        from mata_garuda.workers.scorer import score_with_ollama

        mock_run.side_effect = Exception("Ollama not running")
        result = score_with_ollama("title", "content", "source")
        assert result["score"] == 2
        assert result["topic"] == "other"

    @patch("mata_garuda.workers.scorer.subprocess.run")
    def test_score_with_ollama_success(self, mock_run):
        from mata_garuda.workers.scorer import score_with_ollama
        import json

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "response": '{"score": 4, "topic": "tax_fiscal", "reason": "New tax regulation"}'
            }),
        )
        result = score_with_ollama("PMK 25/2025", "New tax brackets", "ddtc.co.id")
        assert result["score"] == 4
        assert result["topic"] == "tax_fiscal"


class TestBaseWorker:
    def test_content_hash(self):
        from mata_garuda.workers.base_worker import content_hash

        h = content_hash("test")
        assert isinstance(h, str)
        assert len(h) == 16

    def test_stream_publish_format(self):
        from mata_garuda.workers.base_worker import stream_publish

        with patch("mata_garuda.workers.base_worker.redis_cmd") as mock:
            mock.return_value = "1234567890-0"
            result = stream_publish("test:stream", {"key": "value"})
            mock.assert_called_once()
            assert result == "1234567890-0"


class TestConfig:
    def test_streams_defined(self):
        from mata_garuda.config import (
            STREAM_RAW, STREAM_ENRICHED, STREAM_ALERTS,
            STREAM_DIGEST, STREAM_OSINT, STREAM_FEEDBACK,
        )
        assert STREAM_RAW == "garuda:raw"
        assert STREAM_ENRICHED == "garuda:enriched"
        assert STREAM_ALERTS == "garuda:alerts"

    def test_relevance_weights(self):
        from mata_garuda.config import RELEVANCE_WEIGHTS

        assert RELEVANCE_WEIGHTS["immigration_visa"] == 5
        assert RELEVANCE_WEIGHTS["ai_research"] == 4

    def test_tg_config(self):
        from mata_garuda.config import TG_ZERO_CHAT_ID

        assert TG_ZERO_CHAT_ID == "1125336968"

    def test_ai_sources_configured(self):
        from mata_garuda.config import AI_YOUTUBE_CHANNELS, ARXIV_CATEGORIES, AI_RSS_FEEDS

        assert len(AI_YOUTUBE_CHANNELS) >= 5
        assert "cs.AI" in ARXIV_CATEGORIES
        assert len(AI_RSS_FEEDS) >= 4
        assert any("huggingface" in f for f in AI_RSS_FEEDS)
