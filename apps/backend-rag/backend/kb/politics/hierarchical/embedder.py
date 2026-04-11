"""
Batched local embedding for politics KB hierarchical retrieval.

Uses sentence-transformers with paraphrase-multilingual-MiniLM-L12-v2 for
Indonesian/English support. Falls back to all-MiniLM-L6-v2 if the multilingual
model fails to load.

IMPORTANT: This module uses LOCAL embeddings only — no API keys required.
The embedding model is separate from the production text-embedding-3-small
(1536 dims) used in main RAG. The politics hierarchical collection uses
its own dimensionality.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from backend.kb.politics.hierarchical.chunker import Chunk

logger = logging.getLogger(__name__)

# Model priority: multilingual first, fallback to English-only
PREFERRED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
FALLBACK_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Batch size tuned for 4GB memory constraint on Air
DEFAULT_BATCH_SIZE = 64


class LocalEmbedder:
    """Batched local embeddings using sentence-transformers.

    Memory-conscious: processes in configurable batch sizes to stay
    within Air's 4GB available RAM.
    """

    def __init__(
        self,
        model_name: str | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        seed: int = 42,
    ) -> None:
        self._batch_size = batch_size
        self._seed = seed
        self._model_name = model_name or PREFERRED_MODEL
        self._model = None
        self._dimensions: int | None = None

    def _load_model(self) -> None:
        """Lazy-load the sentence-transformers model."""
        if self._model is not None:
            return

        from sentence_transformers import SentenceTransformer

        try:
            logger.info(f"Loading embedding model: {self._model_name}")
            self._model = SentenceTransformer(self._model_name)
            self._dimensions = self._model.get_sentence_embedding_dimension()
            logger.info(f"Loaded {self._model_name} ({self._dimensions} dims)")
        except Exception as e:
            logger.warning(f"Failed to load {self._model_name}: {e}")
            if self._model_name != FALLBACK_MODEL:
                logger.info(f"Falling back to {FALLBACK_MODEL}")
                self._model_name = FALLBACK_MODEL
                self._model = SentenceTransformer(FALLBACK_MODEL)
                self._dimensions = self._model.get_sentence_embedding_dimension()
                logger.info(f"Loaded fallback {FALLBACK_MODEL} ({self._dimensions} dims)")
            else:
                raise

    @property
    def dimensions(self) -> int:
        """Embedding dimensionality (lazy-loads model if needed)."""
        self._load_model()
        assert self._dimensions is not None
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts in batches.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors as lists of floats.
        """
        if not texts:
            return []

        self._load_model()
        assert self._model is not None

        # Set seed for determinism
        np.random.seed(self._seed)

        all_embeddings: list[list[float]] = []
        total = len(texts)
        start = time.perf_counter()

        for i in range(0, total, self._batch_size):
            batch = texts[i : i + self._batch_size]
            embeddings = self._model.encode(
                batch,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            all_embeddings.extend(embeddings.tolist())

            if total > self._batch_size:
                processed = min(i + self._batch_size, total)
                logger.debug(f"Embedded {processed}/{total} texts")

        elapsed = time.perf_counter() - start
        logger.info(f"Embedded {total} texts in {elapsed:.2f}s ({total / elapsed:.0f} texts/s)")
        return all_embeddings

    def embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]:
        """Embed a list of Chunk objects.

        Args:
            chunks: List of Chunk objects.

        Returns:
            List of embedding vectors, same order as input chunks.
        """
        texts = [c.text for c in chunks]
        return self.embed_texts(texts)

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string.

        Args:
            query: Search query text.

        Returns:
            Embedding vector as list of floats.
        """
        result = self.embed_texts([query])
        return result[0] if result else []
