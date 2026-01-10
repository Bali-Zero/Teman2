"""
Oracle Service
==============
Core business logic for the Universal Oracle system.
Decoupled from FastAPI router for better testability and maintainability.

REFACTORED: Uses sub-services following Single Responsibility Principle
- LanguageDetectionService: Language detection
- UserContextService: User profile/memory/personality
- ReasoningEngineService: Gemini reasoning
- DocumentRetrievalService: PDF/Drive integration
- OracleAnalyticsService: Analytics tracking
"""

import logging
import time
from pathlib import Path
from typing import Any

import asyncpg
import httpx
from fastapi import HTTPException
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
from backend.llm.adapters.gemini import GeminiAdapter
from backend.prompts.zantara_prompt_builder import PromptContext, ZantaraPromptBuilder
from qdrant_client.http import exceptions as qdrant_exceptions

from ..classification.intent_classifier import IntentClassifier
from ..memory import MemoryOrchestrator
from ..memory.memory_fact_extractor import MemoryFactExtractor
from ..memory.memory_service_postgres import MemoryServicePostgres
from ..misc.clarification_service import ClarificationService
from ..misc.followup_service import FollowupService
from ..misc.golden_answer_service import GoldenAnswerService
from ..misc.personality_service import PersonalityService
from ..response.validator import ZantaraResponseValidator

# Core Dependencies
# Services
from ..search.citation_service import CitationService
from ..search.search_service import SearchService

# Import directly from submodules to avoid circular import with __init__.py
from .analytics import OracleAnalyticsService
from .document_retrieval import DocumentRetrievalService
from .language_detector import LanguageDetectionService
from .oracle_config import oracle_config as config
from .oracle_database import db_manager
from .reasoning_engine import ReasoningEngineService
from .user_context import UserContextService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MODELS (Moved/Shared)
# ---------------------------------------------------------------------------
# Note: Request/Response models are typically defined in routers or a shared schemas file.
# Since they are currently in the router, we will assume the service receives typed arguments
from ..rag.agentic import create_agentic_rag
from ..rag.agentic.entity_extractor import EntityExtractionService
from ..rag.agentic.orchestrator import AgenticRAGOrchestrator
from ..rag.agentic.schema import CoreResult

# ---------------------------------------------------------------------------
# HELPER FUNCTIONS (Backward Compatibility)
# ---------------------------------------------------------------------------


# These functions are kept for backward compatibility but delegate to services
def detect_query_language(query: str) -> str:
    """
    Detect language from query text (backward compatibility wrapper).

    REFACTORED: Delegates to LanguageDetectionService.
    """
    service = LanguageDetectionService()
    return service.detect_language(query)


def generate_query_hash(query_text: str) -> str:
    """
    Generate hash for query analytics (backward compatibility wrapper).

    REFACTORED: Delegates to OracleAnalyticsService.
    """
    service = OracleAnalyticsService()
    return service.generate_query_hash(query_text)


def download_pdf_from_drive(filename: str) -> str | None:
    """
    Download PDF from Google Drive (backward compatibility wrapper).

    REFACTORED: Delegates to DocumentRetrievalService.
    """
    service = DocumentRetrievalService()
    return service.download_pdf_from_drive(filename)


# ---------------------------------------------------------------------------
# CORE REASONING LOGIC (Backward Compatibility)
# ---------------------------------------------------------------------------


async def reason_with_gemini(
    documents: list[str],
    query: str,
    context: PromptContext,
    prompt_builder: ZantaraPromptBuilder,
    response_validator: ZantaraResponseValidator,
    use_full_docs: bool = False,
    user_memory_facts: list[str] | None = None,
    conversation_history: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Advanced reasoning with Google Gemini (backward compatibility wrapper).

    REFACTORED: Delegates to ReasoningEngineService.
    """
    reasoning_engine = ReasoningEngineService(
        prompt_builder=prompt_builder, response_validator=response_validator
    )
    return await reasoning_engine.reason_with_gemini(
        documents=documents,
        query=query,
        context=context,
        use_full_docs=use_full_docs,
        user_memory_facts=user_memory_facts,
        conversation_history=conversation_history,
    )


# ---------------------------------------------------------------------------
# ORACLE SERVICE CLASS
# ---------------------------------------------------------------------------


class OracleService:
    def __init__(self):
        self.prompt_builder = ZantaraPromptBuilder(model_adapter=GeminiAdapter())
        self.intent_classifier = IntentClassifier()

        # Load communication modes
        config_path = Path(__file__).parent.parent.parent / "config" / "communication_modes.yaml"
        try:
            import yaml

            with open(config_path) as f:
                communication_modes = yaml.safe_load(f)
            self.response_validator = ZantaraResponseValidator(
                mode_config=communication_modes, dry_run=True
            )
        except (OSError, FileNotFoundError, ValueError, KeyError) as e:
            logger.warning(f"Failed to load communication modes: {e}", exc_info=True)
            self.response_validator = ZantaraResponseValidator(mode_config={}, dry_run=True)

        # Initialize sub-services
        self.language_detector = LanguageDetectionService()
        self.user_context = UserContextService()
        self.reasoning_engine = ReasoningEngineService(
            prompt_builder=self.prompt_builder, response_validator=self.response_validator
        )
        self.document_retrieval = DocumentRetrievalService()
        self.analytics = OracleAnalyticsService()

        # Adapter State
        self._orchestrator: AgenticRAGOrchestrator | None = None
        self._db_pool: asyncpg.Pool | None = None
        self._entity_extractor = EntityExtractionService()

        # Lazy loaded services
        self._followup_service: FollowupService | None = None
        self._citation_service: CitationService | None = None
        self._clarification_service: ClarificationService | None = None
        self._personality_service: PersonalityService | None = None
        self._golden_answer_service: GoldenAnswerService | None = None
        self._memory_service: MemoryServicePostgres | None = None
        self._fact_extractor: MemoryFactExtractor | None = None
        self._memory_orchestrator: MemoryOrchestrator | None = None

    async def _get_db_pool(self) -> asyncpg.Pool:
        """Lazy load asyncpg pool for Agentic RAG tools"""
        if not self._db_pool:
            try:
                self._db_pool = await asyncpg.create_pool(dsn=config.database_url)
            except Exception as e:
                logger.error(f"Failed to create asyncpg pool: {e}")
                # Fallback or re-raise depending on criticality.
                # RAG might partially work without DB (except for Memory/Team tools)
                raise
        return self._db_pool

    async def _get_orchestrator(self, search_service: SearchService) -> AgenticRAGOrchestrator:
        """Lazy load orchestrator with injected dependencies"""
        if not self._orchestrator:
            pool = await self._get_db_pool()
            self._orchestrator = create_agentic_rag(
                retriever=search_service,
                db_pool=pool,
                semantic_cache=None,  # Oracle specific cache logic if needed
                clarification_service=self.clarification_service,
            )
            # Inject pre-initialized entity extractor if needed, or rely on factory
            # Factory creates new one. We can inject our shared one if we modify factory or set it after.
            self._orchestrator.entity_extractor = self._entity_extractor
        return self._orchestrator

    @property
    def followup_service(self) -> FollowupService:
        if not self._followup_service:
            self._followup_service = FollowupService()
        return self._followup_service

    @property
    def citation_service(self) -> CitationService:
        if not self._citation_service:
            self._citation_service = CitationService()
        return self._citation_service

    @property
    def clarification_service(self) -> ClarificationService:
        if not self._clarification_service:
            self._clarification_service = ClarificationService()
        return self._clarification_service

    @property
    def personality_service(self) -> PersonalityService:
        if not self._personality_service:
            self._personality_service = PersonalityService()
        return self._personality_service

    @property
    def golden_answer_service(self) -> GoldenAnswerService | None:
        if not self._golden_answer_service:
            try:
                database_url = config.database_url if hasattr(config, "database_url") else None
                if database_url:
                    self._golden_answer_service = GoldenAnswerService(database_url)
            except (asyncpg.PostgresError, ValueError, RuntimeError) as e:
                logger.warning(f"GoldenAnswerService init failed: {e}", exc_info=True)
        return self._golden_answer_service

    @property
    def memory_service(self) -> MemoryServicePostgres | None:
        if not self._memory_service:
            try:
                database_url = config.database_url if hasattr(config, "database_url") else None
                if database_url:
                    self._memory_service = MemoryServicePostgres(database_url)
            except (asyncpg.PostgresError, ValueError, RuntimeError) as e:
                logger.warning(f"MemoryServicePostgres init failed: {e}", exc_info=True)
        return self._memory_service

    @property
    def fact_extractor(self) -> MemoryFactExtractor:
        if not self._fact_extractor:
            self._fact_extractor = MemoryFactExtractor()
        return self._fact_extractor

    @property
    def memory_orchestrator(self) -> MemoryOrchestrator:
        """
        Get the centralized MemoryOrchestrator instance.

        The orchestrator provides unified memory operations:
        - get_user_context(): Retrieve user's stored memory
        - process_conversation(): Extract and save facts from conversations
        """
        if not self._memory_orchestrator:
            try:
                database_url = config.database_url if hasattr(config, "database_url") else None
                self._memory_orchestrator = MemoryOrchestrator(database_url=database_url)
            except (asyncpg.PostgresError, ValueError, RuntimeError) as e:
                logger.warning(f"MemoryOrchestrator init failed: {e}", exc_info=True)
                # Create a basic orchestrator that will operate in degraded mode
                self._memory_orchestrator = MemoryOrchestrator()
        return self._memory_orchestrator

    async def _ensure_memory_orchestrator_initialized(self) -> bool:
        """Ensure the memory orchestrator is initialized and ready."""
        try:
            if not self.memory_orchestrator.is_initialized:
                await self.memory_orchestrator.initialize()
            return True
        except (asyncpg.PostgresError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to initialize memory orchestrator: {e}", exc_info=True)
            return False

    async def _save_memory_facts(
        self,
        user_email: str,
        user_message: str,
        ai_response: str,
    ) -> None:
        """
        Extract and save memory facts from conversation using MemoryOrchestrator.

        This method delegates to the centralized MemoryOrchestrator which:
        1. Extracts facts using MemoryFactExtractor
        2. Deduplicates and ranks facts by confidence
        3. Saves facts to PostgreSQL via MemoryServicePostgres

        Called after successful query processing (via asyncio.create_task).
        """
        if not user_email:
            return

        try:
            # Ensure orchestrator is initialized
            if not await self._ensure_memory_orchestrator_initialized():
                logger.warning("Memory orchestrator not available, skipping fact saving")
                return

            # Use orchestrator to process the conversation
            result = await self.memory_orchestrator.process_conversation(
                user_email=user_email,
                user_message=user_message,
                ai_response=ai_response,
            )

            if result.success and result.facts_saved > 0:
                logger.info(
                    f"💾 MemoryOrchestrator saved {result.facts_saved}/{result.facts_extracted} "
                    f"facts for {user_email} ({result.processing_time_ms:.1f}ms)"
                )

        except (asyncpg.PostgresError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to save memory facts via orchestrator: {e}", exc_info=True)

    async def process_query(
        self,
        request_query: str,
        request_user_email: str | None,
        request_limit: int,
        request_session_id: str | None,
        request_include_sources: bool,
        request_use_ai: bool,
        request_language_override: str | None,
        request_conversation_history: list[Any] | None,
        search_service: SearchService,
    ) -> dict[str, Any]:
        """
        Process the oracle query using hybrid search and reasoning.
        Returns a dictionary that maps to OracleQueryResponse.
        """
        start_time = time.time()
        execution_time = 0
        search_time = 0
        reasoning_time = 0

        try:
            logger.info(f"🚀 Starting oracle service query: {request_query[:100]}...")

            # 1. Get user context (delegated to UserContextService)
            # Update user_context service with actual services if available
            if self.personality_service:
                self.user_context.personality_service = self.personality_service
            if self.memory_service:
                self.user_context.memory_service = self.memory_service

            user_context_data = await self.user_context.get_full_user_context(request_user_email)
            user_profile = user_context_data["profile"]
            personality_used = user_context_data["personality"].get(
                "personality_type", "professional"
            )
            user_memory_facts = user_context_data["memory_facts"]
            user_name = user_context_data["user_name"]
            user_role = user_context_data["user_role"]

            # 2. Context & Intent (delegated to LanguageDetectionService)
            detected_language = self.language_detector.detect_language(request_query)
            target_language = self.language_detector.get_target_language(
                request_query,
                language_override=request_language_override,
                user_language=user_profile.get("language") if user_profile else None,
            )

            # --- CORE ADAPTER LOGIC: Delegate to AgenticRAGOrchestrator ---
            orchestrator = await self._get_orchestrator(search_service)

            # Prepare conversation history
            conv_history_dicts = []
            if request_conversation_history:
                conv_history_dicts = [
                    {"role": msg.role, "content": msg.content}
                    for msg in request_conversation_history
                ]

            # EXECUTE RAG
            # We map user parameters to orchestrator inputs
            rag_result: CoreResult = await orchestrator.process_query(
                query=request_query,
                user_id=request_user_email or "anonymous",
                conversation_history=conv_history_dicts,
                session_id=request_session_id,
            )

            # --- MAP RESULT TO LEGACY FORMAT ---
            answer = rag_result.answer
            sources = rag_result.sources
            model_used = rag_result.model_used
            execution_time = rag_result.timings.get("total", 0) * 1000

            # Extract internal metrics for analytics (approximate mapping)
            search_time = 0  # Not explicit in CoreResult yet, could add to timings
            reasoning_time = 0

            # Handle Clarification / Abstain / Identity
            clarification_needed = rag_result.is_ambiguous
            clarification_question = rag_result.clarification_question

            # Router stats are optional in the refactored AgenticRAG CoreResult
            routing_stats: dict[str, Any] = {}

            # Initialize routing stats for analytics
            routing_stats = rag_result.timings if hasattr(rag_result, "timings") else {}

            # Analytics (delegated to OracleAnalyticsService)
            analytics_data = self.analytics.build_analytics_data(
                query=request_query,
                answer=answer,
                user_profile=user_profile,
                model_used=model_used,
                execution_time_ms=execution_time,
                document_count=rag_result.document_count,
                session_id=request_session_id,
                collection_used=rag_result.collection_used,
                routing_stats=routing_stats,
                search_time_ms=search_time,
                reasoning_time_ms=reasoning_time,
            )
            analytics_data["language_preference"] = target_language
            await self.analytics.store_query_analytics(analytics_data)

            # Return dict matching OracleQueryResponse
            return {
                "success": True,
                "query": request_query,
                "user_email": request_user_email,
                "answer": answer,
                "answer_language": target_language,
                "model_used": model_used,
                "sources": sources if request_include_sources else [],
                "document_count": rag_result.document_count,
                "collection_used": rag_result.collection_used,
                "routing_reason": f"Routed to {rag_result.collection_used}",
                "domain_confidence": routing_stats.get("domain_scores", {}),
                "user_profile": user_profile,
                "language_detected": target_language,
                "execution_time_ms": execution_time,
                "search_time_ms": search_time,
                "reasoning_time_ms": reasoning_time,
                "followup_questions": [],  # Orchestrator could provide these if asked
                "citations": rag_result.sources,  # Use RAG sources as citations
                "clarification_needed": clarification_needed,
                "clarification_question": clarification_question,
                "personality_used": personality_used,
                "golden_answer_used": "golden" in model_used,
                "user_memory_facts": user_memory_facts,
            }

        except (
            HTTPException,
            asyncpg.PostgresError,
            qdrant_exceptions.UnexpectedResponse,
            httpx.HTTPError,
            ResourceExhausted,
            ServiceUnavailable,
            ValueError,
            RuntimeError,
        ) as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Oracle service error: {e}", exc_info=True)

            # Error Analytics (delegated to OracleAnalyticsService)
            await self.analytics.store_query_analytics(
                {"query_text": request_query, "metadata": {"error": str(e)}}
            )

            return {
                "success": False,
                "query": request_query,
                "user_email": request_user_email,
                "error": str(e),
                "execution_time_ms": execution_time,
            }

    async def submit_feedback(self, feedback_data: dict[str, Any]):
        """Submit feedback logic"""
        logger.info(f"📝 Processing feedback from {feedback_data.get('user_email')}")
        return await db_manager.store_feedback(feedback_data)


# Global instance
oracle_service = OracleService()
