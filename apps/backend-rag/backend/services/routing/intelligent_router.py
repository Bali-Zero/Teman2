import logging
from collections.abc import AsyncGenerator
from typing import Any

from ..misc.clarification_service import ClarificationService
from ..misc.context_suggestion_service import get_context_suggestion_service
from ..rag.agentic import create_agentic_rag

logger = logging.getLogger(__name__)


class IntelligentRouter:
    """
    ZANTARA AI Intelligent Router (Agentic RAG Wrapper)

    Acts as a facade for the AgenticRAGOrchestrator, maintaining compatibility
    with the existing WebApp API contract.
    """

    def __init__(
        self,
        ai_client=None,
        search_service=None,
        tool_executor=None,
        cultural_rag_service=None,
        autonomous_research_service=None,
        cross_oracle_synthesis_service=None,
        client_journey_orchestrator=None,
        personality_service=None,
        collaborator_service=None,
        db_pool=None,
    ):
        # Initialize the new Brain (Agentic RAG)
        # We need to pass the retriever (search_service) and db_pool

        # We keep these for potential future use or hybrid scenarios,
        # but the heavy lifting is now done by the Orchestrator.
        self.collaborator_service = collaborator_service
        self.db_pool = db_pool

        # Initialize Context Suggestion Service (Phase 3 Proactive AI)
        self.context_suggestion_service = get_context_suggestion_service(db_pool=db_pool)

        # Initialize Clarification Service
        self.clarification_service = ClarificationService(search_service=search_service)

        self.orchestrator = create_agentic_rag(
            retriever=search_service,
            db_pool=db_pool,
            web_search_client=None,  # TODO: Inject Web Search if available
            clarification_service=self.clarification_service,
        )

        logger.info("🎯 [IntelligentRouter] Initialized (NEXT-GEN AGENTIC RAG MODE)")

    async def initialize(self):
        """Async initialization of the orchestrator"""
        await self.orchestrator.initialize()

    async def route_chat(
        self,
        message: str,
        user_id: str,
        conversation_history: list[dict] | None = None,
        memory: Any | None = None,
        emotional_profile: Any | None = None,
        _last_ai_used: str | None = None,
        collaborator: Any | None = None,
        frontend_tools: list[dict] | None = None,
        include_suggestions: bool = True,
    ) -> dict:
        """
        Delegates to AgenticRAGOrchestrator.process_query

        Args:
            message: User's message
            user_id: User identifier
            conversation_history: Previous conversation turns
            memory: User memory facts
            emotional_profile: User's emotional state
            _last_ai_used: Last AI model used (deprecated)
            collaborator: Collaborator info
            frontend_tools: Tools available in frontend
            include_suggestions: Whether to include proactive suggestions (Phase 3)

        Returns:
            Dict with response, sources, and proactive suggestions
        """
        try:
            logger.info(f"🚦 [Router] Routing message for user {user_id} via Agentic RAG")

            # Delegate to Orchestrator
            result = await self.orchestrator.process_query(
                query=message,
                user_id=user_id,
                conversation_history=conversation_history,
            )

            # FIX: Intelligently handle CoreResult vs Dict
            # The Orchestrator now returns a Pydantic object (CoreResult), BUT
            # for backwards compatibility we must handle accessing it safely.

            # Helper to get attribute or dict item
            def get_val(obj, attr, default=None):
                if hasattr(obj, attr):
                    return getattr(obj, attr)
                if isinstance(obj, dict):
                    return obj.get(attr, default)
                return default

            answer = get_val(result, "answer", "")
            sources = get_val(result, "sources", [])
            routing_stats = get_val(result, "routing_stats")

            response_data = {
                "response": answer,
                "ai_used": "agentic-rag",
                "category": "agentic",
                "model": "gemini-3-flash-preview",  # Zantara AI
                "tokens": {},
                "used_rag": True,
                "used_tools": False,
                "tools_called": [],
                "sources": sources,
            }
            if routing_stats:
                response_data["routing_stats"] = routing_stats

            # Phase 3: Add proactive context suggestions
            if include_suggestions:
                try:
                    suggestions = await self.context_suggestion_service.get_suggestions(
                        query=message,
                        user_id=user_id,
                        response=answer,  # Use the extracted answer
                        conversation_history=conversation_history,
                    )

                    if suggestions:
                        response_data["suggestions"] = [
                            {
                                "id": s.suggestion_id,
                                "type": s.suggestion_type.value,
                                "priority": s.priority.value,
                                "title": s.title,
                                "description": s.description,
                                "action_label": s.action_label,
                                "action_payload": s.action_payload,
                                "icon": s.icon,
                            }
                            for s in suggestions
                        ]
                        logger.info(f"💡 [Router] Added {len(suggestions)} proactive suggestions")

                except Exception as e:
                    logger.warning(f"⚠️ [Router] Failed to get suggestions: {e}")
                    # Don't fail the whole request if suggestions fail

            return response_data

        except Exception as e:
            logger.error(f"❌ [Router] Routing error: {e}")
            raise Exception(f"Routing failed: {str(e)}") from e

    async def stream_chat(
        self,
        message: str,
        user_id: str,
        conversation_history: list[dict] | None = None,
        memory: Any | None = None,
        collaborator: Any | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[dict | str, None]:
        """
        Delegates to AgenticRAGOrchestrator.stream_query
        """
        try:
            logger.info(f"🚦 [Router Stream] Starting stream for user {user_id} via Agentic RAG")

            # Stream from Orchestrator
            # FIX: Pass conversation history and session ID down
            # Need to extract session_id from somewhere or generate one if strictly needed,
            # but usually router statelessness relies on client passing history.
            # Orchestrator stream_query accepts session_id and conversation_history.
            session_id = None  # Logic to get session id if available

            async for chunk in self.orchestrator.stream_query(
                query=message,
                user_id=user_id,
                conversation_history=conversation_history,
                session_id=session_id,
            ):
                # Pass through chunks directly as they are already formatted for frontend
                yield chunk

            logger.info("✅ [Router Stream] Completed")

        except Exception as e:
            logger.error(f"❌ [Router Stream] Error: {e}")
            raise Exception(f"Streaming failed: {str(e)}") from e

    def get_stats(self) -> dict:
        return {
            "router": "agentic_rag_wrapper",
            "model": "gemini-3-flash-preview",
            "rag_available": True,
        }
