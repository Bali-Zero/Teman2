import logging
from collections.abc import AsyncGenerator
from typing import Any

from services.rag.agentic import create_agentic_rag

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

        self.orchestrator = create_agentic_rag(
            retriever=search_service,
            db_pool=db_pool,
            web_search_client=None,  # TODO: Inject Web Search if available
        )

        # We keep these for potential future use or hybrid scenarios,
        # but the heavy lifting is now done by the Orchestrator.
        self.collaborator_service = collaborator_service

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
    ) -> dict:
        """
        Delegates to AgenticRAGOrchestrator.process_query
        """
        try:
            logger.info(f"🚦 [Router] Routing message for user {user_id} via Agentic RAG")

            # Delegate to Orchestrator
            result = await self.orchestrator.process_query(query=message, user_id=user_id)

            return {
                "response": result["answer"],
                "ai_used": "agentic-rag",
                "category": "agentic",
                "model": "gemini-2.5-flash",
                "tokens": {},
                "used_rag": True,
                "used_tools": False,
                "tools_called": [],
                "sources": result["sources"],
            }

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
    ) -> AsyncGenerator[dict | str, None]:
        """
        Delegates to AgenticRAGOrchestrator.stream_query
        """
        try:
            logger.info(f"🚦 [Router Stream] Starting stream for user {user_id} via Agentic RAG")

            # Stream from Orchestrator
            async for chunk in self.orchestrator.stream_query(query=message, user_id=user_id):
                # Pass through chunks directly as they are already formatted for frontend
                yield chunk

            logger.info("✅ [Router Stream] Completed")

        except Exception as e:
            logger.error(f"❌ [Router Stream] Error: {e}")
            raise Exception(f"Streaming failed: {str(e)}") from e

    def get_stats(self) -> dict:
        return {
            "router": "agentic_rag_wrapper",
            "model": "gemini-2.5-flash",
            "rag_available": True,
        }
