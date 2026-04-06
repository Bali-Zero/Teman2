"""
RAGAS Evaluator for Nuzantara RAG System

Implements automated RAG evaluation using RAGAS metrics:
- Faithfulness: Answer is grounded in retrieved context
- Answer Relevance: Answer addresses the question
- Context Precision: Retrieved context is relevant
- Context Recall: All relevant context is retrieved
- Context Entity Recall: Entities in answer are in context

Uses LLM-as-a-judge pattern with Gemini for evaluation prompts.
Supports multilingual evaluation (ID/EN).
"""

import hashlib
import json
import logging
import time
from typing import Any

from backend.app.core.logging_config import get_performance_logger
from backend.llm.base import LLMMessage

try:
    from backend.llm.client import UnifiedLLMClient, create_default_client
except ImportError:
    from typing import Any as UnifiedLLMClient  # type: ignore[assignment]

    def create_default_client() -> Any:  # type: ignore[misc]
        """Placeholder — backend.llm.client not yet implemented."""
        raise NotImplementedError("UnifiedLLMClient not available; pass llm_client explicitly")

logger = logging.getLogger(__name__)

# Evaluation prompt templates (multilingual ID/EN)
FAITHFULNESS_PROMPT = """Anda adalah evaluator yang objektif. Tugas Anda adalah menilai sejauh mana jawaban didukung oleh konteks yang diambil.

Pertanyaan: {question}
Konteks yang Diambil:
{context}

Jawaban yang Diberikan:
{answer}

Instruksi:
1. Identifikasi pernyataan-pernyataan faktual dalam jawaban
2. Untuk setiap pernyataan, tentukan apakah dapat diverifikasi dari konteks
3. Berikan skor 0.0-1.0 berdasarkan proporsi pernyataan yang didukung konteks

Format respons (JSON):
{{
    "reasoning": "Penjelasan singkat dalam Bahasa Indonesia",
    "supported_statements": ["pernyataan 1", "pernyataan 2"],
    "unsupported_statements": ["pernyataan tidak terdukung"],
    "score": 0.85
}}
"""

ANSWER_RELEVANCE_PROMPT = """Anda adalah evaluator yang objektif. Tugas Anda adalah menilai sejauh mana jawaban relevan dengan pertanyaan.

Pertanyaan: {question}

Jawaban yang Diberikan:
{answer}

Instruksi:
1. Apakah jawaban secara langsung menjawab pertanyaan?
2. Apakah ada informasi tidak relevan atau off-topic?
3. Berikan skor 0.0-1.0 berdasarkan kesesuaian jawaban dengan pertanyaan

Format respons (JSON):
{{
    "reasoning": "Penjelasan singkat dalam Bahasa Indonesia",
    "relevant_parts": ["bagian relevan 1"],
    "irrelevant_parts": ["bagian tidak relevan"],
    "score": 0.90
}}
"""

CONTEXT_PRECISION_PROMPT = """Anda adalah evaluator yang objektif. Tugas Anda adalah menilai sejauh mana konteks yang diambil relevan dengan pertanyaan.

Pertanyaan: {question}
Konteks yang Diambil:
{context}

Jawaban Benar (Ground Truth):
{ground_truth}

Instruksi:
1. Evaluasi setiap bagian konteks apakah relevan dengan pertanyaan
2. Konteks relevan harus berisi informasi yang membantu menjawab pertanyaan
3. Berikan skor 0.0-1.0 berdasarkan proporsi konteks yang relevan

Format respons (JSON):
{{
    "reasoning": "Penjelasan singkat dalam Bahasa Indonesia",
    "relevant_chunks": ["bagian relevan 1", "bagian relevan 2"],
    "irrelevant_chunks": ["bagian tidak relevan"],
    "score": 0.75
}}
"""

CONTEXT_RECALL_PROMPT = """Anda adalah evaluator yang objektif. Tugas Anda adalah menilai sejauh mana semua konteks relevan berhasil diambil.

Pertanyaan: {question}
Konteks yang Diambil:
{context}

Jawaban Benar (Ground Truth):
{ground_truth}

Instruksi:
1. Identifikasi informasi apa yang dibutuhkan untuk menjawab pertanyaan dengan lengkap
2. Tentukan berapa banyak informasi tersebut yang tersedia dalam konteks yang diambil
3. Berikan skore 0.0-1.0 berdasarkan kelengkapan informasi dalam konteks

Format respons (JSON):
{{
    "reasoning": "Penjelasan singkat dalam Bahasa Indonesia",
    "covered_information": ["info 1", "info 2"],
    "missing_information": ["info yang hilang"],
    "score": 0.80
}}
"""

CONTEXT_ENTITY_RECALL_PROMPT = """Anda adalah evaluator yang objektif. Tugas Anda adalah menilai sejauh mana entitas dalam jawaban muncul dalam konteks.

Pertanyaan: {question}
Konteks yang Diambil:
{context}

Jawaban yang Diberikan:
{answer}

Instruksi:
1. Identifikasi entitas penting dalam jawaban (nama, tempat, organisasi, angka, tanggal, dll)
2. Tentukan berapa banyak entitas tersebut yang disebutkan dalam konteks
3. Berikan skor 0.0-1.0 berdasarkan proporsi entitas yang ditemukan dalam konteks

Format respons (JSON):
{{
    "reasoning": "Penjelasan singkat dalam Bahasa Indonesia",
    "entities_in_answer": ["entitas 1", "entitas 2"],
    "entities_in_context": ["entitas ditemukan"],
    "missing_entities": ["entitas tidak ditemukan"],
    "score": 0.85
}}
"""


class EvaluationResult:
    """Container for evaluation results."""

    def __init__(
        self,
        query: str,
        context: list[str],
        answer: str,
        ground_truth: str | None = None,
        metrics: dict[str, float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.query = query
        self.context = context
        self.answer = answer
        self.ground_truth = ground_truth
        self.metrics = metrics or {}
        self.metadata = metadata or {}
        self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "context": self.context,
            "answer": self.answer,
            "ground_truth": self.ground_truth,
            "metrics": self.metrics,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    @property
    def overall_score(self) -> float:
        """Calculate overall score from all metrics."""
        if not self.metrics:
            return 0.0
        return sum(self.metrics.values()) / len(self.metrics)


class RAGASEvaluator:
    """
    RAGAS Evaluator for measuring RAG system quality.

    Implements the LLM-as-a-judge pattern using Gemini for evaluation.
    Supports caching of evaluation results to reduce costs.

    Example:
        >>> evaluator = RAGASEvaluator()
        >>> result = await evaluator.evaluate(
        ...     query="What is KITAS?",
        ...     context=["KITAS is a limited stay permit..."],
        ...     answer="KITAS is a stay permit for foreigners...",
        ...     ground_truth="KITAS (Kartu Izin Tinggal Terbatas)..."
        ... )
        >>> result.metrics  # noqa: T201
        {'faithfulness': 0.95, 'answer_relevance': 0.90, ...}
    """

    def __init__(
        self,
        llm_client: UnifiedLLMClient | None = None,
        enable_cache: bool = True,
        cache_ttl: int = 86400,  # 24 hours
    ) -> None:
        """
        Initialize RAGAS Evaluator.

        Args:
            llm_client: Custom LLM client (defaults to create_default_client)
            enable_cache: Whether to cache evaluation results
            cache_ttl: Cache time-to-live in seconds
        """
        self.llm_client = llm_client or create_default_client()
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self._cache: dict[str, dict[str, Any]] = {}
        self._eval_count = 0
        self._cache_hit_count = 0

        logger.info(
            f"RAGASEvaluator initialized (cache={'enabled' if enable_cache else 'disabled'})",
        )

    def _get_cache_key(self, query: str, context: list[str], answer: str, metric: str) -> str:
        """Generate cache key for evaluation result."""
        content = f"{query}:{':'.join(context)}:{answer}:{metric}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _get_cached_result(self, cache_key: str) -> dict[str, Any] | None:
        """Get cached evaluation result if valid."""
        if not self.enable_cache:
            return None

        cached = self._cache.get(cache_key)
        if cached:
            age = time.time() - cached.get("timestamp", 0)
            if age < self.cache_ttl:
                self._cache_hit_count += 1
                return cached["result"]
            # Expired
            del self._cache[cache_key]
        return None

    def _cache_result(self, cache_key: str, result: dict[str, Any]) -> None:
        """Cache evaluation result."""
        if self.enable_cache:
            self._cache[cache_key] = {
                "result": result,
                "timestamp": time.time(),
            }

    async def _call_llm_evaluator(self, prompt: str, temperature: float = 0.1) -> dict[str, Any]:
        """
        Call LLM for evaluation with structured output.

        Args:
            prompt: Evaluation prompt
            temperature: Low temperature for consistent evaluation

        Returns:
            Parsed JSON response with score and reasoning
        """
        messages = [
            LLMMessage(
                role="system",
                content="You are an objective evaluator. Always respond in valid JSON format.",
            ),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            response = await self.llm_client.generate(
                messages=messages,
                temperature=temperature,
                max_tokens=2048,
            )

            # Parse JSON from response
            content = response.content.strip()
            # Handle markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)

            # Validate required fields
            if "score" not in result:
                logger.warning("LLM response missing 'score' field, using default")
                result["score"] = 0.5

            # Ensure score is between 0 and 1
            result["score"] = max(0.0, min(1.0, float(result["score"])))

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM evaluation response: {e}")
            return {
                "score": 0.5,
                "reasoning": "Failed to parse evaluation response",
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}")
            return {
                "score": 0.5,
                "reasoning": f"Evaluation error: {str(e)}",
                "error": str(e),
            }

    async def evaluate_faithfulness(self, answer: str, context: list[str]) -> dict[str, Any]:
        """
        Evaluate faithfulness - answer is grounded in retrieved context.

        Args:
            answer: Generated answer to evaluate
            context: List of retrieved context chunks

        Returns:
            Dictionary with score (0.0-1.0) and reasoning
        """
        cache_key = self._get_cache_key("", context, answer, "faithfulness")
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached

        context_text = "\n\n".join(
            [f"[Konteks {i + 1}]\n{chunk}" for i, chunk in enumerate(context)],
        )

        prompt = FAITHFULNESS_PROMPT.format(
            question="N/A",
            context=context_text,
            answer=answer,
        )

        result = await self._call_llm_evaluator(prompt)
        self._cache_result(cache_key, result)
        self._eval_count += 1

        return result

    async def evaluate_answer_relevance(self, query: str, answer: str) -> dict[str, Any]:
        """
        Evaluate answer relevance - answer addresses the question.

        Args:
            query: Original user query
            answer: Generated answer to evaluate

        Returns:
            Dictionary with score (0.0-1.0) and reasoning
        """
        cache_key = self._get_cache_key(query, [], answer, "answer_relevance")
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached

        prompt = ANSWER_RELEVANCE_PROMPT.format(
            question=query,
            answer=answer,
        )

        result = await self._call_llm_evaluator(prompt)
        self._cache_result(cache_key, result)
        self._eval_count += 1

        return result

    async def evaluate_context_precision(
        self, query: str, context: list[str], ground_truth: str,
    ) -> dict[str, Any]:
        """
        Evaluate context precision - retrieved context is relevant.

        Args:
            query: Original user query
            context: List of retrieved context chunks
            ground_truth: Expected/ground truth answer

        Returns:
            Dictionary with score (0.0-1.0) and reasoning
        """
        cache_key = self._get_cache_key(query, context, "", "context_precision")
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached

        context_text = "\n\n".join(
            [f"[Konteks {i + 1}]\n{chunk}" for i, chunk in enumerate(context)],
        )

        prompt = CONTEXT_PRECISION_PROMPT.format(
            question=query,
            context=context_text,
            ground_truth=ground_truth,
        )

        result = await self._call_llm_evaluator(prompt)
        self._cache_result(cache_key, result)
        self._eval_count += 1

        return result

    async def evaluate_context_recall(
        self, query: str, context: list[str], ground_truth: str,
    ) -> dict[str, Any]:
        """
        Evaluate context recall - all relevant context is retrieved.

        Args:
            query: Original user query
            context: List of retrieved context chunks
            ground_truth: Expected/ground truth answer

        Returns:
            Dictionary with score (0.0-1.0) and reasoning
        """
        cache_key = self._get_cache_key(query, context, "", "context_recall")
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached

        context_text = "\n\n".join(
            [f"[Konteks {i + 1}]\n{chunk}" for i, chunk in enumerate(context)],
        )

        prompt = CONTEXT_RECALL_PROMPT.format(
            question=query,
            context=context_text,
            ground_truth=ground_truth,
        )

        result = await self._call_llm_evaluator(prompt)
        self._cache_result(cache_key, result)
        self._eval_count += 1

        return result

    async def evaluate_context_entity_recall(
        self, answer: str, context: list[str],
    ) -> dict[str, Any]:
        """
        Evaluate context entity recall - entities in answer are in context.

        Args:
            answer: Generated answer to evaluate
            context: List of retrieved context chunks

        Returns:
            Dictionary with score (0.0-1.0) and reasoning
        """
        cache_key = self._get_cache_key("", context, answer, "context_entity_recall")
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached

        context_text = "\n\n".join(
            [f"[Konteks {i + 1}]\n{chunk}" for i, chunk in enumerate(context)],
        )

        prompt = CONTEXT_ENTITY_RECALL_PROMPT.format(
            question="N/A",
            context=context_text,
            answer=answer,
        )

        result = await self._call_llm_evaluator(prompt)
        self._cache_result(cache_key, result)
        self._eval_count += 1

        return result

    async def evaluate(
        self,
        query: str,
        context: list[str],
        answer: str,
        ground_truth: str | None = None,
        metrics: list[str] | None = None,
    ) -> EvaluationResult:
        """
        Run full RAGAS evaluation on a query-answer pair.

        Args:
            query: Original user query
            context: List of retrieved context chunks
            answer: Generated answer to evaluate
            ground_truth: Optional expected/ground truth answer
            metrics: List of metrics to compute (default: all)

        Returns:
            EvaluationResult with all computed metrics

        Example:
            >>> result = await evaluator.evaluate(
            ...     query="What is KITAS?",
            ...     context=["KITAS is a limited stay permit..."],
            ...     answer="KITAS is a stay permit...",
            ...     ground_truth="KITAS (Kartu Izin Tinggal Terbatas)..."
            ... )
        """
        with get_performance_logger(__name__, "ragas_evaluation"):
            all_metrics = [
                "faithfulness",
                "answer_relevance",
                "context_precision",
                "context_recall",
                "context_entity_recall",
            ]
            metrics_to_compute = metrics or all_metrics

            results: dict[str, float] = {}
            detailed_results: dict[str, dict[str, Any]] = {}

            # Always compute faithfulness
            if "faithfulness" in metrics_to_compute:
                faithfulness = await self.evaluate_faithfulness(answer, context)
                results["faithfulness"] = faithfulness["score"]
                detailed_results["faithfulness"] = faithfulness

            # Always compute answer relevance
            if "answer_relevance" in metrics_to_compute:
                relevance = await self.evaluate_answer_relevance(query, answer)
                results["answer_relevance"] = relevance["score"]
                detailed_results["answer_relevance"] = relevance

            # Context precision requires ground truth
            if "context_precision" in metrics_to_compute and ground_truth:
                precision = await self.evaluate_context_precision(query, context, ground_truth)
                results["context_precision"] = precision["score"]
                detailed_results["context_precision"] = precision

            # Context recall requires ground truth
            if "context_recall" in metrics_to_compute and ground_truth:
                recall = await self.evaluate_context_recall(query, context, ground_truth)
                results["context_recall"] = recall["score"]
                detailed_results["context_recall"] = recall

            # Context entity recall
            if "context_entity_recall" in metrics_to_compute:
                entity_recall = await self.evaluate_context_entity_recall(answer, context)
                results["context_entity_recall"] = entity_recall["score"]
                detailed_results["context_entity_recall"] = entity_recall

            evaluation_result = EvaluationResult(
                query=query,
                context=context,
                answer=answer,
                ground_truth=ground_truth,
                metrics=results,
                metadata={
                    "detailed_results": detailed_results,
                    "cache_enabled": self.enable_cache,
                    "eval_count": self._eval_count,
                    "cache_hits": self._cache_hit_count,
                },
            )

            logger.info(
                f"RAGAS evaluation completed: "
                f"faithfulness={results.get('faithfulness', 'N/A')}, "
                f"answer_relevance={results.get('answer_relevance', 'N/A')}, "
                f"overall={evaluation_result.overall_score:.3f}",
            )

            return evaluation_result

    def get_stats(self) -> dict[str, Any]:
        """Get evaluator statistics."""
        return {
            "total_evaluations": self._eval_count,
            "cache_hits": self._cache_hit_count,
            "cache_size": len(self._cache),
            "cache_enabled": self.enable_cache,
        }

    def clear_cache(self) -> None:
        """Clear evaluation cache."""
        self._cache.clear()
        self._cache_hit_count = 0
        logger.info("RAGAS evaluator cache cleared")


# Global singleton instance
_ragas_evaluator: RAGASEvaluator | None = None


def get_ragas_evaluator(
    llm_client: UnifiedLLMClient | None = None,
    enable_cache: bool = True,
) -> RAGASEvaluator:
    """
    Get or create global RAGASEvaluator instance.

    Args:
        llm_client: Optional custom LLM client
        enable_cache: Whether to enable result caching

    Returns:
        RAGASEvaluator singleton
    """
    global _ragas_evaluator
    if _ragas_evaluator is None:
        _ragas_evaluator = RAGASEvaluator(
            llm_client=llm_client,
            enable_cache=enable_cache,
        )
    return _ragas_evaluator
