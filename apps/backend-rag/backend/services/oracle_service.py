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

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Optional

import asyncpg
import httpx
from fastapi import HTTPException, status
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
from llm.adapters.gemini import GeminiAdapter
from prompts.zantara_prompt_builder import PromptContext, ZantaraPromptBuilder
from qdrant_client.http import exceptions as qdrant_exceptions

# Core Dependencies
# Services
from services.citation_service import CitationService
from services.clarification_service import ClarificationService
from services.classification.intent_classifier import IntentClassifier
from services.followup_service import FollowupService
from services.golden_answer_service import GoldenAnswerService
from services.memory import MemoryOrchestrator
from services.memory_fact_extractor import MemoryFactExtractor
from services.memory_service_postgres import MemoryServicePostgres
from services.oracle import (
    DocumentRetrievalService,
    LanguageDetectionService,
    OracleAnalyticsService,
    ReasoningEngineService,
    UserContextService,
)
from services.oracle_config import oracle_config as config
from services.oracle_database import db_manager
from services.personality_service import PersonalityService
from services.response.validator import ZantaraResponseValidator
from services.search_service import SearchService
from services.smart_oracle import smart_oracle

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MODELS (Moved/Shared)
# ---------------------------------------------------------------------------
# Note: Request/Response models are typically defined in routers or a shared schemas file.
# Since they are currently in the router, we will assume the service receives typed arguments
# or Pydantic objects passed from the router. For now, we import them if needed or just use type hints.

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


def download_pdf_from_drive(filename: str) -> Optional[str]:
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
    user_memory_facts: Optional[list[str]] = None,
    conversation_history: Optional[list[dict]] = None,
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
        config_path = Path(__file__).parent.parent / "config" / "communication_modes.yaml"
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

        # Lazy loaded services
        self._followup_service: Optional[FollowupService] = None
        self._citation_service: Optional[CitationService] = None
        self._clarification_service: Optional[ClarificationService] = None
        self._personality_service: Optional[PersonalityService] = None
        self._golden_answer_service: Optional[GoldenAnswerService] = None
        self._memory_service: Optional[MemoryServicePostgres] = None
        self._fact_extractor: Optional[MemoryFactExtractor] = None
        self._memory_orchestrator: Optional[MemoryOrchestrator] = None

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
    def golden_answer_service(self) -> Optional[GoldenAnswerService]:
        if not self._golden_answer_service:
            try:
                database_url = config.database_url if hasattr(config, "database_url") else None
                if database_url:
                    self._golden_answer_service = GoldenAnswerService(database_url)
            except (asyncpg.PostgresError, ValueError, RuntimeError) as e:
                logger.warning(f"GoldenAnswerService init failed: {e}", exc_info=True)
        return self._golden_answer_service

    @property
    def memory_service(self) -> Optional[MemoryServicePostgres]:
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
        request_user_email: Optional[str],
        request_limit: int,
        request_session_id: Optional[str],
        request_include_sources: bool,
        request_use_ai: bool,
        request_language_override: Optional[str],
        request_conversation_history: Optional[list[Any]],
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

            classification = await self.intent_classifier.classify_intent(request_query)
            detected_mode = classification.get("mode", "default")

            clarification_needed = False
            clarification_question = None
            try:
                ambiguity_result = self.clarification_service.detect_ambiguity(request_query)
                if (
                    ambiguity_result.get("is_ambiguous")
                    and ambiguity_result.get("confidence", 0) > 0.7
                ):
                    clarification_needed = True
                    clarification_question = ambiguity_result.get("suggested_question")
            except (ValueError, RuntimeError, KeyError) as e:
                logger.warning(f"ClarificationService error: {e}", exc_info=True)

            # 2b. Golden Answers
            golden_answer = None
            golden_answer_used = False
            if self.golden_answer_service:
                try:
                    if not self.golden_answer_service.pool:
                        await self.golden_answer_service.connect()
                    golden_answer = await self.golden_answer_service.lookup_golden_answer(
                        query=request_query, _user_id=request_user_email
                    )
                    if golden_answer:
                        golden_answer_used = True
                except (asyncpg.PostgresError, ValueError, RuntimeError) as e:
                    logger.warning(f"GoldenAnswerService error: {e}", exc_info=True)

            prompt_context = PromptContext(
                query=request_query,
                language=target_language,
                mode=detected_mode,
                emotional_state="neutral",
                user_name=user_name,
                user_role=user_role,
            )

            # 3. Semantic Search (Refactored to use SearchService with Reranking & Metrics)
            search_start = time.time()
            
            # Keep explicit routing for analytics details
            routing_stats = search_service.query_router.route_query(request_query)
            collection_used = routing_stats["collection_name"]

            # Determine user access level based on role
            user_level = 3 if user_role == "admin" else 1

            # Execute search via centralized service (Enables Metrics, Reranking, Early Exit)
            try:
                search_response = await search_service.search_with_reranking(
                    query=request_query,
                    user_level=user_level,
                    limit=request_limit,
                    collection_override=collection_used,
                    tier_filter=None # Use default tier filtering
                )
                
                # Check for early exit optimization
                if search_response.get("early_exit"):
                    logger.info("🚀 OracleService benefited from Early Exit optimization")

            except Exception as e:
                logger.error(f"SearchService error: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Search service failed: {str(e)}",
                )

            search_time = (time.time() - search_start) * 1000

            # 4. Process Results (Map from SearchService format to Oracle format)
            documents = []
            sources = []
            
            for result in search_response.get("results", []):
                # Extract data from standardized format
                doc_content = result.get("text", "")
                metadata = result.get("metadata", {})
                score = result.get("score", 0.0)
                doc_id = result.get("id") or metadata.get("id")
                
                # Prepare document text for reasoning
                documents.append(doc_content)
                
                # Prepare source metadata for citation
                sources.append(
                    {
                        "content": doc_content[:500] + "..." if len(doc_content) > 500 else doc_content,
                        "metadata": metadata,
                        "relevance": round(score, 4),
                        "source_collection": collection_used,
                        "document_id": doc_id,
                        "is_reranked": search_response.get("reranked", False)
                    }
                )

            # 5. Reasoning
            answer = None
            model_used = None
            reasoning_result = None

            conv_history_dicts = None
            if request_conversation_history:
                conv_history_dicts = [
                    {"role": msg.role, "content": msg.content}
                    for msg in request_conversation_history
                ]

            # Identity Check
            query_lower = request_query.lower()
            identity_patterns = [
                "chi sono io",
                "who am i",
                "siapa saya",
                "mi riconosci",
                "recognize me",
            ]
            is_identity_query = any(pattern in query_lower for pattern in identity_patterns)

            if is_identity_query and user_profile:
                # Identity Logic
                user_role = user_profile.get("role", "team member")
                if target_language in ["it", "italian"]:
                    answer = f"Ciao {user_name}! Sei {user_role}. Sono Zantara."
                elif target_language in ["id", "indonesian"]:
                    answer = f"Halo {user_name}! Kamu adalah {user_role}. Saya Zantara."
                else:
                    answer = f"Hey {user_name}! You're {user_role}. I'm Zantara."
                model_used = "user_profile_identity"
            elif golden_answer and golden_answer.get("answer"):
                answer = golden_answer["answer"]
                model_used = f"golden_answer ({golden_answer.get('match_type', 'exact')})"
            elif request_use_ai and documents:
                # Smart Oracle / Standard Reasoning
                best_result = sources[0] if sources else None
                best_filename = None
                if best_result and best_result.get("metadata"):
                    best_filename = best_result["metadata"].get("filename") or best_result[
                        "metadata"
                    ].get("source")

                if best_filename:
                    smart_response = await smart_oracle(request_query, best_filename)
                    if smart_response and not smart_response.startswith("Error"):
                        reasoning_result = await self.reasoning_engine.reason_with_gemini(
                            documents=[smart_response],
                            query=request_query,
                            context=prompt_context,
                            use_full_docs=True,
                            user_memory_facts=user_memory_facts,
                            conversation_history=conv_history_dicts,
                        )
                        answer = reasoning_result["answer"]
                        model_used = f"{reasoning_result['model_used']} (Smart Oracle)"
                    else:
                        reasoning_result = await self.reasoning_engine.reason_with_gemini(
                            documents=documents,
                            query=request_query,
                            context=prompt_context,
                            use_full_docs=False,
                            user_memory_facts=user_memory_facts,
                            conversation_history=conv_history_dicts,
                        )
                        answer = reasoning_result["answer"]
                        model_used = reasoning_result["model_used"]
                else:
                    reasoning_result = await self.reasoning_engine.reason_with_gemini(
                        documents=documents,
                        query=request_query,
                        context=prompt_context,
                        use_full_docs=False,
                        user_memory_facts=user_memory_facts,
                        conversation_history=conv_history_dicts,
                    )
                    answer = reasoning_result["answer"]
                    model_used = reasoning_result["model_used"]

                reasoning_time = (
                    reasoning_result.get("reasoning_time_ms", 0) if reasoning_result else 0
                )

            elif request_use_ai and not documents:
                # Conversational Fallback
                try:
                    reasoning_result = await self.reasoning_engine.reason_with_gemini(
                        documents=[],
                        query=request_query,
                        context=prompt_context,
                        use_full_docs=False,
                        user_memory_facts=user_memory_facts,
                        conversation_history=conv_history_dicts,
                    )
                    answer = reasoning_result["answer"]
                    model_used = f"{reasoning_result['model_used']} (conversational)"
                    reasoning_time = reasoning_result.get("reasoning_time_ms", 0)
                except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError) as e:
                    logger.error(f"Error in conversational AI: {e}", exc_info=True)

            if not answer:
                answer = f"I'm sorry {user_name}, I couldn't find specific information. Could you rephrase?"
                model_used = "default_response"

            execution_time = (time.time() - start_time) * 1000

            # Analytics (delegated to OracleAnalyticsService)
            analytics_data = self.analytics.build_analytics_data(
                query=request_query,
                answer=answer,
                user_profile=user_profile,
                model_used=model_used,
                execution_time_ms=execution_time,
                document_count=len(documents),
                session_id=request_session_id,
                collection_used=collection_used,
                routing_stats=routing_stats,
                search_time_ms=search_time,
                reasoning_time_ms=reasoning_time,
            )
            analytics_data["language_preference"] = target_language
            await self.analytics.store_query_analytics(analytics_data)

            # Followups & Citations
            followup_questions = []
            try:
                followup_questions = await self.followup_service.get_followups(
                    query=request_query, response=answer or "", use_ai=True
                )
            except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError):
                logger.debug("Failed to generate followup questions", exc_info=True)
                pass

            citations = []
            try:
                citations = self.citation_service.extract_sources_from_rag(sources)
            except (ValueError, KeyError, TypeError):
                logger.debug("Failed to extract citations", exc_info=True)
                pass

            if answer and not clarification_needed:
                # OPTIONAL: Check if AI response itself asks for clarification
                # Currently disabled as detect_clarification_in_response is not implemented
                # try:
                #     response_analysis = self.clarification_service.detect_clarification_in_response(answer)
                #     if response_analysis.get("has_clarification_question"):
                #         clarification_needed = True
                # except (ValueError, RuntimeError, KeyError, AttributeError):
                #     logger.debug("Failed to detect clarification in response", exc_info=True)
                pass

            # 🧠 MEMORY PERSISTENCE: Extract and save facts from conversation
            if answer and request_user_email:
                # Run memory saving in background to not block response
                asyncio.create_task(
                    self._save_memory_facts(
                        user_email=request_user_email,
                        user_message=request_query,
                        ai_response=answer,
                    )
                )

            # Return dict matching OracleQueryResponse
            return {
                "success": True,
                "query": request_query,
                "user_email": request_user_email,
                "answer": answer,
                "answer_language": target_language,
                "model_used": model_used,
                "sources": sources if request_include_sources else [],
                "document_count": len(documents),
                "collection_used": collection_used,
                "routing_reason": f"Routed to {collection_used}",
                "domain_confidence": routing_stats.get("domain_scores", {}),
                "user_profile": user_profile,  # Router will convert to Pydantic
                "language_detected": target_language,
                "execution_time_ms": execution_time,
                "search_time_ms": search_time,
                "reasoning_time_ms": reasoning_time,
                "followup_questions": followup_questions,
                "citations": citations,
                "clarification_needed": clarification_needed,
                "clarification_question": clarification_question,
                "personality_used": personality_used,
                "golden_answer_used": golden_answer_used,
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
