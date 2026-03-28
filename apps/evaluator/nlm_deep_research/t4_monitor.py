"""T4 Social Media Monitor for NLM NB-2.

Fetches immigration-relevant content from:
  - RSS feeds (ngurahrai, ditjenimigrasi)
  - Government websites (/berita/ pages)
  - X/Twitter v2 API (time-boxed 30 days)

Applies a 3-layer relevance filter, computes SVS, and ingests
ADMIT articles into NLM NB-2 via the nlm CLI.
"""

from __future__ import annotations

import logging
import math
from enum import Enum
from typing import Optional


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NB2_ID = "cff93ab0-813a-42f2-a8de-36987e724271"
MAX_T4_SLOTS = 11
CB_T4_FAILURE_THRESHOLD = 3
CB_T4_RECOVERY_MINUTES = 30

CRITICAL_KEYWORDS = [
    "timpora",
    "deportasi",
    "deportation",
    "overstay",
    "blacklist",
    "daftar cekal",
    "visa dicabut",
    "wna ditangkap",
    "razia",
    "pendeportasian",
    "izin tinggal dibatalkan",
    "cegah tangkal",
]

HIGH_KEYWORDS = [
    "kitas",
    "kitap",
    "visa",
    "izin tinggal",
    "paspor",
    "imigrasi",
    "wna",
    "warga negara asing",
    "tenaga kerja asing",
    "tka",
    "peraturan imigrasi",
    "kebijakan visa",
    "perpanjangan visa",
]

REFERENCE_QUERY = (
    "Indonesian immigration enforcement TIMPORA deportation overstay "
    "WNA foreign nationals visa regulation Bali"
)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_SIMILARITY_THRESHOLD = 0.35
EMBEDDING_BORDERLINE_LOW = 0.30
EMBEDDING_BORDERLINE_HIGH = 0.40


# ---------------------------------------------------------------------------
# Enums / dataclasses
# ---------------------------------------------------------------------------


class FilterResult(str, Enum):
    ADMIT = "ADMIT"
    REJECT = "REJECT"
    BORDERLINE = "BORDERLINE"


# ---------------------------------------------------------------------------
# T4RelevanceFilter
# ---------------------------------------------------------------------------


class T4RelevanceFilter:
    """3-layer relevance filter for T4 immigration content.

    Layer 1 — keyword recall (~0ms, fast gate)
    Layer 2 — embedding cosine similarity (~50ms, precision gate)
    Layer 3 — Haiku LLM classifier (~500ms, borderline only)
    """

    def layer1_keywords(self, text: str) -> bool:
        """Return True if text passes keyword recall gate."""
        lower = text.lower()
        critical_hits = sum(1 for kw in CRITICAL_KEYWORDS if kw in lower)
        if critical_hits >= 1:
            return True
        high_hits = sum(1 for kw in HIGH_KEYWORDS if kw in lower)
        return high_hits >= 2

    async def _embed(self, text: str) -> list[float]:
        """Embed text using OpenAI text-embedding-3-small."""
        import openai  # noqa: PLC0415

        client = openai.AsyncOpenAI()
        resp = await client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        return resp.data[0].embedding

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def layer2_embedding(
        self, text: str, *, cached_ref: Optional[list[float]] = None
    ) -> float:
        """Return cosine similarity between text and reference query."""
        ref = cached_ref or await self._embed(REFERENCE_QUERY)
        text_vec = await self._embed(text)
        return self._cosine(text_vec, ref)

    async def _haiku_classify(self, text: str) -> float:
        """Call Haiku to score immigration relevance (0.0–1.0)."""
        import anthropic  # noqa: PLC0415

        client = anthropic.AsyncAnthropic()
        prompt = (
            "You are an immigration advisor for Bali, Indonesia. "
            "Score the following article's relevance to immigration enforcement "
            "(deportation, overstay, visa cancellation, arrests of foreign nationals). "
            "Respond with ONLY a decimal between 0.0 and 1.0. "
            "1.0 = highly relevant enforcement news. 0.0 = irrelevant.\n\n"
            f"Article: {text[:1500]}"
        )
        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        try:
            return float(raw)
        except ValueError:
            logger.warning("Haiku returned non-float: %r — defaulting to 0.0", raw)
            return 0.0

    async def layer3_haiku(self, text: str) -> float:
        """Return Haiku relevance score for text."""
        return await self._haiku_classify(text)

    async def classify(
        self,
        text: str,
        *,
        ref_embedding: Optional[list[float]] = None,
    ) -> FilterResult:
        """Run full 3-layer pipeline. Returns ADMIT, REJECT, or BORDERLINE."""
        if not self.layer1_keywords(text):
            return FilterResult.REJECT

        similarity = await self.layer2_embedding(text, cached_ref=ref_embedding)

        if similarity >= EMBEDDING_SIMILARITY_THRESHOLD:
            return FilterResult.ADMIT

        if EMBEDDING_BORDERLINE_LOW <= similarity < EMBEDDING_BORDERLINE_HIGH:
            score = await self.layer3_haiku(text)
            return FilterResult.ADMIT if score >= 0.5 else FilterResult.REJECT

        return FilterResult.REJECT
