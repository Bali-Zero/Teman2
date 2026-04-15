"""Reranker Registry — swappable reranker backends at runtime.

Provides a Protocol-based registry for different reranker models,
allowing A/B testing and runtime swap via RERANKER_MODEL env var.

Available models:
  ms-marco  — CrossEncoder (existing, fast, English-optimized)
  bge-m3    — BGE Reranker v2 (multilingual, better for ID/EN mix)
  none      — NoOp passthrough (disables reranking)

# Organo: backend-rag/rag → produce reranked docs → consuma da ReAct loop/tools
"""

from __future__ import annotations

import logging
import os
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class RerankerProtocol(Protocol):
    """Interface that all rerankers must implement."""

    async def rerank(
        self, query: str, documents: list[dict[str, Any]], top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Rerank documents by relevance to query. Return top_k."""
        ...


class NoOpReranker:
    """Passthrough reranker — returns documents as-is (truncated to top_k)."""

    async def rerank(
        self, query: str, documents: list[dict[str, Any]], top_k: int = 5
    ) -> list[dict[str, Any]]:
        return documents[:top_k]


class BGEReranker:
    """BGE-M3 Reranker adapter — multilingual, good for ID/EN mixed content.

    Uses sentence-transformers CrossEncoder with BAAI/bge-reranker-v2-m3.
    Lazy-loads model on first call to avoid startup cost.
    """

    MODEL_NAME = "BAAI/bge-reranker-v2-m3"

    def __init__(self) -> None:
        self._model: Any = None

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.MODEL_NAME, max_length=512)
                logger.info("BGEReranker: loaded %s", self.MODEL_NAME)
            except Exception as exc:
                logger.warning("BGEReranker: failed to load model (%s), using NoOp", exc)
                self._model = "FAILED"
        return self._model

    async def rerank(
        self, query: str, documents: list[dict[str, Any]], top_k: int = 5
    ) -> list[dict[str, Any]]:
        if not documents:
            return []

        model = self._load_model()
        if model == "FAILED":
            return documents[:top_k]

        import asyncio

        def _score() -> list[dict[str, Any]]:
            pairs = [
                (query, doc.get("content", doc.get("text", "")))
                for doc in documents
            ]
            scores = model.predict(pairs)
            for doc, score in zip(documents, scores):
                doc["rerank_score"] = float(score)
            ranked = sorted(documents, key=lambda d: d.get("rerank_score", 0), reverse=True)
            return ranked[:top_k]

        return await asyncio.to_thread(_score)


class RerankerRegistry:
    """Registry of available reranker models."""

    def __init__(self) -> None:
        # Lazy import to avoid circular dep with reranker.py
        self._registry: dict[str, type] = {
            "ms-marco": self._get_ms_marco_class,  # type: ignore[dict-item]
            "bge-m3": BGEReranker,
            "none": NoOpReranker,
        }
        self._instances: dict[str, RerankerProtocol] = {}

    @staticmethod
    def _get_ms_marco_class() -> type:
        from backend.services.rag.reranker import CrossEncoderReranker
        return CrossEncoderReranker

    def get(self, model_name: str) -> RerankerProtocol:
        """Get or create a reranker instance by model name."""
        if model_name not in self._registry:
            raise KeyError(
                f"Unknown reranker model '{model_name}'. "
                f"Available: {list(self._registry.keys())}"
            )

        if model_name not in self._instances:
            factory = self._registry[model_name]
            if callable(factory) and model_name == "ms-marco":
                cls = factory()
                self._instances[model_name] = cls()
            else:
                self._instances[model_name] = factory()

        return self._instances[model_name]

    def available_models(self) -> list[str]:
        """List registered model names."""
        return list(self._registry.keys())


# ── Module-level singleton ──

_registry = RerankerRegistry()


def get_reranker(model_name: str | None = None) -> RerankerProtocol:
    """Get a reranker by model name (default from RERANKER_MODEL env var)."""
    name = model_name or os.getenv("RERANKER_MODEL", "ms-marco")
    return _registry.get(name)
