"""
NUZANTARA RAG - BM25 Sparse Vectorizer
Generates BM25 sparse vectors for hybrid search with Qdrant.
Uses hash-based token IDs for vocabulary-free operation.
"""

import logging
import math
import re
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)

# Indonesian stopwords (common words to filter out)
INDONESIAN_STOPWORDS = {
    "dan", "di", "ke", "dari", "yang", "untuk", "pada", "dengan", "ini", "itu",
    "adalah", "atau", "juga", "tidak", "akan", "telah", "sudah", "dapat", "bisa",
    "ada", "serta", "oleh", "sebagai", "dalam", "tersebut", "bahwa", "antara",
    "kepada", "karena", "secara", "melalui", "tentang", "atas", "bagi", "seperti",
    "namun", "tetapi", "sedangkan", "maupun", "baik", "sesuai", "berdasarkan",
    "terhadap", "hingga", "sampai", "sejak", "selama", "setelah", "sebelum",
    "apabila", "jika", "bila", "maka", "yaitu", "yakni", "dimana", "sehingga",
    "walaupun", "meskipun", "agar", "supaya", "tanpa", "hanya", "saja", "pun",
    "lain", "sama", "hal", "cara", "pihak", "masa", "waktu", "saat", "kali",
    # Common legal terms that appear everywhere
    "pasal", "ayat", "huruf", "angka", "butir", "nomor", "tahun", "tentang",
    "peraturan", "undang", "pemerintah", "menteri", "presiden", "republik",
    "indonesia", "negara", "daerah", "pusat", "provinsi", "kabupaten", "kota",
}


class BM25Vectorizer:
    """
    BM25 Sparse Vectorizer for Qdrant hybrid search.

    Uses hash-based token IDs to avoid vocabulary management.
    Implements BM25 scoring with configurable parameters.
    """

    def __init__(
        self,
        vocab_size: int = 30000,
        k1: float = 1.5,
        b: float = 0.75,
        min_token_length: int = 2,
        max_token_length: int = 50,
    ):
        """
        Initialize BM25 Vectorizer.

        Args:
            vocab_size: Size of hash space for token IDs (default 30000)
            k1: BM25 term frequency saturation parameter (default 1.5)
            b: BM25 document length normalization parameter (default 0.75)
            min_token_length: Minimum token length to include (default 2)
            max_token_length: Maximum token length to include (default 50)
        """
        self.vocab_size = vocab_size
        self.k1 = k1
        self.b = b
        self.min_token_length = min_token_length
        self.max_token_length = max_token_length
        self.avg_doc_length = 500  # Default average, can be updated

        logger.info(
            f"BM25Vectorizer initialized: vocab_size={vocab_size}, k1={k1}, b={b}"
        )

    def tokenize(self, text: str) -> list[str]:
        """
        Tokenize text for BM25 processing.

        - Lowercases text
        - Removes punctuation except hyphens in words
        - Splits on whitespace
        - Filters stopwords and short tokens
        - Handles Indonesian legal document patterns

        Args:
            text: Input text to tokenize

        Returns:
            List of tokens
        """
        if not text:
            return []

        # Lowercase
        text = text.lower()

        # Preserve important patterns before cleaning
        # Keep KBLI codes, legal references intact
        text = re.sub(r'kbli\s*(\d+)', r'kbli_\1', text)  # KBLI 56101 -> kbli_56101
        text = re.sub(r'uu\s*no\.?\s*(\d+)', r'uu_\1', text)  # UU No. 6 -> uu_6
        text = re.sub(r'pp\s*no\.?\s*(\d+)', r'pp_\1', text)  # PP No. 28 -> pp_28

        # Remove punctuation except underscores (preserving our patterns)
        text = re.sub(r'[^\w\s_]', ' ', text)

        # Split on whitespace
        tokens = text.split()

        # Filter tokens
        filtered_tokens = []
        for token in tokens:
            # Skip stopwords
            if token in INDONESIAN_STOPWORDS:
                continue
            # Skip too short or too long tokens
            if len(token) < self.min_token_length:
                continue
            if len(token) > self.max_token_length:
                continue
            # Skip pure numbers (unless they're part of codes)
            if token.isdigit() and len(token) < 4:
                continue
            filtered_tokens.append(token)

        return filtered_tokens

    def _hash_token(self, token: str) -> int:
        """
        Hash token to vocabulary index.

        Uses Python's built-in hash with modulo to map to vocab space.
        This avoids needing to maintain a vocabulary file.

        Args:
            token: Token string

        Returns:
            Integer index in [0, vocab_size)
        """
        # Use built-in hash, make it positive, and mod by vocab size
        return abs(hash(token)) % self.vocab_size

    def _calculate_tf(self, token_count: int, doc_length: int) -> float:
        """
        Calculate BM25 term frequency component.

        TF = (token_count * (k1 + 1)) / (token_count + k1 * (1 - b + b * dl/avgdl))

        Args:
            token_count: Number of times token appears in document
            doc_length: Total number of tokens in document

        Returns:
            BM25 TF score
        """
        numerator = token_count * (self.k1 + 1)
        denominator = token_count + self.k1 * (
            1 - self.b + self.b * (doc_length / self.avg_doc_length)
        )
        return numerator / denominator if denominator > 0 else 0.0

    def generate_sparse_vector(self, text: str) -> dict[str, Any]:
        """
        Generate BM25 sparse vector for Qdrant.

        Returns a sparse vector in Qdrant format:
        {"indices": [int], "values": [float]}

        Args:
            text: Input text to vectorize

        Returns:
            Dict with 'indices' (token IDs) and 'values' (BM25 scores)
        """
        tokens = self.tokenize(text)

        if not tokens:
            return {"indices": [], "values": []}

        # Count token frequencies
        token_counts = Counter(tokens)
        doc_length = len(tokens)

        # Calculate BM25 scores for each unique token
        # Use dict to handle hash collisions by summing scores
        index_scores: dict[int, float] = {}

        for token, count in token_counts.items():
            token_id = self._hash_token(token)
            tf_score = self._calculate_tf(count, doc_length)

            # Only include tokens with positive scores
            if tf_score > 0:
                # Sum scores for same index (hash collision handling)
                if token_id in index_scores:
                    index_scores[token_id] += tf_score
                else:
                    index_scores[token_id] = tf_score

        # Sort by index for consistency and ensure unique indices
        sorted_items = sorted(index_scores.items(), key=lambda x: x[0])
        indices = [item[0] for item in sorted_items]
        values = [round(item[1], 4) for item in sorted_items]

        return {"indices": indices, "values": values}

    def generate_query_sparse_vector(self, query: str) -> dict[str, Any]:
        """
        Generate sparse vector for a search query.

        Queries are treated differently - we use simpler TF without length normalization
        since queries are typically short.

        Args:
            query: Search query text

        Returns:
            Dict with 'indices' (token IDs) and 'values' (scores)
        """
        tokens = self.tokenize(query)

        if not tokens:
            return {"indices": [], "values": []}

        # For queries, use simple term frequency (no length normalization)
        token_counts = Counter(tokens)

        # Use dict to handle hash collisions by summing scores
        index_scores: dict[int, float] = {}

        for token, count in token_counts.items():
            token_id = self._hash_token(token)
            # Simple TF for queries: log(1 + count) to dampen repeated terms
            score = math.log(1 + count)
            # Sum scores for same index (hash collision handling)
            if token_id in index_scores:
                index_scores[token_id] += score
            else:
                index_scores[token_id] = score

        # Sort by index for consistency and ensure unique indices
        sorted_items = sorted(index_scores.items(), key=lambda x: x[0])
        indices = [item[0] for item in sorted_items]
        values = [round(item[1], 4) for item in sorted_items]

        return {"indices": indices, "values": values}

    def generate_batch_sparse_vectors(
        self, texts: list[str]
    ) -> list[dict[str, Any]]:
        """
        Generate sparse vectors for a batch of texts.

        Args:
            texts: List of texts to vectorize

        Returns:
            List of sparse vector dicts
        """
        return [self.generate_sparse_vector(text) for text in texts]

    def update_avg_doc_length(self, avg_length: float) -> None:
        """
        Update average document length for BM25 calculation.

        Should be called after indexing corpus to improve scoring accuracy.

        Args:
            avg_length: Average number of tokens per document in corpus
        """
        self.avg_doc_length = avg_length
        logger.info(f"BM25 average document length updated to {avg_length:.1f}")


# Global singleton instance
_bm25_vectorizer: BM25Vectorizer | None = None


def get_bm25_vectorizer() -> BM25Vectorizer:
    """
    Get or create global BM25Vectorizer instance.

    Returns:
        BM25Vectorizer singleton
    """
    global _bm25_vectorizer
    if _bm25_vectorizer is None:
        _bm25_vectorizer = BM25Vectorizer()
    return _bm25_vectorizer
