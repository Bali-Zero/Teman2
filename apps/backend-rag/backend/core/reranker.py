"""
ZANTARA RAG - Semantic Re-ranker (Ze-Rank 2 API)
Implements external API-based re-ranking for high-precision retrieval without local CPU load.
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ReRanker:
    """
    Semantic Re-ranker using Ze-Rank 2 API.
    Re-scores (query, document) pairs to determine true relevance using an external GPU-accelerated service.
    """

    def __init__(self, model_name: str | None = None):
        """
        Initialize the Ze-Rank 2 Re-ranker.

        Args:
            model_name: Optional model name (passed to API if supported, default handled by API).
        """
        self.api_key = settings.zerank_api_key
        self.api_url = settings.zerank_api_url
        self.model_name = model_name or "zerank-2-turbo"
        self.enabled = bool(self.api_key)

        if not self.enabled:
            logger.warning("⚠️ ZERANK_API_KEY not set. Re-ranking will be disabled (pass-through).")
        else:
            logger.info(f"✅ Ze-Rank 2 initialized with endpoint: {self.api_url}")

    async def rerank(
        self, query: str, documents: list[dict[str, Any]], top_k: int = 5
    ) -> list[dict[str, Any]]:
        """
        Re-rank a list of documents based on relevance to the query using Ze-Rank 2 API.

        Args:
            query: The search query
            documents: List of document dictionaries. Must contain 'text' or 'content' key.
            top_k: Number of top results to return

        Returns:
            List of re-ranked document dictionaries with updated 'score' and 'rerank_score'.
        """
        if not self.enabled or not documents:
            return documents[:top_k]

        # Extract text content from documents
        doc_texts = []
        valid_docs = []

        for doc in documents:
            text = doc.get("text") or doc.get("content") or ""
            if text:
                doc_texts.append(text)
                valid_docs.append(doc)

        if not doc_texts:
            return documents[:top_k]

        try:
            # Prepare payload for Ze-Rank 2 API
            payload = {
                "query": query,
                "documents": doc_texts,
                "model": self.model_name,
                "top_k": top_k,
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Call Ze-Rank 2 API (async)
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)

                if response.status_code != 200:
                    logger.error(
                        f"❌ Ze-Rank 2 API Error: {response.status_code} - {response.text}"
                    )
                    return documents[:top_k]

                data = response.json()

                # Assume standard rerank response format:
                # { "results": [ { "index": 0, "relevance_score": 0.98 }, ... ] }
                # Adjust parsing logic if the actual API format differs
                results = data.get("results", [])

                if not results:
                    logger.warning("⚠️ Ze-Rank 2 returned no results")
                    return documents[:top_k]

                # Map results back to documents
                reranked_docs = []
                for res in results:
                    idx = res.get("index")
                    score = res.get("relevance_score", 0.0)

                    if idx is not None and 0 <= idx < len(valid_docs):
                        doc = valid_docs[idx]
                        doc["rerank_score"] = float(score)

                        # Preserve original score if needed
                        if "score" in doc and "vector_score" not in doc:
                            doc["vector_score"] = doc["score"]

                        # Update main score
                        doc["score"] = float(score)
                        reranked_docs.append(doc)

                # If API returned fewer docs than requested or something went wrong with mapping,
                # we might want to fill with remaining original docs (rare)
                # For now, just return what was successfully reranked

                # Sort explicitly just in case API didn't
                reranked_docs.sort(key=lambda x: x["score"], reverse=True)

                return reranked_docs[:top_k]

        except Exception as e:
            logger.error(f"❌ Re-ranking failed (Ze-Rank 2): {e}")
            # Fallback to original order
            return documents[:top_k]
