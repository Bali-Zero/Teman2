"""
Batched local embedding for politics KB hierarchical retrieval.

Dense: sentence-transformers paraphrase-multilingual-MiniLM-L12-v2 (384 dims).
Sparse: BM25-style term frequencies for exact keyword matching on dates, names,
abbreviations. No external dependency — uses Python stdlib only.

IMPORTANT: This module uses LOCAL embeddings only — no API keys required.
"""

from __future__ import annotations

import logging
import math
import re
import time
from collections import Counter
from typing import TYPE_CHECKING, Any

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


# ─── BM25 Sparse Encoder ───────────────────────────────────────────────────


# Indonesian stopwords (common function words that add noise)
_ID_STOPWORDS = frozenset([
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan", "untuk",
    "pada", "adalah", "akan", "juga", "atau", "tidak", "oleh", "sudah",
    "ada", "dalam", "telah", "seorang", "sebuah", "sebagai", "dapat",
    "secara", "mereka", "kami", "kita", "saya", "ia", "dia", "nya",
    "hal", "atas", "bawah", "lain", "masih", "belum", "hanya",
    "the", "a", "an", "is", "of", "in", "to", "and", "for", "was",
    "with", "on", "as", "by", "at", "from", "this", "that",
])

# Regex: split on non-alphanumeric, keep Indonesian chars
_TOKENIZE_RE = re.compile(r"[a-zA-Z0-9\u00C0-\u024F]+")


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase terms, filtering stopwords."""
    tokens = _TOKENIZE_RE.findall(text.lower())
    return [t for t in tokens if t not in _ID_STOPWORDS and len(t) > 1]


class BM25SparseEncoder:
    """BM25-style sparse vector encoder for exact keyword matching.

    Builds IDF from corpus, then encodes documents/queries as sparse vectors
    with BM25 term weights. Uses a deterministic term→index mapping.

    No external dependencies — pure Python with stdlib only.
    """

    # BM25 parameters
    k1: float = 1.2
    b: float = 0.75

    def __init__(self) -> None:
        self._vocab: dict[str, int] = {}  # term → index
        self._idf: dict[str, float] = {}  # term → IDF weight
        self._avg_dl: float = 0.0
        self._fitted = False

    def fit(self, texts: list[str]) -> None:
        """Build vocabulary and IDF from corpus.

        Args:
            texts: All documents in the collection (for IDF computation).
        """
        n = len(texts)
        if n == 0:
            return

        df: Counter[str] = Counter()  # document frequency per term
        total_len = 0

        for text in texts:
            tokens = _tokenize(text)
            total_len += len(tokens)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                df[token] += 1

        self._avg_dl = total_len / n

        # Build vocab (sorted for determinism)
        self._vocab = {term: idx for idx, term in enumerate(sorted(df.keys()))}

        # BM25 IDF: log((N - df + 0.5) / (df + 0.5) + 1)
        for term, freq in df.items():
            self._idf[term] = math.log((n - freq + 0.5) / (freq + 0.5) + 1)

        self._fitted = True
        logger.info(f"BM25 fitted: {len(self._vocab)} terms, avg_dl={self._avg_dl:.1f}")

    @property
    def vocab_size(self) -> int:
        return len(self._vocab)

    def encode_document(self, text: str) -> dict[str, Any]:
        """Encode a document as a sparse vector with BM25 term weights.

        Returns:
            Dict with 'indices' and 'values' for Qdrant sparse vector format.
        """
        if not self._fitted:
            return {"indices": [], "values": []}

        tokens = _tokenize(text)
        dl = len(tokens)
        tf = Counter(tokens)

        indices: list[int] = []
        values: list[float] = []

        for term, count in tf.items():
            if term not in self._vocab:
                continue
            idf = self._idf.get(term, 0.0)
            # BM25 TF component
            tf_score = (count * (self.k1 + 1)) / (count + self.k1 * (1 - self.b + self.b * dl / self._avg_dl))
            weight = idf * tf_score
            if weight > 0:
                indices.append(self._vocab[term])
                values.append(round(weight, 6))

        return {"indices": indices, "values": values}

    def encode_query(self, query: str) -> dict[str, Any]:
        """Encode a query as a sparse vector.

        For queries, TF is binary (present or not) — standard BM25 query encoding.
        """
        if not self._fitted:
            return {"indices": [], "values": []}

        tokens = set(_tokenize(query))
        indices: list[int] = []
        values: list[float] = []

        for term in tokens:
            if term not in self._vocab:
                continue
            idf = self._idf.get(term, 0.0)
            if idf > 0:
                indices.append(self._vocab[term])
                values.append(round(idf, 6))

        return {"indices": indices, "values": values}

    def encode_documents(self, texts: list[str]) -> list[dict[str, Any]]:
        """Encode multiple documents as sparse vectors."""
        return [self.encode_document(t) for t in texts]
