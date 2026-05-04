"""Tests for scorer keyword fast-path (PR #450)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from mata_garuda.workers.scorer import classify_by_keyword, score_with_ollama


class TestKeywordClassifier:
    """7 patterns, ordered by recall."""

    def test_arxiv_to_ai_research(self):
        result = classify_by_keyword("arXiv 2604.07350: Fast Spatial Memory", "preprint")
        assert result is not None
        assert result["topic"] == "ai_research"
        assert result["score"] == 2

    def test_huggingface_to_ai_research(self):
        result = classify_by_keyword("Hugging Face transformers update", "blog")
        assert result is not None
        assert result["topic"] == "ai_research"

    def test_visa_to_immigration(self):
        result = classify_by_keyword("Indonesia Visa Update 2026", "imigrasi.go.id")
        assert result is not None
        assert result["topic"] == "immigration_visa"
        assert result["score"] == 4

    def test_kitas_to_immigration(self):
        result = classify_by_keyword("KITAS extension procedure", "expat news")
        assert result is not None
        assert result["topic"] == "immigration_visa"

    def test_pajak_to_tax(self):
        result = classify_by_keyword("Pajak Tahunan PPh Badan", "DJP")
        assert result is not None
        assert result["topic"] == "tax_fiscal"
        assert result["score"] == 4

    def test_spt_to_tax(self):
        result = classify_by_keyword("SPT extension 2026", "Coretax")
        assert result is not None
        assert result["topic"] == "tax_fiscal"

    def test_pt_pma_to_investment(self):
        result = classify_by_keyword("PT PMA setup with OSS-RBA", "BKPM guide")
        assert result is not None
        assert result["topic"] == "investment_licensing"

    def test_kbli_to_investment(self):
        result = classify_by_keyword("KBLI 47 retail trade classification", "BKPM")
        assert result is not None
        assert result["topic"] == "investment_licensing"

    def test_villa_to_property(self):
        result = classify_by_keyword("Villa SHGB Hak Pakai foreign ownership", "real estate")
        assert result is not None
        assert result["topic"] == "property"

    def test_pbg_to_property(self):
        result = classify_by_keyword("PBG submission via SIMBG", "DPMPTSP")
        assert result is not None
        assert result["topic"] == "property"

    def test_canggu_to_provincial_bali(self):
        result = classify_by_keyword("Canggu beachfront development restrictions", "Bali news")
        assert result is not None
        assert result["topic"] == "provincial_bali"

    def test_peraturan_to_political_risk(self):
        result = classify_by_keyword("Peraturan Presiden 47/2026", "menteri")
        assert result is not None
        assert result["topic"] == "political_risk"

    def test_unmatched_returns_none(self):
        """Items off-topic for Bali Zero fall through to LLM."""
        result = classify_by_keyword("Cooking pasta in Sicily", "lifestyle blog")
        assert result is None

    def test_environmental_falls_through(self):
        """Environmental items not in pattern list — fall through."""
        result = classify_by_keyword("Climate change effects on coral reefs", "NOAA")
        assert result is None

    def test_pattern_order_ai_research_first(self):
        """ai_research pattern is intentionally first because most arxiv
        items contain Bali-irrelevant terms that would otherwise hit nothing."""
        result = classify_by_keyword(
            "Neural network paper on transformer LLMs",
            "preprint",
        )
        assert result is not None
        assert result["topic"] == "ai_research"


class TestScoreWithOllamaFastPath:
    """Verify fast-path bypasses the Ollama subprocess."""

    def test_fast_path_skips_ollama(self):
        """When keyword matches, subprocess.run should NOT be called."""
        with patch("mata_garuda.workers.scorer.subprocess.run") as m_run:
            result = score_with_ollama("Indonesia Visa Update", "news", "imigrasi.go.id")
        assert result["topic"] == "immigration_visa"
        # Ollama subprocess never invoked
        m_run.assert_not_called()

    def test_fall_through_calls_ollama(self):
        """Off-topic items DO reach the Ollama subprocess."""
        # Mock subprocess to return a valid-looking response
        import subprocess as _sp
        mock_result = _sp.CompletedProcess(
            args=[], returncode=0,
            stdout='{"response": "{\\"score\\": 2, \\"topic\\": \\"environmental\\", \\"reason\\": \\"climate\\"}"}',
            stderr="",
        )
        with patch("mata_garuda.workers.scorer.subprocess.run", return_value=mock_result) as m_run:
            result = score_with_ollama("Climate change coral reefs", "NOAA", "noaa.gov")
        # Ollama WAS called
        m_run.assert_called_once()
        # Topic from Ollama parsed
        assert result["topic"] == "environmental"

    def test_ollama_timeout_returns_other_fallback(self):
        """When Ollama times out for a fall-through item, default fallback."""
        import subprocess as _sp
        with patch("mata_garuda.workers.scorer.subprocess.run",
                   side_effect=_sp.TimeoutExpired(cmd="curl", timeout=60)):
            result = score_with_ollama("Random off-topic article", "blog", "random.com")
        assert result["topic"] == "other"
        assert result["score"] == 2
