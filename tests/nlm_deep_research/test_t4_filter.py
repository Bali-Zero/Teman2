"""Unit tests for T4 3-layer relevance filter."""
from __future__ import annotations

import math
from unittest.mock import AsyncMock, patch

import pytest

from apps.evaluator.nlm_deep_research.t4_monitor import (
    FilterResult,
    T4RelevanceFilter,
)


TIMPORA_TEXT = (
    "Timpora Kuta Selatan Tingkatkan Sinergitas dan Perkuat Pengawasan WNA. "
    "Imigrasi Ngurah Rai melakukan razia terhadap warga negara asing yang overstay."
)

DEPORTATION_TEXT = (
    "Imigrasi Ngurah Rai Deportasi WN Korea Selatan yang terbukti melanggar "
    "izin tinggal. Proses pendeportasian dilakukan sesuai prosedur imigrasi."
)

CEREMONY_TEXT = (
    "Selamat ulang tahun Direktorat Jenderal Imigrasi ke-73. "
    "Acara dihadiri oleh seluruh staf dan pegawai kantor imigrasi Denpasar."
)

GENERIC_SINGLE_HIGH_TEXT = (
    "Pengumuman jadwal libur nasional untuk kantor imigrasi seluruh Indonesia."
)


class TestLayer1KeywordFilter:
    """Layer 1: keyword recall pass/fail."""

    def test_critical_keyword_timpora_passes(self):
        f = T4RelevanceFilter()
        result = f.layer1_keywords(TIMPORA_TEXT)
        assert result is True

    def test_critical_keyword_deportasi_passes(self):
        f = T4RelevanceFilter()
        result = f.layer1_keywords(DEPORTATION_TEXT)
        assert result is True

    def test_two_high_keywords_pass(self):
        f = T4RelevanceFilter()
        text = "Peraturan imigrasi baru mengatur perpanjangan visa KITAS untuk TKA."
        result = f.layer1_keywords(text)
        assert result is True

    def test_single_high_keyword_fails(self):
        f = T4RelevanceFilter()
        result = f.layer1_keywords(GENERIC_SINGLE_HIGH_TEXT)
        assert result is False

    def test_ceremony_text_fails(self):
        f = T4RelevanceFilter()
        result = f.layer1_keywords(CEREMONY_TEXT)
        assert result is False

    def test_empty_text_fails(self):
        f = T4RelevanceFilter()
        result = f.layer1_keywords("")
        assert result is False

    def test_case_insensitive(self):
        f = T4RelevanceFilter()
        result = f.layer1_keywords("TIMPORA DAN DEPORTASI WNA")
        assert result is True


class TestLayer2EmbeddingFilter:
    """Layer 2: embedding cosine similarity (mocked)."""

    @pytest.mark.asyncio
    async def test_high_similarity_passes(self):
        f = T4RelevanceFilter()
        with patch.object(f, "_embed", new=AsyncMock(return_value=[0.9] * 1536)):
            result = await f.layer2_embedding(TIMPORA_TEXT, cached_ref=[0.9] * 1536)
        assert result >= 0.35

    @pytest.mark.asyncio
    async def test_low_similarity_fails(self):
        f = T4RelevanceFilter()
        ref = [1.0] + [0.0] * 1535
        text_vec = [0.0] * 1535 + [1.0]
        with patch.object(f, "_embed", new=AsyncMock(return_value=text_vec)):
            result = await f.layer2_embedding(CEREMONY_TEXT, cached_ref=ref)
        assert result < 0.35

    @pytest.mark.asyncio
    async def test_borderline_returns_float(self):
        f = T4RelevanceFilter()
        vec = [0.5] * 1536
        with patch.object(f, "_embed", new=AsyncMock(return_value=vec)):
            result = await f.layer2_embedding("some text", cached_ref=vec)
        assert isinstance(result, float)


class TestLayer3HaikuFilter:
    """Layer 3: Haiku classifier for borderline cases."""

    @pytest.mark.asyncio
    async def test_enforcement_article_scores_high(self):
        f = T4RelevanceFilter()
        with patch.object(
            f, "_haiku_classify", new=AsyncMock(return_value=0.85)
        ):
            score = await f.layer3_haiku(DEPORTATION_TEXT)
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_ceremony_article_scores_low(self):
        f = T4RelevanceFilter()
        with patch.object(
            f, "_haiku_classify", new=AsyncMock(return_value=0.15)
        ):
            score = await f.layer3_haiku(CEREMONY_TEXT)
        assert score < 0.5


class TestFilterPipeline:
    """Full 3-layer pipeline integration."""

    @pytest.mark.asyncio
    async def test_critical_text_returns_admit_no_haiku(self):
        f = T4RelevanceFilter()
        high_sim = [0.9] * 1536
        with patch.object(f, "_embed", new=AsyncMock(return_value=high_sim)):
            result = await f.classify(TIMPORA_TEXT, ref_embedding=high_sim)
        assert result == FilterResult.ADMIT

    @pytest.mark.asyncio
    async def test_ceremony_text_returns_reject(self):
        f = T4RelevanceFilter()
        orth_vec = [0.0] * 1536
        orth_vec[0] = 1.0
        ref_vec = [0.0] * 1536
        ref_vec[1] = 1.0
        with patch.object(f, "_embed", new=AsyncMock(return_value=orth_vec)):
            result = await f.classify(CEREMONY_TEXT, ref_embedding=ref_vec)
        assert result == FilterResult.REJECT

    @pytest.mark.asyncio
    async def test_borderline_similarity_invokes_layer3_admit(self):
        f = T4RelevanceFilter()
        # L1: passes (timpora keyword)
        # L2: borderline (0.33 — between 0.30 and 0.40)
        # L3: scores 0.8 → ADMIT
        borderline_vec_a = [0.0] * 1536
        borderline_vec_a[0] = 1.0
        borderline_vec_b = [0.0] * 1536
        borderline_vec_b[0] = 0.33  # cosine similarity ≈ 0.33 after normalization
        borderline_vec_b[1] = math.sqrt(1 - 0.33**2)

        with patch.object(f, "_embed", new=AsyncMock(return_value=borderline_vec_b)):
            with patch.object(f, "_haiku_classify", new=AsyncMock(return_value=0.8)):
                result = await f.classify(
                    "Timpora razia WNA overstay", ref_embedding=borderline_vec_a
                )
        assert result == FilterResult.ADMIT

    @pytest.mark.asyncio
    async def test_borderline_similarity_invokes_layer3_reject(self):
        f = T4RelevanceFilter()
        borderline_vec_a = [0.0] * 1536
        borderline_vec_a[0] = 1.0
        borderline_vec_b = [0.0] * 1536
        borderline_vec_b[0] = 0.33
        borderline_vec_b[1] = math.sqrt(1 - 0.33**2)

        with patch.object(f, "_embed", new=AsyncMock(return_value=borderline_vec_b)):
            with patch.object(f, "_haiku_classify", new=AsyncMock(return_value=0.3)):
                result = await f.classify(
                    "Timpora razia WNA overstay", ref_embedding=borderline_vec_a
                )
        assert result == FilterResult.REJECT
