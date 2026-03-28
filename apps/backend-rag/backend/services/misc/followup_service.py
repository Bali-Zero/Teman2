"""
Follow-up Service - Generate suggested follow-up questions
Helps users continue conversations naturally by suggesting relevant next questions

This service generates 3-4 contextually relevant follow-up questions after each AI response,
improving engagement and helping users discover what they can ask next.

Author: ZANTARA Development Team
Date: 2025-10-16
Updated: 2026-01-19 - Added comprehensive logging and metrics
"""

import asyncio
import inspect
import logging
import time
from typing import Any

from prometheus_client import REGISTRY, Counter, Histogram

from backend.llm.zantara_ai_client import ZantaraAIClient

logger = logging.getLogger(__name__)


def safe_register_counter(name: Any, documentation: Any, labelnames: Any) -> Any:
    try:
        return Counter(name, documentation, labelnames)
    except ValueError:
        return REGISTRY._names_to_collectors[name]


def safe_register_histogram(
    name: Any, documentation: Any, labelnames: Any, buckets: Any = None
) -> Histogram:
    try:
        if buckets:
            return Histogram(name, documentation, labelnames, buckets=buckets)
        return Histogram(name, documentation, labelnames)
    except ValueError:
        return REGISTRY._names_to_collectors[name]


# Prometheus Metrics for FollowupService
followup_requests_total = safe_register_counter(
    "zantara_followup_requests_total",
    "Total follow-up generation requests",
    ["method", "topic", "language", "status"],
)

followup_generation_duration = safe_register_histogram(
    "zantara_followup_generation_duration_seconds",
    "Time taken to generate follow-ups",
    ["method", "topic", "language"],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
)

followup_ai_generation_total = safe_register_counter(
    "zantara_followup_ai_generation_total",
    "Total AI-generated follow-ups",
    ["status"],  # success, failure, fallback
)

followup_topic_based_total = safe_register_counter(
    "zantara_followup_topic_based_total",
    "Total topic-based follow-ups (fallback)",
    ["topic", "language"],
)


class FollowupService:
    """
    Generates suggested follow-up questions based on conversation context

    Features:
    - Context-aware question generation
    - Language-appropriate suggestions (EN, IT, ID)
    - Topic-specific follow-ups (business, casual, technical)
    - Fast generation using ZANTARA AI
    """

    def __init__(self) -> None:
        """
        Initialize follow-up service with ZANTARA AI
        """
        self._init_start_time = time.time()
        self._ai_available = False
        self._total_requests = 0
        self._ai_generation_count = 0
        self._fallback_count = 0

        try:
            self.zantara_client = ZantaraAIClient()
            self._ai_available = True
            logger.info(
                "✅ [FollowupService] Initialized with ZANTARA AI",
                extra={
                    "component": "FollowupService",
                    "action": "init",
                    "ai_available": True,
                },
            )
        except Exception as e:
            logger.warning(
                f"⚠️ [FollowupService] ZANTARA AI not available: {e}",
                extra={
                    "component": "FollowupService",
                    "action": "init",
                    "ai_available": False,
                    "error": str(e),
                },
            )
            self.zantara_client = None

        init_duration = time.time() - self._init_start_time
        logger.info(
            f"📊 [FollowupService] Initialization completed in {init_duration:.3f}s",
            extra={
                "component": "FollowupService",
                "action": "init_complete",
                "duration_seconds": init_duration,
                "ai_available": self._ai_available,
            },
        )

    def generate_followups(
        self, query: str, response: str, topic: str | None = "business", language: str | None = None
    ) -> list[str]:
        """
        Backward-compatible synchronous entrypoint used by integration tests.
        Tries AI-generated followups; falls back to topic-based suggestions.

        Args:
            query: User's original question
            response: AI's response
            topic: Topic category (None to auto-detect, or: business, immigration, tax, casual, technical)
            language: Language code (None to auto-detect, or: en, it, id, etc.)
        """
        # If we have the AI client, try to use it first
        if self.zantara_client:
            try:
                ai_result = self.zantara_client.generate_response(
                    query=query, response=response, topic=topic
                )
                # Await coroutine if mocked as AsyncMock/coroutine
                if inspect.iscoroutine(ai_result):
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    ai_result = loop.run_until_complete(ai_result)

                if isinstance(ai_result, str):
                    items = [line.strip() for line in ai_result.splitlines() if line.strip()]
                    if items:
                        return items
            except Exception as e:
                logger.warning(f"FollowupService.generate_followups AI path failed: {e}")

        # Fallback: topic-based suggestions
        # Use provided language or auto-detect from query
        detected_language = language if language else self.detect_language_from_query(query)
        detected_topic = self.detect_topic_from_query(query) if topic is None else topic
        return self.get_topic_based_followups(
            _query=query, _response=response, topic=detected_topic, language=detected_language
        )

    def get_topic_based_followups(
        self, _query: str, _response: str, topic: str = "business", language: str = "en"
    ) -> list[str]:
        """
        Get pre-defined topic-based follow-up questions

        Args:
            query: User's original question
            response: AI's response
            topic: Topic category (business, casual, technical, immigration, tax)
            language: Language code (en, it, id)

        Returns:
            List of 3-4 follow-up question strings
        """
        # Topic-specific follow-ups by language
        followups_map = {
            "business": {
                "en": [
                    "What are the costs involved?",
                    "How long does the process take?",
                    "What documents do I need?",
                    "Are there any requirements I should know about?",
                ],
                "it": [
                    "Quali sono i costi?",
                    "Quanto tempo richiede il processo?",
                    "Quali documenti servono?",
                    "Ci sono requisiti da conoscere?",
                ],
                "id": [
                    "Berapa biayanya?",
                    "Berapa lama prosesnya?",
                    "Dokumen apa yang diperlukan?",
                    "Apa saja syaratnya?",
                ],
            },
            "immigration": {
                "en": [
                    "What visa types are available?",
                    "How do I extend my visa?",
                    "What are the requirements?",
                    "Can you help me with the application process?",
                ],
                "it": [
                    "Quali tipi di visto sono disponibili?",
                    "Come posso estendere il mio visto?",
                    "Quali sono i requisiti?",
                    "Puoi aiutarmi con la procedura?",
                ],
                "id": [
                    "Jenis visa apa yang tersedia?",
                    "Bagaimana cara memperpanjang visa?",
                    "Apa saja syaratnya?",
                    "Bisakah bantu proses aplikasi?",
                ],
            },
            "tax": {
                "en": [
                    "What tax information applies to my business?",
                    "How do I register for tax in Indonesia?",
                    "Are there any tax incentives?",
                    "When are tax filing deadlines?",
                ],
                "it": [
                    "Quali informazioni fiscali si applicano?",
                    "Come mi registro per le tasse in Indonesia?",
                    "Ci sono incentivi fiscali?",
                    "Quando scadono le tasse?",
                ],
                "id": [
                    "Informasi pajak apa yang berlaku untuk bisnis saya?",
                    "Bagaimana cara daftar pajak di Indonesia?",
                    "Ada insentif pajak?",
                    "Kapan batas waktu lapor pajak?",
                ],
            },
            "casual": {
                "en": [
                    "Tell me more about this",
                    "Can you explain further?",
                    "What else should I know?",
                    "Any recommendations?",
                ],
                "it": [
                    "Dimmi di più",
                    "Puoi spiegare meglio?",
                    "Cos'altro dovrei sapere?",
                    "Qualche raccomandazione?",
                ],
                "id": [
                    "Ceritakan lebih lanjut",
                    "Bisa jelaskan lebih detail?",
                    "Apa lagi yang perlu saya tahu?",
                    "Ada rekomendasi?",
                ],
            },
            "technical": {
                "en": [
                    "Can you show me a code example?",
                    "What are the best practices?",
                    "How do I debug this?",
                    "Are there any alternatives?",
                ],
                "it": [
                    "Puoi mostrarmi un esempio di codice?",
                    "Quali sono le best practice?",
                    "Come faccio il debug?",
                    "Ci sono alternative?",
                ],
                "id": [
                    "Bisa tunjukkan contoh kode?",
                    "Apa best practice-nya?",
                    "Bagaimana cara debug?",
                    "Ada alternatif lain?",
                ],
            },
        }

        # Get follow-ups for topic and language
        topic_followups = followups_map.get(topic, followups_map["business"])
        followups = topic_followups.get(language, topic_followups["en"])

        # Return 3 random ones
        import random

        selected = random.sample(followups, min(3, len(followups)))

        # Record metrics
        followup_topic_based_total.labels(topic=topic, language=language).inc()

        logger.info(
            f"📝 [Followups] Generated {len(selected)} topic-based follow-ups (topic={topic}, language={language})",
            extra={
                "component": "FollowupService",
                "action": "get_topic_based_followups",
                "topic": topic,
                "language": language,
                "followup_count": len(selected),
                "available_followups": len(followups),
            },
        )
        return selected

    async def generate_dynamic_followups(
        self,
        query: str,
        response: str | None,
        conversation_context: str | None = None,
        language: str = "en",
    ) -> list[str]:
        """
        Generate dynamic, contextually relevant follow-up questions using AI

        Args:
            query: User's original question
            response: AI's response (Optional, if None, generates based on prediction)
            conversation_context: Optional previous conversation context
            language: Language code (en, it, id)
        """
        start_time = time.time()

        if not self.zantara_client:
            logger.warning(
                "⚠️ [Followups] ZANTARA AI client not available, cannot generate dynamic follow-ups",
                extra={
                    "component": "FollowupService",
                    "action": "generate_dynamic_followups",
                    "status": "ai_unavailable",
                    "language": language,
                },
            )
            followup_ai_generation_total.labels(status="ai_unavailable").inc()
            # Fallback to topic-based
            return self.get_topic_based_followups(query, response or "", "business", language)

        # Build prompt for ZANTARA AI
        prompt = self._build_followup_generation_prompt(
            query, response, conversation_context, language
        )

        try:
            logger.info(
                f"🤖 [Followups] Generating dynamic follow-ups using ZANTARA AI (language={language})",
                extra={
                    "component": "FollowupService",
                    "action": "generate_dynamic_followups_start",
                    "language": language,
                    "prompt_length": len(prompt),
                    "is_speculative": response is None,
                },
            )

            # Call ZANTARA AI for fast follow-up generation
            ai_start_time = time.time()
            ai_response = await self.zantara_client.chat_async(
                messages=[{"role": "user", "content": prompt}], max_tokens=8192
            )
            ai_duration = time.time() - ai_start_time

            # Parse response (expecting numbered list)
            text = ai_response["text"].strip()
            followups = self._parse_followup_list(text)

            total_duration = time.time() - start_time

            if followups:
                followup_ai_generation_total.labels(status="success").inc()
                logger.info(
                    f"✅ [Followups] Generated {len(followups)} dynamic follow-ups in {total_duration:.3f}s (AI: {ai_duration:.3f}s)",
                    extra={
                        "component": "FollowupService",
                        "action": "generate_dynamic_followups_success",
                        "language": language,
                        "followup_count": len(followups),
                        "total_duration_seconds": total_duration,
                        "ai_duration_seconds": ai_duration,
                        "response_length": len(text),
                        "is_speculative": response is None,
                    },
                )
                return followups[:4]  # Max 4
            followup_ai_generation_total.labels(status="parse_failure").inc()
            logger.warning(
                "⚠️ [Followups] Failed to parse AI follow-ups, using fallback",
                extra={
                    "component": "FollowupService",
                    "action": "generate_dynamic_followups_parse_failure",
                    "language": language,
                    "response_text": text[:200],  # First 200 chars for debugging
                },
            )
            return self.get_topic_based_followups(query, response or "", "business", language)

        except Exception as e:
            total_duration = time.time() - start_time
            followup_ai_generation_total.labels(status="error").inc()
            logger.error(
                f"❌ [Followups] Dynamic generation failed: {e}",
                extra={
                    "component": "FollowupService",
                    "action": "generate_dynamic_followups_error",
                    "language": language,
                    "duration_seconds": total_duration,
                    "error": str(e),
                },
                exc_info=True,
            )
            # Fallback to topic-based
            return self.get_topic_based_followups(query, response or "", "business", language)

    def _build_followup_generation_prompt(
        self, query: str, response: str | None, conversation_context: str | None, language: str
    ) -> str:
        """Build prompt for AI to generate follow-up questions in the user's language"""

        # LOGIC: If response is None, we are in SPECULATIVE mode (generating while reasoning)
        speculative_mode = response is None
        response_text = (
            f'AI responded: "{response[:300]}..."' if response else "AI response: (In progress...)"
        )

        # CRITICAL: Generate follow-ups in the SAME language as the user's query
        # Use the detected language parameter explicitly in the prompt
        return f"""Analyze this conversation and generate 3-4 likely follow-up questions.
{"[SPECULATIVE MODE] The AI answer is currently being generated. Predict the most relevant next questions based on the USER QUERY." if speculative_mode else ""}

IMPORTANT: Generate the questions in the SAME LANGUAGE as the user's original question.
Detected language: {language.upper()} (en=English, it=Italian, id=Indonesian)
You MUST generate all follow-up questions in {language.upper()} language.

User asked: "{query}"

{response_text}

{f"Previous context: {conversation_context[:200]}..." if conversation_context else ""}

Generate 3-4 short, specific follow-up questions that:
1. Are written in {language.upper()} language (the same language as the user's query)
2. Help the user dig deeper into the topic
3. Explore related areas they might be interested in
4. Are natural continuations of the conversation
5. Are phrased as questions the user would actually ask

Format as a numbered list:
1. First question?
2. Second question?
3. Third question?
4. Fourth question? (optional)

Keep questions concise (max 10 words each).
CRITICAL: All questions MUST be in {language.upper()} language."""


    def _parse_followup_list(self, text: str) -> list[str]:
        """
        Parse AI response into list of follow-up questions

        Args:
            text: AI response text with numbered list

        Returns:
            List of follow-up question strings
        """
        import re

        # Extract numbered items (1., 2., 3., etc.)
        pattern = r"^\s*\d+[\.\)]\s*(.+?)$"
        lines = text.strip().split("\n")

        followups = []
        for line in lines:
            match = re.match(pattern, line.strip())
            if match:
                question = match.group(1).strip()
                # Remove quotes if present
                question = question.strip("\"'")
                followups.append(question)

        return followups

    def detect_topic_from_query(self, query: str) -> str:
        """
        Detect topic category from user query

        Args:
            query: User's question

        Returns:
            Topic string (business, immigration, tax, casual, technical)
        """
        query_lower = query.lower()

        # Immigration keywords
        if any(
            keyword in query_lower
            for keyword in ["visa", "kitas", "immigration", "permit", "imigrasi", "visto"]
        ):
            return "immigration"

        # Tax keywords
        if any(
            keyword in query_lower
            for keyword in [
                "tax",
                "pajak",
                "tassa",
                "tasse",
                "fiscal",
                "fiscali",
                "imposte",
                "npwp",
                "pph",
            ]
        ):
            return "tax"

        # Technical/code keywords
        if any(
            keyword in query_lower
            for keyword in [
                "code",
                "programming",
                "api",
                "develop",
                "software",
                "bug",
                "error",
                "function",
            ]
        ):
            return "technical"

        # Casual keywords
        if any(
            keyword in query_lower
            for keyword in [
                "hello",
                "hi",
                "ciao",
                "halo",
                "how are",
                "come stai",
                "apa kabar",
                "thanks",
                "grazie",
            ]
        ):
            return "casual"

        # Default to business
        return "business"

    def detect_language_from_query(self, query: str) -> str:
        """
        Detect language from user query

        Args:
            query: User's question

        Returns:
            Language code (en, it, id)
        """
        query_lower = query.lower()

        # Italian detection
        italian_keywords = [
            "ciao",
            "come stai",
            "grazie",
            "prego",
            "buongiorno",
            "per favore",
            "cosa",
            "dove",
        ]
        if any(keyword in query_lower for keyword in italian_keywords):
            return "it"

        # Indonesian detection
        indonesian_keywords = [
            "halo",
            "apa kabar",
            "terima kasih",
            "selamat",
            "aku",
            "saya",
            "mau",
            "bisa",
        ]
        if any(keyword in query_lower for keyword in indonesian_keywords):
            return "id"

        # Default to English
        return "en"

    async def get_followups(
        self,
        query: str,
        response: str,
        use_ai: bool = True,
        conversation_context: str | None = None,
    ) -> list[str]:
        """
        Get follow-up questions (main entry point)

        Args:
            query: User's original question
            response: AI's response
            use_ai: Whether to use AI for dynamic generation (default: True)
            conversation_context: Optional conversation context

        Returns:
            List of 3-4 follow-up question strings
        """
        start_time = time.time()
        self._total_requests += 1

        # Detect language and topic
        language = self.detect_language_from_query(query)
        topic = self.detect_topic_from_query(query)

        logger.info(
            f"📊 [Followups] Request #{self._total_requests}: topic={topic}, language={language}, use_ai={use_ai}",
            extra={
                "component": "FollowupService",
                "action": "get_followups",
                "request_id": self._total_requests,
                "topic": topic,
                "language": language,
                "use_ai": use_ai,
                "query_length": len(query),
                "response_length": len(response),
            },
        )

        method = "ai" if (use_ai and self.zantara_client) else "topic_based"
        status = "pending"

        try:
            # Use AI if available and requested
            if use_ai and self.zantara_client:
                result = await self.generate_dynamic_followups(
                    query=query,
                    response=response,
                    conversation_context=conversation_context,
                    language=language,
                )
                status = "success"
                self._ai_generation_count += 1
            else:
                # Use topic-based fallback
                result = self.get_topic_based_followups(query, response, topic, language)
                status = "fallback"
                self._fallback_count += 1

            duration = time.time() - start_time

            # Record metrics
            followup_requests_total.labels(
                method=method, topic=topic, language=language, status=status
            ).inc()
            followup_generation_duration.labels(
                method=method, topic=topic, language=language
            ).observe(duration)

            logger.info(
                f"✅ [Followups] Generated {len(result)} follow-ups in {duration:.3f}s (method={method}, status={status})",
                extra={
                    "component": "FollowupService",
                    "action": "get_followups_complete",
                    "request_id": self._total_requests,
                    "method": method,
                    "status": status,
                    "topic": topic,
                    "language": language,
                    "followup_count": len(result),
                    "duration_seconds": duration,
                },
            )

            return result

        except Exception as e:
            duration = time.time() - start_time
            status = "error"

            # Record error metrics
            followup_requests_total.labels(
                method=method, topic=topic, language=language, status=status
            ).inc()
            followup_generation_duration.labels(
                method=method, topic=topic, language=language
            ).observe(duration)

            logger.error(
                f"❌ [Followups] Failed to generate follow-ups: {e}",
                extra={
                    "component": "FollowupService",
                    "action": "get_followups_error",
                    "request_id": self._total_requests,
                    "method": method,
                    "topic": topic,
                    "language": language,
                    "duration_seconds": duration,
                    "error": str(e),
                },
                exc_info=True,
            )

            # Fallback to topic-based on error
            try:
                fallback_result = self.get_topic_based_followups(query, response, topic, language)
                logger.info(
                    f"🔄 [Followups] Using fallback after error: {len(fallback_result)} follow-ups",
                    extra={
                        "component": "FollowupService",
                        "action": "fallback_after_error",
                        "followup_count": len(fallback_result),
                    },
                )
                return fallback_result
            except Exception as fallback_error:
                logger.error(
                    f"❌ [Followups] Fallback also failed: {fallback_error}",
                    extra={
                        "component": "FollowupService",
                        "action": "fallback_error",
                        "error": str(fallback_error),
                    },
                )
                return []

    async def health_check(self) -> dict[str, Any]:
        """
        Health check for follow-up service

        Returns:
            {
                "status": "healthy",
                "ai_available": bool,
                "features": {...},
                "metrics": {...}
            }
        """
        health_data = {
            "status": "healthy",
            "ai_available": self.zantara_client is not None,
            "features": {
                "dynamic_generation": self.zantara_client is not None,
                "topic_based_fallback": True,
                "supported_languages": ["en", "it", "id"],
                "supported_topics": ["business", "immigration", "tax", "casual", "technical"],
            },
            "metrics": {
                "total_requests": self._total_requests,
                "ai_generation_count": self._ai_generation_count,
                "fallback_count": self._fallback_count,
                "ai_usage_rate": (
                    self._ai_generation_count / self._total_requests
                    if self._total_requests > 0
                    else 0.0
                ),
            },
        }

        logger.debug(
            "🏥 [Followups] Health check",
            extra={
                "component": "FollowupService",
                "action": "health_check",
                "health_data": health_data,
            },
        )

        return health_data
